# 몬타디 Novel 번역·검수 운영

명령은 저장소 루트에서 Python 3.14 이상으로 실행한다. 초기 환경 구성은 루트 README를 따른다. 기존 workspace는 `D:\monmusu_workspace`를 계속 사용한다. gctrans의 현행 `prepare → Codex 초벌 → PRO 의미검수 → check → apply` 흐름을 따른다. 도구는 모델이나 API를 호출하지 않는다. 초벌과 의미검수는 작업자가 파일에 기록하며, 코드가 의미검수를 수행했다고 표시하지 않는다.

## 정본

| 위치 | 역할 |
| --- | --- |
| `HOLD_POLICY.md` | 사용자가 동결한 프로젝트 HOLD 최상위 정본. 수정·자동 갱신 금지 |
| `translation/novel/scenarios/` | 검증된 원문 입력 4,146개, 159,834행 |
| `translations/ko/names.json` | 검수 승인된 exact JP 이름 표시 |
| `translation/knowledge.jsonl` | 현재 승인된 실제 내용과 명시적 scope를 가진 Knowledge. 용어집은 `kind=term` |
| `translation/holds.jsonl` | 검수 확정된 행별 HOLD, 사유, 원문 해시, 위치, 검수 ID |
| `work/novels/<batch>/draft.json` | 진행 중인 초벌과 지식 제안 |
| `work/novels/<batch>/reviews/<round>/review.json` | 별도 PRO 검수본. round별 초벌 스냅샷과 binding도 보존 |
| `work/novels/<batch>/progress.json` | 행별 초벌 상태, 검수 상태, 적용 상태와 기술적 오류 |
| `translation/state/` | 입력 catalog, 적용된 행 상태, 적용 영수증, 복구 journal |
| `translations/ko/novels/` | 승인된 행만 들어 있는 로컬 결과. 중복 JP도 별도 행으로 보존 |
| `knowledge-layer/provenance/current-changes/` | 승인된 지식의 변경 전후 근거. 정상 번역 입력에는 포함하지 않음 |

현재 JP와 장면 전체를 우선하고, exact Names와 명시된 scope 안의 current Knowledge를 참고한다. `source_ids`는 지식이 관찰된 출처이며 전역 적용 권한이 아니다. `scope`가 적용 범위를 정한다. 과거 캐시와 보관본에서 current Knowledge를 자동 재생성하지 않는다.

루트 정책 SHA-256은 `702421dfdffe964ddfd69119c0a37d5c595dbc1c3afd4f3f5f179350782f3099`로 고정했다. 2026-11-01 사용자가 직접 수정한 파일을 새 정본으로 동결하도록 명시적으로 승인했다. 모든 명령에서 원본을 검사하고 배치에는 바이트가 동일한 사본만 둔다. 사용자가 승인한 정책 개정이 없다면 해시 상수를 바꿔 오류를 넘기지 않는다. 서비스 제한이 실제 적용되면 해당 행과 사유를 기록하고 처리 가능한 작업을 계속한다.

## 시작과 초벌

기존 workspace에는 전체 입력과 초기화 결과가 보존되어 있다. 새 clone에서는 원본 추출 스냅샷을 준비하고 intake를 생성한 뒤 init을 실행한다. 이후 같은 명령을 다시 실행해도 초벌과 검수 내용을 초기화하지 않는다. 새 추출의 기본 경로를 사용할 때는 intake generate와 novel init에 `--snapshot extractor/output-current`를 전달한다.

```powershell
python -X utf8 tools/update/cli.py novel init
python -X utf8 tools/update/cli.py novel status --out translation/state/status.json
```

다음 예시는 `10001A0_Nml`의 26행을 첫 배치로 준비한다. 기존 배치가 있으면 파일을 보존하고 상태를 확인한다. 작업 진행 상태는 문서의 고정 수치 대신 `novel status --batch ...`로 확인한다.

```powershell
python -X utf8 tools/update/cli.py novel prepare --batch work/novels/20261101-001 --scenario 10001A0_Nml
```

새 배치는 `--scenario`를 반복해 여러 장면을 지정한다. 이름은 manifest의 `scenario_name`과 완전히 같아야 한다. 끝 공백과 Unicode 변형도 구별한다. `--next`는 아직 배치에 배정되지 않은 다음 장면 하나를 준비한다. 작업량 제한은 없고 여러 장면을 직접 지정할 수 있다. 이미 배정된 미완료 작업은 status에 나온 기존 폴더에서 이어간다.

```powershell
python -X utf8 tools/update/cli.py novel prepare --batch work/novels/20261101-002 --next
```

배치의 `TASK.md`, `HOLD_POLICY.md`, `context.json`, `source/` 전체를 읽고 `draft.json`을 편집한다. source에는 장면 전체가 있고 draft에는 해당 배치의 대상 행이 있다. 원문 입력에 작성해 둔 KO와 검수 메모는 최초 prepare 때 초벌로 가져오며, 기존 review 상태를 자동 승인으로 승격하지 않는다. 이후 초벌 작업은 배치 파일에서 이어간다.

| 초벌 필드 | 작성 방법 |
| --- | --- |
| `ko` | 한국어 초벌. HOLD 행은 빈 문자열 |
| `hold` | 미판정 `null`, 번역 가능한 행 `false`, 보류할 행 `true` |
| `reason` | HOLD는 사유 필수. 실제 서비스 제한은 그 범위와 이유를 명시 |
| `translation_status` | 작성 중 `pending`, 다음 단계에 넘길 행 `drafted`. HOLD도 판정 완료 후 `drafted` |
| `notes` | 번역자 메모 |
| `changes` | Names/Knowledge 변경 제안 목록. 초벌은 `approved:false` |

나머지 행 필드는 원문·위치 정보다. `speaker`는 원래 Arg1이며, 선택지와 연출 명령에서는 실제 화자가 아닐 수 있다. 이 두 종류의 Arg1을 화자 지식의 근거로 자동 사용하지 않는다.

저장한 초벌 파일 자체가 재개 지점이다. 진행 요약을 갱신하려면 다음을 실행한다.

```powershell
python -X utf8 tools/update/cli.py novel checkpoint --batch work/novels/20261101-001
```

태그·변수·보호 토큰·실제 개행·literal `\n`/`\r`은 철자와 순서를 유지한다. KO 안에서 문자 위치는 번역 길이에 따라 바뀔 수 있지만 원문 태그의 위치 기록은 변경하지 않는다. PageCtrl·Voice·source_cells는 원본 그대로 둔다. 구조 오류는 기술 오류로 보고하며 콘텐츠 HOLD로 바꾸지 않는다.

## PRO 검수와 부분 반영

```powershell
python -X utf8 tools/update/cli.py novel review --batch work/novels/20261101-001 --round 001
```

`drafted`이며 구조 검사를 통과한 행만 `reviews/001/review.json`으로 만든다. 미완료 행이나 구조 오류 행은 다음 작업으로 남기고 정상 행을 진행한다. HOLD도 하나의 완료된 초벌 판정으로 검수에 전달한다. 기존 round 파일은 재실행으로 덮어쓰지 않는다.

PRO는 배치의 정책·source 전체·context와 round의 초벌 스냅샷을 읽고 다음을 검수한다.

- 원문의 의미, 누락·추가, 말투·호칭, 사건·관계의 연속성
- 행별 HOLD 판정과 사유
- Names·Knowledge의 실제 내용, 범위, 중복·충돌과 근거

검수 완료 행의 `review_status`를 `approved`, 수정 요청은 `changes_requested`, 미검수는 `pending`으로 둔다. 검수자가 `ko`, `hold`, `reason`, `review_note`를 확정한다. 실제 검수 후 문서의 고유 `review_id`, `pro_review_complete:true`, `knowledge_review`를 작성한다. 신규 지식이 없으면 그 결론을 적고 `changes:[]`를 유지한다. 완료 flag는 실제 의미검수나 검수자의 신원을 자동 증명하지 않는다.

```powershell
python -X utf8 tools/update/cli.py novel check --batch work/novels/20261101-001 --round 001
python -X utf8 tools/update/cli.py novel apply --batch work/novels/20261101-001 --round 001
```

apply는 **approved 행만** 반영한다. pending과 changes_requested 행은 완료로 처리하지 않는다. 한 행의 HOLD는 그 행만 보류하고 나머지 행·장면과 검수 승인된 지식 변경을 진행한다. 승인된 번역과 지식, HOLD ledger, 행 상태, 적용 영수증을 하나의 복구 가능한 파일 transaction으로 기록한다.

로컬 결과의 HOLD 행은 `ko:null`, `hold:true`와 `[시나리오명 - N행 HOLD]` 표시 메타데이터를 가진다. 원문 JP와 제어 정보는 그대로 남는다. 표시문을 KO 본문에 넣어 제어 태그를 잃지 않도록 분리했다. 미검수 행은 로컬 결과에서 제외되며 `pending_rows`로 집계한다.

같은 검수본의 apply 재실행은 이미 반영한 영수증을 반환한다. 반영한 검수본은 변경하지 않고 남은 행을 round `002` 등으로 진행한다. 같은 배치에서 이미 반영한 행을 교정할 때는 새 배치를 사용한다. 다른 배치에서 적용된 결과를 오래된 초벌·검수본으로 덮어쓰지 않는다.

```powershell
python -X utf8 tools/update/cli.py novel review --batch work/novels/20261101-001 --round 002
python -X utf8 tools/update/cli.py novel prepare --batch work/novels/retry-001 --scenario 10001A0_Nml --retry-holds
python -X utf8 tools/update/cli.py novel prepare --batch work/novels/correction-001 --scenario 10001A0_Nml --correction
```

`--retry-holds`는 미처리 행과 HOLD 행, `--correction`은 해당 장면 전체를 선택한다. HOLD 해제는 같은 초벌·검수 절차를 거치며 승인되면 그 행의 현행 HOLD 기록만 제거한다. 이전 검수본과 영수증은 남긴다.

## Knowledge와 glossary

gctrans의 record 종류와 현재 지식 검증·projection·변경 방식은 유지한다. `term`, `entity`, `profile`, `speech`, `relationship`, `claim_guard`, `contextual_term` 등의 실제 내용을 저장한다. current record는 `approved`, `content_available:true`, 유효한 `value`, 명시적 scope와 `origin.review_id`가 있어야 한다.

몬타디에서는 record의 `source_ids`와 `scope.source_ids`가 **정확한 scenario_name 목록**이다. `source_id`의 번들 SHA와 혼동하지 않는다. `scope:"global"`은 실제로 전역 적용을 검수 승인한 경우만 쓴다. 다른 장면에서 관찰된 지식은 참고로 보여도 `effective_authority:"reference"`로 표시한다. scope 안에서 원문과 일치하는 승인 용어는 context 크기 예산 때문에 빠지지 않는다. 나머지 생략 ID는 `omitted_ids`에 남는다.

다음은 형식 설명용 예시이며 실제 지식에 추가하지 않았다.

```json
{
  "kind": "knowledge",
  "id": "term:example",
  "old_sha256": null,
  "approved": false,
  "value": {
    "id": "term:example",
    "kind": "term",
    "status": "approved",
    "content_available": true,
    "scope": {"source_ids": ["10001A0_Nml"]},
    "source_ids": ["10001A0_Nml"],
    "value": {"source_text": "用語", "ko": "용어"},
    "origin": {"review_id": "최종 검수 ID", "evidence": "장면명과 확인한 row_id, 관찰 근거"}
  }
}
```

신규 record는 `old_sha256:null`, 갱신은 `translation_knowledge.record_sha256(현재 record)`를 사용한다. 같은 지식은 같은 ID를 갱신한다. 폐기는 `operation:"retire"`, `old_sha256`, `reason`, `approved:true`를 사용한다. Names 변경은 `kind:"name"`, `jp`, `old_ko`, `ko`, `approved`로 제안한다. 미승인 변경은 current에 반영하지 않는다.

배치가 사용한 Names/Knowledge나 새 적용 용어가 바뀌면 check가 재검토 필요를 알린다. 새로운 배치를 준비해 최신 context로 교정하고 이전 초벌·검수본은 보존한다. 관련 없는 지식 변경만으로 모든 배치를 무효화하지 않는다.

## 중단·재개와 검사

파일 편집 도중에는 저장을 마친 뒤 중단한다. 다음 실행은 배치의 초벌·검수 파일을 그대로 읽는다. 도구 실행 도중 종료되면 OS 잠금은 해제되고, 다음 명령이 남은 journal을 먼저 복구한다. journal 파일을 직접 삭제하지 않는다. 외부 편집과 충돌하면 자동 덮어쓰기하지 않고 충돌 경로를 보고한다.

```powershell
python -X utf8 tools/update/cli.py novel status --batch work/novels/20261101-001
python -X utf8 tools/update/cli.py novel recover
python -X utf8 tools/update/cli.py novel verify
python -X utf8 extractor/novel_intake.py verify
python -X utf8 -m unittest discover -s tools -p test_novel_workflow.py -v
```

전체 status의 pending은 아직 로컬 최종 반영되지 않은 행이다. 초벌·검수 진행은 배치별 status에서 따로 확인한다. 전체 verify는 원문 해시·제어 구문·적용 상태·로컬 결과·HOLD ledger·current 지식을 검사한다. 원본 book까지 다시 대조할 때는 intake verify를 실행한다.

## gctrans에서 달라진 부분

| 항목 | 몬타디 적용 |
| --- | --- |
| 입력 | 쉼표 TextAsset 대신 검증된 Utage book/grid/행/셀 |
| 식별 | 숫자 ID 대신 exact 장면명, 원본 source_id와 row_id. Windows 파일명만 장면명 해시로 구별 |
| 제어 | GC 34 UTF-16칸·3줄 reflow를 적용하지 않고 태그·변수·개행 보존 |
| 중복 | JP→KO dict로 합치지 않고 행 배열 유지. 같은 JP의 서로 다른 번역·HOLD가 공존 가능 |
| 재개 | 초벌·검수·반영을 행별로 관리하고 round를 추가해 부분 진행 |
| HOLD 출력 | 표시문은 별도 메타데이터. KO가 없는 행에서도 원문 제어 정보 보존 |
| 배포 | apply는 로컬 검수 결과까지. 별도 MonmusuMod adapter가 이 행별 결과와 위치를 사용 |

Novel runtime은 몬타디의 행별 원문 대조를 지원하는 manifest를 사용한다. UI/master 배포 형식과 hash/size descriptor는 gctrans를 따른다. [UI 운영 안내](../translation/ui/README_KO.md)에 전체 입력, 부분 검수, manifest 생성을 정리했다. Git commit/push나 CDN 게시를 자동 실행하는 명령은 없다. 참조한 gctrans 구현과 필수 차이는 [UPSTREAM_KO.md](UPSTREAM_KO.md)에 기록했다. 로컬 reference 원본은 Git에 포함하지 않는다.

검수 결과를 게임 적용 후보로 만들 때는 `python -X utf8 tools/update/cli.py mod-package` 또는 [플러그인 빌드 절차](../plugin/README_KO.md)를 사용한다. 이 단계는 `dist/`에 로컬 패키지를 작성하며 게임 설치·실행·CDN 게시를 수행하지 않는다. 실제 표시 확인은 별도로 기록한다.

사용자 승인으로 진행한 설치는 `plugin/Install.ps1`을 사용하며, 2026-11-01 첫 시나리오의 [실기 결과](../plugin/RUNTIME_TEST_KO.md)를 확인했다. XUnity는 사용자 지시로 비활성 상태를 유지한다. 재실행은 지정된 `dmm-ex-launcher.ps1`에서 `mnms_td_r18`을 선택한다. 설치·실기 작업으로 번역본, 검수본, 동결 HOLD 정책을 변경하지 않는다.
