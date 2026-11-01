import json
import struct
import tempfile
import unittest
from pathlib import Path

from core import book_rows, classify, decode_text, decrypt, iter_strings, json_line, load_tree, metadata_literals, store_tree


class ExtractionTests(unittest.TestCase):
    def test_book_preserves_variants_duplicates_tags_and_all_grids(self):
        grid = {'rows': [{'strings': ['Command', 'Text', 'Arg1', 'Voice']},
                         {'strings': ['', '<b>same</b>\ntext', 'speaker', 'voice_1']},
                         {'strings': ['', '<b>same</b>\ntext', '', 'voice_2']},
                         {'strings': ['//comment', 'not dialogue']}]}
        rows = list(book_rows({'m_Name': '10128B1_R18.book ', 'importGridList': [grid, grid]}, 'source'))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['scenario_name'], '10128B1_R18.book ')
        self.assertEqual(rows[0]['message'], rows[1]['message'])
        self.assertNotEqual(rows[0]['row_index_0based'], rows[1]['row_index_0based'])
        self.assertEqual(rows[2]['grid_index'], 1)
        self.assertEqual(rows[2]['message_index_0based'], 2)
        self.assertEqual(rows[0]['physical_line_1based'], 2)
        self.assertEqual(rows[0]['voice'], 'voice_1')

    def test_commented_rows_and_duplicate_headers(self):
        tree = {'importGridList': [{'rows': [
            {'strings': ['Text', 'Command', 'Text']},
            {'strings': ['first value', '', 'duplicate column']},
            {'strings': ['commented', ''], 'isCommentOut': 1},
        ]}]}
        rows = list(book_rows(tree, 'src'))
        self.assertEqual([r['message'] for r in rows], ['first value'])

    def test_binary_fields_roundtrip_and_json_pointer(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            store_tree(tmp, {'a/b~': ['日本語', b'\x00\xff']})
            tree = load_tree(tmp)
            self.assertEqual((Path(tmp) / tree['a/b~'][1]['$binary']).read_bytes(), b'\x00\xff')
            self.assertEqual(list(iter_strings(tree)), [('/a~1b~0/0', '日本語')])
        value = {'text': '日本語\udc80'}
        self.assertEqual(json.loads(json_line(value)), value)
        self.assertIn('日本語', json_line(value))

    def test_crypto_and_decoding(self):
        raw = b'UnityFS\x00' + bytes(range(256))
        self.assertEqual(decrypt(decrypt(raw)), raw)
        self.assertEqual(decode_text('設定'.encode('utf-16'))[0], '設定')
        self.assertIsNone(decode_text(b'\x00\xff')[0])

    def test_spine_is_classified_only_after_structural_parsing(self):
        self.assertEqual(classify({}, {'skeleton': {}, 'bones': []})[0], 'excluded/spine')
        self.assertEqual(classify({}, {'name': 'spine', 'text': 'dialogue'})[0], 'kept/other_text')
        self.assertEqual(classify({}, {'importGridList': []})[0], 'kept/scenario_books')
        self.assertEqual(classify({'script_namespace': 'Spine.Unity'}, {})[0], 'excluded/spine_components')
        self.assertEqual(classify({'type': 'TextAsset'}, {'m_Script': '\u0000bin'})[0], 'excluded/binary_textasset')

    def test_il2cpp_literal_offsets_and_bounds(self):
        raw = struct.pack('<6I', 0xFAB11BAF, 29, 24, 8, 32, 3) + struct.pack('<2I', 3, 0) + b'abc'
        self.assertEqual(list(metadata_literals(raw))[0]['text'], 'abc')
        with self.assertRaises(ValueError):
            list(metadata_literals(raw[:-1]))


if __name__ == '__main__':
    unittest.main()
