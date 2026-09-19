"""Exception types for pySTEMTC.

Java STEM signals bad input with ``IllegalArgumentException``; the Python port
maps those cases to :class:`STEMTCValueError` so callers can catch a single
input-contract error type.
"""


class STEMTCValueError(ValueError):
    """Raised for invalid input or configuration (Java: IllegalArgumentException)."""
