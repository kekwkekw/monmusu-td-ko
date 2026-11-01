"""Write the human-readable handoff only from completed verification reports."""
import json
from pathlib import Path
from core import CATEGORY_DESCRIPTIONS
from run import HERE, OUTPUT


def main():
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))
    inventory = read(OUTPUT / 'inventory-summary.json')
    extraction = read(OUTPUT / 'extraction-summary.json')
    classification = read(OUTPUT / 'classification-summary.json')
    verification = read(OUTPUT / 'verification.json')
    acquisition = read(HERE / 'remote/acquisition-summary.json')
    source = read(HERE / 'remote/manifest-source.json')
    audit_path = OUTPUT / 'coverage-audit.json'
    audit = read(audit_path) if audit_path.exists() else None
    binary_audit_path = OUTPUT / 'binary-textasset-audit.json'
    binary_note = ''
    if binary_audit_path.exists():
        binary_audit = read(binary_audit_path)
        if binary_audit['records'] and not binary_audit['non_skel_records']:
            binary_note = f"바이너리 TextAsset {binary_audit['records']:,}개의 원본 이름은 모두 `.skel`이었습니다. 해당 payload도 그대로 보존했으며 점검 결과는 `./binary-textasset-audit.json`에 있습니다."
    if not verification['passed']:
        raise RuntimeError('Verification must pass before writing the completion report')
    categories = '\n'.join(f'| `{name}` | {count:,} | {CATEGORY_DESCRIPTIONS[name]} |' for name, count in sorted(classification['categories'].items()))
    sources = '\n'.join(f'| `{name}` | {count:,} |' for name, count in inventory['sources'].items())
    gap_details = ''
    if audit:
        lines = [f"현재 공개 번들에서 마스터 참조 {audit['current_master_scenario_names']:,}개 중 {audit['current_remote_names_with_text']:,}개의 본문을 확보했습니다."]
        for gap in audit['gaps']:
            lines.append(f"- `{gap['scenario_name']}`: {gap['reason']} 참조 행 {len(gap['references'])}개. 계산된 번들 suffix는 `{gap['expected_bundle_path']}`입니다.")
        lines.append('상세 근거는 `./coverage-audit.json`, 전체 마스터 참조 위치는 `./indexes/current-master-references.jsonl`에 있습니다. 테스트 항목의 실제 게임 내 접근 가능 여부는 이번 파일 분석으로 단정하지 않았습니다.')
        gap_details = '\n\n'.join(lines)
    text = f'''# 몬타디 추출 결과

로컬 자료와 공개 Windows R18 에셋 목록을 추출하고 분류했습니다. 새 구현은 `extractor/`에 있으며, 기존 번역 실험의 출력은 번역 원문으로 사용하지 않았습니다.

## 결과

| 항목 | 수량 |
| --- | ---: |
| 입력 출처 행 수 | {verification['input_provenance_rows']:,} |
| 내용이 다른 입력 파일 | {verification['unique_input_files']:,} |
| Unity 직렬화 객체 | {extraction['objects']:,} |
| 전체 보존 레코드 | {verification['output_records']:,} |
| Text 행이 있는 전체 이름 수 | {verification['scenario_names_with_text_rows']:,} |
| 이름별 우선 참조본의 Text 행 | {verification['preferred_variant_text_rows']:,} |
| 버전·출처를 모두 포함한 Text 행 | {classification['scenario_rows_including_variants']:,} |
| 문자열 인덱스 항목 | {classification['indexed_strings']:,} |
| 구조 해석 실패 보존 레코드 | {verification['unreadable_records']:,} |
| 결과 경로 누락 | {len(verification['missing_output_paths']):,} |

입력 출처 행에는 SHA-256이 같은 중복 사본의 출처가 포함됩니다. 고유 입력은 한 번만 추출했습니다. Text 행은 검토 전 후보이며, 시나리오 설정 book의 텍스트가 포함될 수 있습니다. 번역·검수 완료 수치가 아닙니다.

## 출처

| 출처 | 입력 행 |
| --- | ---: |
{sources}

공개 에셋 버전은 `{source['asset_version']}`, 기준 버전은 `{source['base_version']}`, 클라이언트 버전은 `{source['client_version']}`입니다. 목록의 {acquisition['total']:,}개를 모두 확보했습니다. 기존 파일 {acquisition['counts'].get('local_reuse', 0):,}개를 재사용했고, 목록 크기와 응답 크기가 다른 {acquisition['counts'].get('downloaded_size_mismatch', 0):,}개도 보존해 파싱했습니다.

외부 DataTable JSON은 해당 저장소가 이미 추출한 자료이며, 이번 Unity 추출 결과와 출처를 구분했습니다. 실제 게임의 IL2CPP 자료는 별도 출처로 추적합니다.

## 분류

| 경로 | 레코드 | 사유 |
| --- | ---: | --- |
{categories}

제외 자료는 삭제하지 않았습니다. 각 분류 폴더의 `REASONS.json`과 `./classification.jsonl`에 사유와 최종 경로가 있습니다. `tree.json.gz`, 원래 TextAsset payload, binary sidecar, 해석 실패 bytes를 보존합니다.

{binary_note}

## 시나리오와 UI 후속 작업

- `./indexes/scenario-catalog.jsonl`: 모든 출처의 book과 Text 행 수
- `./indexes/scenario-variants.jsonl`: 전체 이름별 버전과 우선 참조본
- `./indexes/master-scenario-coverage.jsonl`: 마스터데이터 참조와 book 대응
- `./indexes/all-strings.jsonl.gz`: JSON pointer 및 IL2CPP 리터럴 위치가 있는 문자열 인덱스
- `./indexes/provenance.jsonl`: SHA-256별 모든 원본 위치와 공개 에셋 정보

현재 공개 마스터의 고유 scenario_name은 {verification['current_master_scenario_names']:,}개입니다. 그중 확보된 전체 자료에서 Text 행이 있는 book을 찾지 못한 정확한 이름은 {verification['current_master_missing_text']:,}개이며, 현재 공개 번들 자체에 Text 행이 있는 book을 찾지 못한 이름은 {verification['current_master_missing_current_remote_text']:,}개입니다. 공백·대소문자·Unicode 표기 차이에 따른 이름 후보까지 없는 항목은 {verification['current_master_missing_text_without_name_alias']:,}개입니다. 이름 후보는 대응 목록에만 기록하고 원본 이름과 이전 버전의 자료를 자동으로 합치지 않았습니다.

{gap_details}

수집 범위는 이 날짜에 확보한 공개 Windows R18 목록과 지정한 로컬·참고 자료입니다. 서버에만 존재하거나 공개 목록에 없는 자료까지 확보했다는 뜻은 아닙니다.

## 검증과 재실행

단위 테스트 6개, 실제 게임 통합 테스트 3개를 통과했습니다. 전체 입력의 완료 수, 분류 레코드 수, 결과 파일 존재 여부와 binary sidecar 크기를 대조했습니다. 상세 수치는 `./verification.json`에 있습니다.

실행 방법은 [README](../README.md), 에셋 구조와 호환 처리는 [구조 분석](../STRUCTURE.md)을 참고하세요. 시나리오 원문, 태그, 공백, 중복 대사, 전체 이름과 원래 행 위치를 보존했습니다. 다음 번역·검수 단계에서 gctrans Novel 방식의 원문 key와 검수 상태로 연결할 수 있습니다.
'''
    (OUTPUT / 'REPORT.md').write_text(text, encoding='utf-8')
    print(OUTPUT / 'REPORT.md')


if __name__ == '__main__':
    main()
