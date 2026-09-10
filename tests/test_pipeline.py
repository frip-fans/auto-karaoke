"""All audio/video and CTC evidence are synthetic and generated in temp dirs."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np

from auto_karaoke.alignment import align, ctc_viterbi, morae, reviewed_timing, validate_lyrics, validate_timing
from auto_karaoke.media import check_coverage, prepare, render, replace_audio
from auto_karaoke.ml import choose_device
from auto_karaoke.project import Project, read_json, write_json
from auto_karaoke.subtitles import ass_escape, ass_time, subtitles


class CoreTests(unittest.TestCase):
    def test_device_selection_never_silently_ignores_explicit_cuda(self):
        self.assertEqual(choose_device('auto', True), 'cuda')
        self.assertEqual(choose_device('auto', False), 'cpu')
        self.assertEqual(choose_device('cpu', True), 'cpu')
        with self.assertRaises(ValueError):
            choose_device('cuda', False)

    def test_ctc_repeated_labels_and_uint8_backtrace(self):
        probabilities = np.full((6, 3), 0.001)
        probabilities[np.arange(6), [0, 1, 0, 1, 2, 0]] = 0.998
        spans = ctc_viterbi(np.log(probabilities), [1, 1, 2], 0)
        self.assertEqual([(s['start_frame'], s['end_frame']) for s in spans], [(1, 2), (3, 4), (4, 5)])

    def test_impossible_and_empty_ctc(self):
        for labels in ([1, 1], []):
            with self.assertRaises(ValueError):
                ctc_viterbi(np.log(np.full((2, 3), 1 / 3)), labels, 0)

    def test_mora_and_ass_syntax(self):
        self.assertEqual(morae('きゃっこう'), ['きゃ', 'っ', 'こ', 'う'])
        self.assertEqual(ass_time(60.005), '0:01:00.00')
        self.assertEqual(ass_escape('{x}\\y'), '｛x｝＼y')

    def test_invalid_reading(self):
        with self.assertRaises(ValueError):
            validate_lyrics({'schema_version': 1, 'lines': [{'id': 'a', 'tokens': [['空', 'sora']]}]})

    def test_audio_origin_and_coverage(self):
        check_coverage(30, 60 - 60, 30)
        check_coverage(90, 60 - 0, 30)
        for duration, offset, requested in ((30, 60, 30), (30, -1, 20), (30, float('nan'), 20)):
            with self.assertRaises(ValueError):
                check_coverage(duration, offset, requested)

    def test_timing_rejects_overlap_and_nan(self):
        doc = {'source_duration_seconds': 3, 'lines': [{'tokens': [{'syllables': [
            {'id': 'a', 'start': 0, 'end': 1}, {'id': 'b', 'start': 0.5, 'end': 2}]}]}]}
        with self.assertRaises(ValueError):
            validate_timing(doc)
        doc['lines'][0]['tokens'][0]['syllables'][1]['start'] = float('nan')
        with self.assertRaises(ValueError):
            validate_timing(doc)

    def test_output_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / 'project.json', {'schema_version': 1, 'source': 'work/original.wav', 'lyrics': 'lyrics.json'})
            project = Project(root / 'project.json')
            with self.assertRaises(ValueError):
                project.output('original.wav')
            with self.assertRaises(ValueError):
                project.output('../project.json')


class SyntheticIntegrationTests(unittest.TestCase):
    def test_align_render_and_lossless_video_remux(self):
        import av
        import soundfile as sf
        ffmpeg = os.environ.get('AUTO_KARAOKE_FFMPEG') or shutil.which('ffmpeg')
        font = Path(os.environ.get('AUTO_KARAOKE_TEST_FONT', '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'))
        if not ffmpeg or not font.is_file():
            self.skipTest('Set AUTO_KARAOKE_FFMPEG and AUTO_KARAOKE_TEST_FONT for integration tests')
        with tempfile.TemporaryDirectory(prefix='karaoke-synthetic-') as tmp:
            root = Path(tmp)
            t = np.arange(6 * 44100) / 44100
            wave = 0.05 * np.sin(2 * np.pi * 440 * t)
            sf.write(root / 'source.wav', np.column_stack((wave, wave)), 44100, subtype='FLOAT')
            config = {'schema_version': 1, 'source': 'source.wav', 'lyrics': 'lyrics.json',
                      'clip_start_seconds': 1, 'clip_duration_seconds': 3, 'ffmpeg': ffmpeg,
                      'font_path': str(font), 'font_family': 'IPAGothic',
                      'vocals': {'path': 'source.wav', 'origin_seconds': 0},
                      'instrumental': {'path': 'source.wav', 'origin_seconds': 0}}
            write_json(root / 'project.json', config)
            write_json(root / 'lyrics.json', {'schema_version': 1, 'lines': [
                {'id': 'line-01', 'tokens': [['青い', 'あおい'], ['空', 'そら']]}]})
            project = Project(root / 'project.json')
            prepare(project)
            vocab = {c: i for i, c in enumerate('_|aoisr')}
            probs = np.full((150, len(vocab)), 0.0001)
            probs[:, 0] = 0.9995
            for i, char in enumerate('aoisora'):
                frame = 15 + i * 8
                probs[frame:frame + 4] = 0.0001
                probs[frame:frame + 4, vocab[char]] = 0.9995
            np.save(project.output('emissions.npy'), np.log(probs))
            write_json(project.output('emissions-report.json'), {'model': 'synthetic-no-model', 'seconds': 3,
                       'source_offset_seconds': 1, 'vocals_sha256': hashlib.sha256(project.output('vocals.wav').read_bytes()).hexdigest(),
                       'vocab': vocab, 'blank_id': 0, 'frame_stride_seconds': 0.02})
            align(project)
            timing = read_json(project.output('timing.json'))
            mora = timing['lines'][0]['tokens'][0]['syllables'][0]
            correction = {'syllables': {mora['id']: {'start': mora['start'] + 0.01, 'review_note': 'Synthetic correction'}}}
            write_json(project.output('overrides.json'), correction)
            self.assertEqual(reviewed_timing(project)['lines'][0]['tokens'][0]['syllables'][0]['start'], mora['start'] + 0.01)
            align(project)
            self.assertEqual(read_json(project.output('overrides.json')), correction)
            subtitles(project)
            ass = project.output('karaoke.ass').read_text(encoding='utf-8-sig')
            self.assertIn('Ruby', ass)
            self.assertIn('\\kf', ass)
            self.assertIn('青い', ass)
            render(project)  # audio-only source -> synthetic background
            original = project.output('karaoke-original.mp4')
            alternate = project.output('karaoke-instrumental.mp4')

            def packets(path, kind):
                with av.open(str(path)) as container:
                    stream = getattr(container.streams, kind)[0]
                    return [bytes(packet) for packet in container.demux(stream) if packet.size]

            self.assertEqual(packets(original, 'video'), packets(alternate, 'video'))
            full_track = project.output('full-track-remux.mp4')
            replace_audio(project, original, root / 'source.wav', full_track, 1, 0)
            self.assertEqual(packets(alternate, 'audio'), packets(full_track, 'audio'))
            for path in (original, alternate):
                for kind in ('video', 'audio'):
                    with av.open(str(path)) as container:
                        self.assertGreater(sum(1 for _ in container.decode(**{kind: 0})), 0)
            # Reuse the synthetic render as a video source to cover video extraction/rendering.
            config.update(source=str(original), work_dir='video-work', clip_start_seconds=0)
            write_json(root / 'video-project.json', config)
            video_project = Project(root / 'video-project.json')
            prepare(video_project)
            shutil.copyfile(project.output('karaoke.ass'), video_project.output('karaoke.ass'))
            render(video_project)
            with av.open(str(video_project.output('karaoke-original.mp4'))) as container:
                self.assertEqual(container.streams.video[0].width, 1280)
            write_json(root / 'lyrics.json', {'schema_version': 1, 'lines': []})
            with self.assertRaises(ValueError):
                reviewed_timing(project)


if __name__ == '__main__':
    unittest.main()
