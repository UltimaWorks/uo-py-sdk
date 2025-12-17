from __future__ import annotations

from uo_py_sdk.defs.parser import parse_def


def test_parse_def_basic_pairs() -> None:
    d = parse_def("123 456\n")
    assert d.resolve_first(123) == 456


def test_parse_def_braces() -> None:
    d = parse_def("10 { 20 }\n11 {20, 21}\n")
    assert d.resolve_first(10) == 20
    assert d.mapping[11] == [20, 21]
