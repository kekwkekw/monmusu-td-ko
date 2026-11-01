"""Retain manifest size discrepancies and append remote provenance to the inventory."""
import concurrent.futures as futures
import json
from collections import Counter
from pathlib import Path

from core import dump, json_line
from crawl import REMOTE, acquire
from run import OUTPUT, hash_input, records


def main():
    ab = json.loads((REMOTE / 'ablist.json').read_text())
    entries = list(records(REMOTE / 'acquisition.jsonl'))
    base = f'/assetbundles/ver_{ab["baseVersion"]}/windows_r18'
    repaired = []
    for entry in entries:
        if entry['status'] == 'failed':
            a = entry['asset']
            entry = acquire((a, REMOTE / 'bundles' / (a['hash'] + a['path']), base, None))
        repaired.append(entry)
    with (REMOTE / 'acquisition-final.jsonl').open('w', encoding='utf-8') as f:
        for entry in repaired:
            f.write(json_line(entry))
    counts = Counter(e['status'] for e in repaired)
    dump(REMOTE / 'acquisition-summary.json', {'total': len(repaired), 'counts': dict(counts),
                                              'bytes_available': sum(e.get('bytes', 0) for e in repaired),
                                              'manifest_bytes': sum(int(e['asset']['size']) for e in repaired)})
    if counts['failed']:
        raise RuntimeError('Remote failures remain; see acquisition-final.jsonl')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    current = list(records(OUTPUT / 'inputs.jsonl')) if (OUTPUT / 'inputs.jsonl').exists() else []
    by_path = {x['path']: x for x in current}
    new_inputs = []
    for entry in repaired:
        p = Path(entry['path'])
        stat = p.stat()
        known = by_path.get(str(p))
        digest = entry.get('sha256') or (known['sha256'] if known and known['size'] == stat.st_size and known['mtime_ns'] == stat.st_mtime_ns else None)
        item = {'label': 'current_remote', 'path': str(p), 'relative_path': entry['asset']['hash'] + entry['asset']['path'],
                'kind': 'unity', 'generator': 'game', 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
                'remote_asset': entry['asset'], 'acquisition_status': entry['status']}
        if digest:
            item['sha256'] = digest
        else:
            item = hash_input(item)
        new_inputs.append(item)
    # A standalone addition is merged only after the running local extraction finishes.
    with (OUTPUT / 'remote-inputs.jsonl').open('w', encoding='utf-8') as f:
        for item in new_inputs:
            f.write(json_line(item))
    print(json.dumps({'assets': len(repaired), 'counts': dict(counts), 'remote_inventory_rows': len(new_inputs)}))


if __name__ == '__main__':
    main()
