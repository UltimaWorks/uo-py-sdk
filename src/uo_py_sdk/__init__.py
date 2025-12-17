"""uo-py-sdk: Ultima Online MUL framework.

Core concept: assets are stored as `{type}.mul` data plus `{type}idx.mul` index.
Many types optionally also have `{type}.def` mapping overrides.
"""

from __future__ import annotations

from .settings import UoPySdkSettings

__all__ = ["__version__", "UoPySdkSettings"]

__version__ = "0.1.0"
