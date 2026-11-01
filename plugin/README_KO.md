# 몬타디 한국어 번역 플러그인

BepInEx 6 / IL2CPP용 `MonmusuMod` 0.2.0이다. 승인된 Novel 결과를 Utage 명령 생성 전에 적용하고, ScriptableObject master와 Unity Text/TMP UI도 치환한다. 현재 패키지는 `10001A0_Nml`의 PRO 검수 26행·이름 2건과 Codex가 검수한 실기용 UI 43건·master 8건이다. 0.1.0의 시나리오 실기 기록은 [별도 문서](RUNTIME_TEST_KO.md)에 보존한다. 전체 UI/master 원문과 운영 방법은 [UI 안내](../translation/ui/README_KO.md)를 따른다.

## 빌드

Python 3.14+, .NET SDK 9(또는 net6.0을 빌드할 수 있는 SDK), .NET 6 런타임, 기존 게임의 BepInEx core/interop 참조가 필요하다. 원본 DLL은 저장소와 설치 패키지에 복제하지 않는다.

```powershell
pwsh -File plugin/Build.ps1 -GameDir 'C:\Users\user\mnms_td_r18'
```

`-Book <추출된 book.json 경로>`를 추가하면 첫 확정 장면의 실제 26개 셀 치환/나머지 필드 보존 검사도 실행한다. 이 옵션은 `10001A0_Nml` 테스트 표본에 해당한다. 테스트 중 게임 어셈블리는 실행하지 않는다. 산출물은 workspace의 `dist/MonmusuMod/`에만 작성한다.

현재 노트북에서는 .NET 6 참조 팩이 기존 NuGet 캐시에 있다. `-NugetPackages 'C:\Users\user\.nuget\packages' -Offline`을 추가하면 인터넷 복원 없이 이 캐시로 빌드한다. .NET 6 타깃은 설치된 BepInEx 런타임과 맞추기 위한 것이며, SDK의 지원 종료 경고는 기록한다.

## 적용 방식

- `AdvImportBook.BootInit` 후와 `AdvImportScenarioSheet.CreateCommandList` 전에 exact grid 이름, 헤더, 배열 행 위치, serialized rowIndex, 원문 셀 전체를 대조한다.
- 승인된 Text 셀만 메모리에서 치환한다. 같은 JP의 다른 행은 합치지 않으며, 재초기화는 중복 적용하지 않는다. HOLD/미검수/원문 불일치는 현재 게임 텍스트를 유지한다.
- 이름은 대사창/백로그의 표시 Text에서만 exact Names로 바꾼다. 캐릭터 ID인 Arg1, 선택지 분기, Voice, PageCtrl은 바꾸지 않는다.
- 원본 book 파일을 고치지 않는다. Utage의 본문 파싱, 타자 표시, 백로그, 저장 과정에는 변환된 Text가 전달되는 구조다. 해당 경로의 실제 호출과 저장/로드 동작은 실기 확인 항목이다.
- 한글이 있는 Utage 본문·이름·선택지·백로그에 설치된 `Malgun Gothic` 동적 폰트를 적용한다. GC의 TMP 폰트 번들을 사용하지 않는다.
- master는 AssetBundle/Resources 로드 결과에서 exact asset name·native class·field·JP를 모두 대조해 해당 문자열만 변경한다. ID, kana, 연결 키는 번역하지 않는다.
- 일반 UI는 exact JP만 치환한다. 입력 필드와 Utage 본문/이름/백로그/선택지는 별도 경로로 보호한다. Unity Text에는 동적 한글 폰트를, TMP에는 원래 폰트를 유지하면서 한글 fallback을 적용한다. 이미지 글자는 이 경로로 변경되지 않는다.

## 설치와 실행

빌드는 workspace에만 산출물을 작성한다. 게임을 종료한 뒤 다음 명령으로 설치한다. 설치 스크립트는 기존 플러그인과 설정을 `work/runtime-install/<시각>/`에 보관하고 패키지/설치 파일의 SHA-256을 대조한다. 기존 BepInEx core, interop, 게임 파일은 교체하지 않는다. DLL 2개와 data 폴더가 함께 필요하다.

```powershell
pwsh -File plugin/Install.ps1 -GameDir 'C:\Users\user\mnms_td_r18'
```

사용자 지시에 따라 XUnity AutoTranslator와 ResourceRedirector는 `BepInEx/disabled-plugins/`에 보관한다. `plugins/` 내부의 단순 하위 폴더는 재귀 검색되므로 비활성 위치로 사용하지 않는다. **사용자의 명시적인 재활성 요청 전에는 XUnity를 다시 켜지 않는다.** 기존 설정과 번역 캐시는 보존한다.

이 노트북에서는 `C:\Users\user\Desktop\kekw\dmm-ex-launcher.ps1`을 실행하고 첫 항목 `mnms_td_r18`을 Enter로 선택한다. 게임 실행 파일이나 DMM 런처를 직접 실행하지 않는다. 도구에서 실행할 때는 게임 종료까지 런처의 부모 셸을 유지하고, 타이틀의 START를 지체 없이 눌러 일회용 로그인 토큰 만료를 피한다. 토큰 파일이나 게임 실행 인수를 로그에 남기지 않는다.

첫 실행 후 `BepInEx/config/kekwkekw.monmusu.ko.cfg`가 생성된다. 기본 설정은 번역 켜짐, 공개 GitHub CDN, 한국어 폰트 `Malgun Gothic`이다. 기존 설정은 유지되므로 0.1.0에서 업그레이드할 때 CDN을 활성화하려면 설치 명령에 `-CdnBaseUrl 'https://raw.githubusercontent.com/kekwkekw/monmusu-td-ko/main/translations/ko/'`를 명시한다. 설정은 다음 실행에 적용된다. 플러그인 활성 상태에서의 hot unload는 지원하지 않는다.

`BepInEx/LogOutput.log`에서 확인할 항목:

- `MM_READY`: 패키지, 시나리오/행/이름/UI/master 수, hook 16개.
- `MM_CDN_READY`: 다운로드와 전체 해시 검증을 끝내고 현재 실행에서 선택한 패키지.
- `MM_MASTER_APPLIED`: 변경한 master 에셋과 필드 수. `MM_MASTER_FIELD_MISSING`/`MM_MASTER_FAILED`는 구조 변경 또는 실패.
- `MM_UI_APPLIED`: UI renderer와 exact JP 해시. `MM_TMP_FONT_READY`는 TMP 한글 fallback 준비.
- `MM_GRID`: 첫 로드에서 `applied=26`, `mismatch=0`; 다음 준비 경로에서는 `already=26`이 정상이다.
- `MM_FONT_READY`: 한국어 폰트 준비. `MM_FONT_GLYPH_MISSING`은 누락 글리프를 표시한다.
- `MM_FONT_FAILED`/`MM_FONT_MISSING`: 폰트를 준비하지 못해 게임의 기존 폰트를 유지함.
- `MM_SOURCE_MISMATCH`: 게임 버전/위치/셀이 달라 치환하지 않은 행. `LogUnmatchedGrids=true`이면 발견한 다른 grid 이름도 기록한다.
- `MM_HEADER_MISMATCH`: 원본 헤더가 달라 해당 grid를 치환하지 않음.

반복 검증 항목은 첫/마지막 행, 이름, 한글 글리프·줄바꿈·잘림, 음성, 타자 표시·스킵, 재진입, 백로그, 저장/로드다. 첫 장면에는 선택지가 없으므로 선택지 경로는 별도 표본이 필요하다. 현재 실기에서는 XUnity가 로드되지 않은 것을 로그로 확인했다.

설치된 IL2CPP interop의 `Font.CreateDynamicFontFromOSFont(string, int)`는 unstripping 실패 stub이고 배열 overload는 없는 생성자를 참조했다. 실제로 남아 있는 `Internal_CreateDynamicFont`에 IL2CPP Font wrapper를 전달하도록 수정했고 실기에서 `MM_FONT_READY`를 확인했다. 빌드 전 검사도 이 native initializer를 확인한다. 해당 초기화 순서는 [Unity 2022.3 Font 소스](https://github.com/Unity-Technologies/UnityCsReference/blob/2022.3/Modules/TextRendering/TextRendering.bindings.cs)를 참고했다.

## 데이터 갱신 / CDN

```powershell
python -X utf8 tools/update/cli.py mod-package
```

승인된 로컬 결과만 runtime manifest와 함께 export한다. 행 기반 JSON을 그대로 사용하며 JP dictionary로 다시 합치지 않는다. 각 파일의 SHA-256과 행별 원문/제어 토큰을 검증한다.

`Translation.CdnBaseUrl` 기본값은 `https://raw.githubusercontent.com/kekwkekw/monmusu-td-ko/main/translations/ko/`다. 저장소는 2026-11-01 사용자가 public으로 전환했다. 시작 시 hook 설치 전에 manifest와 데이터 전체를 다운로드·검증하고 현재 실행에 적용한다. HTTP 요청 제한 시간은 20초이며 다운로드 실패/손상/중단 시 기존 검증 캐시 또는 동봉 데이터를 사용한다. 캐시는 `BepInEx/cache/MonmusuMod/`다. 토큰은 필요하지 않다. manifest 외에 names, novels, master, ui, master-bindings가 하나의 검증 단위다.

CDN 설정을 비우면 기존 다운로드 캐시보다 `DataDirectory`의 로컬 패키지를 사용한다. 따라서 설치용 데이터를 새로 복사한 뒤 오래된 캐시가 그 결과를 덮어쓰지 않는다.

## 구현 근거

GCMod의 Novel 치환과 현행 Candidate LocalParity의 master/UI 분리, exact UI hook, 원문 위치 보존, manifest 구조를 참고했다. GC 전용 숫자 Novel ID·DMM EventText·UI 레이아웃 규칙은 이식하지 않았다. 몬타디의 Utage와 ScriptableObject, Unity Text/TMP에 맞춰 별도로 구현했다.

- 정적 분석: `plugin/Inspect-Game.ps1`, `work/plugin-analysis/game-profile.json`
- 패키지 검사: `work/plugin-analysis/package-export.json`, `dist/MonmusuMod/BUILD.json`
- [BepInEx 공식 IL2CPP 플러그인 문서](https://docs.bepinex.dev/master/articles/dev_guide/plugin_tutorial/2_plugin_start.html?tabs=tabid-unityil2cpp)

원본·HOLD 정책·초벌·검수 상태를 변경하지 않는다. 게임 실행 성공은 실제 테스트 이후에만 판정한다.
