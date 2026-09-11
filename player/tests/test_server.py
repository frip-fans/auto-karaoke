import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import wave
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import create_app


def fixture(path, second='Vocals'):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=navy:s=320x180:r=24:d=4',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=4',
                    '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=44100:duration=4',
                    '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-metadata:s:a:0', 'handler_name=Instrumental',
                    '-metadata:s:a:1', 'handler_name='+second, str(path)], check=True)


class LibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        fixture(cls.root / 'source.mp4')
        fixture(cls.root / 'original.mp4', 'Original Mix')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.library = self.root / ('library-'+str(time.time_ns()))
        self.app = create_app(self.library)
        self.client = self.app.test_client()
        self.token = self.client.get('/api/library').json['token']
        self.headers = {'X-Karaoke-Token': self.token}

    def tearDown(self):
        self.app.extensions['karaoke_pool'].shutdown(wait=True)

    def upload(self, filename='source.mp4', **metadata):
        return self.client.post('/api/import', headers=self.headers, data={
            'files': (io.BytesIO((self.root / filename).read_bytes()), filename),
            'album': 'Example album', 'title': 'Example song', **metadata}).json['songs'][0]

    def test_import_versions_and_portability(self):
        a = self.upload(version='Album')
        b = self.upload(version='Live')
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual(a['title'], b['title'])
        catalog = json.loads((self.library/'library.json').read_text())
        self.assertFalse(Path(catalog['songs'][0]['file']).is_absolute())
        relocated = self.library.with_name(self.library.name+'-moved')
        shutil.copytree(self.library, relocated)
        app = create_app(relocated)
        try:
            result = app.test_client().get('/api/library').json
            self.assertEqual(result['library_id'], catalog['library_id'])
            self.assertEqual(len(result['songs']), 2)
            self.assertTrue(all(s['playable'] for s in result['songs']))
        finally:
            app.extensions['karaoke_pool'].shutdown(wait=True)

    def test_pcm_roles_range_and_timing(self):
        song = self.upload()
        route = f'/api/songs/{song["id"]}/prepare'
        self.client.post(route, headers=self.headers)
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            job = self.client.get(route).json
            if job['status'] in {'ready','error'}:
                break
            time.sleep(.05)
        self.assertEqual(job['status'], 'ready', job)
        import array, math
        for role, frequency in [('instrumental',440),('vocals',880)]:
            with self.client.get(job[role]) as response:
                data = response.data
            with wave.open(io.BytesIO(data)) as wav:
                self.assertEqual(wav.getframerate(), 44100)
                self.assertEqual(wav.getnframes(), 4*44100)
                samples = array.array('h', wav.readframes(wav.getnframes()))[::2]
                energy = lambda f: abs(sum(samples[i]*complex(math.cos(2*math.pi*f*i/44100),math.sin(2*math.pi*f*i/44100)) for i in range(4410,8820)))
                self.assertGreater(energy(frequency), energy(1320-frequency)*20)
        response = self.client.get('/video/'+song['id'], headers={'Range':'bytes=0-99'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(len(response.data), 100)
        response.close()

    def test_original_mix_is_never_auto_vocals(self):
        song = self.upload('original.mp4')
        self.assertEqual(song['instrumental'], 1)
        self.assertIsNone(song['vocals'])

    def test_local_mutations_and_validation(self):
        self.assertEqual(self.client.post('/api/scan').status_code, 403)
        self.assertEqual(self.client.post('/api/scan', headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/library', headers={'Host':'evil.example'}).status_code,403)
        song = self.upload()
        url = '/api/songs/'+song['id']
        self.assertEqual(self.client.patch(url,headers=self.headers,json={'mapping':{'instrumental':1,'vocals':1}}).status_code,400)
        response = self.client.patch(url,headers=self.headers,json={'album':'New album','version':'Live'})
        self.assertEqual(response.json['version'],'Live')
        self.assertEqual(self.client.get('/audio/../../etc/passwd').status_code,404)


if __name__ == '__main__':
    unittest.main()
