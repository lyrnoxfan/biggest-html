import json
import tempfile
import unittest
from pathlib import Path

from gen.build import city_js_batch, load_cities

from gen.build import ChunkWriter, js_str


class ChunkWriterTests(unittest.TestCase):
    def test_chunks_reassemble_to_original_text(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = ChunkWriter(directory, max_bytes=6)
            expected = "alpha\nbeta\ngamma\n"
            writer.write(expected)
            total, files = writer.close()

            actual = "".join((Path(directory) / name).read_text(encoding="utf-8") for name in files)
            self.assertEqual(actual, expected)
            self.assertEqual(total, len(expected.encode("utf-8")))
            self.assertTrue(all((Path(directory) / name).stat().st_size <= 6 for name in files))

    def test_rebuild_removes_stale_numbered_chunks_only(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "chunk-00999.html").write_text("stale", encoding="utf-8")
            (out / "keep.txt").write_text("keep", encoding="utf-8")

            ChunkWriter(directory, max_bytes=6)

            self.assertFalse((out / "chunk-00999.html").exists())
            self.assertTrue((out / "keep.txt").exists())

    def test_js_string_cannot_close_script_tag(self):
        encoded = js_str("</script>")
        self.assertNotIn("</script>", encoded)
        self.assertIn("<" + chr(92) + "/script>", encoded)


class CitySelectionTests(unittest.TestCase):
    @staticmethod
    def geonames_row(name, feature, lat, lon, population):
        fields = [""] * 19
        fields[1] = name
        fields[4] = str(lat)
        fields[5] = str(lon)
        fields[7] = feature
        fields[14] = str(population)
        return "\t".join(fields) + "\n"

    def test_city_batch_uses_escaped_json_payload(self):
        rows = [(1.23456, -2.34567, 123, 'quoted "</script>\\name')]
        source = city_js_batch(rows)
        self.assertNotIn("</script>", source)
        payload = source.removeprefix("C.push(...JSON.parse(").removesuffix("));\n")
        decoded = json.loads(json.loads(payload))
        self.assertEqual(decoded, [[1.2346, -2.3457, 123, 'quoted "</script>\\name']])

    def test_bounded_selection_matches_stable_population_sort(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "allCountries.txt"
            source.write_text("".join([
                self.geonames_row("A", "PPL", 1, 2, 30),
                self.geonames_row("not a place", "ADM1", 0, 0, 1000),
                self.geonames_row("B", "PPLA", 3, 4, 30),
                self.geonames_row("C", "PPLC", 5, 6, 50),
                self.geonames_row("D", "PPL", 7, 8, 20),
            ]), encoding="utf-8")

            self.assertEqual(load_cities(source, 3), [
                (5.0, 6.0, 50, "C"),
                (1.0, 2.0, 30, "A"),
                (3.0, 4.0, 30, "B"),
            ])
            self.assertEqual(load_cities(source, 0), [
                (5.0, 6.0, 50, "C"),
                (1.0, 2.0, 30, "A"),
                (3.0, 4.0, 30, "B"),
                (7.0, 8.0, 20, "D"),
            ])


if __name__ == "__main__":
    unittest.main()
