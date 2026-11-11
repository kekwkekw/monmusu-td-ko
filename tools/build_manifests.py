"""Build deterministic public runtime descriptors (no Git/network/game writes)."""
import argparse
import hashlib
from pathlib import Path

from novel_storage import atomic_write, encode, read_json, require
from novel_workflow import policy, POLICY_SHA256
import ui_workflow
import image_catalog

ROOT = Path(__file__).resolve().parents[1]


def approved_grids(document):
    """Only headers referenced by reviewed rows become routing aliases."""
    used = {(row['grid_index'], row['header_row_index_0based']) for row in document['rows']}
    headers = {(h['grid_index'], h['header_row_index_0based']): h for h in document['headers']}
    require(used <= headers.keys(), 'Reviewed row missing its header')
    return sorted({headers[key]['grid_name'] for key in used})


def payloads(root):
    policy(root)
    folder = root / 'translations/ko'
    ui_workflow.verify(root)
    files = {name: (folder / name).read_bytes() for name in ['names.json', 'master.json', 'ui.json', 'master-bindings.json']}
    scenarios = []
    for path in sorted((folder / 'novels').glob('*.json'), key=lambda path: path.name):
        document = read_json(path)
        require(document['schema'] == 'monmusu-reviewed-novel-v1', 'Invalid reviewed Novel schema')
        require(all(row['review_status'] == 'reviewed' and row['policy_sha256'] == POLICY_SHA256 for row in document['rows']),
                'Unreviewed Novel in publication')
        relative = 'novels/' + path.name
        files[relative] = path.read_bytes()
        scenarios.append({'scenario_name': document['scenario_name'], 'path': relative, 'grid_names': approved_grids(document),
                          'sha256': hashlib.sha256(files[relative]).hexdigest()})
    aliases = [grid for entry in scenarios for grid in entry['grid_names']]
    require(len(aliases) == len(set(aliases)) and all(aliases), 'Ambiguous or empty Novel grid alias')
    def entry(name):
        return {'path': name, 'sha256': hashlib.sha256(files[name]).hexdigest()}
    manifest = {'schema': 'monmusu-runtime-manifest-v1', 'policy_sha256': POLICY_SHA256,
                'names': entry('names.json'), 'scenarios': scenarios, 'master': entry('master.json'),
                'ui': entry('ui.json'), 'master_bindings': entry('master-bindings.json')}
    if (folder / 'images.json').exists():
        image_files = image_catalog.validate(folder)
        files.update(image_files)
        manifest['images'] = entry('images.json')
        manifest['image_files'] = [entry(name) for name in sorted(image_files) if name != 'images.json']
    return files, manifest


def build(root, check=False):
    files, manifest = payloads(root)
    items = [{'kind': kind, 'path': name, 'sha256': hashlib.sha256(files[name]).hexdigest(), 'size': len(files[name])}
             for kind, name in [('master', 'master.json'), ('general_ui', 'ui.json'), ('master_bindings', 'master-bindings.json')]]
    descriptor = {'schema_version': 1, 'locale': 'ko', 'origin': 'local', 'files': items,
                  'revision': 'mm-ui-' + hashlib.sha256(encode(items)).hexdigest()[:24]}
    for name, value in [('manifest.json', manifest), ('ui/manifest.json', descriptor)]:
        path = root / 'translations/ko' / name
        if check:
            require(path.read_bytes() == encode(value), 'Stale publication descriptor: ' + name)
        else:
            atomic_write(path, encode(value))
    return hashlib.sha256(encode(manifest)).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(('VERIFIED ' if args.check else 'GENERATED ') + build(ROOT, args.check))
