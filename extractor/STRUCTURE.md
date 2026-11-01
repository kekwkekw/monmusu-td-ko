# 몬타디 에셋과 텍스트 구조

실제 게임 `C:\Users\user\mnms_td_r18`는 IL2CPP 빌드다. 보존된 `monmusurelated/MonmusuTD X`는 Mono 기반 플레이어이며, 두 실행 환경을 구분한다. 원문은 일반 텍스트 파일뿐 아니라 Unity MonoBehaviour 안의 직렬화 필드에 들어 있다.

## 수집 경로

공개 DMM 앱 정보에서 클라이언트 버전을 얻고, 게임의 asset bundle version API를 조회한다. 해당 버전의 `windows_r18/ablist.json`에서 `baseVersion`, 각 asset의 `hash`, `path`, `size`, `dependencies`를 얻는다. 원본 목록과 다운로드 결과를 모두 보존한다.

번들 URL은 `https://assets.game-monmusu-td.net/assetbundles/ver_<baseVersion>/windows_r18/<hash><path>`다. 논리 경로의 suffix는 소문자화 후 `/`를 `-`로 치환한 문자열의 MD5와 `.bytes`를 결합한다. 현재 목록 전체를 받으므로 시나리오명으로 다운로드 범위를 한정하지 않는다.

실제 게임의 캐시는 `<64자리 디렉터리>/<32자리 디렉터리>/__data`에 있다. 캐시에는 여러 버전이 함께 있으며, 원격 번들과 같은 논리 이름이어도 내용이 다를 수 있다. 파일명만으로 합치지 않고 SHA-256이 같은 입력만 공유한다.

## 암호화된 마스터데이터

`MdF_Output/Data` 등 일부 master bundle에는 `KYSSTMDL` 기반 XOR를 적용한다. 문자열 각 바이트를 `0x55`와 XOR한 뒤 SHA-256을 구하고, digest를 `0xAA`와 XOR한다. 짝수 위치와 홀수 위치 바이트를 이어 32바이트 키를 만들고, 그 키의 역순을 붙여 64바이트 반복 키를 만든다.

복호화 결과의 Unity signature와 실제 객체 파싱을 확인한다. 형식이 맞지 않는 결과를 텍스트라고 가정하지 않는다. masterdata 안의 `scenario_name` 값은 추출 완료 후 book 목록과 대조한다.

## Utage 시나리오

book의 기본 구조는 `MonoBehaviour.importGridList[].rows[].strings[]`다. 각 grid의 헤더를 기준으로 `Text`, `Command`, `Arg1`, `Voice`, `PageCtrl` 등을 읽는다. 설정 book도 같은 구조를 사용하므로 book 수와 대사 후보가 있는 장면 수는 다르다.

대사 후보의 원문을 공백 제거, Unicode 정규화, 태그 제거 없이 보존한다. 원본 `m_Name`과 전체 장면 ID, grid 번호, 배열상 행 위치, 직렬화된 `rowIndex`, 화자·명령·보이스·전체 cells를 기록한다. 같은 원문이 반복되어도 별도 행을 유지한다. 주석·빈 행은 전체 book에는 남기고 대사 후보 인덱스에서만 제외한다.

gctrans Novel 흐름의 정확한 원문 key와 위치 추적 방식을 따르되, GC의 숫자 ID·TSV 열 위치를 몬타디에 적용하지 않는다. 같은 장면의 내용이 다른 버전은 `scenario-variants.jsonl`에 나란히 남는다. 선택된 우선 참조본은 번역이나 검수를 완료했다는 뜻이 아니다.

## UI와 기타 텍스트

실제 게임의 `resources.assets`, `sharedassets*.assets`, level 파일과 Unity 기본 resources를 포함한다. TextAsset payload, custom MonoBehaviour 필드, 외부 JSON·텍스트, IL2CPP metadata의 managed string literal table을 확보한다. 보존 후보의 문자열에는 원래 JSON pointer 또는 metadata 위치를 붙인다.

UnityPy 1.25.4와 TypeTreeGeneratorAPI 0.0.10 조합에서 확인한 문제는 프로젝트 adapter로 처리한다.

1. IL2CPP assembly 조회는 `.dll`을 붙이지 않은 이름을 먼저 사용한다.
2. 생성된 MonoBehaviour 헤더를 Unity native typetree 헤더로 대체해 포인터 정렬을 보존한다.
3. 문자열·primitive 배열을 scalar로 잘못 해석하지 않도록 array node 형식을 보정한다.
4. IL2CPP에서 제거된 native `GUISkin`은 보존한 Mono 참조에서 얻은 typetree를 `schemas/GUISkin.json`에서 읽고 전체 바이트 소비를 검증한다.

bundle container 이름을 얻기 위해 외부 의존 파일을 자동 탐색하지 않는다. 현재 serialized file의 container와 preload table에서 로컬 object의 경로를 연결한다. 외부 참조 자체는 typetree 안에 그대로 남는다.

## 추출 후 분류

시나리오, 마스터데이터, UI 후보, 기타 텍스트를 보존 영역으로 모은다. Spine은 skeleton JSON 구조, atlas 구조, 또는 실제 MonoScript의 Spine namespace로 식별한다. 렌더링·엔진 객체는 Unity 타입을 기준으로 분류한다. binary TextAsset, 보조 리소스, 파싱 실패 객체도 별도 폴더에 원문과 사유를 남긴다.

제외 폴더에도 전체 typetree와 binary sidecar 또는 원본 bytes가 있다. 분류는 나중에 수정할 수 있으며, 추출 단계의 누락이나 원본 삭제를 뜻하지 않는다.

## 근거 자료

- [DataTable 크롤러와 사전 추출 JSON](https://github.com/PackageInstaller/DataTable/tree/game/MonmusuTDx)
- [MonmusuPlayer](https://github.com/BithreenGirlen/MonmusuPlayer)
- [몬무스 데이터 사이트](https://github.com/monmusu-td-db/monmusu-td-db.github.io)
- [사용자 몬타디 저장소](https://github.com/kekwkekw/monmusu-td-ko)
- [사용자 gctrans](https://github.com/kekwkekw/gctrans)

확보한 코드의 revision은 `../references/INDEX.json`, 실제 게임과 공개 에셋의 출처는 `output/inputs.jsonl` 및 `remote/`에 기록한다.
