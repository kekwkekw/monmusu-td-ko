# 몬타디 한국어 번역 플러그인

BepInEx 6 / IL2CPP용 `MonmusuMod` 0.4.0이다. 승인된 Novel 결과를 Utage 명령 생성 전에 적용하고, ScriptableObject master와 Unity Text/TMP UI도 치환한다. 공개 Novel은 4,146장면·159,834행(번역 159,817행, 승인 HOLD 17행)·Names 776건이며, UI/master는 기존 부분 번역을 사용한다. [0.2.0 UI/master 실기 결과](UI_RUNTIME_TEST_KO.md)와 [0.1.0 시나리오 기록](RUNTIME_TEST_KO.md)은 당시 표본의 기록이다. 전체 UI/master 원문과 운영 방법은 [UI 안내](../translation/ui/README_KO.md)를 따른다.

GCMod를 참고한 Image/Sprite 및 RawImage 교체는 `monmusu-images-v1` 카탈로그의 원본 텍스처와 UI 경로를 대조한다. 공개 패키지는 manifest의 `images`와 `image_files`를 사용한다. 별도로 설치한 로컬 카탈로그는 `[Images] LocalDirectory`로 선택할 수 있다. 카탈로그가 없는 패키지도 지원한다. [참고 구현과 라이선스](THIRD_PARTY/README.md)

0.4.0의 최종 DLL은 진단 없이 도감 재생·스킵·재진입을 통과했다. 같은 세션의 메인 저장 복원과 장면 요청 실패 시 원문 복원도 확인했다. [CDN 로더 실기 기록](CDN_RUNTIME_TEST_KO.md)

## 빌드

Python 3.14+, .NET SDK 9(또는 net6.0을 빌드할 수 있는 SDK), .NET 6 런타임, 기존 게임의 BepInEx core/interop 참조가 필요하다. 원본 DLL은 저장소와 설치 패키지에 복제하지 않는다.

```powershell
pwsh -File plugin/Build.ps1 -GameDir 'C:\Users\user\mnms_td_r18'
```

`-Book <추출된 book.json 경로>`를 추가하면 첫 확정 장면의 실제 26개 셀 치환/나머지 필드 보존 검사도 실행한다. 이 옵션은 `10001A0_Nml` 테스트 표본에 해당한다. 테스트 중 게임 어셈블리는 실행하지 않는다. 산출물은 workspace의 `dist/MonmusuMod/`에만 작성한다.

현재 노트북에서는 .NET 6 참조 팩이 기존 NuGet 캐시에 있다. `-NugetPackages 'C:\Users\user\.nuget\packages' -Offline`을 추가하면 인터넷 복원 없이 이 캐시로 빌드한다. .NET 6 타깃은 설치된 BepInEx 런타임과 맞추기 위한 것이며, SDK의 지원 종료 경고는 기록한다.

## 적용 방식

- `StoryDataBase.PlayStoryAdv`에서 대상 장면을 준비하고, `AdvChapterData.BootInit`과 `AdvScenarioData.Init`에서 함께 컴파일할 장면을 확인한다. `AdvImportScenarioSheet.CreateCommandList` 직전에 exact grid 이름, 헤더, 배열 행 위치, serialized rowIndex, 원문 셀 전체를 대조한다. 실기에서 호출되지 않은 `AdvImportBook.BootInit`에는 의존하지 않는다.
- 승인된 Text 셀만 메모리에서 치환한다. 같은 JP의 다른 행은 합치지 않으며, 재초기화는 중복 적용하지 않는다. HOLD/미검수/원문 불일치는 현재 게임 텍스트를 유지한다.
- 문자열 배열 기록은 native `Il2CppSystem.Array.SetValue`를 사용한다. 설치 interop의 `Il2CppStringArray` 인덱서에는 GC write barrier가 없어 직접 포인터 쓰기를 사용하지 않는다.
- 이름은 대사창/백로그의 표시 Text에서만 exact Names로 바꾼다. 캐릭터 ID인 Arg1, 선택지 분기, Voice, PageCtrl은 바꾸지 않는다.
- 원본 book 파일을 고치지 않는다. Utage의 본문 파싱, 타자 표시, 백로그, 저장 과정에는 변환된 Text가 전달되는 구조다. 해당 경로의 실제 호출과 저장/로드 동작은 실기 확인 항목이다.
- 한글이 있는 Utage 본문·이름·선택지·백로그에는 설치된 `Malgun Gothic` 동적 폰트를 적용한다.
- master는 게임의 `ntd.database.DataBaseManager.Preload`/`PreloadBeforeTitle` 코루틴 완료 시 등록된 ScriptableObject의 exact asset name·native class·field·JP를 모두 대조해 해당 문자열만 변경한다. ID, kana, 연결 키는 번역하지 않는다. Unity AssetBundle getter 자체는 hook하지 않는다.
- 일반 UI는 exact JP만 치환한다. 입력 필드와 Utage 본문/이름/백로그/선택지는 별도 경로로 보호한다. Unity Text에는 동적 한글 폰트를, TMP에는 원래 폰트를 유지하면서 별도 TMP 번들의 한글 fallback을 적용한다. 이미지 글자는 이 경로로 변경되지 않는다.

## 설치와 실행

빌드는 workspace에만 산출물을 작성한다. 게임을 종료한 뒤 다음 명령으로 설치한다. 설치 스크립트는 기존 플러그인과 설정을 `work/runtime-install/<시각>/`에 보관하고 패키지/설치 파일의 SHA-256을 대조한다. 기존 BepInEx core, interop, 게임 파일은 교체하지 않는다. DLL 2개와 data 폴더가 함께 필요하다.

```powershell
pwsh -File plugin/Install.ps1 -GameDir 'C:\Users\user\mnms_td_r18'
```

사용자 지시에 따라 XUnity AutoTranslator와 ResourceRedirector는 `BepInEx/disabled-plugins/`에 보관한다. `plugins/` 내부의 단순 하위 폴더는 재귀 검색되므로 비활성 위치로 사용하지 않는다. **사용자의 명시적인 재활성 요청 전에는 XUnity를 다시 켜지 않는다.** 기존 설정과 번역 캐시는 보존한다.

이 노트북에서는 `C:\Users\user\Desktop\kekw\dmm-ex-launcher.ps1`을 실행하고 첫 항목 `mnms_td_r18`을 Enter로 선택한다. 게임 실행 파일이나 DMM 런처를 직접 실행하지 않는다. 도구에서 실행할 때는 게임 종료까지 런처의 부모 셸을 유지하고, 타이틀의 START를 지체 없이 눌러 일회용 로그인 토큰 만료를 피한다. 토큰 파일이나 게임 실행 인수를 로그에 남기지 않는다.

첫 실행 후 `BepInEx/config/kekwkekw.monmusu.ko.cfg`가 생성된다. 기본 설정은 번역 켜짐, 공개 GitHub CDN, 한국어 폰트 `Malgun Gothic`이다. 기존 설정은 유지되므로 0.1.0에서 업그레이드할 때 CDN을 활성화하려면 설치 명령에 `-CdnBaseUrl 'https://raw.githubusercontent.com/kekwkekw/monmusu-td-ko/main/translations/ko/'`를 명시한다. 설정은 다음 실행에 적용된다. 플러그인 활성 상태에서의 hot unload는 지원하지 않는다.

`BepInEx/LogOutput.log`에서 확인할 항목:

- `MM_READY`: 선택한 패키지, 등록 시나리오 수와 실제 로드 수, 이름/UI/master 수, hook 21개. 시작의 `loaded_scenarios=0 rows=0`은 정상이다.
- `MM_CDN_READY` / `MM_CDN_STARTUP`: 공통 데이터 검증 후 선택한 세대와 CDN 시작 대기 시간.
- `MM_CDN_REQUEST` / `MM_CACHE_HIT` / `MM_CACHE_REUSE`: 실제 요청과 해시가 일치하는 캐시 재사용.
- `MM_NOVEL_READY` / `MM_NOVEL_FAILED` / `MM_NOVEL_DEADLINE`: 개별 장면 준비, 실패 또는 진입 대기 만료. 만료된 진입에서는 해당 grid를 원문으로 컴파일한다.
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

`Translation.CdnBaseUrl` 기본값은 `https://raw.githubusercontent.com/kekwkekw/monmusu-td-ko/main/translations/ko/`다. 시작에는 manifest와 Names/UI/master/이미지 공통 데이터만 검증한다. Novel 본문은 읽거나 받지 않는다. 같은 manifest와 정상 캐시로 재시작하면 manifest만 요청하고 기존 버전 폴더를 재사용한다. CDN 시작 작업 전체의 대기는 최대 15초이고 HTTP 요청별 상한은 10초다. 실패하면 이전 검증 캐시 또는 동봉 공통 데이터를 선택한다. 캐시는 `BepInEx/cache/MonmusuMod/`이며 토큰은 필요하지 않다.

선택한 manifest·Names·정책은 게임 실행 동안 고정한다. Novel은 필요한 장면만 선택한 해시로 읽고, 없거나 손상된 파일만 받는다. 같은 장면의 동시 요청은 하나로 합치고 실패 후 30초 동안 반복 요청을 억제한다. 재생 진입마다 모든 grid가 최대 10초의 대기 예산을 공유한다. 시간 내 준비하지 못한 grid는 원문을 유지하며, 늦게 완료된 결과로 이미 생성한 명령을 덮어쓰지 않는다. 다시 진입하면 준비된 메모리/디스크 캐시를 사용한다. 같은 세션의 저장 복원은 이미 컴파일된 명령을 사용하므로 초기화 후크 재호출에 의존하지 않는다. 차가운 프로세스에서 저장 파일만으로 장면을 준비하는 기능은 추가하지 않았다.

manifest의 선택적 `grid_names`는 검수 행이 참조하는 원본 전체 grid 이름이다. 공백·대소문자·Unicode를 정규화하지 않으며 중복 소유자는 거부한다. 이 필드가 없는 기존 v1 manifest도 지원한다. 이 경우 실제 `StoryData.scenario_name`과 `AdvScenarioData.name`으로 파일을 준비한 뒤 검증된 본문의 전체 grid 이름을 등록한다. 다른 세대 파일의 해시가 다르면 이전 번역으로 대체하지 않는다. 정책 불일치, 원문 변경, HOLD 검증은 지연 로드에서도 동일하게 적용한다.

CDN 설정을 비우면 기존 다운로드 캐시보다 `DataDirectory`의 로컬 패키지를 사용한다. 따라서 설치용 데이터를 새로 복사한 뒤 오래된 캐시가 그 결과를 덮어쓰지 않는다.

## TMP 폰트 의존성

이 게임에서는 OS 동적 Font를 TMP FontEngine으로 가져올 수 없어, TMP 한글 표시에 별도 font bundle이 필요하다. 현재 개인 설치는 기존 GCMod의 `RHR_Medium_GFSAFE_ADH.bundle`을 복사해 사용한다. 원래 GC 설치는 변경하지 않는다. `Build.ps1 -FontBundle <기존 번들 경로>`로 개인 패키지에 넣고, `Font.TmpBundle`은 기본 `fonts/RHR_Medium_GFSAFE_ADH.bundle`을 가리킨다. 이 선택적 빌드에는 추출기 환경의 UnityPy가 필요하다. 두 게임의 TMP 직렬화 버전 차이로 비어 있는 material 참조는 동일 번들 material로 복원하고 게임의 TMP shader를 사용한다.

번들의 `m_PointSize`는 float, 게임의 FaceInfo는 int라서 크기가 0으로 읽힌다. `tools/font_bundle_metadata.py`가 원래 point size와 번들 SHA-256을 `.bundle.metrics.json`에 보존하고, runtime이 두 파일을 대조해 90을 복원한다. 다른 크기를 추측해 강제로 맞추지 않는다. 현재 실기용 UI/master 번역에 필요한 한글은 이 번들의 1,638개 character table에 모두 있다. 추후 번역 확장 시 누락 문자는 `MM_TMP_GLYPH_MISSING`으로 확인한다.

GCMod와 같이 이 외부 폰트 번들은 Git/CDN 공개 대상에서 제외한다. 공개 소스만 clone한 사용자는 적합한 TMP 폰트를 별도로 준비해야 한다. `dist/MonmusuMod/`는 이전 개인 빌드의 폰트를 유지할 수 있으므로 공개 release 파일로 자동 게시하지 않는다. 글리프와 실제 표시 확인은 런타임 검증에 기록한다.

## 구현 근거

GCMod의 Novel 치환과 현행 Candidate LocalParity의 master/UI 분리, exact UI hook, 원문 위치 보존, manifest 구조를 참고했다. GC 전용 숫자 Novel ID·DMM EventText·UI 레이아웃 규칙은 이식하지 않았다. 몬타디의 Utage와 ScriptableObject, Unity Text/TMP에 맞춰 별도로 구현했다.

- 정적 분석: `plugin/Inspect-Game.ps1`, `work/plugin-analysis/game-profile.json`
- 패키지 검사: `work/plugin-analysis/package-export.json`, `dist/MonmusuMod/BUILD.json`
- [BepInEx 공식 IL2CPP 플러그인 문서](https://docs.bepinex.dev/master/articles/dev_guide/plugin_tutorial/2_plugin_start.html?tabs=tabid-unityil2cpp)

원본·HOLD 정책·초벌·검수 상태를 변경하지 않는다. 게임 실행 성공은 실제 테스트 이후에만 판정한다.
