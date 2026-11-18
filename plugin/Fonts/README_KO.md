# UI 폰트 빌드

일반 TMP UI는 Resource Han Rounded KR Bold, 원본 폰트명에 `Kurokane`가 포함된 TMP UI는 메이플스토리 Bold를 우선 fallback으로 사용한다. 원본 일본어·숫자 글꼴과 재질은 유지한다. `NovelBodyBundle`의 Unity Font는 이 TMP 경로와 별개다.

`Editor/UiFontBuilder.cs`는 Unity 2021.3.45f2와 TMP 3.0.6 프로젝트에서 실행한다. 프로젝트에는 TMP Essential Resources의 셰이더·리소스가 있어야 한다. 원본 TTF를 `Assets/Fonts/RHR.ttf`, `Assets/Fonts/Maple.ttf`에 넣고 빌더를 `Assets/Editor/`로 복사하고 출력용 `Assets/Baked/` 폴더를 만든다. 원본 파일은 수정하지 않는다.

1. workspace에서 `python tools/ui_font_corpus.py --out <UnityProject>/corpus.txt`를 실행한다. 현행 승인 UI·Master·Names의 한글, ASCII와 호환 자모를 모은다.
2. Unity의 `-batchmode -nographics -quit -projectPath <UnityProject> -executeMethod UiFontBuilder.Build -logFile <log>`를 실행한다. PowerShell에서 `Start-Process`를 사용할 때는 `-WindowStyle Hidden -Wait`로 완료를 기다린다.
3. 프로젝트 옆 `bundles/`에 `rhr-bold-ui.bundle`, `maple-bold-ui.bundle`이 생성된다. 60px/8px padding/4096² 단일 정적 아틀라스이며, 글자 누락 또는 다중 아틀라스 발생 시 빌드가 실패한다.
4. 각 번들에 `python tools/font_bundle_metadata.py <bundle> <bundle>.metrics.json`을 실행한다. 게임의 TMP 직렬화 차이로 누락되는 point size를 번들 해시에 연결해 복원한다.
5. 로컬 설치에는 번들·sidecar와 원본 저작권/이용 조건을 함께 보관한다. 설정은 `TmpBundle = fonts/rhr-bold-ui.bundle`, `DecorativeTmpBundle = fonts/maple-bold-ui.bundle`이다. 빌드는 게임 설치나 공개 배포를 자동 실행하지 않는다.

2026-11-16 빌드 작업 및 공식 배포본 출처 자료는 로컬 `work/ui-display-fix-20261116/`, `work/font-study-20261101/`, `work/font-ab-20261102/downloads/`에 있다. RHR TTF SHA-256은 `796587d75f77924294637ca3c2e0a79a5b257a1f753f99a24aa046f87daa62eb`, Maple TTF는 `d57eaff48a793ff872a0f33bba2943d058d07c81ed64c68054858a287b85811a`다.

이번 정적 아틀라스는 1,605자(현행 번역의 현대 한글 1,459자)를 포함한다. 원본 TTF의 한글 11,172자 지원과 구분한다. 번역에 새 글자가 추가되면 corpus를 다시 만들고 아틀라스의 포함 여부를 확인한다. 글꼴의 무단 개조나 게임 원본 폰트의 재배포를 하지 않는다.
