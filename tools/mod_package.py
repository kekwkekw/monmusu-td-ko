"""Export applied Novel rows to a local runtime/CDN package. No game/network/Git writes."""
import argparse
import hashlib
import json
from pathlib import Path

import novel_workflow as workflow
import build_manifests
from novel_storage import encode, read_json, workspace_lock

ROOT = Path(__file__).resolve().parents[1]


def export(root, destination):
    root, destination = root.resolve(), destination.resolve()
    # Output lives in the repository staging tree, never the source/corpus or game installation.
    if not destination.is_relative_to(root / 'dist'):
        raise ValueError('Runtime package output must be under workspace/dist/')
    with workspace_lock(root):
        catalog = workflow.catalog(root)
        entries = {Path(item['file']).name: item for item in catalog['scenarios']}
        files, scenarios, books = {}, [], []
        total, held = 0, 0
        for path in sorted((root / 'translations/ko/novels').glob('*.json')):
            item = entries[path.name]
            source = workflow.source_document(workflow.get_document(root, item))
            state = workflow.load_state(root, item)
            workflow.verify_target(root, item, source, state)
            result = read_json(path)
            if not result['rows']:
                continue
            relative = 'novels/' + path.name
            files[relative] = path.read_bytes()
            scenarios.append({'scenario_name': result['scenario_name'], 'path': relative, 'grid_names': build_manifests.approved_grids(result),
                              'sha256': hashlib.sha256(files[relative]).hexdigest()})
            total += len(result['rows'])
            held += sum(row['hold'] for row in result['rows'])
            books.append({'scenario_name': result['scenario_name'],
                          'source_folder': source['source_folder']})
        names = read_json(root / 'translations/ko/names.json')
        if not isinstance(names, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in names.items()):
            raise ValueError('Invalid approved Names')
        files['names.json'] = (root / 'translations/ko/names.json').read_bytes()
        if (root / 'translations/ko/master.json').exists():
            files, manifest = build_manifests.payloads(root)
        else:
            manifest = {'schema': 'monmusu-runtime-manifest-v1', 'policy_sha256': workflow.POLICY_SHA256,
                        'names': {'path': 'names.json', 'sha256': hashlib.sha256(files['names.json']).hexdigest()},
                        'scenarios': scenarios}
        destination.mkdir(parents=True, exist_ok=True)
        for relative, raw in files.items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        # Only manifest-listed payloads are loaded; unrelated/stale files cannot become active.
        temporary = destination / 'manifest.json.tmp'
        temporary.write_bytes(encode(manifest))
        temporary.replace(destination / 'manifest.json')
        report = {'status': 'EXPORTED_LOCAL', 'destination': str(destination), 'scenarios': len(scenarios),
                  'reviewed_rows': total, 'translated_rows': total - held, 'hold_rows': held, 'names': len(names),
                  'manifest_sha256': hashlib.sha256(encode(manifest)).hexdigest(), 'source_books': books,
                  'game': 'NOT_RUN', 'network': 'NOT_RUN', 'git': 'NOT_RUN'}
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'dist/MonmusuMod/BepInEx/plugins/MonmusuMod/data')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = export(ROOT, args.out)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_bytes(encode(report))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
