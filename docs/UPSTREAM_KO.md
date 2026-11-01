# gctrans와 몬타디 적용 범위

이 저장소는 [kekwkekw/gctrans](https://github.com/kekwkekw/gctrans)의 Novel 운영 흐름과 current Knowledge 구조를 바탕으로 한다. 정상 순서는 원문 준비 → Codex 초벌 → ChatGPT PRO 의미검수 → 로컬 적용·검증 → 승인된 Git 반영이다.

2026-11-01에 확인한 구현은 `upstream-reference.json`의 Git blob SHA로 식별한다. `tools/translation_knowledge.py`는 해당 gctrans 모듈을 가져와 지식의 `source_ids`와 scope 검증만 몬타디 exact 장면명에 맞췄다. Names/current Knowledge, 근거와 유효 범위, 변경 preimage, 승인된 upsert/retire와 provenance 기록을 유지한다.

| gctrans 구성 | 몬타디 구성과 필요한 차이 |
| --- | --- |
| `docs/OPERATOR_KO.md` | 같은 운영 문서 위치와 역할 |
| `tools/update/cli.py novel ...` | 같은 명령 진입점. 기존 `tools/novel_workflow.py`도 계속 사용 가능 |
| `translation/knowledge.jsonl`, `translation/holds.jsonl` | 같은 current 지식·행별 HOLD 역할 |
| `translations/ko/names.json`, `translations/ko/novels/` | 검수 승인된 로컬 결과만 저장 |
| `work/novels/` | 원문·초벌·검수 자료를 로컬에서 보존하고 Git 제외 |
| `knowledge-layer/provenance/current-changes/` | 변경 근거 보존. 정상 context에는 읽지 않음 |
| GC TextAsset 숫자 ID·쉼표 형식 | 몬타디 Utage grid/행/셀, 정확한 전체 장면명과 원본 row_id |
| exact JP dictionary | 중복 원문 위치를 잃지 않는 행 배열. HOLD 표시문도 별도 필드 |
| GC 전용 34 UTF-16칸·3줄 reflow | 몬타디는 원문 태그·변수·개행 순서 보존 |
| `translation/HOLD_POLICY.md` | 사용자가 지정하고 동결한 **루트 `HOLD_POLICY.md`** 유지 |

몬타디에서는 미완료 행·HOLD 행을 별도 상태로 남기면서 나머지 행과 장면의 처리를 이어간다. PRO 검수는 행별 승인과 round로 저장하며 자동 의미검수로 간주하지 않는다. gctrans의 GCMod 빌드·배포·기존 legacy 번역 패키지를 그대로 가져오지 않았다. 몬타디용 runtime adapter는 [plugin/](../plugin/README_KO.md)에 별도로 구현했다. 실제 표시 확인과 CDN 게시는 후속 단계다.

추출기 구조 참고 자료는 [MonmusuPlayer](https://github.com/BithreenGirlen/MonmusuPlayer), [DataTable](https://github.com/PackageInstaller/DataTable/tree/game/MonmusuTDx), [몬무스 데이터 사이트](https://github.com/monmusu-td-db/monmusu-td-db.github.io)다. 게임의 원본 번들과 추출 결과, 참고 저장소 clone은 로컬에 보존하며 이 소스 저장소에 넣지 않는다.
