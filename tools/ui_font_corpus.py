"""Build the local TMP UI corpus from current reviewed outputs (no game writes)."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)


def build(root):
    chars = set(map(chr, range(32, 127))) | set(map(chr, range(0x3131, 0x3164)))
    for name in ('ui.json', 'master.json', 'names.json'):
        document = json.loads((root / 'translations/ko' / name).read_text('utf-8'))
        for value in strings(document):
            chars.update(c for c in value if '\uac00' <= c <= '\ud7a3')
    return ''.join(sorted(chars))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    corpus = build(ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(corpus, encoding='utf-8')
    print(json.dumps({'characters': len(corpus), 'hangul': sum('\uac00' <= c <= '\ud7a3' for c in corpus)}, ensure_ascii=False))
