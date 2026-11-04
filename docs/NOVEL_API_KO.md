# Novel API 초벌 운영

Codex가 운영문서에 따라 업데이트 확인·추출·작업 준비를 관리하고, API는 준비된 행의 초벌만 수행한다. 기존 Codex 초벌과 PRO 검수·Knowledge 승인·Git/CDN 게시 경계는 유지한다. Python 3.14 표준 라이브러리만 사용한다.

## 인증과 실행 경계

- 사용자 지정 `MONMUSU_OPENAI_API_KEY`만 읽는다. 현재 프로세스에 없으면 Windows 사용자 환경 변수의 같은 이름을 읽는다. 키를 파일에 쓰거나 출력하지 않는다.
- Codex의 ChatGPT 로그인과 `OPENAI_API_KEY`는 변경하거나 대체하지 않는다.
- `plan`, `status`, `import`, `handoff`, preflight 및 테스트는 네트워크를 사용하지 않는다.
- `run --approve-plan <plan.json SHA256>`만 입력 토큰 계수와 Responses 생성 API를 호출한다. 모델·범위·예산에 대한 실제 사용자 확인 후 이 명령을 실행한다. SHA 인자는 검수자 신원 인증이 아니다.
- 모델은 `gpt-5.6-sol`, reasoning mode는 `standard`, effort는 `high`/`xhigh`. `store:false`, `service_tier:default`, 30분 implicit cache, 도구 호출 없음, 자동 입력 절삭 없음.
- 신규 계획에서 effort를 생략하면 **xhigh**를 사용한다. 2026-11-04 PRO 비교에 따른 Novel 잠정 기본값이며, 비용·처리량을 우선할 때 `--effort high`를 명시할 수 있다. 기존에 동결한 계획의 설정·해시를 변경하지 않는다.
- 데이터 공유·조직·프로젝트·결제 설정은 이 도구가 조회하거나 변경하지 않는다. `store:false`는 학습 공유 설정과 별개다.

## 정상 초벌

기존 `novel prepare`로 만든 배치를 사용한다. 작성 중 KO·메모·HOLD 결정이 있거나 검수 round에 들어간 행은 API 대상으로 선택하지 않는다. 기존 초벌을 API로 다시 번역할 때는 별도 배치를 만든다.

```powershell
python -X utf8 tools/update/cli.py novel-api plan --batch work/novels/new-scene --run work/novels/api-new-scene --effort xhigh --budget-usd 5 --max-calls 8
python -X utf8 tools/update/cli.py novel-api status --run work/novels/api-new-scene
# 실제 사용자 확인 후, status가 표시한 정확한 SHA 사용
python -X utf8 tools/update/cli.py novel-api run --run work/novels/api-new-scene --approve-plan <SHA256>
python -X utf8 tools/update/cli.py novel-api import --run work/novels/api-new-scene --job <job-id> --batch work/novels/new-scene
python -X utf8 tools/update/cli.py novel review --batch work/novels/new-scene --round 001
python -X utf8 tools/update/cli.py novel-api handoff --batch work/novels/new-scene --round 001 --out work/novels/new-scene/PRO-001.zip
```

한 배치에 여러 장면이 있으면 장면별 job을 각각 import한다. API는 source 전체와 batch의 current context를 받지만 선택된 target_row_ids만 출력한다. 원본 source_cells·화자·명령·위치 등은 API에 다시 작성시키지 않고 로컬 정본에서 보존한다.

## high/xhigh 비교

```powershell
python -X utf8 tools/update/cli.py novel-api plan --comparison --scenario 10001A0_Nml --scenario 10289B0_Nml --scenario 10109C0_Nml --effort high --effort xhigh --run work/novels/api-trial-20261104 --budget-usd 5 --max-calls 8
```

이 예시는 26+33+27=86개 고유 원문 행, 6개 생성 job이다. 각 장면의 전체 문맥·Names/Knowledge가 두 effort에서 동일하며, 기존 정답 KO·검수 메모는 API에 전달하지 않는다. 이는 비교 계획 생성이며 API 실행이 아니다.

각 결과를 **새로운 배치**에 import하여 기존 PRO 경로를 사용한다. 예: `work/novels/trial-scene-high`, `work/novels/trial-scene-xhigh`. PRO가 두 후보를 비교한 후 최종 채택본 하나를 확정한다. 비교 후보를 모두 apply하지 않는다. 적용 기준 상태가 달라지면 오래된 후보는 기존 preimage 검사에 의해 차단된다. 동일 KO의 명시적 교정 배치도 검수할 수 있다.

## 예산과 요청 수

모든 금액은 정수 nanodollar로 계산한다. 2026-11-04 확인 단가를 계획에 기록했으며 2026-11-21 이후 생성 실행을 차단하여 단가 재확인을 요구한다.

| 토큰 | USD / 100만 토큰 |
| --- | ---: |
| 일반 입력 | 4 |
| 캐시 읽기 | 0.40 |
| 30분 캐시 쓰기 | 5 |
| 출력(추론 포함) | 20 |

- 입력 최대 20,000토큰, `max_output_tokens` 최대 25,000. 각 생성 전에 계수 endpoint로 동일한 instructions/input/schema/reasoning을 측정한다. 계수 실패 또는 입력 상한 초과 시 생성하지 않는다.
- 오프라인 계획의 `offline_request_utf8_bytes`는 요청 크기이며 토큰 수가 아니다. 실제 토큰 수는 승인 후 계수 API에서만 확인한다.
- 최악의 입력 요금으로 생성당 **$0.60**를 먼저 영구 저장하여 예약한다. 생성 8회가 모두 상한을 쓰면 **$4.80**이며 실행 예산은 $5다. 실제 사용량이 확인되면 사용액으로 정산한다.
- 캐시 쓰기는 일반 입력 요금에 추가하지 않는다. reasoning은 output_tokens에 이미 포함되어 있으므로 다시 더하지 않는다. 캐시 쓰기 분류가 없으면 비캐시 입력 전체를 쓰기 요금으로 보수적으로 계산한다.
- 기본 6회 + 추가 생성 최대 2회. 숨은 SDK 재시도는 없다. 계수 HTTP 요청도 별도로 기록하며 전체 HTTP 요청 상한은 생성 상한의 2배(이 예시는 16회)다. 자동 연결 시험·모델 목록 조회는 하지 않는다.
- 실패 응답/통신 중단으로 과금을 확인할 수 없으면 $0로 간주하지 않고 $0.60 예약을 유지한다. 새 호출 전 `실제 사용/예약 합계 + 다음 예약 ≤ 예산`을 확인한다.
- 사용량·모드·가격 범위를 검증할 수 없거나 상한을 넘는 응답이면 후속 호출을 중단한다. 원시 응답과 상태를 확인한 후 운영자가 처리한다. 기록을 지워 재시도하지 않는다.
- 이 한도는 **이 실행 계획만** 통제한다. 다른 프로그램·별도 실행 계획의 지출이나 플랫폼 전체 월 한도는 통제하지 않는다. 무료 혜택·잔액을 비용 0의 근거로 삼지 않는다.

공식 근거: [모델 단가](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [캐시 요금](https://developers.openai.com/api/docs/guides/prompt-caching), [입력 계수](https://developers.openai.com/api/docs/guides/token-counting), [실행별 예산](https://developers.openai.com/cookbook/articles/per_run_spending_controller_responses_api).

## 중단·재개·부분 오류

`plan.json`은 모델·정책·입력·문맥·코드·단가·상한을 고정한다. 변경된 계획을 기존 state와 함께 재사용하지 않는다. 코드/원문/current context가 변경되면 새 계획이 필요하다.

`state.json`은 호출 직전 예약을 기록한다. 요청은 `requests/`, 응답은 `responses/`, 검증 결과는 `results/`에 즉시 저장한다. `run` 재실행 시 저장 응답이 있으면 새 호출 없이 검증을 끝낸다. 응답 없이 중단된 생성은 `unknown`으로 남기고 자동 재호출하지 않는다. 한 workspace의 Novel 명령은 기존 OS 잠금으로 직렬화한다.

명시적 재시도:

```powershell
python -X utf8 tools/update/cli.py novel-api run --run work/novels/api-new-scene --approve-plan <SHA256> --retry-job <job-id>
```

- 재시도도 기존 예산·횟수 안에서 수행한다. 이미 유효하게 생성된 행은 제외한다.
- 누락·태그 오류는 해당 행의 기술 오류로 남긴다. 정상 행과 명시적 행별 HOLD는 import할 수 있다.
- 중복 ID·알 수 없는 ID·행 순서 변경은 해당 응답을 무효화한다. 원문 순서를 임의로 추측해 복구하지 않는다.
- 요청 전체 refusal/incomplete는 행 전체의 콘텐츠 HOLD로 확정하지 않는다. 해당 요청의 제한/미완료로 보고하고 다른 job은 계속한다. 인증·권한·rate/quota 오류는 호출을 중단하며 운영자 확인 후 재개한다.
- 이미 import한 job은 동결한다. 남은 blank 행은 기존 배치에서 새 API 계획으로 이어간다. 다른 미완료 job은 원래 run에서 이어갈 수 있다.

## Knowledge와 PRO 인계

API의 `changes_json`은 기존 changes 배열을 표현하는 JSON 문자열이다. 구조화 출력이 임의 Knowledge 내부 형식을 고정하지 않도록 이 필드만 별도로 파싱한다. 제안은 기존 Knowledge 검증기로 검사하며 approved=true 제안은 거부한다. 신규/갱신 Knowledge는 해당 장면 scope로 한정한다. 잘못된 제안은 기술 오류로 남기고 정상 번역 행을 버리지 않는다. 유효한 제안도 current에는 적용하지 않는다.

import는 기존 draft의 허용 필드와 changes에만 반영하고 API 메타데이터는 `api-provenance.json`에 둔다. 원문과 검수 상태에 API 필드를 추가하지 않는다. import와 영수증은 기존 journal transaction으로 함께 반영한다.

`novel review` 후 `handoff`는 정책, 전체 source, context, 초벌, 검수 snapshot/binding/review.json, provenance, 파일별 해시를 ZIP에 담는다. 원시 API 응답이나 키를 PRO ZIP에 넣지 않는다. 실패 원인은 provenance에 포함한다. 기존 Codex 배치도 동일한 handoff를 사용할 수 있다.

PRO는 실제 검수한 행만 approved로 확정하고, Knowledge의 origin.review_id를 최종 review_id에 맞춘다. 반환본을 원래 round의 review.json에 반영한 뒤 기존 `novel check → apply → verify`를 사용한다. Git commit/push/CDN 게시 및 게임 설치는 이 도구가 수행하지 않는다.

## 검증 범위

```powershell
python -X utf8 -m unittest discover -s tools -p test_novel_api.py -v
python -X utf8 tools/update/cli.py preflight
```

모든 API 테스트는 합성 원문과 가짜 전송 객체를 사용한다. 실제 호출·키 유효성·모델 품질·계정 과금 검증은 별도이며 오프라인 통과로 완료를 주장하지 않는다.

## 첫 실제 시험 기록 (2026-11-04)

사용자 승인으로 위 86행을 high/xhigh에서 생성했다. 6회 생성·12회 HTTP 요청(계수 6회 포함), 재시도 0회, 구조 검사 172/172행 통과, 오류·HOLD 0건이다. API 응답 사용량과 공식 단가로 계산한 비용은 high $0.401726, xhigh $0.629126, 합계 $1.030852다. 플랫폼의 크레딧 차감·청구 정산은 조회하지 않았다.

실행·보고서·PRO ZIP은 로컬 `work/novels/api-trial-20261104/`에 있다. Names 제안 8건은 미승인으로 인계했다. current Knowledge와 새 Knowledge 레코드 제안이 모두 0건이었으므로 비어 있지 않은 Knowledge의 실제 모델 적용 품질은 이 표본으로 검증되지 않았다.

## PRO 반환 반영 (2026-11-04)

사용자가 반환한 PRO 검수에서 세 장면 모두 xhigh 기반 최종본을 선택했고, 86행 승인·HOLD 0행을 확인했다. 초벌 대비 교정은 12+5+4=21행이며, 표현 다듬기와 다른 후보의 장점을 가져온 경우를 포함하므로 오역 21건으로 해석하지 않는다. 프로젝트의 기존 check를 통과한 세 검수본만 로컬 apply했다. 검수 준비 round `001`은 보존하고 반환 완료본은 동일 binding·초벌 snapshot을 갖는 round `002`에 기록했다.

Names는 `ナナエ → 나나에`, `ランケ → 란케`, `女魔術師Ａ → 여마술사 A`를 승인·반영했다. `？？？ → ???`는 미승인으로 유지하며 current Knowledge 변경은 0건이다. 장면 내 발언과 사실, 뒤에서 거짓말로 밝혀지는 주장을 구분하여 관찰 메모를 자동으로 current에 승격하지 않는다.

xhigh는 이 표본에서 high보다 $0.227400(약 56.6%) 비쌌다. 행 경계를 넘는 발화 연결과 단어 중간 정지 연출, 장면 안의 말투 전환에서 PRO가 확인한 이점을 근거로 잠정 기본값을 정했다. 나나에 장면은 내용 정확도가 동률이었다. 세 장면을 설정당 한 번 생성한 결과이므로 일반적인 정확도·품질 향상률이나 전체 작품 비용으로 확대하지 않는다. PRO 검수와 실행별 예산 확인은 계속 유지한다.

반환 원본·검사·적용 기록은 `work/novels/api-trial-20261104/pro-return-20261104/`에 보존한다. 추가 API 호출과 Git/CDN 게시·게임 검증은 이 반환 반영에서 수행하지 않는다.
