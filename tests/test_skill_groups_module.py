from __future__ import annotations

from pathlib import Path

from uo_py_sdk.ultima.skill_groups import SkillGroups


def test_skill_groups_loads() -> None:
    client_files = Path(__file__).parent / "client_files"
    sg = SkillGroups.from_path(client_files / "skillgrp.mul")

    assert len(sg.groups) >= 1
    assert sg.groups[0].name == "Misc"
    assert isinstance(sg.skill_list, list)
