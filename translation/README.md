# 몬타디 Novel 번역 입력

번역·검수 파이프라인은 [운영 안내](OPERATOR_KO.md)를 따른다. `tools/novel_workflow.py`가 gctrans 방식의 초벌, PRO 검수, 행별 HOLD, 현재 Names·Knowledge, 중단 후 재개와 로컬 반영을 관리한다. 최초 입력 파일의 편집 내용은 prepare에서 가져오며, 이후 작업은 `work/novels/<batch>/draft.json`과 별도 검수본에서 이어간다.

로컬 `translation/novel/scenarios/`에서 작업할 장면의 JSON을 연다. `translation/novel/manifest.json`은 원래 장면명과 파일명, 우선본의 출처 ID, 원본 위치, 행 수를 연결한다. 이 입력은 Git에 포함하지 않으며, 새 환경에서는 검증된 추출본으로 생성한다. 2026-10-28 검증본에서는 본문이 있는 4,146개 이름을 선택했으며, 총 159,834행을 원래 순서대로 담았다.

## 번역·검수

각 행의 `jp`를 읽고 `ko`에 한국어를 작성한다. 초기 `ko`와 `review_note`는 빈 문자열이다. `translation_status`는 `untranslated`, `review_status`는 `unreviewed`에서 시작한다. 초안을 마친 행에는 예를 들어 `drafted`, 검수한 행에는 `reviewed`를 쓸 수 있다. 검수 의견은 `review_note`에 쓴다. 이 네 칸이 편집 필드다.

| 필드 | 읽는 방법 |
| --- | --- |
| `jp`, `jp_sha256` | 치환에 사용할 정확한 일본어 원문과 UTF-8 해시. 공백·개행·태그가 포함된다. |
| `kind`, `speaker`, `command` | `speaker`는 추출본의 `Arg1` 원값이다. 빈 칸은 그대로 둔다. `selection`의 `Arg1`은 분기 대상일 수 있고, `command` 행에서는 효과·연출 명령의 인자일 수 있다. `dialogue`에는 지문도 포함된다. |
| `inline_tags` | `jp` 안의 꺾쇠 태그를 등장 순서와 철자 그대로 기록한다. `start`는 포함, `end`는 제외하는 0 기준 유니코드 코드 포인트 위치다. |
| `page_ctrl`, `voice`, `source_cells` | 페이지 제어값과 보이스 키, 원래 셀 배열. 특수 열이나 헤더 표기도 확인할 수 있도록 `headers[].columns`에 원래 열 이름을 둔다. |
| `row_id`, `message_index_0based` | 선택한 소스 안의 고유 행 ID와 book 전체의 대사 순번. 같은 문장이 두 번 나오면 각각 별도 행이다. |
| `grid_index`, `row_index_0based`, `serialized_row_index`, `physical_line_1based` | 원본 grid 번호, 배열에서의 행 위치, 게임이 기록한 행 번호, 사람이 읽는 grid 내 1 기준 행 번호. `header_row_index_0based`로 해당 헤더를 찾고 `text_column_index_0based`로 원래 Text 셀을 찾는다. |

원문 근거는 `extractor/output/` 아래에서 각 문서의 `source_folder`가 가리키는 `book.json`과 `rows.jsonl`이다. 파일명 뒤의 짧은 해시는 대소문자·끝 공백·유니코드 표기가 다른 이름도 Windows에서 구별한다. JSON 안의 `scenario_name`과 `book_name`은 원래 표기를 유지한다.

## 생성과 검증

workspace 루트에서 실행한다.

```powershell
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/novel_intake.py generate
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/novel_intake.py verify
```

처음 생성할 때는 검증을 마친 전체 파일을 한 번에 작업 폴더에 반영한다. 같은 폴더에 다시 실행하면 이미 작성한 네 편집 필드를 보존하고 원문·위치·파일 목록을 검증한다. `verify`는 한국어의 번역 품질과 검수 상태값의 의미를 판정하지 않는다. 새 추출 스냅샷을 사용하려면 `--snapshot`에 그 경로를, `--out`에 새 작업 폴더를 지정한다.

gctrans Novel의 정확한 JP 키, 행 식별자, 화자·명령·물리 위치를 함께 넘기는 방식을 적용했다. 몬타디의 위치는 Utage book의 grid·행·셀을 기준으로 기록한다. [gctrans 참조](../docs/UPSTREAM_KO.md) · [몬타디 입력 생성기](../extractor/novel_intake.py)
