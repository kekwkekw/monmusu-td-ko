"""Generate or verify editable Korean Novel inputs from a verified Utage snapshot."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import tempfile

from core import book_rows


HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / 'output'
DESTINATION = HERE.parent / 'translation' / 'novel'
SCHEMA = 'monmusu-novel-input-v1'
TAG = re.compile(r'<[^<>\r\n]+>')
EDITABLE = {'ko': '', 'translation_status': 'untranslated', 'review_status': 'unreviewed', 'review_note': ''}


def read_json(path):
    return json.loads(path.read_bytes())


def write_json(path, value):
    raw = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.write_bytes(raw.encode('utf-8', errors='backslashreplace'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def scenario_file(name):
    # A readable hint plus the exact name hash survives Windows case folding and trailing spaces.
    hint = re.sub(r'[^A-Za-z0-9_-]+', '_', name)[:60] or 'scenario'
    digest = hashlib.sha256(name.encode('utf-8', 'surrogatepass')).hexdigest()
    return f'scenarios/{hint}--{digest[:16]}.json'


def selection(snapshot):
    check = read_json(snapshot / 'verification.json')
    require(check['passed'] and not check['missing_output_paths'] and not check['unreadable_records'],
            f'Incomplete or unreadable extraction in {snapshot}')
    index = (snapshot / 'indexes/scenario-variants.jsonl').read_bytes()
    sources = []
    names, filenames = set(), set()
    for line in index.splitlines():
        entry = json.loads(line)
        name = entry['scenario_name']
        require(name not in names, f'Duplicate scenario name {name!r}')
        names.add(name)
        matches = [v for v in entry['variants'] if v['source_id'] == entry['preferred_source_id']]
        require(len(matches) == 1, f'Ambiguous or missing preferred source for {name!r}')
        variant = matches[0]
        if variant['rows'] == 0:
            require(all(v['rows'] == 0 for v in entry['variants']), f'Preferred source has no text for {name!r}')
            continue
        file = scenario_file(name)
        require(file.casefold() not in filenames, f'Filename collision for {name!r}')
        filenames.add(file.casefold())
        source_id = variant['source_id']
        require(re.fullmatch(r'[0-9a-f]{64}:(?:file|[0-9]+_-?[0-9]+)', source_id), f'Invalid source ID {source_id}')
        digest, object_id = source_id.split(':')
        folder = f'kept/scenario_books/{digest[:2]}/{digest}/{object_id}'
        require(variant['name'].removesuffix('.book') == name, f'Book name mismatch for {name!r}')
        sources.append({'scenario_name': name, 'book_name': variant['name'], 'source_id': source_id,
                        'sources': variant['sources'], 'grid_sha256': variant['grid_sha256'],
                        'source_folder': folder, 'row_count': variant['rows'], 'file': file})
    require(len(names) == check['scenario_names_including_config'] and
            len(sources) == check['scenario_names_with_text_rows'] and
            sum(s['row_count'] for s in sources) == check['preferred_variant_text_rows'],
            'Preferred selection disagrees with extraction verification')
    return sources, hashlib.sha256(index).hexdigest()


def scenario_input(snapshot, source):
    folder = snapshot / source['source_folder']
    book = read_json(folder / 'book.json')
    grids = book['importGridList']
    raw = json.dumps(grids, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
    require(hashlib.sha256(raw).hexdigest() == source['grid_sha256'] and book['m_Name'] == source['book_name'],
            f'Book changed: {folder}')
    headers, rows = {}, []
    locations = set()
    with (folder / 'rows.jsonl').open(encoding='utf-8') as stream:
        for expected, row in zip(book_rows(book, source['source_id']), map(json.loads, stream), strict=True):
            require(row == expected, f'Extracted row differs from book: {expected["row_id"]}')
            grid = row['grid_index']
            header = row['header_row_index_0based']
            pos = row['row_index_0based']
            require((grid, pos) not in locations, f'Duplicate position in {folder}: {grid}, {pos}')
            locations.add((grid, pos))
            if (grid, header) not in headers:
                record = grids[grid]['rows'][header]
                columns = record['strings'] if isinstance(record, dict) else record
                text_column = next(i for i, col in enumerate(columns) if isinstance(col, str) and col.strip() == 'Text')
                headers[grid, header] = {'grid_index': grid, 'grid_name': row['grid_name'],
                                         'header_row_index_0based': header, 'columns': columns,
                                         'text_column_index_0based': text_column}
            column = headers[grid, header]['text_column_index_0based']
            jp = row['message']
            require(row['cells'][column] == jp, f'Text cell mismatch: {row["row_id"]}')
            command = row['command']
            rows.append({
                'row_id': row['row_id'], 'kind': 'selection' if command == 'Selection' else 'command' if command else 'dialogue',
                'speaker': row['speaker'], 'jp': jp, **EDITABLE,
                'command': command, 'voice': row['voice'], 'page_ctrl': row['fields'].get('PageCtrl', ''),
                'inline_tags': [{'raw': m[0], 'start': m.start(), 'end': m.end()} for m in TAG.finditer(jp)],
                'jp_sha256': row['source_sha256'], 'grid_index': grid, 'header_row_index_0based': header,
                'row_index_0based': pos, 'serialized_row_index': row['serialized_row_index'],
                'physical_line_1based': row['physical_line_1based'], 'message_index_0based': row['message_index_0based'],
                'grid_message_index_0based': row['grid_message_index_0based'], 'source_cells': row['cells'],
            })
    require(len(rows) == source['row_count'], f'Row count mismatch: {folder}')
    return {'schema': SCHEMA, **{k: v for k, v in source.items() if k != 'file'},
            'headers': list(headers.values()), 'rows': rows}


def check_document(path, expected):
    actual = read_json(path)
    rows = actual.pop('rows')
    require(actual == {k: v for k, v in expected.items() if k != 'rows'} and len(rows) == len(expected['rows']),
            f'Scenario metadata or row count changed: {path}')
    for row, original in zip(rows, expected['rows'], strict=True):
        for key in EDITABLE:
            require(isinstance(row.get(key), str), f'Missing or invalid {key} in {path}')
            row[key] = EDITABLE[key]  # Ignore translator-owned values when comparing source fields.
        require(row == original, f'Source fields changed: {path} / {original["row_id"]}')


def process(snapshot, dest, sources, index_digest, workers, generate):
    def process_one(source):
        path = dest / source['file']
        document = scenario_input(snapshot, source)
        if generate:
            write_json(path, document)
        check_document(path, document)
        rows = document['rows']
        return Counter(rows=len(rows), inline_tags=sum(len(r['inline_tags']) for r in rows),
                       rows_with_inline_tags=sum(bool(r['inline_tags']) for r in rows),
                       selection_rows=sum(r['kind'] == 'selection' for r in rows))

    totals = Counter()
    with ThreadPoolExecutor(workers) as pool:
        for i, stats in enumerate(pool.map(process_one, sources, buffersize=workers * 4), 1):
            totals.update(stats)
            if i % 1000 == 0:
                print(f'{i}/{len(sources)} scenarios checked', flush=True)
    expected_files = {s['file'] for s in sources}
    actual_files = {p.relative_to(dest).as_posix() for p in (dest / 'scenarios').glob('*.json')}
    require(actual_files == expected_files, 'Missing or unexpected scenario JSON files')
    manifest = {'schema': SCHEMA, 'source_language': 'ja', 'target_language': 'ko',
                'variants_index_sha256': index_digest, 'scenario_count': len(sources),
                'counts': dict(totals), 'scenarios': sources}
    if generate:
        write_json(dest / 'manifest.json', manifest)
    require(read_json(dest / 'manifest.json') == manifest, f'Manifest mismatch in {dest}')
    return manifest


def run(action, snapshot, dest, workers):
    sources, index_digest = selection(snapshot)
    if action == 'verify' or dest.exists():
        # Re-running on an existing workspace must preserve every edit, even a partial draft.
        return process(snapshot, dest, sources, index_digest, workers, generate=False)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.novel-intake-', dir=dest.parent) as tmp:
        stage = Path(tmp) / 'novel'
        (stage / 'scenarios').mkdir(parents=True)
        manifest = process(snapshot, stage, sources, index_digest, workers, generate=True)
        stage.rename(dest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['generate', 'verify'])
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    parser.add_argument('--out', type=Path, default=DESTINATION)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    result = run(args.action, args.snapshot.resolve(), args.out.resolve(), args.workers)
    print(json.dumps({'directory': str(args.out.resolve()), 'scenarios': result['scenario_count'], **result['counts']}))


if __name__ == '__main__':
    main()
