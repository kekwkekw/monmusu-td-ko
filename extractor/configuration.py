"""Resolve machine-local extraction paths relative to their configuration file."""
import json
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent / 'sources.json'


def load_config(path=DEFAULT_CONFIG):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'{path} is missing. Copy sources.example.json to sources.json and set game_root.')
    value = json.loads(path.read_text(encoding='utf-8-sig'))

    def absolute(text):
        if not isinstance(text, str) or not text:
            raise ValueError('Configuration paths must be nonempty strings')
        candidate = Path(text).expanduser()
        return str((path.parent / candidate).resolve())

    game = absolute(value['game_root'])
    value['game_root'] = game
    for source in value['sources']:
        source['root'] = absolute(source['root'].replace('${game_root}', game))
    return value
