import json
import re
import tempfile
import unittest
from pathlib import Path
from gen.atlas import build, record

class AtlasTests(unittest.TestCase):
    def test_deterministic_complete_offline_document(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / 'a.html', Path(d) / 'b.html'
            size = build(512, a)
            build(512, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(size, len(a.read_bytes()))
            text = a.read_text()
            self.assertTrue(text.startswith('<!doctype html>'))
            self.assertTrue(text.endswith('</body></html>\n'))
            self.assertNotIn('__COUNT__', text)
            self.assertNotIn('<!--ATLAS_DATA-->', text)
            blocks = re.findall(r'<script type="application/json" id="data-\d+">(.*?)</script>', text)
            self.assertEqual(len(blocks), 2)
            rows = sum([json.loads(s) for s in blocks], [])
            self.assertEqual([r[0] for r in rows], list(range(512)))
            self.assertTrue(all(len(r[7]) == 12 for r in rows))
            self.assertEqual(rows[-1], record(511))
            self.assertNotRegex(text, r'(?:src|href)=["\']https?://')

    def test_chunked_output_is_exact_single_document(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            build(16384, p/'atlas.html', p/'chunks', p/'src', 1)
            manifest = (p/'src/chunks.js').read_text()
            files = json.loads(manifest.split(' = ', 1)[1].split(';', 1)[0])
            self.assertGreater(len(files), 1)
            self.assertEqual(b''.join((p/'chunks'/f).read_bytes() for f in files), (p/'atlas.html').read_bytes())
            self.assertTrue(all((p/'chunks'/f).stat().st_size <= 1048576 for f in files))

    def test_invalid_sizes_and_half_worker_config_are_rejected(self):
        for n in (0, 255, 257, 262400, 1048576):
            with self.assertRaises(ValueError):
                build(n, 'must-not-write.html')
        with self.assertRaises(ValueError):
            build(256, 'must-not-write.html', out='x')
        with self.assertRaises(ValueError):
            build(256, 'must-not-write.html', chunk_mib=25)
