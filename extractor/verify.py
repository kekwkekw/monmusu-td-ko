"""Verify coverage and prepare source/variant catalogs after classification."""
import argparse
import concurrent.futures as futures
import json
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from core import dump, json_line, load_tree, sha256
from run import OUTPUT, records


def checked_records(manifest, sizes, workers):
    def check(rec):
        missing = []
        path = Path(rec['output_path'])
        if not (path / 'record.json').is_file() or not rec.get('reason'):
            missing.append(str(path))
        required = []
        if rec['kind'] == 'unity':
            required.append('object.bin' if rec.get('status') == 'unreadable' else 'tree.json.gz')
        elif rec.get('type') != 'BundleResource':
            suffix = Path(rec['source_path']).suffix
            source = path / ('source' + suffix if suffix else 'source.bin')
            if not source.is_file() or source.stat().st_size != sizes[rec['source_sha256']]:
                missing.append(str(source))
        if rec.get('payload_sha256'):
            required.append('payload.bin')
        if rec['kind'] == 'il2cpp_literals':
            required.append('literals.jsonl.gz')
        for filename in required:
            if not (path / filename).is_file():
                missing.append(str(path / filename))
        for binary in rec.get('binary_fields', []):
            file = path / binary['$binary']
            if not file.is_file() or file.stat().st_size != binary['bytes']:
                missing.append(str(file))
        return rec, missing
    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(check, records(manifest), buffersize=workers * 8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--workers', type=int, default=16)
    args = parser.parse_args()
    out = args.output
    inputs = list(records(out / 'inputs.jsonl'))
    by_sha = defaultdict(list)
    for item in inputs:
        by_sha[item['sha256']].append(item)
    extraction = json.loads((out / 'extraction-summary.json').read_text())
    classification = json.loads((out / 'classification-summary.json').read_text())
    counts, kind_counts = Counter(), Counter()
    ids = set()
    missing = []
    failures = []
    books = defaultdict(list)
    master_refs = defaultdict(set)
    provenance = out / 'indexes' / 'provenance.jsonl'
    with provenance.open('w', encoding='utf-8') as f:
        for digest, sources in by_sha.items():
            f.write(json_line({'sha256': digest, 'sources': sources}))
    last = time.monotonic()
    sizes = {digest: sources[0]['size'] for digest, sources in by_sha.items()}
    for index, (rec, record_missing) in enumerate(checked_records(out / 'classification.jsonl', sizes, args.workers), 1):
        if rec['id'] in ids:
            raise ValueError(f'Duplicate output identity: {rec["id"]}')
        ids.add(rec['id'])
        path = Path(rec['output_path'])
        missing.extend(record_missing)
        counts[rec['category']] += 1
        kind_counts[rec['kind']] += 1
        if rec.get('status') == 'unreadable':
            failures.append(rec)
        if rec['category'] == 'kept/scenario_books':
            tree = load_tree(path)
            name = tree.get('m_Name', '')
            scenario = name[:-5] if name.endswith('.book') else name
            grids = tree['importGridList']
            content_hash = sha256(json.dumps(grids, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode())
            labels = sorted({s['label'] for s in by_sha[rec['source_sha256']]})
            rows = sum(1 for _ in records(path / 'rows.jsonl'))
            books[scenario].append({'source_id': rec['id'], 'name': name, 'grid_sha256': content_hash,
                                    'rows': rows, 'sources': labels, 'output_path': str(path)})
        if rec['category'] == 'kept/masterdata':
            tree = load_tree(path) if (path / 'tree.json.gz').exists() else None
            def find(value):
                if isinstance(value, dict):
                    for k, child in value.items():
                        if k == 'scenario_name' and isinstance(child, str) and child:
                            yield child
                        else:
                            yield from find(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from find(child)
            labels = {s['label'] for s in by_sha[rec['source_sha256']]}
            for scenario in find(tree):
                master_refs[scenario].update(labels)
        if time.monotonic() - last > 20:
            print(json.dumps({'stage': 'verify', 'records': index, 'missing': len(missing)}), flush=True)
            last = time.monotonic()
    ranks = {'current_remote': 100, 'game': 90, 'datatable': 80, 'legacy_bundles': 50, 'archived_player': 40}
    for category in counts:
        if not (out / category / 'REASONS.json').is_file():
            missing.append(str(out / category / 'REASONS.json'))
    variant_rows = []
    preferred_rows = 0
    for scenario, variants in sorted(books.items()):
        variants.sort(key=lambda v: (v['rows'] > 0, max((ranks.get(s, 0) for s in v['sources']), default=0), v['source_id']), reverse=True)
        preferred_rows += variants[0]['rows']
        variant_rows.append({'scenario_name': scenario, 'distinct_grid_versions': len({v['grid_sha256'] for v in variants}),
                             'preferred_source_id': variants[0]['source_id'], 'variants': variants})
    with (out / 'indexes' / 'scenario-variants.jsonl').open('w', encoding='utf-8') as f:
        for v in variant_rows:
            f.write(json_line(v))
    coverage = []
    def alias_key(name):
        value = unicodedata.normalize('NFKC', name).strip()
        if value.lower().endswith('.book'):
            value = value[:-5].strip()
        return value.casefold()
    aliases = defaultdict(list)
    for name, variants in books.items():
        if any(v['rows'] for v in variants):
            aliases[alias_key(name)].append(name)
    for name, labels in sorted(master_refs.items()):
        exact = books.get(name, [])
        coverage.append({'scenario_name': name, 'master_sources': sorted(labels), 'books': len(exact),
                         'has_text_rows': any(v['rows'] for v in exact),
                         'current_remote_book': any('current_remote' in v['sources'] for v in exact),
                         'current_remote_has_text': any('current_remote' in v['sources'] and v['rows'] for v in exact),
                         'name_alias_candidates_not_merged': [v for v in aliases.get(alias_key(name), []) if v != name],
                         'variant_source_ids': [v['source_id'] for v in exact]})
    with (out / 'indexes' / 'master-scenario-coverage.jsonl').open('w', encoding='utf-8') as f:
        for v in coverage:
            f.write(json_line(v))
    dump(out / 'unreadable.json', failures)
    current_master = [v for v in coverage if 'current_remote' in v['master_sources']]
    result = {'input_provenance_rows': len(inputs), 'unique_input_files': len(by_sha), 'output_records': len(ids),
              'record_categories': dict(counts), 'record_kinds': dict(kind_counts), 'missing_output_paths': missing,
              'unreadable_records': len(failures), 'scenario_names_including_config': len(books),
              'scenario_names_with_text_rows': sum(any(v['rows'] for v in variants) for variants in books.values()),
              'names_with_multiple_grid_versions': sum(v['distinct_grid_versions'] > 1 for v in variant_rows),
              'preferred_variant_text_rows': preferred_rows, 'all_master_scenario_names': len(coverage),
              'all_master_missing_text': sum(not v['has_text_rows'] for v in coverage),
              'current_master_scenario_names': len(current_master),
              'current_master_missing_text': sum(not v['has_text_rows'] for v in current_master),
              'current_master_missing_text_without_name_alias': sum(not v['has_text_rows'] and not v['name_alias_candidates_not_merged'] for v in current_master),
              'current_master_missing_current_remote_text': sum(not v['current_remote_has_text'] for v in current_master),
              'current_master_missing_current_remote_book': sum(not v['current_remote_book'] for v in current_master)}
    result['passed'] = (not missing and len(ids) == classification['records'] == extraction['records']
                        and len(by_sha) == extraction['total_files'] and not extraction['fatal_files'])
    dump(out / 'verification.json', result)
    print(json.dumps(result, ensure_ascii=True), flush=True)
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
