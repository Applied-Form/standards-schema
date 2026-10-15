#!/usr/bin/env python3
"""Isolated regressions for complete, current Agent Skill distribution bundles."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("standards_compiler", Path(__file__).resolve().parents[1] / "schema/compile.py")
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)


class ClaudeBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pack = self.root / "synthetic"
        self.pack.mkdir()
        self.bundle = self.pack / "dist/claude/synthetic"
        self.files = {
            "SKILL.md": b"# Synthetic\nRead `REFERENCE.md`. Token `color.text.primary` is not a file.\n",
            "REFERENCE.md": b"# Reference\nRead [detail](docs/detail.md#formats), `Example.docx` and `Reference card.pdf`.\n[site](https://example.invalid/guide.md)\n",
            "LICENSE": b"Synthetic pack notice. Attribution must remain.\n",
            "docs/detail.md": b"Use [template](../Example.pptx) and [data](<../assets/nested/data file.json>).\n",
            "assets/tokens.css": b":root{--ink:#111111}\n",
            "assets/nested/data file.json": b'{"synthetic":true}\n',
            "Example.docx": b"Synthetic document bytes\x00\xff",
            "Example.pptx": b"Synthetic deck bytes\x00\xfe",
            "Reference card.pdf": b"Synthetic reference card bytes\x00\xfd",
        }
        for name, content in self.files.items():
            self.write(name, content)

    def write(self, name, content):
        target = self.pack / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def emit(self):
        compiler.emit_distribution(str(self.pack), "synthetic", (self.pack / "SKILL.md").read_text(), "---\n---\nCompact\n", "")

    def test_all_advertised_files_and_notices_match_canonical_bytes(self):
        self.emit()
        actual = {path.relative_to(self.bundle).as_posix(): path.read_bytes()
                  for path in self.bundle.rglob("*") if path.is_file()}
        self.assertEqual(actual, self.files)
        self.assertTrue((self.pack / "dist/cursor/synthetic.mdc").is_file())

    def test_rebuild_removes_deleted_references_and_stale_assets(self):
        self.emit()
        self.write("REFERENCE.md", b"# Reference\nNo local files needed.\n")
        (self.pack / "assets/nested/data file.json").unlink()
        (self.bundle / "stale.txt").write_text("obsolete generated data")
        self.emit()
        for name in ("docs/detail.md", "Example.docx", "Example.pptx", "Reference card.pdf", "assets/nested/data file.json", "stale.txt"):
            self.assertFalse((self.bundle / name).exists(), name)
        # Only generated output is cleaned; unreferenced authored files remain.
        self.assertTrue((self.pack / "Example.docx").is_file())
        self.assertEqual((self.bundle / "REFERENCE.md").read_bytes(), (self.pack / "REFERENCE.md").read_bytes())

    def test_missing_reference_or_licence_fails_without_replacing_previous_bundle(self):
        self.emit()
        previous = (self.bundle / "REFERENCE.md").read_bytes()
        self.write("REFERENCE.md", b"Read `missing.docx`.\n")
        with self.assertRaisesRegex(FileNotFoundError, "missing.docx"):
            self.emit()
        self.assertEqual((self.bundle / "REFERENCE.md").read_bytes(), previous)
        self.write("REFERENCE.md", self.files["REFERENCE.md"])
        (self.pack / "LICENSE").unlink()
        with self.assertRaisesRegex(FileNotFoundError, "LICENSE"):
            self.emit()
        self.assertEqual((self.bundle / "LICENSE").read_bytes(), self.files["LICENSE"])

    def test_reference_cycles_terminate_and_copy_each_file_once(self):
        self.write("docs/detail.md", b"Return to [reference](../REFERENCE.md).\n")
        self.emit()
        self.assertEqual((self.bundle / "docs/detail.md").read_bytes(), (self.pack / "docs/detail.md").read_bytes())

    def test_unsafe_references_and_external_asset_symlinks_are_rejected(self):
        outside = self.root / "outside.md"
        outside.write_text("OUTSIDE-SYNTHETIC-SENTINEL")
        for link in ("../outside.md", str(outside), "../%6futside.md", "dist/claude/synthetic/SKILL.md"):
            with self.subTest(link=link):
                self.write("SKILL.md", f"[detail]({link})\n".encode())
                with self.assertRaises(ValueError):
                    self.emit()
        self.write("SKILL.md", self.files["SKILL.md"])
        (self.pack / "assets/escape.md").symlink_to(outside)
        with self.assertRaises(ValueError):
            self.emit()


if __name__ == "__main__":
    unittest.main()
