# 로컬 실제 에셋 테스트 표본

`manifest.json`은 `master.bytes`, `story.bytes`의 SHA-256과 원래 번들 이름을 기록한다. 실제 두 payload는 로컬 보관 자료이며 Git에 포함하지 않는다. 기존 workspace에는 이 파일들이 보존되어 있다.

새 환경에서 실제 에셋 통합 테스트를 실행하려면 보유한 원본 번들 또는 추출 당시의 보관본에서 두 파일을 복사하고 manifest의 SHA-256과 대조한다. 원본 게임 설치 경로는 `extractor/sources.json`으로 지정한다.

소스 checkout의 CI는 합성 데이터를 생성하는 단위·통합 테스트만 실행한다. `test_live_assets.py`는 UnityPy/TypeTreeGeneratorAPI, 실제 게임과 이 두 표본을 준비한 로컬 환경에서 별도로 실행한다.
