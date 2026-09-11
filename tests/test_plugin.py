"""Exercise portable skill installation without touching personal Codex settings."""
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('karaoke_install', ROOT / 'plugins/auto-karaoke/install_skills.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class PluginInstallTests(unittest.TestCase):
    def test_selected_skill_retains_local_references_after_relocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'skills'
            installer.install(destination, ['karaoke-author'])
            self.assertEqual([p.name for p in destination.iterdir()], ['karaoke-author'])
            self.assertEqual((destination / 'karaoke-author/LICENSE').read_bytes(),
                             (ROOT / 'LICENSE').read_bytes())
            skill = destination / 'karaoke-author/SKILL.md'
            for target in re.findall(r'\]\(([^)]+)\)', skill.read_text()):
                if '://' not in target:
                    self.assertTrue((skill.parent / target).is_file(), target)

    def test_conflict_leaves_existing_and_other_skills_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)
            existing = destination / 'karaoke-author'
            existing.mkdir()
            marker = existing / 'personal.md'
            marker.write_text('personal changes')
            with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
                installer.install(destination, list(installer.NAMES))
            self.assertEqual(marker.read_text(), 'personal changes')
            self.assertFalse((destination / 'audio-separate').exists())


class EnvironmentCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'plugins/auto-karaoke/skills/karaoke-setup/scripts/check_environment.py'
        spec = importlib.util.spec_from_file_location('karaoke_environment', path)
        cls.check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.check)

    def test_minimal_machine_reports_missing_tools_without_installing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(self.check.shutil, 'which', return_value=None), \
                 patch.object(self.check, 'versions', return_value={'auto-karaoke': None}), \
                 patch.object(self.check, 'run') as run:
                result = self.check.collect('render', tmp)
            self.assertIsNone(result['ffmpeg'])
            self.assertIsNone(result['nvidia'])
            self.assertEqual(result['missing_packages'], ['auto-karaoke'])
            run.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_compiled_gpu_encoder_does_not_imply_working_driver(self):
        from unittest.mock import patch
        def fake_run(args, timeout=20):
            if '-filters' in args:
                return {'ok': True, 'output': ' ... ass V->V subtitle rendering'}
            if '-encoders' in args:
                return {'ok': True, 'output': ' V..... h264_nvenc NVIDIA encoder'}
            return {'ok': False, 'output': 'Cannot load driver'}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(self.check.shutil, 'which', side_effect=lambda name: '/usr/bin/ffmpeg' if name == 'ffmpeg' else None), \
             patch.object(self.check, 'run', side_effect=fake_run):
            result = self.check.collect('render', tmp, encoder='h264_nvenc')
        self.assertTrue(result['compiled_encoders']['h264_nvenc'])
        self.assertFalse(result['encoder_smoke_test']['ok'])
        self.assertNotIn('ready', result)

    def test_font_collection_is_not_accepted_as_single_font(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            font = Path(tmp) / 'font.ttf'
            font.write_bytes(b'ttcf' + b'\0' * 20)
            with patch.object(self.check.shutil, 'which', return_value=None):
                result = self.check.collect('render', tmp, font=font)
            self.assertFalse(result['font']['single_font_header_valid'])
