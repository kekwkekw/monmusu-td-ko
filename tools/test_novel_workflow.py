"""Benign synthetic integration tests. Never translate the real corpus."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import novel_workflow as flow
import novel_storage as storage
import translation_knowledge as knowledge
from core import book_rows


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='.test-novel-', dir=Path(__file__).resolve().parent)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'HOLD_POLICY.md').write_bytes((flow.ROOT / 'HOLD_POLICY.md').read_bytes())
        self.snapshot = self.root / 'extractor/output'
        self.input = self.root / 'translation/novel'
        self.names = ['Scene_Nmⅼ ', 'Other_Nml']
        index = []
        for char, name in zip('ab', self.names):
            sha = char * 64
            identity = sha + ':000001_-123'
            folder = self.snapshot / 'kept/scenario_books' / sha[:2] / sha / '000001_-123'
            folder.mkdir(parents=True)
            jp = '<ruby=はな>花</ruby><interval=0.4>\r\n花です。'
            grids = [{'name': '前半', 'rows': [
                {'rowIndex': 50, 'strings': ['Command', 'Arg1', 'Text', 'PageCtrl', 'Voice']},
                {'rowIndex': 55, 'strings': ['', '案内人', jp, 'Next\t', 'voice01']},
                {'rowIndex': 60, 'strings': ['', '案内人', jp, 'Br ', 'voice02']}]},
                {'name': '後半', 'rows': [['Arg1', 'Text', 'Command'], ['*次', '進む', 'Selection']]}]
            book = {'m_Name': name + '.book', 'importGridList': grids}
            self.save(folder / 'book.json', book)
            (folder / 'rows.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in book_rows(book, identity)), encoding='utf-8')
            raw = json.dumps(grids, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
            variant = {'source_id': identity, 'name': name + '.book', 'rows': 3,
                       'sources': ['current_remote'], 'grid_sha256': hashlib.sha256(raw).hexdigest()}
            index.append({'scenario_name': name, 'preferred_source_id': identity, 'variants': [variant]})
        (self.snapshot / 'indexes').mkdir()
        (self.snapshot / 'indexes/scenario-variants.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in index), encoding='utf-8')
        self.save(self.snapshot / 'verification.json', {'passed': True, 'missing_output_paths': [], 'unreadable_records': 0,
            'scenario_names_including_config': 2, 'scenario_names_with_text_rows': 2, 'preferred_variant_text_rows': 6})
        flow.intake.run('generate', self.snapshot, self.input, 1)
        flow.initialize(self.root, self.snapshot)
        self.batch = self.root / 'work/novels/first'
        flow.prepare(self.root, self.batch, [self.names[0]])

    def save(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(storage.encode(value))

    def draft(self, batch=None, indices=(0, 1, 2), holds=()):
        path = (batch or self.batch) / 'draft.json'
        doc = storage.read_json(path)
        for i in indices:
            row = doc['rows'][i]
            row.update(ko='' if i in holds else ('앞으로' if row['kind'] == 'selection' else '<ruby=はな>꽃</ruby><interval=0.4>\r\n꽃입니다.'),
                       hold=i in holds, reason='검수 보류 표본' if i in holds else '', translation_status='drafted')
        self.save(path, doc)
        return doc

    def review(self, batch=None, round_name='001', review_id='review-1', approve=None):
        batch = batch or self.batch
        flow.prepare_review(self.root, batch, round_name)
        path = batch / 'reviews' / round_name / 'review.json'
        doc = storage.read_json(path)
        doc.update(review_id=review_id, pro_review_complete=True, knowledge_review='신규 후보 없음')
        for i, row in enumerate(doc['rows']):
            if approve is None or i in approve:
                row['review_status'] = 'approved'
        self.save(path, doc)
        return path

    def test_partial_resume_and_hold_isolation(self):
        original = {p.name: p.read_bytes() for p in (self.input / 'scenarios').glob('*.json')}
        self.draft(indices=(0, 1), holds=(1,))
        flow.checkpoint(self.root, self.batch)
        path = self.review()
        # An unrelated draft row may advance without invalidating already reviewed rows.
        self.draft(indices=(2,))
        result = flow.apply_review(self.root, self.batch, path)
        self.assertEqual((result['rows'], result['hold_rows']), (2, 1))
        queue = flow.queue(self.root)
        self.assertEqual((queue['pending_rows'], queue['hold_rows'], queue['reviewed_rows']), (4, 1, 1))
        self.assertEqual(flow.apply_review(self.root, self.batch, path)['status'], 'ALREADY_APPLIED')
        path2 = self.review(round_name='002', review_id='review-2')
        self.assertEqual(len(storage.read_json(path2)['rows']), 1)
        flow.apply_review(self.root, self.batch, path2)
        entry = flow.catalog(self.root)['scenarios'][0]
        output = storage.read_json(self.root / 'translations/ko/novels' / Path(entry['file']).name)
        self.assertEqual(len(output['rows']), 3)
        self.assertEqual(output['rows'][0]['jp'], output['rows'][1]['jp'])
        self.assertNotEqual(output['rows'][0]['row_id'], output['rows'][1]['row_id'])
        self.assertIsNone(output['rows'][1]['ko'])
        self.assertTrue(output['rows'][1]['hold_placeholder'].endswith('2행 HOLD]'))
        self.assertEqual(output['rows'][0]['page_ctrl'], 'Next\t')
        self.assertEqual(output['rows'][2]['grid_index'], 1)
        self.assertEqual(original, {p.name: p.read_bytes() for p in (self.input / 'scenarios').glob('*.json')})
        other = self.root / 'work/novels/other'
        flow.prepare(self.root, other, [self.names[1]])
        self.draft(other)
        flow.apply_review(self.root, other, self.review(other, review_id='other-review'))
        self.assertEqual(flow.queue(self.root)['pending_rows'], 0)

    def test_retry_hold_only_and_clear_ledger(self):
        self.draft(holds=(1,))
        flow.apply_review(self.root, self.batch, self.review())
        retry = self.root / 'work/novels/retry'
        flow.prepare(self.root, retry, [self.names[0]], retry_holds=True)
        self.assertEqual(len(storage.read_json(retry / 'draft.json')['rows']), 1)
        self.draft(retry, indices=(0,))
        flow.apply_review(self.root, retry, self.review(retry, review_id='resolved'))
        self.assertEqual((self.root / 'translation/holds.jsonl').read_bytes(), b'')

    def test_partial_pro_review_does_not_mark_unreviewed_rows_complete(self):
        self.draft()
        path = self.review(approve=(0,))
        result = flow.apply_review(self.root, self.batch, path)
        self.assertEqual((result['rows'], result['pending_review_rows']), (1, 2))
        flow.prepare_review(self.root, self.batch, '002')
        self.assertEqual(len(storage.read_json(self.batch / 'reviews/002/review.json')['rows']), 2)

    def test_rerun_preserves_draft_review_and_input_edits(self):
        self.draft(indices=(0,))
        path = self.review()
        before = (self.batch / 'draft.json').read_bytes(), path.read_bytes()
        flow.initialize(self.root, self.snapshot)
        flow.prepare(self.root, self.batch, [self.names[0]])
        flow.prepare_review(self.root, self.batch, '001')
        self.assertEqual(before, ((self.batch / 'draft.json').read_bytes(), path.read_bytes()))

    def test_bad_tag_is_technical_error_other_rows_continue(self):
        doc = self.draft()
        doc['rows'][0]['ko'] = '태그가 빠짐'
        self.save(self.batch / 'draft.json', doc)
        ready = flow.prepare_review(self.root, self.batch, '001')
        self.assertEqual((ready['rows'], len(ready['errors'])), (2, 1))
        self.assertEqual(flow.checkpoint(self.root, self.batch)['translation']['error'], 1)
        self.assertEqual(flow.queue(self.root)['hold_rows'], 0)

    def test_source_and_draft_tampering_rejected(self):
        self.draft()
        path = self.review()
        doc = storage.read_json(path)
        doc['rows'][0]['speaker'] = 'other'
        self.save(path, doc)
        with self.assertRaisesRegex(ValueError, 'Source/identity'):
            flow.apply_review(self.root, self.batch, path)
        doc['rows'][0]['speaker'] = '案内人'
        self.save(path, doc)
        draft = storage.read_json(self.batch / 'draft.json')
        draft['rows'][0]['ko'] += '변경'
        self.save(self.batch / 'draft.json', draft)
        with self.assertRaisesRegex(ValueError, 'draft row changed'):
            flow.apply_review(self.root, self.batch, path)

    def test_stale_parallel_batch_cannot_overwrite(self):
        other = self.root / 'work/novels/parallel'
        flow.prepare(self.root, other, [self.names[0]])
        self.draft()
        self.draft(other)
        a, b = self.review(), self.review(other, review_id='parallel-review')
        flow.apply_review(self.root, self.batch, a)
        with self.assertRaisesRegex(ValueError, 'Applied row changed'):
            flow.apply_review(self.root, other, b)

    def test_review_completion_required_and_output_tamper_detected(self):
        self.draft()
        path = self.review()
        review = storage.read_json(path)
        review['pro_review_complete'] = False
        self.save(path, review)
        with self.assertRaisesRegex(ValueError, 'Actual PRO'):
            flow.apply_review(self.root, self.batch, path)
        review['pro_review_complete'] = True
        self.save(path, review)
        flow.apply_review(self.root, self.batch, path)
        self.assertEqual(flow.verify_all(self.root)['reviewed_rows'], 3)
        entry = flow.catalog(self.root)['scenarios'][0]
        output = self.root / 'translations/ko/novels' / Path(entry['file']).name
        payload = storage.read_json(output)
        payload['rows'][0]['ko'] += '임의 편집'
        self.save(output, payload)
        with self.assertRaisesRegex(ValueError, 'Local output changed'):
            flow.verify_all(self.root)

    def test_reviewed_knowledge_update_retirement_and_preimage(self):
        record = self.record()
        new = copy.deepcopy(record)
        new['value']['ko'] = '꽃 이름'
        new['origin']['review_id'] = 'update'
        change = {'kind': 'knowledge', 'id': record['id'], 'old_sha256': knowledge.record_sha256(record),
                  'approved': True, 'value': new}
        updated, _ = knowledge.apply_reviewed_changes([record], {}, [change], review_id='update')
        self.assertEqual(updated, [new])
        with self.assertRaisesRegex(ValueError, 'preimage'):
            knowledge.apply_reviewed_changes(updated, {}, [change], review_id='update')
        retire = {'kind': 'knowledge', 'id': record['id'], 'operation': 'retire', 'approved': True,
                  'old_sha256': knowledge.record_sha256(new), 'reason': '더 정확한 관찰로 교체'}
        self.assertEqual(knowledge.apply_reviewed_changes(updated, {}, [retire], review_id='retire')[0], [])

    def record(self, review_id='review-1'):
        return {'id': 'term:flower', 'kind': 'term', 'status': 'approved', 'content_available': True,
                'scope': {'source_ids': [self.names[0]]}, 'source_ids': [self.names[0]],
                'value': {'source_text': '花', 'ko': '꽃'},
                'origin': {'review_id': review_id, 'source': self.names[0]}}

    def test_current_knowledge_approval_scope_history_and_names(self):
        self.draft()
        path = self.review()
        review = storage.read_json(path)
        record = self.record()
        review['changes'] = [{'kind': 'knowledge', 'id': record['id'], 'old_sha256': None, 'approved': True, 'value': record},
            {'kind': 'name', 'jp': '案内人', 'old_ko': None, 'ko': '안내인', 'approved': True},
            {'kind': 'name', 'jp': '未確定', 'old_ko': None, 'ko': '미확정', 'approved': False}]
        self.save(path, review)
        flow.apply_review(self.root, self.batch, path)
        records = knowledge.load_current(self.root)
        self.assertEqual(records, [record])
        self.assertNotIn('未確定', storage.read_json(self.root / 'translations/ko/names.json'))
        same = knowledge.project(records, source_ids=[self.names[0]], jp_texts=['花'], max_chars=1)
        self.assertEqual(same['required_term_ids'], ['term:flower'])
        self.assertTrue(same['budget_exceeded'])
        different = knowledge.project(records, source_ids=[self.names[1]], jp_texts=['花'])
        self.assertEqual(different['effective_authority']['term:flower'], 'reference')
        self.assertEqual(len(list((self.root / 'knowledge-layer/provenance/current-changes').glob('*.json'))), 1)

    def test_new_applicable_term_invalidates_context(self):
        self.draft()
        path = self.review()
        (self.root / 'translation/knowledge.jsonl').write_bytes(knowledge.dump_knowledge([self.record('separate-review')]))
        with self.assertRaisesRegex(ValueError, 'New applicable terms'):
            flow.apply_review(self.root, self.batch, path)

    def test_frozen_policy_and_actual_input_mutation_rejected(self):
        canonical = (self.root / 'HOLD_POLICY.md').read_bytes()
        (self.root / 'HOLD_POLICY.md').write_bytes(canonical + b'\n')
        with self.assertRaisesRegex(ValueError, 'Frozen'):
            flow.checkpoint(self.root, self.batch)
        (self.root / 'HOLD_POLICY.md').write_bytes(canonical)
        item = flow.catalog(self.root)['scenarios'][0]
        path = self.input / item['file']
        doc = storage.read_json(path)
        doc['rows'][0]['jp'] += ' '
        self.save(path, doc)
        with self.assertRaisesRegex(ValueError, 'Source fields changed'):
            flow.checkpoint(self.root, self.batch)

    def test_control_tokens_and_names_do_not_use_selection_arg1(self):
        context = storage.read_json(self.batch / 'context.json')
        self.assertEqual(set(context['names']), {'案内人'})
        self.assertEqual(flow.structure('<color="a>b">x</color>\r\n{0}\\n%s'),
                         ['<color="a>b">', '</color>', '\r\n', '{0}', '\\n', '%s'])
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            flow.structure('<color="oops>')
        bad = self.record()
        bad['source_ids'] = ['bad\0id']
        with self.assertRaises(ValueError):
            knowledge.dump_knowledge([bad])
        bad = self.record()
        bad['status'] = 'reviewing'
        with self.assertRaises(ValueError):
            knowledge.validate_current([bad])

    def test_crash_recovery_finishes_entire_apply_once(self):
        self.draft(holds=(1,))
        path = self.review()
        real_write = storage.atomic_write
        writes = []
        def fail_after_first_target(target, raw):
            writes.append(target)
            if len(writes) == 3:
                raise OSError('simulated power loss')
            real_write(target, raw)
        with patch.object(storage, 'atomic_write', side_effect=fail_after_first_target):
            with self.assertRaisesRegex(OSError, 'power loss'):
                flow.apply_review(self.root, self.batch, path)
        self.assertTrue(list((self.root / 'translation/state/transactions').glob('*.json')))
        with storage.workspace_lock(self.root):
            self.assertEqual(flow.apply_review(self.root, self.batch, path)['status'], 'ALREADY_APPLIED')
        self.assertFalse(list((self.root / 'translation/state/transactions').glob('*.json')))
        self.assertEqual((flow.queue(self.root)['reviewed_rows'], flow.queue(self.root)['hold_rows']), (2, 1))

    def test_recovery_preserves_external_edit_and_rejects_policy_output(self):
        real_write = storage.atomic_write
        def stop_targets(target, raw):
            if target.parent.name != 'transactions':
                raise OSError('stopped')
            real_write(target, raw)
        with patch.object(storage, 'atomic_write', side_effect=stop_targets):
            with self.assertRaises(OSError):
                storage.publish(self.root, {'translations/ko/names.json': storage.encode({'a': 'b'})})
        self.save(self.root / 'translations/ko/names.json', {'someone': 'else'})
        with self.assertRaisesRegex(ValueError, 'external edit'):
            storage.recover(self.root)
        self.assertEqual(storage.read_json(self.root / 'translations/ko/names.json'), {'someone': 'else'})
        with self.assertRaises(ValueError):
            storage.owned(self.root, 'HOLD_POLICY.md')


if __name__ == '__main__':
    unittest.main()
