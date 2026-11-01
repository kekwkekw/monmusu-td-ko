"""Apply explicitly reviewed Master/UI pairs; preserve pending/HOLD independently."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from novel_storage import encode, read_json, require, publish, workspace_lock
from novel_workflow import policy, POLICY_SHA256, structure

ROOT = Path(__file__).resolve().parents[1]


def structural(field):
    leaf = field.split('.')[-1].replace('[]', '')
    return leaf.lower() in {'id', 'key', 'code', 'kana', 'scenario_name', 'm_name', 'm_script'} or leaf.lower().endswith(('_id', '_ids', '_rid'))


def numbers(value):
    return re.findall(r'\d+(?:[.,]\d+)*', unicodedata.normalize('NFKC', value))


def identity(row):
    return json.dumps([row['lane'], row.get('table'), row.get('field'), row['jp']], ensure_ascii=False, separators=(',', ':'))


def sources(root):
    source = root / 'translation/ui/source'
    return (read_json(source / 'master.json'), read_json(source / 'ui.json'),
            {r['table']: r for r in read_json(source / 'master-sources.json')['tables']})


def outputs(root, decisions):
    original_master, original_ui, source_tables = sources(root)
    master, ui, bindings = {}, {}, {}
    ids = set()
    counts = Counter()
    for row in decisions:
        key = identity(row)
        require(key not in ids, 'Duplicate Master/UI decision')
        ids.add(key)
        require(row['lane'] in {'master', 'ui'} and row['jp'], 'Invalid lane/source')
        require(row.get('reviewer') and row.get('evidence') and row.get('review_id') and row.get('approved') is True,
                'Explicit review evidence/approval required')
        if row['lane'] == 'ui':
            require(row['jp'] in original_ui, 'UI source is absent; collect it before reviewing')
        else:
            table, field = row['table'], row['field']
            require(row['jp'] in original_master.get(table, {}).get(field, {}), 'Master source is absent')
        disposition = row['disposition']
        require(disposition in {'translate', 'hold', 'keep_source'}, 'Only reviewed decisions are applied')
        counts[disposition] += 1
        if disposition != 'translate':
            require(not row.get('ko'), 'HOLD/keep_source cannot contain a runtime translation')
            if disposition == 'hold':
                require(row.get('reason'), 'HOLD requires a row-specific reason')
            continue
        if row['lane'] == 'master':
            require(not structural(field), 'Identifier/lookup field is source-only: ' + field)
        ko = row['ko']
        require(isinstance(ko, str) and ko.strip() and ko != row['jp'] and '\0' not in ko, 'Invalid Korean translation')
        require(structure(row['jp']) == structure(ko), 'Control tags/placeholders/newlines changed')
        require(numbers(row['jp']) == numbers(ko), 'Numeric content changed')
        if row['lane'] == 'ui':
            ui[row['jp']] = ko
        else:
            master.setdefault(table, {}).setdefault(field, {})[row['jp']] = ko
            bindings[table] = {'class': source_tables[table]['class'],
                               'source_id': source_tables[table]['preferred_source_id']}
    return {'master.json': master, 'ui.json': ui,
            'master-bindings.json': {'schema_version': 1, 'tables': bindings}}, dict(counts)


def current(root):
    path = root / 'translations/ko/ui/decisions.json'
    if not path.exists():
        return {'schema': 'monmusu-ui-decisions-v1', 'policy_sha256': POLICY_SHA256, 'rows': []}
    doc = read_json(path)
    require(doc['schema'] == 'monmusu-ui-decisions-v1' and doc['policy_sha256'] == POLICY_SHA256, 'Invalid decisions/policy')
    return doc


def verify(root):
    policy(root)
    doc = current(root)
    expected, counts = outputs(root, doc['rows'])
    for name, value in expected.items():
        require((root / 'translations/ko' / name).read_bytes() == encode(value), 'Runtime export differs: ' + name)
    return {'status': 'VERIFIED', 'decisions': len(doc['rows']), **counts}


def apply(root, review_path, check=False):
    policy(root)
    review = read_json(review_path)
    require(review['schema'] == 'monmusu-ui-review-v1' and review['policy_sha256'] == POLICY_SHA256, 'Invalid review/policy')
    require(review.get('review_id') and review.get('reviewer'), 'Review identity required')
    with workspace_lock(root):
        doc = current(root)
        existing = {identity(row): row for row in doc['rows']}
        seen = set()
        for entry in review['rows']:
            key = identity(entry)
            require(key not in seen, 'Duplicate review entry')
            seen.add(key)
            if entry['disposition'] == 'pending':
                continue
            row = {k: v for k, v in entry.items() if k != 'previous_sha256'}
            row.update(review_id=review['review_id'], reviewer=review['reviewer'])
            previous = existing.get(key)
            if previous and previous != row:
                require(entry.get('previous_sha256') == hashlib.sha256(encode(previous)).hexdigest(), 'Stale or unreviewed overwrite')
            existing[key] = row
        doc['rows'] = [existing[key] for key in sorted(existing)]
        generated, counts = outputs(root, doc['rows'])
        changes = {'translations/ko/' + name: encode(value) for name, value in generated.items()}
        changes['translations/ko/ui/decisions.json'] = encode(doc)
        changes['translation/state/ui.json'] = encode({'schema': 'monmusu-ui-state-v1', 'last_review': review['review_id'],
                                                       'decisions_sha256': hashlib.sha256(encode(doc)).hexdigest(), **counts})
        if not check:
            publish(root, changes)
        return {'status': 'CHECKED' if check else 'APPLIED_LOCAL', 'decisions': len(doc['rows']), **counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply', 'check', 'verify', 'status'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action in {'apply', 'check'}:
        require(args.review is not None, '--review required')
        result = apply(root, args.review, args.action == 'check')
    else:
        result = verify(root)
        if args.action == 'status':
            report = read_json(root / 'translation/ui/source/intake-report.json')
            result.update(master_source_pairs=report['master_pairs'], ui_source_pairs=report['ui_unique_strings'],
                          pending=report['master_pairs'] + report['ui_unique_strings'] - result['decisions'])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
