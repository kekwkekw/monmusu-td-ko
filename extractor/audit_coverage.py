"""Explain master/book coverage gaps using the preserved public manifest and rows."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from core import dump, json_line, load_tree
from run import HERE, OUTPUT, records


def bundle_suffix(logical_path):
    return hashlib.md5(logical_path.lower().replace('/', '-').encode('utf-8')).hexdigest() + '.bytes'


def scenario_references(value, pointer=''):
    if isinstance(value, dict):
        for key, child in value.items():
            escaped = key.replace('~', '~0').replace('/', '~1')
            location = pointer + '/' + escaped
            if key == 'scenario_name' and isinstance(child, str) and child:
                yield child, location, {k: value[k] for k in ('id', 'story_id', 'title', 'chapter_name') if k in value}
            else:
                yield from scenario_references(child, location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from scenario_references(child, pointer + '/' + str(index))


def main():
    verification = json.loads((OUTPUT / 'verification.json').read_text(encoding='utf-8'))
    if not verification['passed']:
        raise RuntimeError('Complete output verification before auditing coverage')
    manifest = json.loads((HERE / 'remote/ablist.json').read_text(encoding='utf-8'))
    assets = {asset['path']: asset for asset in manifest['data']}
    master_suffix = bundle_suffix('MdF_Output/Data')
    master_sources = [r for r in records(OUTPUT / 'inputs.jsonl')
                      if r['label'] == 'current_remote' and r.get('remote_asset', {}).get('path') == master_suffix]
    references = defaultdict(list)
    for item in master_sources:
        digest = item['sha256']
        source = OUTPUT / 'raw' / digest[:2] / digest
        for record in records(source / 'classification-records.jsonl'):
            if record['category'] != 'kept/masterdata':
                continue
            for name, pointer, context in scenario_references(load_tree(Path(record['output_path']))):
                references[name].append({'source_id': record['id'], 'table': record.get('name'),
                                         'output_path': record['output_path'], 'pointer': pointer, 'row': context})
    coverage = list(records(OUTPUT / 'indexes/master-scenario-coverage.jsonl'))
    current = [row for row in coverage if 'current_remote' in row['master_sources']]
    expected = {row['scenario_name'] for row in current}
    if set(references) != expected:
        raise RuntimeError('Current master audit does not cover the same names as full verification')
    with (OUTPUT / 'indexes/current-master-references.jsonl').open('w', encoding='utf-8') as stream:
        for name, refs in sorted(references.items()):
            stream.write(json_line({'scenario_name': name, 'references': refs}))
    gaps = []
    for entry in current:
        if entry['current_remote_has_text']:
            continue
        name = entry['scenario_name']
        suffix = bundle_suffix('ScenarioChapter/' + name + '.book')
        refs = references[name]
        is_test = all(ref['row'].get('chapter_name') == 'scn_test' and
                      str(ref['row'].get('title', '')).startswith('テスト') for ref in refs)
        listed = suffix in assets
        if is_test and not listed:
            reason = '마스터의 scn_test 장 및 テスト 제목에서 참조하지만 공개 목록에 대응 번들이 없습니다.'
            status = 'test_reference_absent_from_public_manifest'
        elif not listed:
            reason = '표준 ScenarioChapter 이름 규칙으로 계산한 번들이 공개 목록에 없습니다.'
            status = 'absent_from_public_manifest'
        else:
            reason = '공개 목록에는 대응 번들이 있으나 현재 출처의 정확한 이름으로 Text 행을 찾지 못했습니다.'
            status = 'listed_but_no_exact_text_book'
        gaps.append({**entry, 'expected_bundle_path': suffix, 'listed_in_current_manifest': listed,
                     'status': status, 'reason': reason, 'references': refs})
    result = {'current_master_scenario_names': len(current),
              'current_remote_names_with_text': sum(row['current_remote_has_text'] for row in current),
              'current_master_reference_rows': sum(map(len, references.values())),
              'gaps': gaps,
              'note': 'Missing public entries are not extraction failures. Test titles are source evidence; runtime reachability is not inferred.'}
    dump(OUTPUT / 'coverage-audit.json', result)
    print(json.dumps({'current_master_names': len(current), 'gaps': len(gaps),
                      'statuses': [gap['status'] for gap in gaps]}), flush=True)


if __name__ == '__main__':
    main()
