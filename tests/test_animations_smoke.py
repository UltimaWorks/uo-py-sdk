from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima import Animations, Files


def test_animations_can_decode_some_frame() -> None:
    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)

    # Scan a small set of likely bodies/actions/directions.
    anim = Animations.from_files(files, file_set=1)

    decoded = None
    for body in range(0, 20):
        for action in range(0, 10):
            for direction in range(0, 8):
                frames = anim.frames(body=body, action=action, direction=direction, file_set=1)
                if not frames:
                    continue
                # Find a non-empty frame
                for fr in frames:
                    if fr.width > 0 and fr.height > 0 and len(fr.pixels_1555) == fr.width * fr.height:
                        decoded = fr
                        break
                if decoded is not None:
                    break
            if decoded is not None:
                break
        if decoded is not None:
            break

    assert decoded is not None
    assert decoded.width > 0
    assert decoded.height > 0


def test_animations_can_export_gif(tmp_path: Path) -> None:
    try:
        import PIL  # type: ignore
    except Exception:
        return

    client_files = Path(__file__).parent / "client_files"
    files = Files.from_path(client_files)
    anim = Animations.from_files(files, file_set=1)

    exported = False
    for body in range(0, 20):
        for action in range(0, 10):
            for direction in range(0, 8):
                out_path = tmp_path / f"anim_{body}_{action}_{direction}.gif"
                if anim.export_gif(body=body, action=action, direction=direction, out_path=out_path, duration_ms=80):
                    assert out_path.exists()
                    assert out_path.stat().st_size > 0
                    exported = True
                    break
            if exported:
                break
        if exported:
            break

    assert exported
