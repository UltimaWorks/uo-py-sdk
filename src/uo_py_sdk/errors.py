from __future__ import annotations


class UoPySdkError(Exception):
    """Base exception for uo-py-sdk."""


class MulFormatError(UoPySdkError):
    """Raised when a MUL/IDX/DEF file is malformed."""


class MulIndexOutOfRange(UoPySdkError, IndexError):
    """Raised when an index is out of bounds."""
