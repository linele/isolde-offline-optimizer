from enum import Enum
import logging
import time

from cernml.coi import cancellation

import pyda
import pyda_japc

# TODO: Set to False for production version
DEBUG = True

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
LOG = logging.getLogger(__name__)

if DEBUG:
    LOG.warning(
        "Running Tape station acquisition in DEBUG mode: "
        "no hardware changes will be applied."
    )


class TapestationState(Enum):
    READY = 0
    WAITING_FOR_TRIGGER = 1
    CYCLE_IN_PROGRESS = 2
    MOVING_TO_STABILIZE = 3
    CYCLE_FINISHED = 4
    REWINDING = 5


class Tapestation:
    STATE_ADDR: str = "ISLTFTSA/Status"
    ARM_ADDR: str = "ISLTFTSA/Arm"
    STOP_ADDR: str = "ISLTFTSA/Stop"
    ACQ_ADDR: str = "ISLTFTSA/Acq"
    READOUT_FIELD: str = "measurement1Count"

    def __init__(
        self,
        japc_provider: pyda_japc.JapcProvider,
    ) -> None:
        LOG.info("Initializing Tapestation acquisition device")
        self._pyda_client = pyda.SimpleClient(provider=japc_provider)
        self._sleep_time_s = 0.1
        LOG.info("Tapestation initialization complete")

    def acquire(
        self,
        token: cancellation.Token,
    ) -> pyda.access.PropertyRetrievalResponse | None:
        """Acquire tape station measurement data.

        Waits for state to be READY, arms, then waits for tape station
        readout to be ready before reading measurement data. Additional
        check on readout value != -1 necessary due to unforeseeable
        lag. Returns None if cancelled.
        """
        start_time = time.time()
        LOG.info("Starting tapestation acquisition")

        # Phase 1: Wait for READY state
        LOG.info("Phase 1: Waiting for READY state")
        if not self._wait_for_ready(token):
            LOG.info("Acquisition cancelled during Phase 1")
            return None

        # Phase 2: Arm the tapestation
        LOG.info("Phase 2: Arming tapestation")
        if not DEBUG:
            self._arm_tapestation()
        else:
            LOG.debug("DEBUG mode: Skipping Arm operation")

        # Phase 3: Wait for CYCLE_IN_PROGRESS, CYCLE_FINISHED state
        LOG.info("Phase 3: Waiting for CYCLE_FINISHED state")
        if not DEBUG:
            if not self._wait_for_cycle_finished(token):
                LOG.info("Acquisition cancelled during Phase 3")
                return None
        else:
            LOG.debug("DEBUG mode: Skipping phase 3")

        # Phase 4: Read out acquisition data and return
        LOG.info("Phase 4: Reading out acquisition data")
        result = self._read_acquisition_data()
        elapsed_time = time.time() - start_time
        LOG.info(
            f"Tapestation acquisition completed successfully in {elapsed_time:.2f} s"
        )
        return result

    def _wait_for_ready(self, token: cancellation.Token) -> bool:
        """Wait for tapestation to reach READY state.

        Returns True if READY state reached, False if cancelled.
        """
        wait_start_time = time.time()
        retry_count = 0
        res = self._pyda_client.get(endpoint=self.STATE_ADDR, context="")
        state_enum = res.data["state"]

        while state_enum.value != TapestationState.READY.value:
            if retry_count % int(5.0 / self._sleep_time_s) == 0:
                elapsed_time = time.time() - wait_start_time
                LOG.warning(
                    f"Waiting for Tape station to be in state READY "
                    f"(elapsed {elapsed_time:.1f}s); "
                    f"Current state: {state_enum.name}"
                )
            time.sleep(self._sleep_time_s)
            retry_count += 1

            if token.cancellation_requested:
                LOG.info("Tape station acquisition cancelled during wait for READY.")
                return False

            res = self._pyda_client.get(endpoint=self.STATE_ADDR, context="")
            state_enum = res.data["state"]

        wait_duration = time.time() - wait_start_time
        LOG.info(f"Tape station READY (after {wait_duration:.2f} s)")
        return True

    def _arm_tapestation(self) -> None:
        """Arm the tapestation to start measurement cycle."""
        self._pyda_client.set(self.ARM_ADDR, context="", data={"value": True})

    def _wait_for_cycle_finished(self, token: cancellation.Token) -> bool:
        """Wait for tapestation to reach CYCLE_IN_PROGRESS or CYCLE_FINISHED
        state.

        Returns True if either CYCLE_IN_PROGRESS or CYCLE_FINISHED state
        reached, False if cancelled.
        """
        wait_start_time = time.time()
        retry_count = 0
        res = self._pyda_client.get(endpoint=self.STATE_ADDR, context="")
        state_enum = res.data["state"]

        while (state_enum.value != TapestationState.CYCLE_FINISHED.value) and (
            state_enum.value != TapestationState.CYCLE_IN_PROGRESS.value
        ):
            if retry_count % int(5.0 / self._sleep_time_s) == 0:
                elapsed_time = time.time() - wait_start_time
                LOG.warning(
                    f"Waiting for Tape station to be ready for readout "
                    f"(elapsed {elapsed_time:.1f} s)"
                )
            time.sleep(self._sleep_time_s)
            retry_count += 1

            if token.cancellation_requested:
                LOG.info("Tape station acquisition cancelled during cycle.")
                if not DEBUG:
                    LOG.info("Sending STOP command to tapestation")
                    self._pyda_client.set(
                        self.STOP_ADDR,
                        context="",
                        data={"value": True},
                    )
                else:
                    LOG.debug("DEBUG mode: Skipping STOP command")
                return False

            res = self._pyda_client.get(endpoint=self.STATE_ADDR, context="")
            state_enum = res.data["state"]

        wait_duration = time.time() - wait_start_time
        LOG.info(
            f"Tape station reached readout-ready state (after {wait_duration:.1f} s)"
        )
        return True

    def _read_acquisition_data(self) -> pyda.access.PropertyRetrievalResponse:
        """Read out acquisition data from tapestation."""
        LOG.info("Reading out Tape station data")
        while True:
            res = self._pyda_client.get(endpoint=self.ACQ_ADDR, context="")
            val = res.data[self.READOUT_FIELD][0]
            if DEBUG:
                LOG.info("DEBUG mode: Tape station readout complete")
                return res

            if val != -1:
                LOG.info("Tape station readout complete")
                return res

            time.sleep(0.5)
