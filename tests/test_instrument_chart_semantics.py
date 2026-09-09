"""Instrument's default chart palettes must not encode data with signal red."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
import zipfile


PACK = Path(__file__).resolve().parents[1] / "packs" / "instrument"
NEUTRAL = {"111111", "6B6B6B"}


class InstrumentChartSemanticsTests(unittest.TestCase):
    def test_javascript_chart_cycle_contains_only_neutral_data_colours(self):
        theme = json.loads((PACK / "assets" / "chart-theme.json").read_text(encoding="utf-8"))
        colours = {colour.lstrip("#").upper() for colour in theme["seriesOrder"]}
        self.assertEqual(colours, NEUTRAL)

    def test_matplotlib_default_cycle_contains_only_neutral_data_colours(self):
        style = (PACK / "assets" / "instrument.mplstyle").read_text(encoding="utf-8")
        cycle = next(line for line in style.splitlines() if line.startswith("axes.prop_cycle:"))
        colours = {colour.upper() for colour in re.findall(r"['\"]#?([0-9a-fA-F]{6})['\"]", cycle)}
        self.assertEqual(colours, NEUTRAL)

    def test_installed_skill_ships_the_same_chart_assets_as_the_source(self):
        installed = PACK / "dist" / "claude" / "instrument" / "assets"
        for name in ("chart-theme.json", "instrument.mplstyle", "tokens.css"):
            with self.subTest(asset=name):
                self.assertEqual((installed / name).read_bytes(), (PACK / "assets" / name).read_bytes())

    def test_deck_template_uses_neutral_data_marks_and_portable_chart_data(self):
        deck = PACK / "Instrument-deck.pptx"
        bundled = PACK / "dist" / "claude" / "instrument" / deck.name
        self.assertEqual(deck.read_bytes(), bundled.read_bytes())
        with zipfile.ZipFile(deck) as archive:
            names = set(archive.namelist())
            chart_name = next(name for name in names if name.endswith("/charts/chart1.xml"))
            chart_xml = archive.read(chart_name).decode("utf-8")
            self.assertNotIn("C8102E", chart_xml.upper())
            slide = ET.fromstring(archive.read("ppt/slides/slide4.xml"))
            text = " ".join(node.text or "" for node in slide.iter()
                            if node.tag.endswith("}t"))
            self.assertIn("Series colours are ink and muted only", text)
            self.assertIn("never a red data mark", text)
            workbooks = [name for name in names
                         if name.startswith("ppt/embeddings/") and name.endswith(".xlsx")]
            self.assertEqual(len(workbooks), 1)
            self.assertTrue(any(name.endswith("/charts/_rels/chart1.xml.rels") for name in names))


if __name__ == "__main__":
    unittest.main()
