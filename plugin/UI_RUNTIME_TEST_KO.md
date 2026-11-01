# MonmusuMod 0.2.0 UI/master 실기 기록

2026-11-01, Unity 2022.3.62f2 / BepInEx 6.0.0-be.752 / IL2CPP 게임에서 지정된 dmm-ex-launcher.ps1로 실행했다. XUnity AutoTranslator와 ResourceRedirector는 계속 비활성이다. 테스트 중 구매·강화·소모품 사용은 하지 않았다.

## 데이터와 실제 확인

- 전체 입력: master 4,158개 에셋, 82,503쌍; UI 2,799개 고유 문자열. 원문 등장 위치와 다른 출처를 보존했다. 표시 용도 미확인 필드 81,297건은 별도 파일로 보존했다.
- 배포: Codex 검수 UI 43건과 master 8건, 기존 PRO 검수 Novel 26행과 Names 2건. 나머지 원문은 미번역이다.
- 공개 GitHub raw의 브랜치 CDN을 인증 없이 게임에서 수신했고 전체 파일 해시를 검증했다. `MM_CDN_READY`와 `MM_READY ... hooks=13`을 확인했다.
- master preload 캐시 4,235개를 읽고 `1`, `picturebook_data`, `sub_story_tab_data`에서 총 9개 필드를 치환했다. 8개 JP/KO쌍 중 한 쌍은 같은 필드의 두 위치에 나타난다.
- 도감 프로필의 `에테지아`, `켄타우로스 소녀`, `프로필`을 눈으로 확인했다. 능력치 화면에서 master 이름과 공격력·물리 방어·마법 방어·저지 수·사거리·공격 속도·출격 비용을 확인했다.
- 정렬 팝업의 `정렬`, `▲오름차순`, `▼내림차순`이 제어 태그를 유지하고 표시됐다. 정렬 설정은 바꾸지 않았다.
- 공통 제목의 `확인`, `설정`, `능력치`가 정상 표시됐다. 최종 후보 실행에서 UI exact hook 10종이 기록됐고 오류·누락 글리프·master 실패 로그는 0건이었다.
- 시나리오 회귀 실행에서 `10001A0_Nml applied=26 already=0 hold=0 mismatch=0`, 첫 대사, 에테지아 이름, 다음 대사, 백로그와 `뒤로`를 확인했다. 최종 후보 직전의 동일 0.2.0에서 수행했으며, 이후 변경은 공통 TMP fallback 등록과 재사용 제목 갱신이다. 기존 26행 전체 표시 기록은 [0.1.0 기록](RUNTIME_TEST_KO.md)에 있다.

## 실기에서 수정한 문제

Unity generic `GetComponentInParent<T>` 래퍼의 제약 오류는 native Type/Boolean overload로 수정했다. AssetBundleRequest.asset에 건 hook은 .NET 6 충돌 덤프에서 잘못된 포인터 반환을 확인해 제거했다. 현행 master hook은 게임의 DataBaseManager Preload 코루틴 완료 시점 두 곳이다. 이 경로로 바꾼 뒤 반복 홈 진입·도감·시나리오 테스트에서 종료 문제가 재현되지 않았다.

OS 동적 Font는 Text에서 정상 동작하지만 TMP 생성은 실패했다. 기존 개인 GCMod TMP 번들을 사용하고 누락 material, 게임 shader, float→int pointSize(원문 90)를 복원했다. metric sidecar는 번들 SHA-256과 asset 이름을 대조한다. 공통 TMP fallback을 등록하고 새 primary font에 연결할 때 mesh를 갱신해 재사용 제목의 네모 표시를 해결했다. 원본 GCMod 폰트와 게임 파일은 변경하지 않았다.

## 검증 범위와 파일 식별

Python 기존 26개 + UI 7개 테스트, .NET core 17개 검사(실제 추출 book 포함), native hook 13개 정적 확인, 플러그인 빌드 경고/오류 0개를 통과했다. Windows/Ubuntu CI도 통과했다. 이것은 의미 검수나 모든 게임 화면의 호환성을 뜻하지 않는다.

| 파일 | SHA-256 |
| --- | --- |
| MonmusuMod.dll | `d5edf8d942bb03986091ed6590e79d7ea80b10c4cc4492cc85fe8522d39d0005` |
| MonmusuMod.Core.dll | `5aa454a7faad924d0e6c59b2d043a76d1be96cbdb29f0ebfda84e31d1da56b55` |
| runtime manifest | `4e5cde1317e60dcf5f6ac16319e08946b913f1a920217c89049886504f345a1a` |
| 개인 설치 TMP bundle | `b2087a14149d7d2de92c675e0ce6c04c722fcb53f227c5427e288d00eacffe80` |

외부 폰트 번들, 개인 게임 로그·덤프·계정 화면, 원본 게임 DLL은 공개하지 않는다. 로컬 증거는 `work/ui-runtime/20261101/`, 설치 전 보관본은 `work/runtime-install/`에 있다. 동결 정책과 기존 시나리오 원문·초벌·검수·배포의 11개 보호 파일 해시가 그대로인 것을 확인했다.

그림으로 만들어진 버튼/배너와 미번역 일본어는 남아 있다. sub_story_tab_data는 native 치환 로그까지 확인했고 해당 탭의 시각 검증은 하지 않았다. 모든 UI 43건의 노출, 입력창, 전투, 선택지, 음성 청취와 저장/로드 전체 검증은 이번 범위에 포함하지 않았다. TMP 번들은 현재 표본의 한글을 모두 포함하지만 향후 전체 번역에는 글리프 확장이 필요할 수 있다.
