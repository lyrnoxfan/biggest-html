import hashlib, io, tempfile, unittest, wave
from pathlib import Path
import numpy as np
from gen.echo import pcm, PATCHES, DRUMS, build

class EchoSamples(unittest.TestCase):
 def test_wav_format_duration_and_headroom(self):
  for patch in PATCHES+DRUMS:
   raw=pcm(patch,60,.72,24000,True)
   with wave.open(io.BytesIO(raw)) as w:
    self.assertEqual((w.getnchannels(),w.getsampwidth(),w.getframerate()),(2,2,24000))
    self.assertEqual(w.getnframes(),round(patch['duration']*24000))
    samples=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)
    self.assertGreater(abs(samples).max(),100)
    self.assertLess(abs(samples).max(),30000)
    self.assertLess(abs(samples[-1]).max(),500)
    self.assertGreater(np.count_nonzero(samples[:,0]-samples[:,1]),100)
 def test_unique_notes_velocities_and_timbres(self):
  hashes=[]
  for p in PATCHES:
   for n in [36,60,83,95]:
    for v in [.38,.69,1.0]:hashes.append(hashlib.sha256(pcm(p,n,v,24000,False)).digest())
  self.assertEqual(len(hashes),len(set(hashes)))
 def test_repeatable_render(self):
  self.assertEqual(pcm(PATCHES[0],60,.72,24000,False),pcm(PATCHES[0],60,.72,24000,False))
 def test_builder_one_file_and_no_network_assets(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'echo.html';r=build(path,60,60,1,24000,False);s=path.read_text()
   self.assertNotIn('__CONFIG__',s);self.assertNotIn('<!--SAMPLE_BANK-->',s)
   self.assertEqual(s.count('<script type="application/octet-stream"'),9)
   self.assertEqual(r['sampleCount'],r['uniqueSamples'])
   self.assertEqual(r['bytes'],path.stat().st_size)
   self.assertNotIn('<script src=',s);self.assertNotIn('<img src=',s)
   self.assertIn('id="export-wav"',s)
   self.assertIn('MIT License — Echo Workshop original work only',s)
   self.assertIn('THE SOFTWARE IS PROVIDED',s)
if __name__=='__main__':unittest.main()
