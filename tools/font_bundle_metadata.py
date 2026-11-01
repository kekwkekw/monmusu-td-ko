"""Extract compatibility metrics for a locally supplied TMP font (no publication)."""
import hashlib
import json
from pathlib import Path
import sys
import UnityPy

source, destination = map(Path, sys.argv[1:])
env = UnityPy.load(str(source))
fonts = [obj.read_typetree() for obj in env.objects if obj.type.name == 'MonoBehaviour']
fonts = [font for font in fonts if 'm_FaceInfo' in font and 'm_CharacterTable' in font]
if len(fonts) != 1:
    raise ValueError('Expected one TMP font asset')
font = fonts[0]
point = float(font['m_FaceInfo']['m_PointSize'])
if not point.is_integer() or not 1 <= point <= 4096:
    raise ValueError('Font point size cannot be represented by this player')
destination.write_bytes((json.dumps({'schema': 'monmusu-tmp-metrics-v1',
    'bundle_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'asset': font['m_Name'], 'point_size': int(point)}, indent=2) + '\n').encode('utf-8'))
