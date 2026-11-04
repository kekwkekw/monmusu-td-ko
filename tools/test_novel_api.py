"""Offline API contract, money, recovery and PRO integration tests. No real HTTP."""
import copy
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch
import zipfile

import novel_api as api
import novel_workflow as flow
import novel_storage as storage
import test_novel_workflow as fixtures


class FakeTransport:
    def __init__(self, mutate=None, fail=None, count=1000):
        self.calls = []
        self.mutate, self.fail, self.count = mutate, fail, count

    def post(self, path, payload, request_id):
        self.calls.append((path, copy.deepcopy(payload)))
        if path.endswith('input_tokens'):
            return {'input_tokens': self.count}
        if self.fail:
            raise self.fail
        prompt = json.loads(payload['input'])
        originals = {r['row_id']: r for r in prompt['source_rows']}
        rows = []
        for rid in prompt['target_row_ids']:
            source = originals[rid]
            ko = '앞으로' if source['kind'] == 'selection' else '<ruby=はな>꽃</ruby><interval=0.4>\r\n꽃입니다.'
            rows.append({'row_id': rid, 'ko': ko, 'hold': False, 'reason': '', 'notes': ''})
        value = {'rows': rows, 'changes_json': '[]'}
        response = {'id': 'resp_fixture', 'model': api.MODEL, 'status': 'completed',
                    'service_tier': 'default', 'reasoning': payload['reasoning'],
                    'usage': {'input_tokens': 1000, 'output_tokens': 200,
                              'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                              'output_tokens_details': {'reasoning_tokens': 150}},
                    'output': []}
        if self.mutate:
            self.mutate(value, response)
        if not response['output']:
            response['output'] = [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps(value, ensure_ascii=False)}]}]
        return response


class APITests(unittest.TestCase):
    setUp = fixtures.WorkflowTests.setUp
    save = fixtures.WorkflowTests.save
    draft = fixtures.WorkflowTests.draft
    review = fixtures.WorkflowTests.review
    record = fixtures.WorkflowTests.record

    def make_plan(self, **kw):
        self.run = self.root / 'work/novels/api-test'
        with patch.object(api, 'OpenAITransport', side_effect=AssertionError('Offline planning must not access network')):
            result = api.plan(self.root, self.run, **({'batch': self.batch} | kw))
        self.sha = result['plan_sha256']
        self.jobs = api.load(self.run)[0]['jobs']
        return result

    def execute(self, transport=None, retry=()):
        # Pricing is deliberately frozen in production; tests remain date-independent.
        with patch.object(api, 'datetime') as clock:
            clock.now.return_value = datetime(2026, 11, 4, tzinfo=timezone.utc)
            return api.execute(self.root, self.run, self.sha, retry, transport or FakeTransport())

    def test_offline_plan_preserves_input_and_draft_and_requires_exact_approval(self):
        before = (self.batch / 'draft.json').read_bytes()
        result = self.make_plan()
        self.assertEqual(result['generation_calls'], 0)
        self.assertEqual(before, (self.batch / 'draft.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'Explicit approval'):
            api.execute(self.root, self.run, 'wrong', transport=FakeTransport())
        with self.assertRaisesRegex(ValueError, 'already exists'):
            api.plan(self.root, self.run, batch=self.batch)

    def test_only_blank_unreviewed_rows_are_selected(self):
        self.draft(indices=(0,))
        flow.prepare_review(self.root, self.batch, '001')
        draft = storage.read_json(self.batch / 'draft.json')
        draft['rows'][1]['notes'] = '작성 중 메모'
        self.save(self.batch / 'draft.json', draft)
        self.make_plan()
        self.assertEqual(self.jobs[0]['row_ids'], [draft['rows'][2]['row_id']])

    def test_comparison_has_identical_input_no_answer_leak_and_new_import_only(self):
        self.draft()
        flow.apply_review(self.root, self.batch, self.review())
        result = self.make_plan(batch=None, scenarios=[self.names[0]], comparison=True, efforts=['high', 'xhigh'])
        self.assertEqual(len(result['jobs']), 2)
        self.assertEqual(self.jobs[0]['prompt'], self.jobs[1]['prompt'])
        self.assertTrue(all('ko' not in r for r in self.jobs[0]['prompt']['source_rows']))
        original = (self.batch / 'draft.json').read_bytes()
        self.execute()
        with self.assertRaisesRegex(ValueError, 'NEW batch'):
            api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)
        out = self.root / 'work/novels/comparison'
        api.import_job(self.root, self.run, self.jobs[0]['id'], out)
        flow.prepare_review(self.root, out, '001')
        self.assertEqual(original, (self.batch / 'draft.json').read_bytes())
        self.assertFalse(storage.read_json(out / 'reviews/001/review.json')['pro_review_complete'])

    def test_success_resume_does_not_recall_and_pro_flow_is_unchanged(self):
        self.make_plan()
        transport = FakeTransport()
        result = self.execute(transport)
        self.assertEqual(result['jobs'][0]['valid_rows'], 3)
        self.execute(transport)
        self.assertEqual(len(transport.calls), 2)
        api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)
        self.assertEqual(api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)['status'], 'ALREADY_IMPORTED')
        review_path = self.review()
        flow.apply_review(self.root, self.batch, review_path)
        self.assertEqual(flow.verify_all(self.root)['reviewed_rows'], 3)

    def test_partial_error_hold_and_retry_only_invalid_row(self):
        self.make_plan()
        def mutate(value, response):
            value['rows'][0]['ko'] = 'missing controls'
            value['rows'][1].update(hold=True, ko='', reason='합성 검수 보류 사례')
        result = self.execute(FakeTransport(mutate=mutate))
        self.assertEqual(result['jobs'][0]['valid_rows'], 2)
        retry = FakeTransport()
        result = self.execute(retry, retry=[self.jobs[0]['id']])
        self.assertEqual(result['jobs'][0]['valid_rows'], 3)
        self.assertEqual(len(json.loads(retry.calls[-1][1]['input'])['target_row_ids']), 1)
        api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)
        review_path = self.review()
        applied = flow.apply_review(self.root, self.batch, review_path)
        self.assertEqual((applied['rows'], applied['hold_rows']), (3, 1))

    def test_budget_call_cap_and_uncertain_requests_keep_reservations(self):
        self.make_plan(efforts=['high', 'xhigh'], budget='0.60', max_calls=2)
        transport = FakeTransport(fail=api.TransportError())
        result = self.execute(transport)
        self.assertEqual(result['generation_calls'], 1)
        self.assertEqual(result['reserved_or_spent_usd'], '0.6')
        self.execute(transport, retry=[self.jobs[0]['id']])
        self.assertEqual(len(transport.calls), 2)

    def test_generation_limit_counts_explicit_retries(self):
        self.make_plan(max_calls=1)
        transport = FakeTransport(fail=api.TransportError(500))
        self.execute(transport)
        self.execute(transport, retry=[self.jobs[0]['id']])
        self.assertEqual(len(transport.calls), 2)

    def test_count_above_cap_does_not_generate(self):
        self.make_plan()
        transport = FakeTransport(count=20001)
        result = self.execute(transport)
        self.assertEqual(result['generation_calls'], 0)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(result['reserved_or_spent_usd'], '0')

    def test_response_crash_recovery_uses_saved_response_without_new_call(self):
        self.make_plan()
        transport = FakeTransport()
        with patch.object(api, 'finish', side_effect=OSError('simulated disk interruption')):
            with self.assertRaises(OSError):
                self.execute(transport)
        self.assertEqual(api.load(self.run)[1]['attempts'][0]['status'], 'running')
        self.execute(transport)
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(api.summary(self.run)['jobs'][0]['valid_rows'], 3)

    def test_crash_before_response_is_unknown_not_automatic_retry(self):
        self.make_plan()
        with patch.object(FakeTransport, 'post', side_effect=[{'input_tokens': 1000}, KeyboardInterrupt()]):
            with self.assertRaises(KeyboardInterrupt):
                self.execute()
        fresh = FakeTransport()
        result = self.execute(fresh)
        self.assertEqual(fresh.calls, [])
        self.assertEqual(result['attempts'][0]['status'], 'unknown')
        self.assertEqual(result['reserved_or_spent_usd'], '0.6')

    def test_cache_and_reasoning_cost_no_double_count(self):
        response = {'usage': {'input_tokens': 1000, 'output_tokens': 500,
            'input_tokens_details': {'cached_tokens': 300, 'cache_write_tokens': 200},
            'output_tokens_details': {'reasoning_tokens': 400}}}
        self.assertEqual(api.usage_cost(response), 500*4000 + 300*400 + 200*5000 + 500*20000)

    def test_refusal_and_incomplete_are_not_row_holds(self):
        self.make_plan(efforts=['high', 'xhigh'])
        def mutate(value, response):
            if response['reasoning']['effort'] == 'high':
                response['output'] = [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'fixture'}]}]
            else:
                response['status'] = 'incomplete'
        result = self.execute(FakeTransport(mutate=mutate))
        self.assertEqual([a['status'] for a in result['attempts']], ['refused', 'incomplete'])
        self.assertEqual(sum(j['valid_rows'] for j in result['jobs']), 0)
        self.assertEqual((self.root / 'translation/holds.jsonl').read_bytes(), b'')

    def test_duplicate_unknown_and_reordered_ids_are_rejected(self):
        self.make_plan()
        job = self.jobs[0]
        for mode in ('duplicate', 'unknown', 'reordered'):
            def mutate(value, response):
                if mode == 'duplicate': value['rows'].append(value['rows'][0])
                if mode == 'unknown': value['rows'][0]['row_id'] = 'unknown'
                if mode == 'reordered': value['rows'].reverse()
            raw = FakeTransport(mutate=mutate).post('/v1/responses', api.request(job), 'test')
            result = api.validate_response(self.root, raw, job, job['row_ids'])
            self.assertEqual(result['rows'], [], mode)

    def test_missing_row_keeps_other_rows_as_partial(self):
        self.make_plan()
        def mutate(value, response): value['rows'].pop(1)
        result = self.execute(FakeTransport(mutate=mutate))
        self.assertEqual(result['jobs'][0]['valid_rows'], 2)
        self.assertEqual(result['attempts'][0]['status'], 'partial')

    def test_draft_or_source_change_blocks_network(self):
        self.make_plan()
        self.draft(indices=(0,))
        transport = FakeTransport()
        with self.assertRaisesRegex(ValueError, 'Draft edited'):
            self.execute(transport)
        self.assertFalse(transport.calls)

    def test_names_knowledge_remain_proposals_until_pro_approval(self):
        self.make_plan()
        change = {'kind': 'name', 'jp': '案内人', 'old_ko': None, 'ko': '안내인', 'approved': False}
        def mutate(value, response): value['changes_json'] = json.dumps([change])
        self.execute(FakeTransport(mutate=mutate))
        api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)
        self.assertEqual(storage.read_json(self.root / 'translations/ko/names.json'), {})
        self.assertEqual(storage.read_json(self.batch / 'draft.json')['changes'], [change])
        review_path = self.review()
        review = storage.read_json(review_path)
        review['changes'][0]['approved'] = True
        self.save(review_path, review)
        flow.apply_review(self.root, self.batch, review_path)
        self.assertEqual(storage.read_json(self.root / 'translations/ko/names.json')['案内人'], '안내인')

    def test_api_approved_proposal_rejected_without_losing_good_rows(self):
        self.make_plan()
        def mutate(value, response):
            value['changes_json'] = json.dumps([{'kind': 'name', 'jp': '案内人', 'ko': '안내인', 'old_ko': None, 'approved': True}])
        result = self.execute(FakeTransport(mutate=mutate))
        self.assertEqual(result['jobs'][0]['valid_rows'], 3)
        self.assertEqual(result['jobs'][0]['proposals'], 0)
        self.assertEqual(result['attempts'][0]['status'], 'partial')

    def test_unverified_usage_stops_further_requests(self):
        self.make_plan(efforts=['high', 'xhigh'])
        def mutate(value, response): response.pop('usage')
        transport = FakeTransport(mutate=mutate)
        self.execute(transport)
        with self.assertRaisesRegex(ValueError, 'Unverified usage'):
            self.execute(transport)
        self.assertEqual(len(transport.calls), 2)

    def test_handoff_contains_bound_source_context_and_unreviewed_pro_file(self):
        self.make_plan()
        self.execute()
        api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)
        flow.prepare_review(self.root, self.batch, '001')
        out = self.batch / 'handoff.zip'
        api.handoff(self.root, self.batch, '001', out)
        with zipfile.ZipFile(out) as z:
            manifest = json.loads(z.read('HANDOFF.json'))
            for name, sha in manifest['files'].items():
                self.assertEqual(storage.digest(z.read(name)), sha)
            self.assertFalse(json.loads(z.read('reviews/001/review.json'))['pro_review_complete'])
            self.assertEqual(z.read('HOLD_POLICY.md'), (self.root / 'HOLD_POLICY.md').read_bytes())
        with self.assertRaisesRegex(ValueError, 'new .zip'):
            api.handoff(self.root, self.batch, '001', out)

    def test_project_key_only_and_transport_has_no_retry(self):
        with patch.dict(api.os.environ, {api.KEY_ENV: 'synthetic-key', 'OPENAI_API_KEY': 'do-not-use'}):
            self.assertEqual(api.credential(), 'synthetic-key')
            with patch.object(api.http.client, 'HTTPSConnection') as conn:
                conn.return_value.getresponse.return_value.status = 429
                conn.return_value.getresponse.return_value.read.return_value = b'ignored'
                with self.assertRaises(api.TransportError):
                    api.OpenAITransport().post('/v1/responses', {}, 'test')
                self.assertEqual(conn.return_value.request.call_count, 1)

    def test_multi_scene_import_preserves_other_jobs_and_provenance(self):
        both = self.root / 'work/novels/both'
        flow.prepare(self.root, both, self.names)
        self.make_plan(batch=both)
        self.execute()
        for job in self.jobs:
            api.import_job(self.root, self.run, job['id'], both)
        provenance = storage.read_json(both / 'api-provenance.json')
        self.assertEqual(len(provenance['imports']), 2)
        self.assertEqual(flow.prepare_review(self.root, both, '001')['rows'], 6)

    def test_import_transaction_recovers_after_interruption(self):
        self.make_plan()
        self.execute()
        actual_write = storage.atomic_write
        calls = []
        def crash(path, raw):
            calls.append(path)
            if len(calls) == 3:
                raise OSError('simulated import crash')
            return actual_write(path, raw)
        with patch.object(storage, 'atomic_write', side_effect=crash):
            with self.assertRaises(OSError):
                api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)
        with storage.workspace_lock(self.root):
            result = api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)
        self.assertEqual(result['status'], 'ALREADY_IMPORTED')
        self.assertEqual(flow.prepare_review(self.root, self.batch, '001')['rows'], 3)

    def test_knowledge_proposal_validation_and_final_pro_binding(self):
        self.make_plan()
        record = self.record('pending-pro-review')
        change = {'kind': 'knowledge', 'id': record['id'], 'old_sha256': None, 'approved': False, 'value': record}
        def mutate(value, response): value['changes_json'] = json.dumps([change])
        self.execute(FakeTransport(mutate=mutate))
        api.import_job(self.root, self.run, self.jobs[0]['id'], self.batch)
        self.assertEqual(flow.knowledge.load_current(self.root), [])
        path = self.review()
        review = storage.read_json(path)
        review['changes'][0]['approved'] = True
        review['changes'][0]['value']['origin']['review_id'] = review['review_id']
        self.save(path, review)
        flow.apply_review(self.root, self.batch, path)
        self.assertEqual(flow.knowledge.load_current(self.root)[0]['id'], record['id'])

    def test_expired_price_and_changed_plan_are_fail_closed(self):
        self.make_plan()
        transport = FakeTransport()
        with patch.object(api, 'datetime') as clock:
            clock.now.return_value = datetime(2026, 11, 22, tzinfo=timezone.utc)
            with self.assertRaisesRegex(ValueError, 'Pricing expired'):
                api.execute(self.root, self.run, self.sha, transport=transport)
        self.assertFalse(transport.calls)
        value = storage.read_json(self.run / 'plan.json')
        value['budget_nano'] += api.NANO
        self.save(self.run / 'plan.json', value)
        with self.assertRaisesRegex(ValueError, 'plan changed'):
            api.load(self.run)


if __name__ == '__main__':
    unittest.main()
