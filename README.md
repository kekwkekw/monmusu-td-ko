# 몬스터娘TD 한국어화 파이프라인

몬타디 IL2CPP 게임의 원본 수집·추출과 Novel 번역·검수 도구다. [gctrans](https://github.com/kekwkekw/gctrans)의 Novel 흐름을 따라 **시나리오 수집 → Codex 초벌 → ChatGPT PRO 의미검수 → 로컬 반영·검증 → 승인된 Git 반영**으로 진행한다. [BepInEx 플러그인](plugin/README_KO.md)은 승인된 행 기반 결과를 게임의 Utage 시나리오에 연결한다. `10001A0_Nml` 26행의 실제 게임 표시와 백로그를 확인했으며, 검증 범위는 [실기 기록](plugin/RUNTIME_TEST_KO.md)에 남겼다. CDN 게시와 전체 시나리오 검증은 별도다.

운영 정본은 **[docs/OPERATOR_KO.md](docs/OPERATOR_KO.md)**다. 원문·제어 태그·화자 원값·행 위치·중복 행을 보존하고, HOLD는 해당 행만 보류한다. 초벌·검수·반영 상태를 나누어 중단 후 이어갈 수 있다.

## 새 환경 구성

Python **3.14 이상**을 사용한다. 번역 입력·Novel 작업·오프라인 테스트에는 표준 라이브러리만 필요하다. Unity 추출을 실행할 때 추가 의존성을 설치한다.

```powershell
git clone https://github.com/kekwkekw/monmusu-td-ko.git
cd monmusu-td-ko
py -3.14 -m venv extractor/.venv
& 'extractor/.venv/Scripts/Activate.ps1'
python -X utf8 tools/update/cli.py preflight
```

Unity 추출을 사용할 때는 다음을 추가 실행하고 `extractor/sources.json`의 `game_root`를 실제 게임 폴더로 수정한다.

```powershell
python -m pip install -r extractor/requirements.lock.txt
Copy-Item extractor/sources.example.json extractor/sources.json
```

기존 workspace에는 로컬 설정이 있으므로 덮어쓰지 않는다. 설정의 상대 경로는 설정 파일이 있는 폴더 기준이며 `${game_root}`는 게임 경로로 치환된다. 공개 참고 자료의 clone 위치와 전체 추출 명령은 [추출기 안내](extractor/README.md)를 따른다.

## 정상 Novel 흐름

검증된 추출 스냅샷이 `extractor/output/`에 있을 때의 예시다. 새 추출의 기본 출력인 `extractor/output-current/`를 사용할 때는 intake와 init에 `--snapshot extractor/output-current`를 추가한다.

```powershell
python -X utf8 tools/update/cli.py intake generate
python -X utf8 tools/update/cli.py novel init
python -X utf8 tools/update/cli.py novel prepare --batch work/novels/first --scenario 10001A0_Nml
# TASK.md, source/, context.json, HOLD_POLICY.md를 읽고 draft.json에 초벌 작성
python -X utf8 tools/update/cli.py novel checkpoint --batch work/novels/first
python -X utf8 tools/update/cli.py novel review --batch work/novels/first --round 001
# PRO가 실제 의미검수 후 reviews/001/review.json의 행별 판정과 지식 변경안을 확정
python -X utf8 tools/update/cli.py novel check --batch work/novels/first --round 001
python -X utf8 tools/update/cli.py novel apply --batch work/novels/first --round 001
python -X utf8 tools/update/cli.py novel verify
```

기계 검사는 의미검수를 대신하지 않는다. `apply`는 승인된 행과 Names/Knowledge 변경만 로컬에 반영한다. Git 쓰기, 번역 API 호출, CDN 게시, 게임 설치를 자동으로 수행하지 않는다.

## 저장소 구조

| 경로 | 역할 |
| --- | --- |
| [docs/OPERATOR_KO.md](docs/OPERATOR_KO.md) | 정상 운영과 중단·재개 방법 |
| [HOLD_POLICY.md](HOLD_POLICY.md) | 사용자 승인으로 동결한 프로젝트 HOLD 정본 |
| `tools/update/cli.py`, `tools/novel_workflow.py` | gctrans 방식의 작업·검수·반영 진입점 |
| `translation/knowledge.jsonl`, `translation/holds.jsonl` | 현재 승인 지식과 확정된 행별 HOLD |
| `translations/ko/names.json`, `translations/ko/novels/` | 검수 승인된 로컬 결과 |
| `knowledge-layer/provenance/current-changes/` | 지식 변경 전후 근거 |
| `extractor/` | 전체 수집·추출 후 분류와 검증, Novel 입력 생성 |
| `plugin/` | IL2CPP/BepInEx 플러그인, 독립적인 행 치환 core, 오프라인 검사 및 빌드 |
| `tools/mod_package.py` | 검수된 행과 Names를 해시 manifest가 있는 로컬 runtime 패키지로 export |
| [translation/ui/README_KO.md](translation/ui/README_KO.md) | 전체 master/UI 원문, 위치, 부분 검수와 배포 운영 |
| `translations/ko/master.json`, `translations/ko/ui.json` | gctrans 형식의 승인된 master/UI exact 치환 |

원본 번들, 추출 스냅샷, `translation/novel/`, `translation/state/`, `work/novels/`, 로컬 설정과 보관 자료는 Git에서 제외한다. 새 clone에는 이 데이터가 없으며, 기존 workspace의 원본과 작업 파일은 그대로 유지한다. [기존 추출 결과](docs/EXTRACTION_SNAPSHOT_KO.md) · [gctrans 참조와 몬타디 차이](docs/UPSTREAM_KO.md)

CI는 Windows와 Linux에서 동결 정책과 합성 데이터 테스트를 검사한다. 실제 게임 검사는 원본 설치와 로컬 표본이 있는 환경에서 별도로 실행한다.

## 게임 적용 준비

`10001A0_Nml` 26행과 이름 2건의 PRO 검수 결과가 main에 반영돼 있다. 게임을 실행하지 않고 다음 명령으로 패키지와 플러그인을 빌드한다.

```powershell
pwsh -File plugin/Build.ps1 -GameDir 'C:\Users\user\mnms_td_r18'
```

결과는 `dist/MonmusuMod/`에 생성된다. 빌드는 게임 폴더에 설치하지 않는다. 설정, 로컬/CDN 데이터 로딩, 한국어 폰트, 진단 로그 및 후속 실기 확인 절차는 [플러그인 운영 안내](plugin/README_KO.md)를 따른다.

UI/master 전체 원문 85,302쌍과 등장 위치를 `translation/ui/source/`에 공개한다. 현재 번역은 실기용 51건만 Codex가 검수했다. MonmusuMod 0.2.0은 공개 GitHub CDN의 해시 manifest를 받아 Novel·master·UI를 함께 읽는다. 원문 입력, 검수 판정, 게임 배포 파일은 각각 분리되어 있다.
