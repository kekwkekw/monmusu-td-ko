import json
from pathlib import Path
import tempfile
import unittest

from configuration import load_config


class ConfigurationTests(unittest.TestCase):
    def test_relative_config_and_game_root_placeholder(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            path = Path(folder) / 'sources.json'
            path.write_text(json.dumps({'game_root': '../game', 'sources': [
                {'label': 'game', 'root': '${game_root}/Data'},
                {'label': 'remote', 'root': 'remote/acquisition-final.jsonl'}]}), encoding='utf-8')
            config = load_config(path)
            self.assertEqual(Path(config['game_root']), (path.parent / '../game').resolve())
            self.assertEqual(Path(config['sources'][0]['root']), Path(config['game_root']) / 'Data')
            self.assertEqual(Path(config['sources'][1]['root']), path.parent / 'remote/acquisition-final.jsonl')

    def test_missing_config_explains_setup(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            with self.assertRaisesRegex(FileNotFoundError, 'sources.example.json'):
                load_config(Path(folder) / 'missing.json')


if __name__ == '__main__':
    unittest.main()
