"""Write a small real-input inventory for a fresh extraction smoke test."""
import argparse
import json
from pathlib import Path

from run import CONFIG, hash_input, json_line
from configuration import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=CONFIG.parent / 'probe-standalone')
    parser.add_argument('--config', type=Path, default=CONFIG)
    args = parser.parse_args()
    config = load_config(args.config)
    game = Path(config['game_root']) / 'monster_musume_tdx_Data'
    fixtures = CONFIG.parent / 'fixtures'
    samples = [
        (game / 'resources.assets', 'unity', 'game'),
        (game / 'sharedassets4.assets', 'unity', 'game'),
        (game / 'Resources/unity default resources', 'unity', 'game'),
        (game / 'il2cpp_data/Metadata/global-metadata.dat', 'metadata', 'game'),
        (fixtures / 'master.bytes', 'unity', 'fixture'),
        (fixtures / 'story.bytes', 'unity', 'fixture'),
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'inputs.jsonl').open('w', encoding='utf-8') as stream:
        for path, kind, label in samples:
            item = hash_input({'path': str(path.resolve()), 'kind': kind, 'generator': 'game', 'label': label})
            stream.write(json_line(item))
    print(f'{len(samples)} inputs in {args.output}')


if __name__ == '__main__':
    main()
