import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_source_headers import render_source_headers


class GenerateSourceHeadersTests(unittest.TestCase):
    def test_render_source_headers_uses_abbreviation_and_title(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "source_headers.tex"
            sources = [
                {
                    "abbreviation": "MS",
                    "title": "Mieczysław Surname",
                    "gramps_id": "S0001",
                }
            ]

            render_source_headers(sources, output_path)

            content = output_path.read_text(encoding="utf-8")

            self.assertIn("\\def\\source_ms{", content)
            self.assertIn("Mieczysław Surname", content)
            self.assertIn("S0001", content)


if __name__ == "__main__":
    unittest.main()
