"""Crash-recoverable local file transactions for Novel authoring (stdlib only)."""
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import uuid


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def pairs(items):
    value = {}
    for key, child in items:
        require(key not in value, 'Duplicate JSON key: ' + key)
        value[key] = child
    return value


def read_json(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)


def file_hash(path):
    return digest(path.read_bytes()) if path.exists() else None


def atomic_write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def owned(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root), 'Output outside workspace')
    rel = path.relative_to(root).as_posix()
    require(rel in {'translation/knowledge.jsonl', 'translation/holds.jsonl'} or
            any(rel.startswith(p) for p in ('translation/state/', 'work/novels/',
                                            'translations/ko/', 'knowledge-layer/provenance/')),
            'Output is not pipeline-owned: ' + rel)
    require(path.name != 'HOLD_POLICY.md' or rel.startswith('work/novels/'), 'Canonical policy is read-only')
    return path


def recover(root):
    """Finish a committed intent, preserving unexpected non-cooperating edits."""
    folder = root / 'translation/state/transactions'
    for journal in sorted(folder.glob('*.json')):
        transaction = read_json(journal)
        entries = []
        for entry in transaction['files']:
            path = owned(root, entry['path'])
            raw = base64.b64decode(entry['data'], validate=True)
            require(digest(raw) == entry['after'], 'Transaction data is damaged')
            require(file_hash(path) in {entry['before'], entry['after']},
                    'Pending transaction conflicts with an external edit: ' + entry['path'])
            entries.append((path, raw, entry['after']))
        for path, raw, after in entries:
            if file_hash(path) != after:
                atomic_write(path, raw)
        journal.unlink()


def publish(root, updates, previous=None):
    files = []
    for relative, raw in updates.items():
        path = owned(root, relative)
        before = file_hash(path)
        if previous is not None:
            require(before == previous[relative], 'Concurrent edit: ' + relative)
        if before != digest(raw):
            files.append({'path': relative, 'before': before, 'after': digest(raw),
                          'data': base64.b64encode(raw).decode('ascii')})
    if not files:
        return
    journal = root / 'translation/state/transactions' / (uuid.uuid4().hex + '.json')
    atomic_write(journal, encode({'schema': 'monmusu-file-transaction-v1', 'files': files}))
    recover(root)


@contextmanager
def workspace_lock(root):
    """OS lock is released by the kernel even after a killed Python process."""
    path = root / 'translation/state/.workflow.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'\0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise ValueError('Another Novel command is running') from error
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            recover(root)
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
