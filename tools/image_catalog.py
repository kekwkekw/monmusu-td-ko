"""Validate reviewed image descriptors and exact-size content-addressed PNGs."""
import hashlib
import json
import struct
from pathlib import Path


def validate(folder):
    folder = Path(folder)
    raw = (folder / 'images.json').read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != 'monmusu-images-v1' or not isinstance(doc.get('entries'), list):
        raise ValueError('Invalid image catalog')
    files = {'images.json': raw}
    ids = set()
    for item in doc['entries']:
        if item['id'] in ids or not item['id'] or item['kind'] not in ('sprite', 'texture'):
            raise ValueError('Duplicate/invalid image identity')
        ids.add(item['id'])
        if not item.get('name') or item.get('width', 0) <= 0 or item.get('height', 0) <= 0:
            raise ValueError('Missing image name or canvas: ' + item['id'])
        if item.get('review_status') != 'reviewed' or not item.get('review_id') or not item.get('jp') or not item.get('ko'):
            raise ValueError('Unreviewed image: ' + item['id'])
        if not item.get('context_suffixes') or not item.get('source_textures') or not item.get('source_ids'):
            raise ValueError('Missing source/context binding: ' + item['id'])
        if any(not s.strip() or s.startswith('/') or '\\' in s for s in item['context_suffixes']):
            raise ValueError('Invalid component context: ' + item['id'])
        if any(not s.get('name') or s.get('width', 0) <= 0 or s.get('height', 0) <= 0 for s in item['source_textures']):
            raise ValueError('Invalid source texture identity: ' + item['id'])
        digest = item['sha256']
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest) or item['file'] != f'images/{digest}.png':
            raise ValueError('Invalid content-addressed image path')
        payload = (folder / item['file']).read_bytes()
        if len(payload) != item['bytes'] or hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError('Image checksum mismatch: ' + item['id'])
        if len(payload) < 33 or payload[:8] != b'\x89PNG\r\n\x1a\n' or payload[12:16] != b'IHDR' or struct.unpack('>II', payload[16:24]) != (item['width'], item['height']):
            raise ValueError('Image dimensions/header mismatch: ' + item['id'])
        files[item['file']] = payload
    return files
