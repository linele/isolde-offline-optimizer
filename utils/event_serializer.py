"""Serializer for JAPC event data to JSON-compatible format.

This module provides utilities to convert PropertyRetrievalResponse objects
from the event builder into JSON-serializable dictionaries.

Example:
    >>> from generic_event_builder import GenericEventBuilder
    >>> from event_serializer import serialize_event
    >>> import json
    >>>
    >>> builder = GenericEventBuilder(provider, subscriptions)
    >>> event = builder.last_acquisition()
    >>> if event:
    ...     serialized = serialize_event(event)
    ...     json_str = json.dumps(serialized, indent=2)
"""

from __future__ import annotations

import typing as t

import numpy as np
import pyda.access


def _serialize_value(value: t.Any) -> t.Any:
    """Convert a single value to a JSON-serializable type.

    Args:
        value: Value to serialize

    Returns:
        JSON-serializable version of the value
    """
    # Handle numpy floating point numbers
    if isinstance(value, np.floating):
        return float(value)

    # Handle numpy integers
    if isinstance(value, np.integer):
        return int(value)

    # Handle booleans (already JSON-serializable)
    if isinstance(value, bool):
        return value

    # Handle numpy arrays and array-like objects
    if hasattr(value, "__array__") or isinstance(value, (list, tuple)):
        arr = np.array(value)
        return arr.tolist()

    # Handle None
    if value is None:
        return None

    # Handle strings and basic types
    if isinstance(value, (str, int, float)):
        return value

    # Handle dict-like objects recursively
    if hasattr(value, "items"):
        return {k: _serialize_value(v) for k, v in value.items()}

    # For anything else, try to convert to list or return as-is
    try:
        return list(value)
    except (TypeError, ValueError):
        return str(value)


def serialize_parameter_data(
    fspv: pyda.access.PropertyRetrievalResponse,
) -> dict[str, t.Any]:
    """Serialize a single parameter's PropertyRetrievalResponse.

    Args:
        fspv: PropertyRetrievalResponse from JAPC subscription

    Returns:
        Dictionary with 'cycle_stamp' and 'data' keys, fully JSON-serializable
    """
    cycle_stamp = fspv.header.cycle_timestamp
    selector = str(fspv.header.selector)
    data_dict = dict(fspv.data)

    serialized_data = {key: _serialize_value(value) for key, value in data_dict.items()}

    return {
        "cycle_stamp": cycle_stamp,
        "selector": selector,
        "data": serialized_data,
    }


def serialize_event(
    event: dict[str, pyda.access.PropertyRetrievalResponse],
) -> dict[str, t.Any]:
    """Serialize a complete event from the event builder.

    Args:
        event: Event dictionary from GenericEventBuilder (param_name -> fspv)

    Returns:
        JSON-serializable dictionary with structure:
        {
            "param_name": {
                "cycle_stamp": float,
                "selector": str,
                "data": {...}
            },
            ...
        }
    """
    return {
        param_name: serialize_parameter_data(fspv) for param_name, fspv in event.items()
    }
