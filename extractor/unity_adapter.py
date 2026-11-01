"""UnityPy compatibility for IL2CPP assembly names, without patching dependencies."""
import json
from functools import lru_cache
from pathlib import Path

from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.helpers.Tpk import get_typetree_node
from UnityPy.helpers.UnityVersion import UnityVersion
from UnityPy.helpers.TypeTreeHelper import FUNCTION_READ_MAP
from UnityPy.enums import ClassIDType


class GameTypeTreeGenerator(TypeTreeGenerator):
    def __init__(self, unity_version):
        super().__init__(unity_version)
        self.unity_version = UnityVersion.from_str(unity_version)

    def get_nodes_up(self, assembly, fullname):
        key = (assembly, fullname)
        if key in self.cache:
            return self.cache[key]
        # Some built-in Unity MonoBehaviours are native and absent from IL2CPP.
        if fullname.startswith('UnityEngine.'):
            native_id = getattr(ClassIDType, fullname.removeprefix('UnityEngine.'), None)
            if native_id is not None and native_id != ClassIDType.MonoBehaviour:
                native = get_typetree_node(int(native_id), self.unity_version)
                self.cache[key] = native
                return native
        stem = assembly.removesuffix(".dll")
        errors = []
        for candidate in (stem, stem + ".dll"):
            try:
                base = self.get_nodes(candidate, fullname)
                converted = []
                for i, n in enumerate(base):
                    typ = n.m_Type
                    if typ in FUNCTION_READ_MAP and i + 3 < len(base) and base[i + 1].m_Type == 'Array' and base[i + 1].m_Level == n.m_Level + 1:
                        if not (typ == 'string' and base[i + 3].m_Type == 'char'):
                            typ = 'vector'
                    converted.append(TypeTreeNode(n.m_Level, typ, n.m_Name, 0, 0, m_MetaFlag=n.m_MetaFlag))
                node = TypeTreeNode.from_list(converted)
                # The generator's synthetic MB prefix can misalign m_Script while
                # still consuming the expected byte count. Use Unity's native prefix.
                native = get_typetree_node(114, self.unity_version)
                native_by_name = {n.m_Name: n for n in native.m_Children}
                node.m_Children = [native_by_name.get(n.m_Name, n) for n in node.m_Children]
                self.cache[key] = node
                return node
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")
        raise ValueError("; ".join(errors))


@lru_cache(maxsize=3)
def generator(game_root, version):
    result = GameTypeTreeGenerator(version)
    result.load_local_game(game_root)
    return result


@lru_cache(maxsize=1)
def guiskin_schema():
    schema = Path(__file__).resolve().parent / 'schemas' / 'GUISkin.json'
    return TypeTreeNode.from_list(json.loads(schema.read_text(encoding='utf-8'))['nodes'])
