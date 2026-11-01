"""Build complete current Master/UI authoring inputs from the verified extraction.

Only text/provenance is published. No game, Git, network or translation API writes.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
JP = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
RANK = {'current_remote': 0, 'game_root_bundle': 1, 'game': 2, 'datatable': 3,
        'db_site': 4, 'legacy_masterdata': 5, 'legacy_bundles': 6, 'archived_player': 7}
TEXT_FIELDS = {'m_text', 'text', 'label', 'message', 'title', 'caption'}


def rows(path):
    with path.open(encoding='utf-8-sig') as stream:
        for line in stream:
            yield json.loads(line)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def strings(value, pointer=''):
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, pointer + '/' + key.replace('~', '~0').replace('/', '~1'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, pointer + '/' + str(index))


def field_path(pointer):
    """Serialized field path; [] means every array item, never an ID substitution."""
    parts = pointer.strip('/').split('/')
    result = []
    for part in parts:
        if part.isdigit() and result:
            result[-1] += '[]'
        else:
            result.append(part.replace('~1', '/').replace('~0', '~'))
    return '.'.join(result)


def intake(snapshot, destination):
    snapshot, destination = snapshot.resolve(), destination.resolve()
    if not json.loads((snapshot / 'verification.json').read_text(encoding='utf-8-sig'))['passed']:
        raise ValueError('Extraction snapshot is not verified')
    ranks, labels = {}, defaultdict(set)
    for entry in rows(snapshot / 'inputs.jsonl'):
        sha, label = entry['sha256'], entry['label']
        ranks[sha] = min(ranks.get(sha, 99), RANK.get(label, 99))
        labels[sha].add(label)
    masters, ui_records = defaultdict(list), {}
    category_counts = Counter()
    print('Indexing preserved records...', flush=True)
    for rec in rows(snapshot / 'classification.jsonl'):
        category = rec['category']
        if category not in {'kept/masterdata', 'kept/ui_candidates'}:
            continue
        category_counts[category] += 1
        if category == 'kept/masterdata' and rec.get('name') and rec.get('type') == 'MonoBehaviour':
            masters[rec['name']].append(rec)
        elif category == 'kept/ui_candidates' and ranks.get(rec['source_sha256'], 99) <= 2:
            ui_records[rec['id']] = {
                'source_id': rec['id'], 'source_sha256': rec['source_sha256'],
                'class': '.'.join(filter(None, (rec.get('script_namespace'), rec.get('script_class')))),
                'asset_name': rec.get('name', ''), 'containers': rec.get('containers', []),
                'kind': rec.get('kind'), 'labels': sorted(labels[rec['source_sha256']]),
            }
    print(f'Indexed {sum(map(len, masters.values()))} master records and {len(ui_records)} current UI records', flush=True)
    master, master_bindings, master_sources = {}, [], []
    master_fields, occurrences = 0, 0
    for name, variants in sorted(masters.items()):
        preferred = sorted(variants, key=lambda r: (ranks.get(r['source_sha256'], 99), r['id']))[0]
        # Current acquired assets are authoritative. Preserve historical-only tables
        # in the source index without pretending they are current runtime tables.
        current = ranks.get(preferred['source_sha256'], 99) <= 2
        source = {'table': name, 'preferred_source_id': preferred['id'], 'current': current,
                  'class': '.'.join(filter(None, (preferred.get('script_namespace'), preferred.get('script_class')))),
                  'variants': [{'source_id': r['id'], 'labels': sorted(labels[r['source_sha256']])} for r in variants]}
        master_sources.append(source)
        if not current:
            continue
        folder = Path(preferred['output_path'])
        if not folder.resolve().is_relative_to(snapshot):
            # Portable snapshots preserve the historical absolute root in their index.
            folder = snapshot / 'kept/masterdata' / preferred['source_sha256'][:2] / preferred['source_sha256'] / preferred['folder']
        with gzip.open(folder / 'tree.json.gz', 'rt', encoding='utf-8') as stream:
            tree = json.load(stream)
        fields = defaultdict(dict)
        values = list(strings(tree))
        human_fields = {field_path(p) for p, text in values if JP.search(text) and
                        not p.startswith(('/m_Name', '/m_Script', '/m_GameObject'))}
        for pointer, text in values:
            if not text or field_path(pointer) not in human_fields:
                continue
            path = field_path(pointer)
            fields[path][text] = ''
            occurrences += 1
            master_bindings.append({'table': name, 'field': path, 'jp': text,
                                    'source_id': preferred['id'], 'pointer': pointer})
        if fields:
            master[name] = dict(fields)
            master_fields += len(fields)
    print(f'Master: {len(master)} text tables, {master_fields} fields, {occurrences} occurrences', flush=True)
    resources, bindings, other_candidates, candidates = {}, [], [], Counter()
    print('Reading all preserved string locations...', flush=True)
    with gzip.open(snapshot / 'indexes/all-strings.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            source = ui_records.get(row['source_id'])
            if source is None or not row['text']:
                continue
            pointer = row['pointer']
            literal = source['kind'] == 'il2cpp_literals'
            if literal and not JP.search(row['text']):
                continue
            # Unknown serialized strings remain in the verified snapshot; they are
            # counted separately instead of being mislabeled as displayed UI text.
            if not literal and pointer.rsplit('/', 1)[-1].lower() not in TEXT_FIELDS:
                if JP.search(row['text']):
                    candidates['other_serialized_japanese_fields'] += 1
                    other_candidates.append({'source_id': source['source_id'], 'pointer': pointer,
                                             'jp': row['text'], 'class': source['class'],
                                             'asset_name': source['asset_name'],
                                             'reason': 'Not a Text field or code literal; display role requires review'})
                continue
            text = row['text']
            resource_id = 'ui.' + hashlib.sha256(text.encode()).hexdigest()[:24]
            kind = 'code_literal' if literal else 'literal'
            if resource_id not in resources:
                resources[resource_id] = {'id': resource_id, 'jp': text, 'ko': '', 'kind': kind,
                                          'disposition': 'pending', 'role': 'unreviewed_ui_candidate'}
            elif not literal:
                resources[resource_id]['kind'] = 'literal'
            bindings.append({'resource_id': resource_id, 'source_id': source['source_id'],
                             'pointer': pointer, 'class': source['class'], 'asset_name': source['asset_name'],
                             'containers': source['containers'], 'source_kind': kind})
            candidates[kind] += 1
    destination.mkdir(parents=True, exist_ok=True)
    # Rebuilding intake must never replace translations or authoring decisions.
    dump(destination / 'master.json', master)
    dump(destination / 'ui.json', {item['jp']: '' for item in resources.values()})
    dump(destination / 'ui/resources.json', {'schema_version': 1, 'locale': 'ja',
                                           'resources': sorted(resources.values(), key=lambda r: r['id'])})
    dump(destination / 'master-sources.json', {'schema_version': 1, 'tables': master_sources})
    for filename, values in [('master-bindings.jsonl', master_bindings), ('ui/bindings.jsonl', bindings),
                             ('ui/other-serialized-candidates.jsonl', other_candidates)]:
        path = destination / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as stream:
            for row in values:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
    report = {'schema': 'monmusu-ui-intake-v1', 'snapshot': '2026-10-28',
              'asset_version': 'b5aff4d749', 'source_categories': dict(category_counts),
              'master_tables': len(master), 'master_fields': master_fields,
              'master_pairs': sum(len(pairs) for fields in master.values() for pairs in fields.values()),
              'master_occurrences': occurrences, 'master_table_variants': len(master_sources),
              'ui_unique_strings': len(resources), 'ui_occurrences': len(bindings), 'ui_candidates': dict(candidates),
              'translated': 0, 'policy': 'Pending is not HOLD. Original snapshot including non-display strings remains preserved.',
              'images': 'Image pixels are not text entries; OCR/translation not performed.'}
    dump(destination / 'intake-report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'extractor/output')
    parser.add_argument('--out', type=Path, default=ROOT / 'translation/ui/source')
    args = parser.parse_args()
    print(json.dumps(intake(args.snapshot, args.out), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
