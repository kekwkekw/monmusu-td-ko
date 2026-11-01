import copy
import json
from pathlib import Path
import tempfile
import unittest
from novel_storage import encode
from novel_workflow import POLICY_SHA256
import ui_workflow as ui

ROOT = Path(__file__).resolve().parents[1]


class UiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.test-ui-', dir=ROOT)
        self.root = Path(self.temp.name)
        (self.root / 'HOLD_POLICY.md').write_bytes((ROOT / 'HOLD_POLICY.md').read_bytes())
        self.write('translation/ui/source/master.json', {'table': {'table[].name': {'名前1': ''}, 'table[].id': {'日本語ID': ''}}})
        self.write('translation/ui/source/ui.json', {'確認': '', '<b>残り2</b>\n{0}': ''})
        self.write('translation/ui/source/master-sources.json', {'tables': [{'table': 'table', 'class': 'Game.Table', 'preferred_source_id': 'fixture'}]})
        self.review = {'schema': 'monmusu-ui-review-v1', 'policy_sha256': POLICY_SHA256,
                       'review_id': 'synthetic-test', 'reviewer': 'synthetic-test', 'rows': [
                           {'lane': 'ui', 'jp': '確認', 'ko': '확인', 'disposition': 'translate', 'approved': True, 'evidence': 'synthetic'},
                           {'lane': 'master', 'table': 'table', 'field': 'table[].name', 'jp': '名前1', 'ko': '이름1',
                            'disposition': 'translate', 'approved': True, 'evidence': 'synthetic'}]}

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(encode(value))
        return p

    def apply(self, review=None, check=False):
        return ui.apply(self.root, self.write('review.json', review or self.review), check)

    def test_partial_apply_and_idempotent_resume(self):
        self.review['rows'].append({'lane': 'ui', 'jp': '<b>残り2</b>\n{0}', 'disposition': 'pending'})
        self.assertEqual(self.apply()['decisions'], 2)
        before = (self.root / 'translations/ko/master.json').read_bytes()
        self.apply()
        self.assertEqual((self.root / 'translations/ko/master.json').read_bytes(), before)
        self.assertEqual(ui.verify(self.root)['translate'], 2)

    def test_hold_is_per_row(self):
        self.review['rows'][0].update(disposition='hold', ko='', reason='synthetic row-specific reason')
        result = self.apply()
        self.assertEqual((result['hold'], result['translate']), (1, 1))
        self.assertEqual(json.loads((self.root / 'translations/ko/ui.json').read_bytes()), {})

    def test_approval_and_source_required(self):
        for key, value in [('approved', False), ('evidence', ''), ('jp', '存在しない')]:
            review = copy.deepcopy(self.review)
            review['rows'][0][key] = value
            with self.assertRaises(ValueError): self.apply(review)
            self.assertFalse((self.root / 'translations/ko/ui.json').exists())

    def test_tags_numbers_and_newlines_preserved(self):
        row = self.review['rows'][0]
        row['jp'] = '<b>残り2</b>\n{0}'
        for bad in ['<b>남음3</b>\n{0}', '남음2\n{0}', '<b>남음2</b>{0}']:
            row['ko'] = bad
            with self.assertRaises(ValueError): self.apply()
        row['ko'] = '<b>남음2</b>\n{0}'
        self.apply()

    def test_identifier_fields_are_source_only(self):
        row = self.review['rows'][1]
        row.update(field='table[].id', jp='日本語ID', ko='한국어ID')
        with self.assertRaises(ValueError): self.apply()
        row.update(disposition='keep_source', ko='')
        self.assertEqual(self.apply()['keep_source'], 1)

    def test_stale_overwrite_and_tampered_export_rejected(self):
        self.apply()
        self.review['rows'][0]['ko'] = '확인하기'
        with self.assertRaises(ValueError): self.apply()
        self.write('translations/ko/ui.json', {'確認': '무단 변경'})
        with self.assertRaises(ValueError): ui.verify(self.root)

    def test_check_does_not_publish(self):
        self.assertEqual(self.apply(check=True)['status'], 'CHECKED')
        self.assertFalse((self.root / 'translations/ko/ui.json').exists())


if __name__ == '__main__':
    unittest.main()
