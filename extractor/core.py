"""Lossless extraction primitives. Classification deliberately happens later."""
import gzip
import hashlib
import json
import re
import struct
from pathlib import Path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8', 'backslashreplace'))
    temporary.replace(path)


def json_line(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8', 'backslashreplace').decode('utf-8')


CATEGORY_DESCRIPTIONS = {
    'kept/scenario_books': 'Utage book 전체 구조. 대사 후보와 설정 book을 함께 보존합니다.',
    'kept/masterdata': '게임 마스터데이터. UI 명칭·설명·시나리오 참조를 포함한 모든 필드를 보존합니다.',
    'kept/ui_candidates': 'UI 텍스트가 들어갈 수 있는 직렬화 필드 또는 IL2CPP 문자열 리터럴입니다.',
    'kept/other_text': '추가 검토할 텍스트와 기타 직렬화 자료입니다.',
    'excluded/spine': 'Spine skeleton JSON의 뼈대·슬롯·애니메이션 데이터입니다.',
    'excluded/spine_atlas': '텍스처 atlas의 영역·좌표·회전 정보입니다.',
    'excluded/spine_components': 'MonoScript namespace로 확인한 Spine 런타임·애니메이션 구성 요소입니다.',
    'excluded/rendering': 'Unity 타입으로 확인한 그래픽·애니메이션·음성 등 렌더링 및 미디어 자료입니다.',
    'excluded/engine_metadata': 'Unity 객체 계층·참조·엔진 설정 등 구조 메타데이터입니다.',
    'excluded/binary': '원본 바이너리 또는 번들 보조 리소스입니다.',
    'excluded/binary_textasset': 'TextAsset이지만 NUL 또는 비 UTF-8 바이트가 있는 바이너리 payload입니다.',
    'excluded/unreadable': '구조 파싱에 실패했습니다. 오류와 원본 bytes를 보존했습니다.'
}


def decrypt(data):
    digest = hashlib.sha256(bytes(b ^ 0x55 for b in b'KYSSTMDL')).digest()
    mixed = bytes(b ^ 0xAA for b in digest)
    first = mixed[::2] + mixed[1::2]
    key = first + first[::-1]
    # Translate each byte lane in C; avoids a Python loop over large bundles.
    result = bytearray(len(data))
    for i, b in enumerate(key):
        result[i::64] = data[i::64].translate(bytes(x ^ b for x in range(256)))
    return bytes(result)


def decode_text(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        try:
            return raw.decode('utf-16'), 'utf-16'
        except UnicodeError:
            pass
    try:
        text = raw.decode('utf-8-sig')
        if '\x00' not in text and not any(ord(c) < 9 or 13 < ord(c) < 32 for c in text):
            return text, 'utf-8-sig'
    except UnicodeError:
        pass
    return None, None


def iter_strings(value, pointer=''):
    if isinstance(value, str):
        yield pointer, value
    elif isinstance(value, dict):
        if '$binary' in value:
            return
        for key, child in value.items():
            escaped = str(key).replace('~', '~0').replace('/', '~1')
            yield from iter_strings(child, pointer + '/' + escaped)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from iter_strings(child, pointer + '/' + str(index))


def store_tree(folder, tree):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    binaries = []

    def binary_default(value):
        if isinstance(value, (bytes, bytearray, memoryview)):
            value = bytes(value)
            filename = f'field_{len(binaries):04d}.bin'
            (folder / filename).write_bytes(value)
            info = {'$binary': filename, 'bytes': len(value), 'sha256': sha256(value)}
            binaries.append(info)
            return info
        raise TypeError(f'Unsupported typetree value {type(value).__name__}')

    # dumps uses the C encoder; dump streams millions of scalar writes for meshes.
    encoded = json.dumps(tree, ensure_ascii=True, separators=(',', ':'), default=binary_default).encode('utf-8')
    with gzip.open(folder / 'tree.json.gz', 'wb', compresslevel=1) as f:
        f.write(encoded)
    return binaries


def load_tree(folder):
    with gzip.open(Path(folder) / 'tree.json.gz', 'rt', encoding='utf-8') as f:
        return json.load(f)


def book_rows(tree, source_id):
    """Retain every grid and physical row; never collapse duplicate source text."""
    name = tree.get('m_Name', '')
    message_index = 0
    for gi, grid in enumerate(tree.get('importGridList', [])):
        if not isinstance(grid, dict):
            continue
        header = None
        header_index = None
        grid_message_index = 0
        for ri, row in enumerate(grid.get('rows', [])):
            cells = row.get('strings', []) if isinstance(row, dict) else row
            if not isinstance(cells, list):
                continue
            normalized = [v.strip() if isinstance(v, str) else '' for v in cells]
            if 'Text' in normalized and ('Command' in normalized or 'Arg1' in normalized):
                header, header_index = normalized, ri
                continue
            if header is None:
                continue
            if isinstance(row, dict) and (row.get('isCommentOut') or row.get('isEmpty')):
                continue
            fields = {}
            for i, column in enumerate(header):
                if column and column not in fields:
                    fields[column] = cells[i] if i < len(cells) else ''
            text = fields.get('Text', '')
            command = fields.get('Command', '')
            commented = isinstance(command, str) and command.lstrip().startswith('//')
            if not isinstance(text, str) or not text or commented:
                continue
            yield {'source_id': source_id, 'row_id': f'{source_id}:g{gi}:r{ri}', 'scenario_name': name, 'grid_index': gi,
                   'grid_name': grid.get('name', grid.get('sheetName', '')),
                   'row_index_0based': ri, 'physical_line_1based': ri + 1,
                   'serialized_row_index': row.get('rowIndex') if isinstance(row, dict) else None,
                   'header_row_index_0based': header_index,
                   'message_index_0based': message_index,
                   'grid_message_index_0based': grid_message_index,
                   'message': text, 'source_sha256': sha256(text.encode('utf-8', 'surrogatepass')),
                   'speaker': fields.get('Arg1', ''), 'command': command,
                   'voice': fields.get('Voice', ''), 'fields': fields, 'cells': cells}
            message_index += 1
            grid_message_index += 1


def metadata_literals(raw):
    if len(raw) < 24:
        raise ValueError('Truncated IL2CPP metadata header')
    magic, version, offset, size, data_offset, data_size = struct.unpack_from('<6I', raw)
    if magic != 0xFAB11BAF or size % 8 or offset + size > len(raw) or data_offset + data_size > len(raw):
        raise ValueError('Unsupported or invalid IL2CPP string-literal table')
    for i in range(size // 8):
        length, index = struct.unpack_from('<2I', raw, offset + i * 8)
        if index + length > data_size:
            raise ValueError(f'Invalid string-literal range at {i}')
        value = raw[data_offset + index:data_offset + index + length]
        yield {'index': i, 'offset': data_offset + index, 'byte_length': length,
               'metadata_version': version, 'text': value.decode('utf-8', 'surrogateescape')}


RENDERING_TYPES = set('Texture2D Texture3D Texture2DArray Cubemap Sprite SpriteAtlas Mesh Material Shader ComputeShader ShaderVariantCollection AnimationClip Animation Animator AnimatorController AnimatorOverrideController AnimatorState AnimatorStateMachine Avatar AudioClip VideoClip Font RenderTexture SkinnedMeshRenderer MeshRenderer MeshFilter SpriteRenderer LineRenderer TrailRenderer Canvas CanvasRenderer ParticleSystem ParticleSystemRenderer Light LightingDataAsset LightmapSettings OcclusionCullingSettings ReflectionProbe'.split())
ENGINE_TYPES = set('MonoScript AssetBundle Transform RectTransform GameObject Camera AudioListener AudioSource BoxCollider SphereCollider CapsuleCollider MeshCollider Rigidbody NavMeshSettings RenderSettings QualitySettings PlayerSettings GraphicsSettings PhysicsManager Physics2DSettings InputManager TagManager TimeManager AudioManager BuildSettings PreloadData MonoManager RuntimeInitializeOnLoadManager DelayedCallManager ResourceManager'.split())


def classify(meta, tree=None, text=None):
    """Conservative classification: keep unknown text, exclude only explained structures."""
    if isinstance(tree, dict) and isinstance(tree.get('importGridList'), list):
        return 'kept/scenario_books', 'Utage importGridList/rows/strings structure; includes dialogue and configuration books'
    script = tree.get('m_Script') if isinstance(tree, dict) else None
    candidate = tree
    if isinstance(script, str) and text is None:
        text = script
    if text is not None:
        try:
            candidate = json.loads(text)
        except (ValueError, TypeError):
            pass
    if isinstance(candidate, dict) and 'skeleton' in candidate and ('bones' in candidate or 'slots' in candidate):
        return 'excluded/spine', 'Spine skeleton JSON (skeleton with bones/slots), retained in full'
    if meta.get('script_namespace', '') == 'Spine' or meta.get('script_namespace', '').startswith('Spine.'):
        return 'excluded/spine_components', 'Serialized Spine runtime/animation component identified by MonoScript namespace; retained in full'
    if isinstance(text, str) and re.search(r'(?m)^\s*(?:size|bounds):\s*\d+,\s*\d+', text) and re.search(r'(?m)^\s*(?:filter|rotate|xy):', text):
        return 'excluded/spine_atlas', 'Texture atlas region/coordinate format, retained in full'
    if meta.get('status') == 'unreadable':
        return 'excluded/unreadable', 'Structured parse failed; exact original object/file bytes and error retained'
    if meta.get('kind') == 'il2cpp_literals':
        return 'kept/ui_candidates', 'IL2CPP managed string-literal table; candidate strings require later review'
    typ = meta.get('type', '')
    if typ in RENDERING_TYPES:
        return 'excluded/rendering', f'Unity {typ} rendering/media data; serialized fields and binary sidecars retained'
    if typ in ENGINE_TYPES:
        return 'excluded/engine_metadata', f'Unity {typ} structural metadata; retained for reference'
    containers = ' '.join(meta.get('containers', [])).lower()
    origin = meta.get('source_path', '').lower()
    if 'mdf_output' in containers or '/masterdata/' in origin.replace('\\', '/'):
        return 'kept/masterdata', 'Masterdata provenance; all fields preserved'
    if meta.get('kind') == 'binary':
        return 'excluded/binary', 'Non-text payload or companion resource; exact source retained'
    if meta.get('type') == 'TextAsset' and isinstance(text, str) and ('\x00' in text or any(0xDC80 <= ord(c) <= 0xDCFF for c in text)):
        return 'excluded/binary_textasset', 'TextAsset contains binary payload (NUL or non-UTF8 bytes); payload and serialized representation retained'
    if typ == 'MonoBehaviour':
        return 'kept/ui_candidates', 'Custom serialized behaviour; possible UI/localization fields kept without content filtering'
    if text is not None or tree is not None:
        return 'kept/other_text', 'Other serialized/text material; preserved for later UI and terminology analysis'
    return 'excluded/binary', 'Raw payload retained; no structured/text decoder applied successfully'
