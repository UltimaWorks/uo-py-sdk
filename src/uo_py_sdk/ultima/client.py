"""Convenience entry point for opening Ultima Online client data.

This module defines a small wrapper over :class:`uo_py_sdk.ultima.files.Files`
and the new asset store abstraction.  The goal is to centralise client
configuration (e.g. whether to prefer UOP archives, whether to overlay
verdata patches) and provide a single place to evolve the API surface
without breaking the existing ``Files`` class.

At present, the :class:`UltimaClient` delegates all of its per‑asset
helpers (e.g. ``art()``, ``gumps()``) to an underlying
:class:`~uo_py_sdk.ultima.files.Files` instance.  Once support for UOP
archives is added, this class will instantiate an appropriate
``IAssetStore`` and pass it through to asset types that can use it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .files import Files
from .asset_store import IAssetStore, MulIdxStore


@dataclass(slots=True)
class ClientProfile:
    """Configuration describing how to open a client data set.

    Parameters correspond to common variations in client installations.  In
    particular, callers can elect to prefer UOP archives over legacy
    ``.mul``/``.idx`` pairs (once UOP support is implemented) and choose
    whether to honour ``verdata.mul`` patch files.
    """

    client_path: Path
    client_version_hint: Optional[str] = None
    prefer_uop: bool = False
    use_verdata: bool = True
    shard_overrides: Dict[str, Path] | None = None

    @classmethod
    def from_env(cls) -> "ClientProfile":
        """Construct a profile from environment variables.

        Expected variables are:

        - ``UO_DIR``: path to the Ultima Online client folder (required).
        - ``UO_CLIENT_VERSION``: optional version hint string.
        - ``UO_PREFER_UOP``: if set to ``"1"``, ``"true"``, or
          ``"yes"``, UOP archives will be preferred over MUL/IDX pairs when
          supported.
        - ``UO_USE_VERDATA``: if set to ``"0"``, ``"false"``, or
          ``"no"``, verdata patch files will be ignored.  Defaults to
          ``True`` otherwise.
        """
        uo_dir = os.getenv("UO_DIR")
        if not uo_dir:
            raise RuntimeError("UO_DIR environment variable is not set")
        version_hint = os.getenv("UO_CLIENT_VERSION")
        prefer_uop_str = os.getenv("UO_PREFER_UOP", "0").lower()
        prefer_uop = prefer_uop_str in ("1", "true", "yes")
        use_verdata_str = os.getenv("UO_USE_VERDATA", "1").lower()
        use_verdata = use_verdata_str not in ("0", "false", "no")
        return cls(
            client_path=Path(uo_dir),
            client_version_hint=version_hint,
            prefer_uop=prefer_uop,
            use_verdata=use_verdata,
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "ClientProfile":
        """Load a profile from a JSON file.

        The JSON object must contain a ``client_path`` field.  Other
        properties are optional and default to sensible values if omitted.
        """
        p = Path(path)
        data = json.loads(p.read_text())
        client_path = Path(data["client_path"])
        return cls(
            client_path=client_path,
            client_version_hint=data.get("client_version_hint"),
            prefer_uop=bool(data.get("prefer_uop", False)),
            use_verdata=bool(data.get("use_verdata", True)),
            shard_overrides=data.get("shard_overrides"),
        )


class UltimaClient:
    """Entry point for accessing Ultima Online client data.

    This class wraps a :class:`~uo_py_sdk.ultima.files.Files` instance and
    constructs an asset store.  In the future, this will incorporate
    support for UOP archives and other alternative backends, but for now
    it simply uses the classic ``.mul``/``.idx`` files.

    Most per‑asset methods (e.g. :meth:`art`, :meth:`gumps`) are
    forwarded to the underlying :class:`~uo_py_sdk.ultima.files.Files`
    instance, so existing code continues to work with minimal changes.
    """

    def __init__(self, profile: ClientProfile) -> None:
        self.profile: ClientProfile = profile
        # Underlying Files instance handles classic MUL/IDX resolution.
        self.files: Files = Files.from_path(profile.client_path)
        # Default to a MUL/IDX store; future implementations may switch
        # based on profile.prefer_uop.
        self.store: IAssetStore = MulIdxStore(self.files)

    @classmethod
    def open(
        cls,
        path: str | Path,
        *,
        prefer_uop: bool = False,
        use_verdata: bool = True,
    ) -> "UltimaClient":
        """Convenience constructor.

        Creates a :class:`ClientProfile` with the supplied arguments and
        returns a new :class:`UltimaClient`.  The ``path`` parameter is
        required.  ``prefer_uop`` and ``use_verdata`` will be carried
        through to the profile; other profile fields remain at their
        defaults.
        """
        profile = ClientProfile(
            client_path=Path(path),
            prefer_uop=prefer_uop,
            use_verdata=use_verdata,
        )
        return cls(profile)

    @property
    def root_dir(self) -> Path:
        """Return the root directory of the client installation."""
        return self.profile.client_path

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attribute accesses to the Files instance.

        This allows code such as ``client.art()`` or ``client.gumps()`` to
        continue working exactly as it does with the :class:`Files` API.
        If the attribute does not exist on :class:`Files` either, a
        standard :class:`AttributeError` will be raised.
        """
        return getattr(self.files, name)
