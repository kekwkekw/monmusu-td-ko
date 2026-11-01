"""Acquire the full public windows_r18 asset manifest, with exact local reuse."""
import argparse
import concurrent.futures as futures
import hashlib
import http.client
import json
import re
import threading
import time
import urllib.request
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

from core import dump, json_line
from configuration import DEFAULT_CONFIG, load_config

ROOT = Path(__file__).resolve().parent
REMOTE = ROOT / 'remote'
HOST = 'assets.game-monmusu-td.net'
LOCAL = threading.local()


def refresh_manifest():
    def fetch(url, payload=None):
        request = urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None,
                                         headers={'Content-Type': 'application/json', 'User-Agent': 'MonmusuWorkspaceExtractor/1.0'})
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    app_url = 'https://api.store.games.dmm.com/freeapp/688044'
    version_url = 'https://gapi.game-monmusu-td.net/api/asset_bundle/version'
    app = fetch(app_url)
    version = fetch(version_url, {'cvr': app['free_appinfo']['app_version_name'], 'provider': 'dmm'})
    version_id = str(version['data']['version'])
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', version_id):
        raise ValueError('Unexpected asset version identifier')
    url = f'https://{HOST}/assetbundles/ver_{version_id}/windows_r18/ablist.json'
    manifest = fetch(url)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot = REMOTE / 'manifests' / (version_id + '_' + stamp)
    snapshot.mkdir(parents=True, exist_ok=True)
    for name, value in [('app-info.json', app), ('version.json', version), ('ablist.json', manifest)]:
        dump(snapshot / name, value)
        dump(REMOTE / name, value)
    dump(REMOTE / 'manifest-source.json', {'captured_utc': stamp, 'client_version': app['free_appinfo']['app_version_name'],
                                          'asset_version': version_id, 'base_version': manifest['baseVersion'],
                                          'platform': 'windows_r18', 'app_url': app_url, 'version_api': version_url,
                                          'manifest_url': url, 'snapshot_path': str(snapshot)})


def acquire(task):
    asset, path, base, reuse = task
    expected = int(asset['size'])
    if reuse is not None:
        return {'asset': asset, 'path': str(reuse), 'status': 'local_reuse', 'bytes': expected}
    if path.exists() and path.stat().st_size == expected:
        return {'asset': asset, 'path': str(path), 'status': 'download_present', 'bytes': expected}
    url_path = base + '/' + asset['hash'] + asset['path']
    error = None
    for attempt in range(5):
        try:
            conn = getattr(LOCAL, 'connection', None)
            if conn is None:
                conn = http.client.HTTPSConnection(HOST, timeout=45)
                LOCAL.connection = conn
            conn.request('GET', url_path, headers={'User-Agent': 'MonmusuWorkspaceExtractor/1.0'})
            response = conn.getresponse()
            if response.status != 200:
                response.read()
                raise ValueError(f'HTTP {response.status} {response.reason}')
            raw = response.read()
            content_length = response.getheader('Content-Length')
            if content_length is not None and len(raw) != int(content_length):
                raise ValueError(f'Truncated HTTP response: {len(raw)} != {content_length}')
            temp = path.with_suffix('.partial')
            temp.write_bytes(raw)
            temp.replace(path)
            return {'asset': asset, 'path': str(path), 'status': 'downloaded' if len(raw) == expected else 'downloaded_size_mismatch',
                    'bytes': len(raw), 'manifest_size': expected, 'sha256': hashlib.sha256(raw).hexdigest(),
                    'url': 'https://' + HOST + url_path}
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            conn = getattr(LOCAL, 'connection', None)
            if conn:
                conn.close()
            LOCAL.connection = None
            time.sleep(min(2 ** attempt, 8))
    return {'asset': asset, 'status': 'failed', 'error': error, 'url': 'https://' + HOST + url_path}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--refresh-manifest', action='store_true')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.refresh_manifest or not (REMOTE / 'ablist.json').exists():
        refresh_manifest()
    manifest = json.loads((REMOTE / 'ablist.json').read_text())
    local = {}
    cache = Path(config['game_root']) / 'monster_musume_tdx_Data/Caches'
    for p in cache.rglob('__data'):
        local.setdefault(p.parent.parent.name + '.bytes', p)
    dest = REMOTE / 'bundles'
    dest.mkdir(exist_ok=True)
    base = f'/assetbundles/ver_{manifest["baseVersion"]}/windows_r18'
    tasks = []
    for asset in manifest['data']:
        filename = asset['hash'] + asset['path']
        if not re.fullmatch(r'[a-fA-F0-9]+\.bytes', filename):
            raise ValueError(f'Unexpected manifest filename: {filename}')
        reuse = local.get(filename)
        if reuse and reuse.stat().st_size != int(asset['size']):
            reuse = None
        tasks.append((asset, dest / filename, base, reuse))
    counts = Counter()
    byte_counts = Counter()
    start = last = time.monotonic()
    print(json_line({'stage': 'download_start', 'assets': len(tasks), 'local_reuse': sum(t[3] is not None for t in tasks),
                     'missing_bytes': sum(int(t[0]['size']) for t in tasks if t[3] is None)}), end='', flush=True)
    with (REMOTE / 'acquisition.jsonl').open('w', encoding='utf-8') as report, futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, result in enumerate(pool.map(acquire, tasks, buffersize=args.workers * 4), 1):
            report.write(json_line(result))
            counts[result['status']] += 1
            byte_counts[result['status']] += result.get('bytes', 0)
            if time.monotonic() - last > 20 or i == len(tasks):
                report.flush()
                last = time.monotonic()
                progress = {'completed': i, 'total': len(tasks), 'counts': dict(counts), 'bytes': dict(byte_counts),
                            'elapsed_seconds': round(last - start)}
                dump(REMOTE / 'progress.json', progress)
                print(json_line(progress), end='', flush=True)
    dump(REMOTE / 'acquisition-summary.json', progress)
    if counts['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
