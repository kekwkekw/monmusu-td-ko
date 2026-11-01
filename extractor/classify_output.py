"""Parallel post-extraction classification; never used to prefilter input assets."""
import argparse
import concurrent.futures as futures
import gzip
import json
import shutil
import time
from collections import Counter
from pathlib import Path

from core import CATEGORY_DESCRIPTIONS, ENGINE_TYPES, RENDERING_TYPES, book_rows, classify, decode_text, dump, iter_strings, json_line, load_tree
from run import CONFIG, OUTPUT, event, initialize_worker, records, unique_inputs

OUT = None
RECLASSIFY = False


def initialize(out, reclassify=False):
    global OUT, RECLASSIFY
    OUT = Path(out).resolve()
    RECLASSIFY = reclassify


def classify_source(item):
    source = OUT / 'raw' / item['sha256'][:2] / item['sha256']
    complete = source / 'classification-complete.json'
    if complete.exists() and not RECLASSIFY:
        return json.loads(complete.read_text())
    counts, reasons = Counter(), Counter()
    rows_count = strings_count = 0
    source_records = list(records(source / 'records.jsonl'))
    script_types = {}
    resuming = (source / 'classification-records.jsonl').exists()
    previous_locations = {}
    if resuming:
        lines = (source / 'classification-records.jsonl').read_text(encoding='utf-8').splitlines()
        for index, line in enumerate(lines):
            try:
                previous = json.loads(line)
            except ValueError:
                if index == len(lines) - 1 and not complete.exists():
                    break
                raise
            previous_locations[previous['id']] = Path(previous['output_path'])
    created_parents = set()
    def locate(rec):
        original = source / rec['folder']
        if resuming and not original.exists():
            if rec['id'] in previous_locations:
                return previous_locations[rec['id']]
            matches = [OUT / category / item['sha256'][:2] / item['sha256'] / rec['folder'] / 'record.json'
                       for category in CATEGORY_DESCRIPTIONS]
            matches = [p for p in matches if p.is_file()]
            if len(matches) != 1:
                raise ValueError(f'Cannot locate extracted record {rec["id"]}')
            original = matches[0].parent
        return original
    for rec in source_records:
        if rec.get('type') == 'MonoScript' and rec.get('status') == 'ok':
            script = load_tree(locate(rec))
            script_types[(rec['serialized_file'], rec['path_id'])] = script
    with (source / 'classification-records.jsonl').open('w', encoding='utf-8') as manifest, \
         (source / 'catalog.jsonl').open('w', encoding='utf-8') as catalog, \
         gzip.open(source / 'strings.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1) as strings:
        for rec in source_records:
            original = locate(rec)
            known_metadata = rec.get('type') in ENGINE_TYPES | RENDERING_TYPES
            tree = load_tree(original) if not known_metadata and (original / 'tree.json.gz').exists() else None
            if rec.get('type') == 'MonoBehaviour' and isinstance(tree, dict):
                pointer = tree.get('m_Script', {})
                script = script_types.get((rec['serialized_file'], pointer.get('m_PathID'))) if isinstance(pointer, dict) and pointer.get('m_FileID') == 0 else None
                if script:
                    rec['script_namespace'] = script.get('m_Namespace', '')
                    rec['script_class'] = script.get('m_ClassName', '')
            text = (original / 'text.txt').read_text(encoding='utf-8', errors='surrogatepass') if (original / 'text.txt').exists() else None
            if rec.get('type') == 'TextAsset' and (original / 'payload.bin').exists():
                with (original / 'payload.bin').open('rb') as f:
                    prefix = f.read(3)
                if prefix.startswith((b'\xff\xfe', b'\xfe\xff', b'\xef\xbb\xbf')):
                    text, encoding = decode_text((original / 'payload.bin').read_bytes())
                    if text is not None:
                        (original / 'text.txt').write_text(text, encoding='utf-8')
                        rec['payload_encoding'] = encoding
            category, reason = classify(rec, tree, text)
            target = OUT / category / item['sha256'][:2] / item['sha256'] / rec['folder']
            original_absolute, target_absolute = original.resolve(), target.resolve()
            if original_absolute != target_absolute:
                if not original_absolute.is_relative_to(OUT) or not target_absolute.is_relative_to(OUT):
                    raise ValueError('Classification path escaped output directory')
                if target.parent not in created_parents:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    created_parents.add(target.parent)
                shutil.move(str(original), str(target))
            manifest.write(json_line({**rec, 'category': category, 'reason': reason, 'output_path': str(target)}))
            counts[category] += 1
            reasons[reason] += 1
            if category == 'kept/scenario_books':
                rows = list(book_rows(tree, rec['id']))
                dump(target / 'book.json', tree)
                with (target / 'rows.jsonl').open('w', encoding='utf-8') as f:
                    f.writelines(json_line(row) for row in rows)
                catalog.write(json_line({'source_id': rec['id'], 'scenario_name': tree.get('m_Name', ''),
                                         'rows': len(rows), 'grids': len(tree['importGridList']),
                                         'source_sha256': item['sha256'], 'output_path': str(target)}))
                rows_count += len(rows)
            if rec.get('kind') == 'il2cpp_literals':
                with gzip.open(target / 'literals.jsonl.gz', 'rt', encoding='utf-8') as f:
                    for line in f:
                        literal = json.loads(line)
                        strings.write(json_line({'source_id': rec['id'], 'category': category,
                                                  'pointer': '/literals/' + str(literal['index']), 'text': literal['text']}))
                        strings_count += 1
            elif category.startswith('kept/'):
                values = iter_strings(tree) if tree is not None else [('/text', text)] if text is not None else []
                for pointer, value in values:
                    if value:
                        strings.write(json_line({'source_id': rec['id'], 'category': category, 'pointer': pointer, 'text': value}))
                        strings_count += 1
                if tree is not None and text is not None:
                    strings.write(json_line({'source_id': rec['id'], 'category': category, 'pointer': '/decoded_payload', 'text': text}))
                    strings_count += 1
    result = {'sha256': item['sha256'], 'records': sum(counts.values()), 'categories': dict(counts),
              'reasons': dict(reasons), 'scenario_rows': rows_count, 'strings': strings_count}
    dump(complete, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--reclassify', action='store_true', help='Apply classification again to already classified artifacts')
    args = parser.parse_args()
    out = args.output.resolve()
    extraction = json.loads((out / 'extraction-summary.json').read_text())
    if extraction['fatal_files']:
        raise RuntimeError('Extraction failures must be resolved first')
    items = unique_inputs(out)
    if len(items) != extraction['total_files']:
        raise RuntimeError('New inputs remain unextracted')
    counts, reasons = Counter(), Counter()
    rows_count = strings_count = 0
    start = last = time.monotonic()
    with futures.ProcessPoolExecutor(max_workers=args.workers, initializer=initialize, initargs=(str(out), args.reclassify), max_tasks_per_child=600) as pool:
        def completed():
            iterator = iter(items)
            active = set()
            for _ in range(args.workers * 4):
                item = next(iterator, None)
                if item is not None:
                    active.add(pool.submit(classify_source, item))
            while active:
                finished, active = futures.wait(active, return_when=futures.FIRST_COMPLETED)
                for future in finished:
                    yield future.result()
                    item = next(iterator, None)
                    if item is not None:
                        active.add(pool.submit(classify_source, item))
        for i, result in enumerate(completed(), 1):
            counts.update(result['categories'])
            reasons.update(result['reasons'])
            rows_count += result['scenario_rows']
            strings_count += result['strings']
            if time.monotonic() - last > 20 or i == len(items):
                last = time.monotonic()
                progress = {'stage': 'classify', 'completed_files': i, 'total_files': len(items),
                            'records': sum(counts.values()), 'scenario_rows': rows_count,
                            'elapsed_seconds': round(last - start)}
                dump(out / 'progress.json', progress)
                event(**progress)
    index = out / 'indexes'
    index.mkdir(exist_ok=True)
    for category in CATEGORY_DESCRIPTIONS:
        count = counts[category]
        dump(out / category / 'REASONS.json', {'category': category, 'records': count,
                                             'reason': CATEGORY_DESCRIPTIONS[category],
                                             'per_file_reasons': str(out / 'classification.jsonl'),
                                             'note': 'All artifacts retained. Detailed reason and source for each file are in the global manifest.'})
    def read_indexes(item):
        source = out / 'raw' / item['sha256'][:2] / item['sha256']
        result = json.loads((source / 'classification-complete.json').read_text())
        return ((source / 'classification-records.jsonl').read_bytes(),
                (source / 'catalog.jsonl').read_bytes() if result['categories'].get('kept/scenario_books') else b'',
                (source / 'strings.jsonl.gz').read_bytes() if result['strings'] else b'')
    with (out / 'classification.jsonl').open('wb') as manifest, \
         (index / 'scenario-catalog.jsonl').open('wb') as catalog, \
         (index / 'all-strings.jsonl.gz').open('wb') as strings:
        with futures.ThreadPoolExecutor(max_workers=args.workers * 2) as readers:
            for blocks in readers.map(read_indexes, items, buffersize=args.workers * 4):
                for block, dest in zip(blocks, (manifest, catalog, strings)):
                    dest.write(block)
    result = {'records': sum(counts.values()), 'categories': dict(counts), 'reasons': dict(reasons),
              'scenario_rows_including_variants': rows_count, 'indexed_strings': strings_count,
              'elapsed_seconds': round(time.monotonic() - start)}
    dump(out / 'classification-summary.json', result)
    dump(out / 'progress.json', {'stage': 'classified', **result})
    event('classification_complete', **result)


if __name__ == '__main__':
    main()
