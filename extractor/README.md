# 몬타디 원본 추출기

`extractor/`는 파이프라인의 수집·추출 단계다. 기존 workspace는 `D:\monmusu_workspace`를 계속 사용한다. 번역 API 호출, Git 커밋, push, 게임 파일 수정을 하지 않는다. gctrans Novel 흐름에 맞춰 원문과 위치를 보존하고, 몬타디의 Utage book 형식을 독립적으로 해석한다.

2026-10-28 전체 수집·추출·분류·검증 완료 결과는 [스냅샷 기록](../docs/EXTRACTION_SNAPSHOT_KO.md)에 있다. 세부 REPORT.md와 RESUME.md는 기존 workspace의 로컬 기록이다. 아래 명령은 갱신 수집 또는 재실행용이다. 10월 28일 스냅샷은 `output/`에 유지하며, 이후 기본 실행은 `output-current/`에 쓴다.

새 clone에서는 Python 3.14 환경과 `requirements.lock.txt`의 추출기 의존성을 준비하고 `sources.example.json`을 `sources.json`으로 복사한 뒤 `game_root`를 설정한다. 상대 경로는 설정 파일 기준이며 `${game_root}`는 공통 게임 경로다. 기존 로컬 설정은 그대로 사용할 수 있다. 참고 자료가 없다면 다음 위치로 확보하거나 설정의 해당 source를 실제 보유한 경로로 수정한다.

```powershell
git clone --depth 1 --branch game/MonmusuTDx https://github.com/PackageInstaller/DataTable.git references/DataTable
git clone --depth 1 https://github.com/monmusu-td-db/monmusu-td-db.github.io.git references/monmusu-db-site
```

## 실행

PowerShell에서 workspace를 기준으로 실행한다.

```powershell
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/crawl.py --refresh-manifest --workers 20
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/finish_acquisition.py
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/run.py inventory --workers 8
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/run.py extract --workers 6
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/classify_output.py --workers 12
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/verify.py
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/audit_coverage.py
& 'extractor\.venv\Scripts\python.exe' -X utf8 extractor/report.py
```

이미 확보한 공개 목록과 파일을 재사용할 때는 앞의 다운로드 명령을 생략한다. `--refresh-manifest`는 DMM 클라이언트 버전 → 게임 에셋 버전 → 전체 `ablist.json`을 다시 조회하며 이전 목록도 timestamp 폴더에 남긴다.

`sources.json`에 실제 IL2CPP 게임, 공개 번들 수집 목록, DataTable과 데이터 사이트의 JSON을 지정한다. 전체 입력의 SHA-256과 출처를 `output-current/inputs.jsonl`에 기록하고 내용이 완전히 같은 파일만 한 번 처리한다. 다른 버전·다른 경로·같은 이름은 출처 목록에 남는다. 파일 크기나 시나리오 이름으로 추출 대상을 제한하지 않는다.

`crawl.py`는 `remote/ablist.json`의 현재 공개 Windows R18 목록 전체를 확보한다. 원격 파일명과 크기가 일치하는 기존 파일은 재사용한다. HTTP 전송은 끝났지만 목록의 크기와 다른 파일도 버리지 않고 별도 상태로 기록한다. manifest 크기를 실제 파일 크기로 덮어쓰지 않는다.

## 보존 형식

- Unity 컨테이너의 모든 직렬화 객체를 `tree.json.gz`로 추출한다. 바이너리 필드는 `field_*.bin`과 SHA-256 참조로 보존한다.
- TextAsset의 원래 payload는 `payload.bin`에도 저장한다. 번들 안의 `.resS` 등 비직렬화 멤버도 추출한다.
- 파싱할 수 없는 객체는 `object.bin`과 오류를 보존한다. 읽힌 기본 헤더만으로 전체 파싱 성공을 보고하지 않는다.
- 실제 게임의 IL2CPP metadata 문자열 테이블을 인덱스·바이트 위치와 함께 추출한다.
- 외부 JSON은 참고 저장소에서 가져온 기존 추출물로 출처를 유지한다. 새 Unity 추출물과 구분한다.
- 같은 드라이브의 원본 파일을 그대로 보존할 때는 hard link를 사용한다. 원본과 연결되므로 `source.*`를 편집하지 않는다. 번역·정규화 결과는 별도 파일에 쓴다.

전체 추출이 끝난 다음 `classify_output.py`를 실행한다. 대사 book, 마스터데이터, UI 후보, 기타 텍스트는 `output-current/kept/`에 둔다. Spine, atlas, 렌더링·엔진 데이터, 바이너리, 해석 실패 자료는 `output-current/excluded/`에 실제 파일과 함께 둔다. 분류 폴더의 `REASONS.json`과 전체 `classification.jsonl`에 사유가 있다. 제외는 삭제를 뜻하지 않는다.

## 시나리오와 UI 인덱스

book은 모든 grid를 순회하며 `Command`, `Text`, `Arg1` 등의 헤더로 열을 찾는다. 원본 전체 이름, 화자, 명령, Voice, 행 번호, 제어 태그, 공백, 중복 원문을 보존한다. 숫자만 뽑아 장면을 병합하지 않는다.

- 각 book 폴더의 `book.json`: 전체 구조
- 각 book 폴더의 `rows.jsonl`: 대사 후보와 원래 cells/fields
- `indexes/scenario-catalog.jsonl`: 모든 출처·버전의 book 목록
- `indexes/scenario-variants.jsonl`: 정확한 이름별 내용 버전과 우선 참조본
- `indexes/master-scenario-coverage.jsonl`: 마스터의 scenario_name과 book 대응
- `indexes/current-master-references.jsonl`: 현재 마스터 참조의 실제 테이블·행 위치
- `indexes/all-strings.jsonl.gz`: 보존 후보의 JSON pointer별 원문 및 IL2CPP 리터럴
- `indexes/provenance.jsonl`: SHA-256별 원본 위치와 공개 에셋 정보

10월 28일 인덱스는 `output/`, 갱신 실행의 인덱스는 `output-current/` 아래에 있다. `output/coverage-audit.json`은 현재 마스터의 미대응 이름과 공개 목록·테스트 행 근거를 기록한다. 우선 참조본은 Text 행이 있는 자료를 우선하고, 현재 공개 자료 → 실제 게임 → DataTable → 기존 번들 → 보존 플레이어 순서로 선택한다. 이전 버전도 그대로 보존한다.

Utage 설정 book도 같은 구조를 쓰므로 대사 행이 없는 book이 포함된다. 전체 행 수에는 다른 출처와 버전의 중복이 들어간다. 이 수를 번역해야 하는 고유 대사 수로 해석하지 않는다.

## 호환 처리와 검증

`unity_adapter.py`는 TypeTreeGeneratorAPI 0.0.10의 IL2CPP assembly 이름, MonoBehaviour 헤더 정렬, primitive/string 배열 노드를 보정한다. 설치된 패키지는 수정하지 않는다. 생성한 tree의 전체 바이트 소비를 확인하며 기본 MonoScript 포인터도 실제 헤더와 대조해 검증했다.

```powershell
& 'extractor\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s extractor -p test_core.py -v
& 'extractor\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s extractor -p test_live_assets.py -v
```

새 inventory와 추출·분류 요약, 검증 결과 및 보고서는 `output-current/`에 남는다. 성공한 입력의 `raw/<hash prefix>/<hash>/complete.json`을 이용해 추출을 재개할 수 있다. 파싱 로직을 바꿔 기존 결과를 재생성할 때는 별도 output 경로를 사용하거나 해당 결과를 명시적으로 보관 후 재처리한다.

추출을 다시 하지 않고 분류 규칙만 적용하려면 `classify_output.py --reclassify`를 사용한다. 이미 분류된 실제 경로를 찾아 자료를 보존하면서 새 위치와 사유를 기록한다.

GUISkin 해석에는 프로젝트에 보관한 `schemas/GUISkin.json`을 사용한다. 2022.3.6f1 Mono 참조에서 추출한 필드 구조와 어셈블리 해시가 들어 있다. 독립 통합 테스트는 실제 IL2CPP 게임과 `fixtures/`의 마스터·시나리오 표본을 읽는다. 표본의 원래 번들 이름과 SHA-256은 `fixtures/manifest.json`에 있고 실제 payload는 로컬에만 보존한다. [실제 표본 준비](fixtures/README.md)

기존 workspace의 `archive/extractor-20261028/`과 `archive/README.md`는 최초 코드·설정 및 옛 Git 복구를 위한 로컬 보관 기록이다. 이 보관 폴더 없이 현재 코드와 합성 테스트를 사용할 수 있다. 원본 스냅샷의 출처 경로는 추출 당시 경로를 기록한다.
