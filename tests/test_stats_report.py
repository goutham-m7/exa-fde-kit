import re
import xml.etree.ElementTree as ET

import pytest

from exa_fde_kit.report_html import render
from exa_fde_kit.stats import Observation, paired_effect


def obs(name, case, window, supported):
    return Observation(case, name, window, 1.0, supported, 100.0, 0.01, 0, False)


def test_bootstrap_pairs_by_case_and_clusters_windows():
    rows = [
        obs(p, c, w, v)
        for w in ("early", "late")
        for c in ("a", "b")
        for p, v in [("lite", False), ("router", c == "a")]
    ]
    effect = paired_effect(rows, "router", "lite")
    assert (effect.estimate, effect.low, effect.high, effect.cases, effect.windows) == (
        0.5,
        0,
        1,
        2,
        2,
    )
    assert paired_effect(list(reversed(rows)), "router", "lite") == effect
    for bad in (rows[1:], rows + [rows[0]]):
        with pytest.raises(ValueError):
            paired_effect(bad, "router", "lite")


def test_report_has_standalone_svg_and_escaped_labels():
    rows = [obs("<script>", "a", "one", False), obs("lite", "a", "one", False)]
    page = render(rows, "Synthetic <test>", "lite")
    assert "<script" not in page and "&lt;test&gt;" in page
    assert "undefined" not in page and "n/a" in page.lower()
    charts = re.findall(r"<svg\b.*?</svg>", page, re.S)
    assert len(charts) >= 6 and all(ET.fromstring(s) is not None for s in charts)


def test_repeated_windows_are_averaged_before_resampling():
    rows = [
        obs(p, "same-case", w, v)
        for w, candidate in [("early", True), ("late", False)]
        for p, v in [("lite", False), ("router", candidate)]
    ]
    effect = paired_effect(rows, "router", "lite")
    assert (effect.estimate, effect.low, effect.high, effect.cases, effect.windows) == (
        0.5,
        0.5,
        0.5,
        1,
        2,
    )
