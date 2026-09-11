"""Synthetic DOCX fixtures only: section legends, soft breaks and inline roles."""
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from auto_karaoke.docx_lyrics import W, convert_docx, formatted_lines


def docx(path, paragraphs, styles=None):
    document = ET.Element(W+'document');body = ET.SubElement(document, W+'body')
    for runs in paragraphs:
        p = ET.SubElement(body, W+'p')
        for text, options in runs:
            r = ET.SubElement(p, W+'r');props = ET.SubElement(r, W+'rPr')
            for key, value in options.items():
                ET.SubElement(props, W+key, {W+'val':str(value)})
            for i, part in enumerate(text.split('\n')):
                if i: ET.SubElement(r, W+'br')
                ET.SubElement(r, W+'t').text = part
    with ZipFile(path, 'w') as z:
        z.writestr('word/document.xml', ET.tostring(document))
        if styles is not None:z.writestr('word/styles.xml', ET.tostring(styles))


class DocxLyricsTests(unittest.TestCase):
    def test_blank_line_spacing_is_preserved_as_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'spacing.docx'
            docx(path, [[('青い空\n\n白い雲', {})]])
            result=formatted_lines(path)
            self.assertEqual(len(result),2)
            self.assertEqual([r['blank_lines_before'] for r in result],[0,1])

    def test_bold_is_a_solo_voice_when_section_legend_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'chorus.docx'
            docx(path, [[('[Chorus: Both, ', {}), ('Hisayo Abe', {'i':'1'}),
                          (', ', {}), ('Mao Uesugi', {'b':'1'}), (']\n青い空\n', {}),
                          ('白い雲\n', {'i':'1'}), ('赤い花', {'b':'1'})]])
            self.assertEqual([l['singer'] for l in convert_docx(path)['lines']], ['duet','hisayo','mao'])

    def test_character_style_toggles_against_paragraph_style(self):
        styles=ET.Element(W+'styles')
        normal=ET.SubElement(styles,W+'style',{W+'styleId':'Normal',W+'type':'paragraph',W+'default':'1'})
        ET.SubElement(ET.SubElement(normal,W+'rPr'),W+'i')
        emphasis=ET.SubElement(styles,W+'style',{W+'styleId':'Emphasis',W+'type':'character'})
        ET.SubElement(ET.SubElement(emphasis,W+'rPr'),W+'i')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'toggle.docx'
            docx(path, [[('青い空\n', {}), ('白い雲\n', {'rStyle':'Emphasis'}),
                          ('赤い花', {'rStyle':'Emphasis','i':'1'})]], styles)
            lines=formatted_lines(path)
            self.assertEqual([line['runs'][0]['italic'] for line in lines],[True,False,True])

    def test_section_legends_reverse_and_mixed_roles_are_not_collapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.docx'
            docx(path, [[('[Verse 1: Mao Uesugi, ', {}), ('Hisayo Abe', {'i':'1'}),
                (', ', {}), ('Both', {'b':'1'}), (']\n青い空\n', {}),
                ('白い雲\n', {'i':'1'}), ('赤い花\n', {'b':'1'}),
                ('星の光（', {}), ('ああ', {'b':'1'}), ('）\n', {}),
                ('[Verse 2: Hisayo Abe, ', {}), ('Mao Uesugi', {'i':'1'}),
                (']\n短い夢\n', {}), ('長い道', {'i':'1'})]])
            result=convert_docx(path);lines=result['lines']
            self.assertEqual([l['text'] for l in lines],['青い空','白い雲','赤い花','星の光（ああ）','短い夢','長い道'])
            self.assertEqual([l['singer'] for l in lines],['mao','hisayo','duet','unknown','hisayo','mao'])
            self.assertEqual(result['sections'][1]['style_mapping'],{'plain':'hisayo','italic':'mao'})
            mixed=lines[3];self.assertTrue(mixed['mixed_singers'])
            self.assertEqual([p['singer'] for p in mixed['singer_segments']],['mao','duet','mao'])
            self.assertEqual(''.join(p['text'] for p in mixed['singer_segments']),mixed['text'])
            self.assertFalse(result['import_report']['timestamps_generated'])

    def test_attached_solo_and_unlabelled_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'solo.docx'
            docx(path, [[('上杉真央solo', {})], [('[Verse]\n青い空\n[Chorus]\n白い雲', {})]])
            result=convert_docx(path)
            self.assertEqual(result['import_report']['whole_song_solo'],'mao')
            self.assertEqual([l['singer'] for l in result['lines']],['mao','mao'])
            self.assertEqual(len(result['lines']),2)

    def test_run_style_and_explicit_italic_off(self):
        styles=ET.Element(W+'styles')
        style=ET.SubElement(styles,W+'style',{W+'styleId':'Emphasis',W+'type':'character'})
        props=ET.SubElement(style,W+'rPr');ET.SubElement(props,W+'i')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'style.docx'
            docx(path, [[('[Verse: Mao Uesugi, ', {}), ('Hisayo Abe', {'rStyle':'Emphasis'}),
                (']\n青い空\n', {'rStyle':'Emphasis','i':'0'}),
                ('白い雲', {'rStyle':'Emphasis'})]],styles)
            result=convert_docx(path)
            self.assertEqual([l['singer'] for l in result['lines']],['mao','hisayo'])

    def test_ambiguous_header_style_stays_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ambiguous.docx'
            docx(path, [[('[Verse: Mao Uesugi, Hisayo Abe]\n青い空', {})]])
            result=convert_docx(path)
            self.assertEqual(result['lines'][0]['singer'],'unknown')
            self.assertTrue(result['import_report']['issues'])


if __name__ == '__main__':unittest.main()
