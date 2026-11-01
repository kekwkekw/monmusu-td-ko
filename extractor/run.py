"""Inventory -> extract every input -> classify. No translation or publishing side effects."""
import argparse
import concurrent.futures as futures
import gc
import gzip
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from core import (book_rows, classify, decode_text, decrypt, dump, iter_strings,
                  json_line, load_tree, metadata_literals, sha256, store_tree)
from configuration import load_config

VERSION = 1
HERE = Path(__file__).resolve().parent
CONFIG = HERE / 'sources.json'
OUTPUT = HERE / 'output-current'
SETTINGS = None


def event(stage, **values):
    print(json_line({'stage': stage, 'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'), **values}), end='', flush=True)


def copy_exact(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size == source.stat().st_size:
        return
    try:
        os.link(source, destination)
    except OSError:
        temporary = destination.with_name(destination.name + '.copying')
        shutil.copyfile(source, temporary)
        temporary.replace(destination)


def enumerate_source(source):
    root = Path(source['root'])
    if not root.exists():
        raise FileNotFoundError(root)
    mode = source['mode']
    if mode == 'root_bundles':
        for p in root.iterdir():
            if p.is_file():
                with p.open('rb') as f:
                    prefix = f.read(8)
                if prefix.startswith((b'UnityFS', b'UnityRaw', b'UnityWeb')):
                    yield {'label': source['label'], 'path': str(p), 'relative_path': p.name, 'kind': 'unity', 'generator': 'game'}
        return
    if mode == 'acquisition':
        for entry in records(root):
            if entry['status'] == 'failed':
                continue
            yield {'label': source['label'], 'path': entry['path'],
                   'relative_path': entry['asset']['hash'] + entry['asset']['path'], 'kind': 'unity',
                   'generator': 'game', 'remote_asset': entry['asset'], 'acquisition_status': entry['status']}
        return
    for p in root.rglob('*'):
        if not p.is_file() or '.git' in p.relative_to(root).parts:
            continue
        rel = p.relative_to(root)
        first = rel.parts[0]
        kind = 'auto'
        if mode == 'json':
            if p.suffix.lower() != '.json':
                continue
            kind = 'json'
        elif mode == 'bundles':
            kind = 'unity'
        elif mode == 'game_data':
            if first == 'Caches':
                kind = 'unity' if p.name == '__data' else 'binary'
            elif first == 'il2cpp_data':
                if p.name != 'global-metadata.dat':
                    continue
                kind = 'metadata'
            elif first in ('Managed', 'Plugins'):
                continue  # Code dependencies for typetree generation, not serialized assets.
            elif first in ('StreamingAssets', 'Resources') or len(rel.parts) == 1:
                if p.suffix.lower() in ('.assets',) or p.name.startswith(('level', 'globalgamemanagers')) or p.name in ('unity default resources', 'unity_builtin_extra'):
                    kind = 'unity'
                if p.suffix.lower() in ('.ress', '.resource', '.png', '.jpg', '.jpeg', '.ogg', '.wav', '.mp4', '.ttf', '.otf'):
                    kind = 'binary'
            else:
                continue
        yield {'label': source['label'], 'path': str(p.resolve()), 'relative_path': rel.as_posix(),
               'kind': kind, 'generator': source.get('generator'),
               'equivalent_copy': source.get('equivalent_copy')}


def hash_input(item):
    p = Path(item['path'])
    stat = p.stat()
    with p.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    return {**item, 'sha256': digest, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def inventory(config, out, workers):
    cfg = load_config(config)
    out.mkdir(parents=True, exist_ok=True)
    items = [x for source in cfg['sources'] for x in enumerate_source(source)]
    event('inventory_start', files=len(items))
    counts = Counter()
    total = 0
    with (out / 'inputs.jsonl').open('w', encoding='utf-8') as f, futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for index, item in enumerate(pool.map(hash_input, items, buffersize=workers * 4), 1):
            f.write(json_line(item))
            counts[item['label']] += 1
            total += item['size']
            if index % 5000 == 0:
                event('inventory', completed=index, total=len(items))
    summary = {'files': len(items), 'bytes': total, 'sources': dict(counts), 'config': cfg}
    dump(out / 'inventory-summary.json', summary)
    event('inventory_complete', **{k: v for k, v in summary.items() if k != 'config'})


def records(path):
    with Path(path).open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def initialize_worker(config, output):
    global SETTINGS, OUTPUT
    SETTINGS = load_config(config)
    OUTPUT = Path(output)


def source_folder(digest):
    return OUTPUT / 'raw' / digest[:2] / digest


def save_record(folder, record):
    dump(folder / 'record.json', record)
    return record


def emit_plain(item, folder, raw=None, kind=None):
    source = Path(item['path'])
    record = {'id': item['sha256'] + ':file', 'source_sha256': item['sha256'],
              'source_path': str(source), 'kind': kind or item['kind'], 'type': '',
              'name': source.name, 'status': 'ok', 'folder': 'file'}
    target = folder / 'file'
    target.mkdir(parents=True, exist_ok=True)
    copy_exact(source, target / ('source' + source.suffix if source.suffix else 'source.bin'))
    if record['kind'] != 'binary':
        raw = raw if raw is not None else source.read_bytes()
    if item['kind'] == 'metadata':
        with gzip.open(target / 'literals.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1) as f:
            count = 0
            for literal in metadata_literals(raw):
                f.write(json_line(literal))
                count += 1
        record.update(kind='il2cpp_literals', literal_count=count)
    elif record['kind'] != 'binary':
        text, encoding = decode_text(raw)
        if text is not None:
            record.update(kind='text', encoding=encoding)
            (target / 'text.txt').write_text(text, encoding='utf-8', errors='surrogatepass')
            try:
                tree = json.loads(text)
                store_tree(target, tree)
                record['kind'] = 'json'
            except ValueError:
                pass
        else:
            record['kind'] = 'binary'
    return save_record(target, record)


def _extract_one(item):
    import UnityPy
    from UnityPy.streams import EndianBinaryReader
    from unity_adapter import generator, guiskin_schema

    folder = source_folder(item['sha256'])
    complete = folder / 'complete.json'
    if complete.exists():
        result = json.loads(complete.read_text(encoding='utf-8'))
        return {**result, 'resumed': True}
    folder.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result = {'sha256': item['sha256'], 'path': item['path'], 'version': VERSION,
              'objects': 0, 'records': 0, 'errors': 0, 'types': {}, 'strategies': {}}
    entries = []
    try:
        p = Path(item['path'])
        if p.stat().st_size != item['size'] or p.stat().st_mtime_ns != item['mtime_ns']:
            raise ValueError('Input changed since inventory; regenerate inventory')
        if item['kind'] in ('binary', 'json', 'metadata'):
            entries.append(emit_plain(item, folder))
        else:
            raw = p.read_bytes()
            decoded = raw
            strategy = 'plain'
            # Decrypt only when the resulting signature positively identifies a Unity bundle.
            if not raw.startswith((b'UnityFS', b'UnityRaw', b'UnityWeb')):
                probe = decrypt(raw[:64])
                if probe.startswith((b'UnityFS', b'UnityRaw', b'UnityWeb')):
                    decoded = decrypt(raw)
                    strategy = 'xor64_KYSSTMDL'
            env = None
            load_error = None
            try:
                # File path preserves dependency resolution for standalone game assets.
                if strategy == 'plain' and not raw.startswith(b'Unity'):
                    env = UnityPy.load(str(p))
                else:
                    env = UnityPy.Environment(path=str(p.parent))
                    env.load_file(decoded, name=p.name)
                objects = list(env.objects)
            except Exception as exc:
                load_error = f'{type(exc).__name__}: {exc}'
                objects = []
            if not objects:
                rec = emit_plain(item, folder, raw)
                if item['kind'] == 'unity' and rec['kind'] == 'binary':
                    rec.update(status='unreadable', error=load_error or 'No serialized objects found')
                    result['errors'] += 1
                    save_record(folder / rec['folder'], rec)
                entries.append(rec)
            else:
                result['objects'] = len(objects)
                result['decryption'] = strategy
                types, strategies = Counter(), Counter()
                container_maps = {}
                for obj in objects:
                    af = obj.assets_file
                    if id(af) in container_maps:
                        continue
                    mapping = {}
                    helper = af.container
                    for logical, info in helper.container:
                        pointers = [info.asset]
                        if helper._preload_table is not None:
                            pointers += helper._preload_table[info.preloadIndex:info.preloadIndex + info.preloadSize]
                        for pointer in pointers:
                            if pointer.m_FileID == 0:
                                mapping.setdefault(pointer.m_PathID, set()).add(logical)
                    container_maps[id(af)] = mapping
                for oi, obj in enumerate(objects):
                    typ = obj.type.name
                    types[typ] += 1
                    oid = f'{oi:06d}_{obj.path_id}'
                    dest = folder / oid
                    dest.mkdir(parents=True, exist_ok=True)
                    record = {'id': item['sha256'] + ':' + oid, 'source_sha256': item['sha256'],
                              'source_path': str(p), 'folder': oid, 'kind': 'unity', 'type': typ,
                              'path_id': obj.path_id, 'serialized_file': str(obj.assets_file.name),
                              'byte_size': obj.byte_size, 'unity_version': str(obj.assets_file.unity_version),
                              'decryption': strategy, 'status': 'ok'}
                    # Container labels do not require resolving external assets.
                    # UnityPy's obj.container walks the entire workspace for missing
                    # dependencies, even though this object's full fields are local.
                    record['containers'] = sorted(container_maps[id(obj.assets_file)].get(obj.path_id, []))
                    tree = None
                    try:
                        embedded = bool(obj.serialized_type and obj.serialized_type.node)
                        parse_strategy = 'embedded' if embedded else 'unity_builtin'
                        if typ == 'MonoBehaviour' and not embedded:
                            from UnityPy.helpers.Tpk import get_typetree_node
                            head = obj.parse_monobehaviour_head()
                            if head.m_Script.m_PathID == 0:
                                node = get_typetree_node(114, obj.version)
                                parse_strategy = 'native_header_complete'
                            else:
                                env.typetree_generator = generator(SETTINGS['game_root'], '2022.3.62f2')
                                parse_strategy = 'generated'
                                script = head.m_Script.deref_parse_as_object()
                                if script.m_Namespace == 'UnityEngine' and script.m_ClassName == 'GUISkin':
                                    node = guiskin_schema()
                                    parse_strategy = 'bundled_guiskin_schema'
                                else:
                                    node = obj.generate_monobehaviour_node()
                            tree = obj.read_typetree(nodes=node, check_read=True)
                        else:
                            tree = obj.read_typetree(check_read=True)
                        record['name'] = tree.get('m_Name', '') if isinstance(tree, dict) else ''
                        record['strategy'] = parse_strategy
                        record['binary_fields'] = store_tree(dest, tree)
                        if typ == 'TextAsset':
                            script = tree.get('m_Script', '')
                            payload = script.encode('utf-8', 'surrogateescape') if isinstance(script, str) else bytes(script)
                            (dest / 'payload.bin').write_bytes(payload)
                            record['payload_sha256'] = sha256(payload)
                        strategies[parse_strategy] += 1
                    except Exception as exc:
                        record.update(status='unreadable', error=f'{type(exc).__name__}: {exc}')
                        result['errors'] += 1
                        strategies['raw_fallback'] += 1
                        (dest / 'object.bin').write_bytes(obj.get_raw_data())
                        # An available base header is evidence, not a successful full parse.
                        if typ == 'MonoBehaviour':
                            try:
                                head = obj.parse_monobehaviour_head()
                                record['name'] = head.m_Name
                            except Exception:
                                pass
                    entries.append(save_record(dest, record))
                # Preserve non-serialized bundle members (resS/resource/etc.) as well.
                def members(container, prefix=''):
                    for name, value in (getattr(container, 'files', None) or {}).items():
                        member = prefix + '/' + str(name)
                        if isinstance(value, EndianBinaryReader):
                            yield member, value.bytes
                        elif hasattr(value, 'files'):
                            yield from members(value, member)
                for mi, (name, payload) in enumerate(members(env)):
                    sub = f'member_{mi:04d}'
                    dest = folder / sub
                    dest.mkdir(exist_ok=True)
                    (dest / 'payload.bin').write_bytes(payload)
                    rec = {'id': item['sha256'] + ':' + sub, 'source_sha256': item['sha256'],
                           'source_path': str(p), 'folder': sub, 'kind': 'binary', 'type': 'BundleResource',
                           'name': name, 'status': 'ok', 'bytes': len(payload), 'payload_sha256': sha256(payload)}
                    entries.append(save_record(dest, rec))
                result['types'], result['strategies'] = dict(types), dict(strategies)
            del env
        with (folder / 'records.jsonl').open('w', encoding='utf-8') as f:
            for entry in entries:
                f.write(json_line(entry))
        result['records'] = len(entries)
        result['seconds'] = round(time.monotonic() - started, 3)
        dump(complete, result)
    except Exception as exc:
        result.update(fatal_error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
        dump(folder / 'failure.json', result)
    return result


WORKER_FILES = 0


def extract_one(item):
    global WORKER_FILES
    result = _extract_one(item)
    WORKER_FILES += 1
    # Collect after the parsing frame has released its object/PPtr locals.
    # Re-scanning the entire typetree cache after every tiny audio bundle is costly.
    if result['objects']:
        gc.collect(0)
    if WORKER_FILES % 32 == 0 or item['size'] >= 8 * 1024 * 1024 or result['objects'] >= 1000:
        gc.collect()
    return result


def unique_inputs(out):
    unique = {}
    # Preserve every provenance row; process byte-identical content only once.
    for item in records(out / 'inputs.jsonl'):
        old = unique.get(item['sha256'])
        if old is None or (old['kind'] == 'binary' and item['kind'] != 'binary'):
            unique[item['sha256']] = item
    return list(unique.values())


def extract(config, out, workers):
    items = unique_inputs(out)
    event('extract_start', unique_files=len(items), workers=workers)
    counters = Counter()
    types, strategies = Counter(), Counter()
    started = time.monotonic()
    last = started
    with (out / 'extraction-results.jsonl').open('w', encoding='utf-8') as f, futures.ProcessPoolExecutor(
            max_workers=workers, initializer=initialize_worker, initargs=(str(config), str(out)),
            max_tasks_per_child=300) as pool:
        def completed_and_new():
            pending = []
            def existing_result(item):
                marker = out / 'raw' / item['sha256'][:2] / item['sha256'] / 'complete.json'
                if marker.exists():
                    return item, {**json.loads(marker.read_text()), 'resumed': True}
                return item, None
            with futures.ThreadPoolExecutor(max_workers=workers * 2) as readers:
                for item, result in readers.map(existing_result, items, buffersize=workers * 8):
                    if result is not None:
                        yield result
                    else:
                        pending.append(item)
            # Bounded unordered work prevents a large prefab from blocking dispatch
            # of unrelated small bundles behind it. Output IDs do not depend on order.
            iterator = iter(pending)
            active = set()
            for _ in range(workers * 3):
                item = next(iterator, None)
                if item is not None:
                    active.add(pool.submit(extract_one, item))
            while active:
                finished, active = futures.wait(active, return_when=futures.FIRST_COMPLETED)
                for future in finished:
                    yield future.result()
                    item = next(iterator, None)
                    if item is not None:
                        active.add(pool.submit(extract_one, item))
        for index, result in enumerate(completed_and_new(), 1):
            f.write(json_line(result))
            counters['completed_files'] += 1
            for key in ('objects', 'records', 'errors'):
                counters[key] += result[key]
            counters['fatal_files'] += int('fatal_error' in result)
            counters['reused_files'] += int(result.get('resumed', False))
            types.update(result['types'])
            strategies.update(result['strategies'])
            if time.monotonic() - last > 20 or index == len(items):
                last = time.monotonic()
                f.flush()
                progress = {'total_files': len(items), **counters, 'elapsed_seconds': round(last - started)}
                dump(out / 'progress.json', {'stage': 'extract', **progress})
                event('extract', **progress)
    summary = {'total_files': len(items), **counters, 'types': dict(types), 'strategies': dict(strategies),
               'elapsed_seconds': round(time.monotonic() - started)}
    dump(out / 'extraction-summary.json', summary)
    event('extract_complete', **counters)


def classify_all(out, workers=6):
    import subprocess
    subprocess.run([sys.executable, "-X", "utf8", str(HERE / "classify_output.py"),
                    "--output", str(out.resolve()), "--workers", str(workers)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['inventory', 'extract', 'classify', 'all'])
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.stage in ('inventory', 'all'):
        inventory(args.config, args.output, args.workers)
    if args.stage in ('extract', 'all'):
        extract(args.config, args.output, args.workers)
    if args.stage in ('classify', 'all'):
        classify_all(args.output, args.workers)


if __name__ == '__main__':
    main()
