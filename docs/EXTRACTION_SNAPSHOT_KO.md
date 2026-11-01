# 기존 로컬 추출 스냅샷

2026-10-28의 로컬 검증 결과다. 새 clone에 원본 데이터가 포함되어 있다는 뜻은 아니다.

| 항목 | 결과 |
| --- | ---: |
| 고유 입력 SHA-256 | 216,929 |
| 보존 레코드 | 2,232,113 |
| 파싱 오류 / 결과 경로 누락 | 0 / 0 |
| Text가 있는 우선 시나리오 | 4,146 |
| 우선 시나리오의 번역 대상 행 | 159,834 |
| 현재 공개 master의 대응 | 3,174 / 3,175 |

누락된 이름 `text_9010006`은 master의 테스트 참조이며 공개 목록에 대응 번들이 없다. 근거는 로컬 `extractor/output/coverage-audit.json`에 남아 있다. 제외된 Spine·렌더링·엔진 자료도 사유별 폴더에 보존했다.

이 스냅샷은 `extractor/output/`, 이후 추출 기본 출력은 `extractor/output-current/`다. 입력 파일은 `translation/novel/`에, 검수 작업은 `work/novels/`에 생성한다. 두 경로와 원본 추출 스냅샷은 Git에서 제외한다. 복사한 데이터는 `extractor/novel_intake.py verify`로 book과 비교하고, 번역 중인 초벌은 기존 배치에서 이어간다.
