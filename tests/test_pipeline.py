"""All audio/video and CTC evidence are synthetic and generated in temp dirs."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from types import SimpleNamespace

import numpy as np

from auto_karaoke.alignment import align, ctc_viterbi, morae, reviewed_timing, validate_lyrics, validate_timing
from auto_karaoke.media import check_coverage, prepare, render, replace_audio, video_encoding_args, combine_audio_tracks
from auto_karaoke.ml import choose_device
from auto_karaoke.project import Project, read_json, write_json
from auto_karaoke.subtitles import ass_escape, ass_time, kanji_ruby_spans, lyric_appearances, singer_change_lines, subtitles
from auto_karaoke.rhythm import entrance_cues
from auto_karaoke.singers import import_singers, singer_styles


class CoreTests(unittest.TestCase):
    def test_audio_only_project_does_not_require_lyrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / 'project.json', {'schema_version': 1, 'source': 'input.wav'})
            project = Project(root / 'project.json')
            self.assertEqual(project.source, root / 'input.wav')
            self.assertEqual(project.output('vocals.wav'), root / 'work/vocals.wav')
            with self.assertRaisesRegex(ValueError, 'needs lyrics'):
                align(project)
            with self.assertRaises(ValueError):
                project.output('../input.wav')

    def test_english_words_keep_acoustic_spans_and_token_singers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root/'project.json', {'schema_version':1,'source':'source.wav','lyrics':'lyrics.json','clip_duration_seconds':3})
            p = Project(root/'project.json')
            write_json(p.lyrics, {'schema_version':1,'lines':[{'id':'en','language':'en',
                'tokens':[['Hello','hello'],['world!','world']], 'token_singers':['mao','hisayo']}]})
            p.output('vocals.wav').write_bytes(b'synthetic fingerprint fixture')
            vocab={c:i for i,c in enumerate('_|helowrd')}
            probs=np.full((150,len(vocab)),.0001);probs[:,0]=.999
            for i,c in enumerate('helloworld'):
                frame=15+i*8;probs[frame:frame+4]=.0001;probs[frame:frame+4,vocab[c]]=.999
            np.save(p.output('emissions.npy'),np.log(probs))
            write_json(p.output('emissions-report.json'),{'model':'synthetic','seconds':3,'source_offset_seconds':0,
                'vocals_sha256':hashlib.sha256(p.output('vocals.wav').read_bytes()).hexdigest(),
                'vocab':vocab,'blank_id':0,'frame_stride_seconds':.02})
            align(p);tokens=read_json(p.output('timing.json'))['lines'][0]['tokens']
            self.assertEqual([t['singer'] for t in tokens],['mao','hisayo'])
            self.assertEqual([t['syllables'][0]['unit'] for t in tokens],['word','word'])
            self.assertEqual(len(tokens[0]['syllables']),1)
            self.assertAlmostEqual(tokens[0]['start'],.3)

    def test_singer_name_only_on_first_line_and_changes(self):
        voices = ['mao', 'mao', 'hisayo', 'duet', 'duet', 'mao', 'unknown', 'mao']
        lines = [{'id': str(i)} for i in range(len(voices))]
        assignments = {str(i): {'singer': sid} for i, sid in enumerate(voices)}
        self.assertEqual(singer_change_lines(lines, assignments), {'0', '2', '3', '5', '7'})

    def test_countdown_stages_last_at_least_a_second_after_long_gaps(self):
        lines = [{'id': 'a', 'start': 1, 'end': 3}, {'id': 'b', 'start': 10, 'end': 12},
                 {'id': 'c', 'start': 12.3, 'end': 14}]
        cues = entrance_cues(lines, [6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12])
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0], {'line_id': 'b', 'marks': [6, 7, 8, 9], 'end': 10})
        entries = lyric_appearances(lines, 15)
        self.assertEqual({(line['id'], row) for line, start, end, row in entries if start <= 8 < end},
                         {('b', 'upper'), ('c', 'lower')})
        self.assertEqual({(line['id'], row) for line, start, end, row in entries if start <= 10.5 < end},
                         {('b', 'upper'), ('c', 'lower')})
        fast = entrance_cues(lines, [i * .4 for i in range(32)])
        edges = fast[0]['marks'] + [fast[0]['end']]
        self.assertTrue(all(b - a >= 1 - 1e-8 for a, b in zip(edges, edges[1:])))
        self.assertEqual(entrance_cues(lines, [1, 2, 3]), [])
        with self.assertRaises(ValueError):
            entrance_cues(lines, [9, 8])

    def test_manual_singer_import_and_disabled_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / 'lyrics.json', {'schema_version': 1, 'lines': []})
            write_json(root / 'project.json', {'schema_version': 1, 'source': 'source.wav', 'lyrics': 'lyrics.json',
                'singer_map': 'singers.json', 'clip_duration_seconds': 20})
            p = Project(root / 'project.json')
            lines = [{'id': lid, 'text': 'あ', 'start': t, 'end': t+1,
                'tokens': [{'surface': 'あ', 'reading': 'あ', 'syllables': [{'id': lid+'-m', 'kana': 'あ', 'start': t, 'end': t+1}]}]}
                for lid, t in [('one', 1), ('two', 10)]]
            write_json(p.output('timing.json'), {'schema_version': 1, 'source_offset_seconds': 0, 'source_duration_seconds': 20,
                'lines': lines, 'alignment': {'lyrics_sha256': hashlib.sha256(p.lyrics.read_bytes()).hexdigest()}})
            write_json(root/'incoming.json', {'schema_version': 1, 'lines': {'one': 'mao'},
                'ranges': [{'start': 9, 'end': 12, 'singer': 'hisayo'}]})
            before = p.output('timing.json').read_bytes()
            import_singers(p, root/'incoming.json')
            legend, resolved = singer_styles(p, lines)
            self.assertEqual(legend, {})
            self.assertEqual(resolved['one']['singer'], 'unknown')
            import_singers(p, root/'incoming.json', enable=True)
            legend, resolved = singer_styles(p, lines)
            self.assertEqual(resolved['one']['color'], '#FF76B5')
            self.assertEqual(resolved['two']['color'], '#FFE45C')
            self.assertTrue(read_json(p.path)['singer_colors_enabled'])
            self.assertEqual(p.output('timing.json').read_bytes(), before)
            annotated = {'schema_version': 1,
                'singers': {'guest': {'label': 'Guest', 'color': '#123456'},
                            'duet': {'label': 'Together', 'color': '#FF7700'}},
                'singer_legend': ['guest', 'duet'],
                'lines': [{'id': 'one', 'tokens': [['あ', 'あ']], 'singer': 'guest', 'singer_status': 'confirmed'},
                          {'id': 'two', 'text': 'あ', 'singer': 'duet', 'extra': 'retained in source'}]}
            write_json(root/'annotated.json', annotated)
            import_singers(p, root/'annotated.json')
            legend, resolved = singer_styles(p, lines)
            self.assertEqual(resolved['one']['color'], '#123456')
            self.assertEqual(resolved['two']['color'], '#FF7700')
            self.assertEqual(list(legend), ['guest', 'duet'])
            self.assertEqual(read_json(root/'annotated.json'), annotated)
            self.assertEqual(p.output('timing.json').read_bytes(), before)
            saved = (root/'singers.json').read_bytes()
            annotated['lines'][0]['tokens'] = [['い', 'い']]
            write_json(root/'annotated.json', annotated)
            with self.assertRaises(ValueError): import_singers(p, root/'annotated.json')
            self.assertEqual((root/'singers.json').read_bytes(), saved)
            write_json(root/'incoming.json', {'schema_version': 1, 'ranges': [{'start': 10.5, 'end': 12, 'singer': 'duet'}]})
            with self.assertRaises(ValueError): import_singers(p, root/'incoming.json')
            self.assertEqual((root/'singers.json').read_bytes(), saved)

    def test_lyrics_stay_in_fixed_alternating_rows(self):
        lines = [{'id': 'a', 'start': 1, 'end': 3}, {'id': 'b', 'start': 3.2, 'end': 5},
                 {'id': 'c', 'start': 5.2, 'end': 7}, {'id': 'd', 'start': 20, 'end': 22}]
        entries = lyric_appearances(lines, 24)
        at_two = [(line['id'], row) for line, start, end, row in entries if start <= 2 < end]
        self.assertEqual(set(at_two), {('a', 'upper'), ('b', 'lower')})
        at_four = {(line['id'], row) for line, start, end, row in entries if start <= 4 < end}
        self.assertEqual(at_four, {('c', 'upper'), ('b', 'lower')})
        self.assertEqual(len(entries), len(lines))
        for row in ['upper', 'lower']:
            intervals = sorted((s, e) for _, s, e, r in entries if r == row)
            self.assertTrue(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])))
        self.assertTrue(all(end > start for _, start, end, _ in entries))
        self.assertTrue(all(not (start <= 8 < end) for line, start, end, _ in entries if line['id'] == 'd'))
        self.assertEqual(next(row for line, _, _, row in entries if line['id'] == 'd'), 'upper')

    def test_video_encoder_selection_and_invalid_settings(self):
        project = SimpleNamespace(config={}, threads=2)
        self.assertIn('libx264', video_encoding_args(project))
        project.config = {'video_encoder': 'h264_nvenc', 'video_quality': 18}
        args = video_encoding_args(project)
        self.assertIn('h264_nvenc', args)
        self.assertNotIn('-crf', args)
        self.assertEqual(args[args.index('-cq') + 1], 18)
        for config in ({'video_encoder': 'unknown'}, {'video_quality': -1},
                       {'video_quality': 52}, {'video_quality': True}):
            project.config = config
            with self.assertRaises(ValueError):
                video_encoding_args(project)

    def test_ruby_only_covers_kanji_and_preserves_reading_offsets(self):
        for surface, reading, expected in [
            ('食べる', 'たべる', [('食', 'た', 0, 1)]),
            ('引き出す', 'ひきだす', [('引', 'ひ', 0, 1), ('出', 'だ', 2, 3)]),
            ('お祝い', 'おいわい', [('祝', 'いわ', 1, 3)]),
            ('図書館', 'としょかん', [('図書館', 'としょかん', 0, 5)]),
            ('「会える」', 'あえる', [('会', 'あ', 0, 1)]),
            ('ひらがな', 'ひらがな', []),
        ]:
            with self.subTest(surface=surface):
                spans = kanji_ruby_spans(surface, reading)
                self.assertEqual([(surface[s['surface_start']:s['surface_end']], s['reading'],
                                   s['reading_start'], s['reading_end']) for s in spans], expected)
        with self.assertRaises(ValueError):
            kanji_ruby_spans('食べる', 'たべた')

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
    def test_prepare_audio_without_lyrics_or_fonts(self):
        import soundfile as sf
        ffmpeg = os.environ.get('AUTO_KARAOKE_FFMPEG') or shutil.which('ffmpeg')
        if not ffmpeg:
            self.skipTest('FFmpeg required')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            samples = .05 * np.sin(2 * np.pi * 440 * np.arange(44100) / 44100)
            sf.write(root / 'input.wav', samples, 44100)
            write_json(root / 'project.json', {'schema_version': 1, 'source': 'input.wav',
                       'clip_duration_seconds': 1, 'ffmpeg': ffmpeg})
            project = Project(root / 'project.json')
            prepare(project)
            result, rate = sf.read(project.output('original.wav'), always_2d=True)
            self.assertEqual((len(result), rate, result.shape[1]), (44100, 44100, 2))
            self.assertTrue(np.isfinite(result).all())
            self.assertGreater(float(np.corrcoef(samples, result[:, 0])[0, 1]), .999)
            self.assertFalse((root / 'lyrics.json').exists())


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
            project.config['show_preview_label'] = False
            subtitles(project)
            ass = project.output('karaoke.ass').read_text(encoding='utf-8-sig')
            self.assertIn('Ruby', ass)
            self.assertIn('\\kf', ass)
            self.assertIn('青い', ass)
            self.assertNotIn('KARAOKE PREVIEW', ass)
            self.assertNotIn(r'\p1', ass)  # No background rectangle.
            current = next(row for row in read_json(project.output('layout.json'))['lines'] if row['row'] == 'upper')
            self.assertEqual(current['x'], 60)
            self.assertEqual(current['font_scale'], 1.2)
            project.config['intro_card'] = {'title':'Synthetic Song','artist':'Test Artist','album':'Test Album','seconds':2}
            project.config['outro_card'] = {'seconds':1}
            subtitles(project)
            title_ass=project.output('karaoke.ass').read_text(encoding='utf-8-sig')
            self.assertIn('Synthetic Song',title_ass)
            self.assertIn('Test Artist',title_ass)
            self.assertIn(r'\an5\pos(640,270)',title_ass)
            self.assertIn(r'\bord4.0',title_ass)
            self.assertEqual(read_json(project.output('layout.json'))['title_cards'],
                             [{'kind':'intro','start':0,'end':2},{'kind':'outro','start':2,'end':3}])
            render(project)  # audio-only source -> synthetic background
            from PIL import Image
            Image.new('RGB',(64,36),(20,40,200)).save(root/'background.png')
            project.config.update(background_image=str(root/'background.png'), render_width=640, render_height=360)
            render(project)
            original = project.output('karaoke-original.mp4')
            alternate = project.output('karaoke-instrumental.mp4')
            with av.open(str(original)) as container:
                frame=next(container.decode(video=0))
                self.assertEqual((frame.width,frame.height),(640,360))
                rgb=frame.to_ndarray(format='rgb24')[0,0]
                self.assertGreater(int(rgb[2]),int(rgb[0])+100)

            def packets(path, kind, index=0):
                with av.open(str(path)) as container:
                    stream = getattr(container.streams, kind)[index]
                    return [bytes(packet) for packet in container.demux(stream) if packet.size]

            self.assertEqual(packets(original, 'video'), packets(alternate, 'video'))
            full_track = project.output('full-track-remux.mp4')
            replace_audio(project, original, root / 'source.wav', full_track, 1, 0)
            self.assertEqual(packets(alternate, 'audio'), packets(full_track, 'audio'))
            sf.write(root/'quiet.wav',np.zeros((6*44100,2)),44100)
            quiet_video=project.output('quiet-instrumental.mp4')
            replace_audio(project,original,root/'quiet.wav',quiet_video,1,0)
            dual=project.output('dual.mp4')
            combine_audio_tracks(project,quiet_video,original,dual)
            self.assertEqual(packets(dual,'video'),packets(original,'video'))
            self.assertEqual(packets(dual,'audio',0),packets(quiet_video,'audio'))
            self.assertEqual(packets(dual,'audio',1),packets(original,'audio'))
            with av.open(str(dual)) as container:
                self.assertEqual(len(container.streams.audio),2)
                self.assertTrue(int(container.streams.audio[0].disposition)&1)
                self.assertFalse(int(container.streams.audio[1].disposition)&1)
            vocal_dual=project.output('vocal-dual.mp4')
            track_report=combine_audio_tracks(project,quiet_video,project.output('vocals.wav'),vocal_dual,secondary_role='vocals')
            self.assertEqual(packets(vocal_dual,'video'),packets(original,'video'))
            self.assertEqual(packets(vocal_dual,'audio',0),packets(quiet_video,'audio'))
            self.assertEqual(track_report['audio_tracks'][1]['role'],'vocals')
            with av.open(str(vocal_dual)) as container:
                self.assertEqual(container.streams.audio[1].metadata['handler_name'],'Vocals')
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
