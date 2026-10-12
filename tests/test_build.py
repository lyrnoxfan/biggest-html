import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
