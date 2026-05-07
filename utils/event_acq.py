"""Generic event builder for grouping JAPC subscriptions by cycle stamp.

This module provides a reusable event builder that groups parameter subscriptions
by cycle stamp and provides complete events when all parameters are ready.

Example:
    >>> import pyda_japc
    >>> provider = pyda_japc.JapcProvider()
    >>> subscriptions = [
    ...     "ITF.BCT25/Acquisition",
    ...     "LEI.BQS.L/FFTAcquisition",
    ... ]
    >>> builder = GenericEventBuilder(provider, subscriptions, selector="LEI.USER.ALL")
    >>> builder.start()
    >>> event = next(builder)  # Blocks until next complete event
    >>> print(event)  # dict with param_name -> fspv mapping
"""

from __future__ import annotations

import logging
import re
import threading
import typing as t
from collections.abc import Iterator
from queue import Queue

import pyda
import pyda.access
import pyda.clients.callback
import pyda_japc

log = logging.getLogger(__name__)

ENDPOINT_RE = re.compile(
    r"^(?P<device>(?P<protocol>.+:\/\/)?[\w\/\.-]+)/(?P<property>[\w\#\.-]+)$"
)


class JapcEndpoint(pyda.access.StandardEndpoint):
    """Endpoint for JAPC access."""

    def __init__(self, *, device_name: str, property_name: str) -> None:
        self._dev = device_name
        self._prop = property_name

    @classmethod
    def from_str(cls, value: str) -> JapcEndpoint:
        m = ENDPOINT_RE.match(value)
        if not m:
            msg = f"Not a valid endpoint: {value}."
            raise ValueError(msg)
        return cls(device_name=m.group("device"), property_name=m.group("property"))


class GenericEventBuilder(Iterator[dict[str, pyda.access.PropertyRetrievalResponse]]):
    """Generic event builder that groups JAPC subscriptions by cycle stamp.

    Subscribes to a list of parameters and groups their responses by cycle stamp.
    When all parameters have arrived for a given cycle, the event is ready and
    can be retrieved via next_event() or by iterating over the builder.

    Args:
        provider: JAPC provider instance for data access
        subscriptions: List of parameter addresses (e.g., "DEVICE.NAME/Property")
        selector: Timing selector (default: "LEI.USER.ALL")
        buffer_size: Maximum number of incomplete events to buffer (default: 10)
        timeout: Timeout in seconds for next_event() (default: 60.0)
        ignore_first_updates: Skip first update from subscriptions (default: True)
    """

    def __init__(
        self,
        provider: pyda_japc.JapcProvider,
        subscriptions: list[str],
        selector: str = "LEI.USER.ALL",
        *,
        buffer_size: int = 10,
        timeout: float = 60.0,
        ignore_first_updates: bool = True,
    ) -> None:
        self._provider = provider
        self._subscriptions = subscriptions
        self._selector = selector
        self._buffer_size = buffer_size
        self._timeout = timeout
        self._ignore_first_updates = ignore_first_updates

        # Buffers: parameter -> selector -> cycle_stamp -> response
        self._buffers: dict[
            str, dict[str, dict[float, pyda.access.PropertyRetrievalResponse]]
        ] = {}

        # Queue for complete events
        self._event_queue: Queue[dict[str, pyda.access.PropertyRetrievalResponse]] = (
            Queue()
        )
        self._last_event: None | dict[str, pyda.access.PropertyRetrievalResponse] = None

        # Control flags
        self._started = False
        self._stopped = False
        self._lock = threading.Lock()

        # Setup pyda client
        self._da = pyda.CallbackClient(
            provider=provider,
        )

        # Setup subscription handles
        self._handles: dict[str, pyda.clients.callback.CallbackSubscription] = {}
        for param in subscriptions:
            endpoint = JapcEndpoint.from_str(param)
            log.debug(
                f"Setting up subscription {endpoint} @ {selector}, "
                f"receive_first_updates={not ignore_first_updates}"
            )
            handle = self._da.subscribe(
                endpoint=endpoint,
                context=selector,
                receive_first_updates=not ignore_first_updates,
                callback=self._handle_acquisition,
            )
            self._handles[param] = handle

    def start(self) -> None:
        """Start all subscriptions."""
        with self._lock:
            if self._started:
                return
            if self._stopped:
                msg = "Cannot restart a stopped event builder"
                raise RuntimeError(msg)

            for param, handle in self._handles.items():
                log.debug(f"Starting subscription for {param}")
                handle.start()

            self._started = True

    def stop(self) -> None:
        """Stop all subscriptions and signal completion."""
        with self._lock:
            if self._stopped:
                return

            for param, handle in self._handles.items():
                log.debug(f"Stopping subscription for {param}")
                handle.stop()

            self._stopped = True
            # Signal any waiting threads by putting None in queue
            self._event_queue.put(None)  # type: ignore[arg-type]

    def _handle_acquisition(self, fspv: pyda.access.PropertyRetrievalResponse) -> None:
        """Handle incoming acquisition from a subscription."""
        if self._stopped:
            return

        try:
            self._handle_acquisition_impl(fspv)
        except Exception:
            log.exception(
                f"Error handling acquisition for {fspv.query.endpoint}@{fspv.header.selector}"
            )

    def _handle_acquisition_impl(
        self, fspv: pyda.access.PropertyRetrievalResponse
    ) -> None:
        """Implementation of acquisition handling with buffering and event assembly."""
        if fspv.exception is not None:
            log.error(
                f"Received exception for {fspv.query.endpoint}@{fspv.header.selector}: {fspv.exception}"
            )
            return

        parameter = str(fspv.query.endpoint)
        selector = str(fspv.header.selector)
        cycle_stamp = fspv.header.cycle_timestamp
        """
        if cycle_stamp is None:
            log.warning(
                f"Received acquisition without cycle timestamp for {parameter}@{selector}",
            )
            return

        log.debug(
            f"Received acquisition for {parameter}@{selector} at cycle {cycle_stamp}"
        )"""

        with self._lock:
            # Initialize buffers for this parameter/selector if needed
            if parameter not in self._buffers:
                self._buffers[parameter] = {}
            if selector not in self._buffers[parameter]:
                self._buffers[parameter][selector] = {}

            # Store the response
            self._buffers[parameter][selector][cycle_stamp] = fspv

            # Clean old entries to prevent memory leaks
            if len(self._buffers[parameter][selector]) > self._buffer_size:
                oldest_stamp = min(self._buffers[parameter][selector].keys())
                log.debug(
                    f"Dropping old cycle {oldest_stamp} for {parameter}@{selector}"
                )
                del self._buffers[parameter][selector][oldest_stamp]

            # Check if all subscriptions have data for this cycle
            if self._check_ready(cycle_stamp, selector):
                log.debug(
                    f"All subscriptions ready for {selector} at cycle {cycle_stamp}"
                )
                event = self._build_event(cycle_stamp, selector)
                self._clear_cycle_stamp(cycle_stamp, selector)
                self._last_event = event
                self._event_queue.put(event)

    def _check_ready(self, cycle_stamp: float, selector: str) -> bool:
        """Check if all subscriptions have data for the given cycle stamp."""
        for param in self._subscriptions:
            if not (
                param in self._buffers
                and selector in self._buffers[param]
                and cycle_stamp in self._buffers[param][selector]
            ):
                return False
        return True

    def _build_event(
        self, cycle_stamp: float, selector: str
    ) -> dict[str, pyda.access.PropertyRetrievalResponse]:
        """Build event dictionary from buffered data."""
        event = {}
        for param in self._subscriptions:
            event[param] = self._buffers[param][selector][cycle_stamp]
        return event

    def _clear_cycle_stamp(self, cycle_stamp: float, selector: str) -> None:
        """Clear buffered data for a specific cycle stamp after event is built."""
        for param in self._subscriptions:
            if (
                param in self._buffers
                and selector in self._buffers[param]
                and cycle_stamp in self._buffers[param][selector]
            ):
                del self._buffers[param][selector][cycle_stamp]

    def last_event(self) -> dict[str, pyda.access.PropertyRetrievalResponse]:
        """Iterate through self._event_queue until the last element, return
        the last, i.e. newest element."""
        return self._last_event

    def next_event(self) -> dict[str, pyda.access.PropertyRetrievalResponse]:
        """Wait for and return the next complete event.

        Returns:
            Dictionary mapping parameter names to their PropertyRetrievalResponse objects.

        Raises:
            TimeoutError: If no event received within timeout period.
            RuntimeError: If event builder was stopped.
        """
        if not self._started:
            self.start()

        event = self._event_queue.get(timeout=self._timeout)

        if event is None:
            msg = "Event builder was stopped"
            raise RuntimeError(msg)

        return event

    def __next__(self) -> dict[str, pyda.access.PropertyRetrievalResponse]:
        """Support iteration protocol."""
        try:
            return self.next_event()
        except TimeoutError as e:
            raise StopIteration from e

    def __iter__(self) -> GenericEventBuilder:
        """Support iteration protocol."""
        return self

    def __enter__(self) -> t.Self:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.stop()
