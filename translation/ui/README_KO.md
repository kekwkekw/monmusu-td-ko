# Master / UI 운영

검증된 2026-10-28 추출 스냅샷에서 현재 게임/원격 에셋 우선본을 선택했다. `source/`에는 master 4,158개 에셋의 82,503쌍(142,458회 등장), UI 2,799개 문자열(41,790회 등장)이 있다. 번역이 없는 원문도 모두 보존한다. 표시 용도가 확인되지 않은 일본어 직렬화 필드 81,297건은 `source/ui/other-serialized-candidates.jsonl`에 사유와 위치를 따로 남겼다. 이미지 안의 글자는 이 텍스트 입력에 포함되지 않는다.

gctrans와 같이 배포 master는 `{table: {field: {JP: KO}}}`, 일반 UI는 `{JP: KO}`다. 몬타디 master는 JSON 로더 대신 ScriptableObject를 사용하므로 table은 exact asset name, field는 `table[].tab_name` 같은 직렬화 경로다. 별도 `master-bindings.json`에서 native class도 대조한다. 일본어가 들어 있는 ID·kana·scenario_name도 원문 입력에는 보존하지만 번역 대상으로 승인할 수 없다. master 전체를 일반 UI 사전으로 합치지 않는다.

UI_RESTART001과 MASTER001~012에서 Pro 번역과 자체 재검수를 마친 배포 대상은 UI 1,183행과 Master 74,567행이다. 두 작업 모두 HOLD와 미처리는 0행이다. UI 1,616행과 Master 7,936행은 번역 대상 선정 단계에서 원문 유지로 분류했다. Master 원문 유지 항목에는 `help_window_data/table[].helpId` 같은 도움말 조회 키와 `mission_data/table[].target` 같은 미션 대상 ID·분류 키가 포함된다.

| 위치 | 내용 |
| --- | --- |
| `source/master.json`, `source/ui.json` | KO가 비어 있는 전체 원문 |
| `source/master-sources.json`, `source/master-bindings.jsonl` | 우선본/다른 출처, class, 원본 JSON pointer |
| `source/ui/resources.json`, `source/ui/bindings.jsonl` | 고유 문자열과 모든 등장 위치, literal/code_literal 구분 |
| `reviews/` | 실제 검수자와 변경 근거를 가진 검수본 |
| `../../translations/ko/ui/decisions.json` | 현행 승인 판정과 근거. 새 clone에서도 상태 복원 가능 |
| `../state/ui.json` | 로컬 적용 요약. 중단된 쓰기는 기존 transaction journal로 복구 |

```powershell
python -X utf8 tools/update/cli.py ui-intake --help
python -X utf8 tools/update/cli.py ui status
python -X utf8 tools/update/cli.py ui export --batch UI001
python -X utf8 tools/update/cli.py ui check --review work/ui/UI001/return/review.json
python -X utf8 tools/update/cli.py ui apply --review work/ui/UI001/return/review.json
python -X utf8 tools/update/cli.py manifests
python -X utf8 tools/update/cli.py manifests --check
```

`export`는 미판정 일반 UI, 출현 위치, 기존 승인 UI와 최신 Names·Knowledge를 `work/ui/UI001/INPUT_UI001.zip`으로 묶는다. 새 Pro 채팅에는 이 ZIP과 [시작 프롬프트](../../docs/PRO_START_UI_KO.txt)를 제공한다. 반환 ZIP(`RETURN_UI001.zip`)을 풀어 `review.json`을 `ui check`로 확인한 뒤 `ui apply`를 실행한다. 위 예시는 `work/ui/UI001/return/`에 푼 경우다. [폰트 역할](../../docs/FONT_SELECTION_KO.md)은 시작 프롬프트와 ZIP에도 포함한다.

검수본은 `monmusu-ui-review-v1`, 정책 SHA-256, 고유 `review_id`, `reviewer`, `rows`를 사용한다. 행에는 `lane`(`ui`/`master`), master의 table/field, exact jp, ko, disposition, approved, evidence를 기록한다. `translate`만 배포한다. `hold`는 빈 KO와 사유를 기록하고 해당 행만 보류한다. `keep_source`는 의도적으로 원문을 유지한다. `pending`은 다른 행 진행을 막지 않는다. 개행·태그·변수·숫자를 보존하며 기존 판정 변경에는 이전 행의 canonical JSON SHA-256인 `previous_sha256`가 필요하다. 같은 검수본 재적용은 멱등이다. 정책 정본은 루트 HOLD_POLICY.md이며 이 도구는 수정하지 않는다.

초기 실기용 51건(UI 43, Master 8)은 **Codex 검수**를 거쳤다. `reviews/20261101-001.json`에 당시 정책과 검수 근거를 보존한다. 지금 배포하는 UI/Master 번역의 승인 판정은 `translations/ko/ui/decisions.json`에서 배치별 검수 ID와 함께 확인할 수 있다.

`manifests`는 해시와 크기를 가진 gctrans 형식 `translations/ko/ui/manifest.json`과 전체 runtime `translations/ko/manifest.json`을 함께 작성한다. `apply`/`manifests`는 로컬 파일 작업이며 Git push나 게임 설치를 실행하지 않는다. 배포는 이 결과를 검사한 뒤 Git에 커밋하고 게시한다. CDN은 공개 저장소 `main/translations/ko/`를 사용한다.
