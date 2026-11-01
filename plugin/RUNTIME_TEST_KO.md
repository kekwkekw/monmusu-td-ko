# 첫 시나리오 실기 기록 — 2026-11-01

대상은 검수 확정된 `10001A0_Nml` 26행이다. `C:\Users\user\mnms_td_r18`에 설치하고, 사용자가 지정한 `C:\Users\user\Desktop\kekw\dmm-ex-launcher.ps1`의 `mnms_td_r18`로 실행했다. 테스트 후 게임을 종료했다. Git/CDN 게시 작업은 수행하지 않았다.

## 환경과 설치

- Unity 2022.3.62f2, BepInEx 6.0.0-be.752, IL2CPP, 게임 UI 버전 1.0.61, AB 버전 `b5aff4d749`.
- 플러그인: `BepInEx/plugins/MonmusuMod/`. 로컬 데이터, CDN 설정 빈 값.
- XUnity AutoTranslator 43개 파일과 ResourceRedirector 2개 파일을 `BepInEx/disabled-plugins/`로 옮기고 해시를 확인했다. 삭제하지 않았다. 로그의 로드 플러그인은 MonmusuMod 1개다.
- XUnity는 **사용자가 다시 요청할 때까지 비활성**이다. 설정/번역 캐시와 core의 XUnity.Common.dll은 보존했다.
- 초기 설치 백업: `work/runtime-install/20261101-185557/`. 수정본 설치 백업: `work/runtime-install/20261101-190947/`.
- 수정 후 MonmusuMod.dll SHA-256: `a1377a6bd149c4551a17105c9e6b67e8ff99224988effddca9de00624261c601`.
- 데이터 manifest SHA-256: `56ca2c6320db07634b5a30feec90c0da531c95fe5a16f511896094f110e1ba67`.

## 재현 경로와 계정 변경

홈 → 도감(図鑑) → 도감 ID 오름차순 → ID 11 에테지아 → 첫 시나리오 `他言無用！？　秘密のエテジア` → `冒頭`.

처음에는 Lv15 해금 조건 때문에 잠겨 있었다. 사용자가 승인한 테스트 범위에서 일반 경험치 재료 8개(보유 8,047개 중)를 사용해 에테지아를 Lv1에서 Lv15로 올렸다. 재접속 후에도 해금 상태를 확인했다. 도감 정렬은 ID 오름차순으로 남아 있다. 유료 구매나 뽑기는 실행하지 않았다.

## 확인 결과

| 항목 | 결과와 범위 |
| --- | --- |
| 로드/훅 | 정상 접속. 등록 대상 5개 훅이 모두 설치됨. 단, 선택지 훅 실행은 이 장면에 선택지가 없어 미검증 |
| 정확한 원문 치환 | 실제 grid 로그 `applied=26 already=0 hold=0 mismatch=0` |
| 첫/마지막 행 | 첫 서술부터 26번째 마지막 서술까지 직접 진행. 모두 한국어 표시 |
| 이름 | `에테지아`, `주인공`의 대사창 및 백로그 표시 확인 |
| 폰트 | 수정 후 `MM_FONT_READY family=Malgun Gothic route=Internal_CreateDynamicFont`. 누락 글리프 경고 없음 |
| 레이아웃 | 기본 창 크기에서 확인. 3줄 본문, 긴 문장의 자동 줄바꿈, 기호가 표시됨. 관찰한 화면에서 잘림/깨진 글자 없음 |
| 진행/연출 | 클릭 진행, 타자 표시, 표정/확대/화면 전환 정상. 마지막 행에서 Skip 버튼으로 다음 원문 구간 진입 확인 |
| 백로그 | 처음 3행의 전체 한국어 본문, 두 화자 이름, 음성 재생 아이콘 확인. 정상 복귀 |
| 재실행 | 수정본 설치 후 지정 런처로 다시 접속하고 같은 시나리오의 처음부터 마지막까지 진행 |
| 번역 범위 밖 | 다음 미번역 구간의 첫 일본어 문장이 유지되는 것 확인 후 게임 종료 |
| 오류 | 수정 후 실행 로그에 `MM_HOOK_FAILED`, `MM_FONT_FAILED`, `MM_SOURCE_MISMATCH`, `MM_HEADER_MISMATCH`, 누락 글리프 경고 없음 |

초기 실행에서 `Font.CreateDynamicFontFromOSFont(string, int)`의 `Method unstripping failed`를 발견했다. 설치 게임의 interop을 확인해 남아 있는 native initializer로 수정했으며, 재빌드 후 오프라인 14개 검사와 실제 폰트 초기화/표시를 통과했다. 기존 Il2CppInterop의 `Class::Init ... using a substitute` 경고는 플러그인 로드 전부터 발생하며 이번 시나리오 실행은 완료됐다.

## 아직 확인하지 않은 항목

- 실제 음성 청취. Voice 필드 보존은 오프라인 검사했고 아이콘은 보였지만 도구로 소리를 듣지는 않았다.
- 선택지, 저장/로드, 자동 재생, 같은 실행 안에서의 동일 장면 반복 재진입.
- 다른 화면 크기, 다른 시나리오/언어 혼합 및 번역 범위 밖의 모든 글리프.
- CDN 실제 배포/다운로드. 이번 실기는 동봉 로컬 패키지를 사용했다.

기계 검사나 실기 표시 확인을 번역 의미검수로 계산하지 않는다. 의미검수 정본은 기존 PRO 결과이며 이번 테스트로 수정하지 않았다.

## 로컬 증거

- `work/runtime-test/20261101/initial-font-failure.log`: 수정 전 오류.
- `work/runtime-test/20261101/verified-game.log`: 수정 후 실제 게임 로그.
- `work/runtime-test/20261101/rebuild.log`: 재빌드와 14개 검사.
- `work/runtime-test/20261101/plugin-config.cfg`: 테스트 설정.
- `handover/RUNTIME_TEST_20261101.json`: 파일 해시, 설치/보존 검증, 테스트 판정.

로그와 계정별 로컬 증거는 Git에서 제외한다. `Build.ps1`의 BUILD.json은 빌드 자체의 정적 결과만 나타내며, 실기 판정은 테스트 대상 DLL/데이터 해시를 가진 별도 기록으로 연결한다.
