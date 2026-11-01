"""Integration checks against the installed game and preserved reference data."""
import json
import unittest
from pathlib import Path

import UnityPy
from UnityPy.helpers.Tpk import get_typetree_node

from core import book_rows, decrypt
from unity_adapter import generator, guiskin_schema
from configuration import load_config

ROOT = Path(__file__).resolve().parent
CONFIG = load_config(ROOT / 'sources.json')
GAME = Path(CONFIG['game_root'])
DATA = GAME / 'monster_musume_tdx_Data'


class LiveAssetTests(unittest.TestCase):
    def test_generated_trees_consume_full_object_and_keep_script_pointers(self):
        total = 0
        for filename in ['resources.assets', 'sharedassets4.assets']:
            env = UnityPy.load(str(DATA / filename))
            env.typetree_generator = generator(str(GAME), '2022.3.62f2')
            for obj in env.objects:
                if obj.type.name != 'MonoBehaviour':
                    continue
                head = obj.parse_monobehaviour_head()
                node = obj.generate_monobehaviour_node() if head.m_Script.m_PathID else get_typetree_node(114, obj.version)
                tree = obj.read_typetree(nodes=node, check_read=True)
                self.assertEqual(tree['m_Script']['m_PathID'], head.m_Script.m_PathID)
                self.assertEqual(tree['m_Script']['m_FileID'], head.m_Script.m_FileID)
                if head.m_Name == 'DontClearFonts':
                    self.assertIsInstance(tree['m_dontRemoveAb'], list)
                    self.assertTrue(all(isinstance(x, str) for x in tree['m_dontRemoveAb']))
                total += 1
        self.assertGreaterEqual(total, 177)

    def test_native_guiskin_reference_matches_serialized_size(self):
        env = UnityPy.load(str(DATA / 'Resources/unity default resources'))
        node = guiskin_schema()
        skins = [obj for obj in env.objects if obj.type.name == 'MonoBehaviour']
        self.assertTrue(skins)
        for obj in skins:
            tree = obj.read_typetree(nodes=node, check_read=True)
            self.assertIn('m_CustomStyles', tree)

    def test_encrypted_master_and_story_bundle(self):
        master = ROOT / 'fixtures/master.bytes'
        raw = decrypt(master.read_bytes())
        self.assertTrue(raw.startswith(b'UnityFS'))
        env = UnityPy.load(raw)
        self.assertGreater(len(env.objects), 100)
        story = ROOT / 'fixtures/story.bytes'
        env = UnityPy.load(str(story))
        books = [o.read_typetree() for o in env.objects if o.type.name == 'MonoBehaviour']
        rows = [row for book in books for row in book_rows(book, 'integration')]
        self.assertTrue(rows)
        self.assertTrue(all(r['scenario_name'] == '1100031Nml.book' for r in rows))


if __name__ == '__main__':
    unittest.main()
