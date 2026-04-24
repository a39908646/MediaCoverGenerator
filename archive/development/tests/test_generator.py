from __future__ import annotations

import unittest
from pathlib import Path
import shutil

from mediacovergenerator.generator import PosterGenerator


class PosterGeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parent.parent
        self.generator = PosterGenerator(self.project_root)
        self.temp_root = self.project_root / "tests" / "_tmp"
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_prepare_library_images_fills_missing_targets(self) -> None:
        library_dir = self.temp_root / "library"
        library_dir.mkdir(parents=True, exist_ok=True)
        (library_dir / "source_a.jpg").write_bytes(b"a")
        (library_dir / "source_b.jpg").write_bytes(b"b")

        prepared = self.generator.prepare_library_images(library_dir, required_items=3)

        self.assertTrue(prepared)
        self.assertTrue((library_dir / "1.jpg").exists())
        self.assertTrue((library_dir / "2.jpg").exists())
        self.assertTrue((library_dir / "3.jpg").exists())


if __name__ == "__main__":
    unittest.main()
