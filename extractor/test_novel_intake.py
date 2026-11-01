import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from core import book_rows
from novel_intake import read_json, run, scenario_file, write_json


class NovelIntakeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(temp.cleanup)
        self.snapshot = Path(temp.name) / 'snapshot'
        self.out = Path(temp.name) / 'work'
        digest = 'a' * 64
        source_id = digest + ':000001_-123'
        name = 'Scene_Nmⅼ '
        folder = self.snapshot / 'kept/scenario_books' / digest[:2] / digest / '000001_-123'
        folder.mkdir(parents=True)
        self.jp = '　<ruby=よみ>字</ruby><interval=0.4>\r\n同じ行　'
        def rawrow(i, *cells):
            return {'rowIndex': i, 'strings': list(cells)}
        grids = [{'name': '前半', 'rows': [rawrow(50, 'Command', 'Arg1', 'Text', 'PageCtrl'),
                                        rawrow(51, '', ' 話者 ', self.jp, 'Next '),
                                        rawrow(55, '', ' 話者 ', self.jp, 'Br\t')]},
                 {'name': '後半', 'rows': [rawrow(70, ''), rawrow(71, 'Arg1', 'Text', 'Command'),
                                        rawrow(77, '*分岐', '選択', 'Selection')]}]
        book = {'m_Name': name + '.book', 'importGridList': grids}
        write_json(folder / 'book.json', book)
        rows = list(book_rows(book, source_id))
        (folder / 'rows.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        grid_hash = hashlib.sha256(json.dumps(grids, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        preferred = {'source_id': source_id, 'name': book['m_Name'], 'rows': 3,
                     'sources': ['current_remote'], 'grid_sha256': grid_hash}
        entry = {'scenario_name': name, 'preferred_source_id': source_id,
                 'variants': [dict(preferred, source_id='older'), preferred]}
        empty = {'scenario_name': 'cfg', 'preferred_source_id': 'empty', 'variants': [{'source_id': 'empty', 'rows': 0}]}
        indexes = self.snapshot / 'indexes'
        indexes.mkdir()
        (indexes / 'scenario-variants.jsonl').write_text(json.dumps(entry) + '\n' + json.dumps(empty), encoding='utf-8')
        write_json(self.snapshot / 'verification.json',
                   {'passed': True, 'missing_output_paths': [], 'unreadable_records': 0,
                    'scenario_names_including_config': 2, 'scenario_names_with_text_rows': 1, 'preferred_variant_text_rows': 3})
        self.file = self.out / scenario_file(name)
        self.source_rows = folder / 'rows.jsonl'

    def test_preferred_rows_and_position(self):
        result = run('generate', self.snapshot, self.out, 1)
        first, repeat, choice = read_json(self.file)['rows']
        self.assertEqual(result['scenario_count'], 1)
        self.assertNotEqual(scenario_file('Scene_Nmⅼ '), scenario_file('Scene_Nml'))
        self.assertEqual((first['jp'], first['speaker'], first['page_ctrl']), (self.jp, ' 話者 ', 'Next '))
        self.assertEqual([self.jp[t['start']:t['end']] for t in first['inline_tags']],
                         ['<ruby=よみ>', '</ruby>', '<interval=0.4>'])
        self.assertEqual(first['jp'], repeat['jp'])
        self.assertNotEqual(first['row_id'], repeat['row_id'])
        self.assertEqual((choice['kind'], choice['grid_index'], choice['header_row_index_0based'],
                          choice['physical_line_1based'], choice['serialized_row_index'],
                          choice['message_index_0based'], choice['grid_message_index_0based']),
                         ('selection', 1, 1, 3, 77, 2, 0))

    def test_repeat_preserves_draft_and_detects_source_edits(self):
        run('generate', self.snapshot, self.out, 1)
        doc = read_json(self.file)
        doc['rows'][0].update(ko='작성 중', translation_status='drafted', review_note='확인 필요')
        write_json(self.file, doc)
        edited = self.file.read_bytes()
        run('generate', self.snapshot, self.out, 1)
        self.assertEqual(self.file.read_bytes(), edited)
        doc['rows'][0]['jp'] = self.jp.strip()
        write_json(self.file, doc)
        with self.assertRaisesRegex(ValueError, 'Source fields changed'):
            run('verify', self.snapshot, self.out, 1)

    def test_inconsistent_source_does_not_publish_partial_batch(self):
        self.source_rows.write_text('', encoding='utf-8')
        with self.assertRaises(ValueError):
            run('generate', self.snapshot, self.out, 1)
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
