# 추가 기능 백엔드 및 프론트엔드 연동 안내

이 문서는 기존 Flask 백엔드에 추가한 10개 기능 영역의 API 계약과 운영 범위를 설명한다. 기존 회원가입·로그인, 가상 계좌, 월 현금흐름, 예·적금 가입·해지·배치, 주식·ETF 주문 기능을 기반으로 한다. API 구현과 실제 AWS 배포 완료는 별개이며, 아래 배포 항목은 운영 환경에서 확인할 절차다.

## 1. 기존 기능과 추가 구현의 경계

| 영역 | 기존 코드에서 사용하는 데이터·기능 | 추가 구현 |
| --- | --- | --- |
| 1. 저축 목표 | 가상 계좌, 예·적금 원금, 주식·ETF 평가금액 | 목표 생성·조회·수정·삭제, 달성률, 완료 처리 |
| 2. 미래 자산 시뮬레이션 | 현재 자산, 월 수입·지출, 예·적금 계산식 | 자유 시뮬레이션, 목표일 시뮬레이션, 가정 수익률·환율·월 배분 계산 |
| 3. 대시보드·자산 기록 | 계좌, 계약, 보유자산, 거래 및 원장 | 총자산·손익·구성비 조회, 일별 스냅샷 |
| 4. 거래·원장 조회 | 기존 `ledger_transactions`, `ledger_entries`, `market_transactions` | 본인 거래 목록·상세, 관리자 거래 조회 |
| 5. 프로필·공개 설정 | 회원 닉네임·가입일 | 본인 프로필 수정, 대표 뱃지, 항목별 공개 허용 |
| 6. 뱃지 | 실제 목표 완료·적금 납입·투자 손익 | 뱃지 목록, 자동 지급, 중복 방지 |
| 7. 커뮤니티 | 기존 JWT 인증 | 게시판, 게시글·댓글, 이미지, 추천·비추천, 검색·정렬, 신고 |
| 8. 거래 오류 문의 | 본인 금융 원장의 거래 식별자 | 문의 생성·조회, 이미지, 관리자 답변 |
| 9. 관리자 | 기존 `User.role`, 계좌 입출금·원장 생성 | 회원 상태·탈퇴, 사유가 있는 계좌 조정, 상품 수정·비활성화, 운영 처리 |
| 10. 감사 로그 | 기존 업무 트랜잭션 | 주요 변경 기록, 관리자 조회, 초기화·탈퇴 정책 연결 |

추가 코드는 `app/models/features.py`, `app/schemas/features.py`, `app/routes/features.py`, `app/routes/admin.py` 및 도메인별 `app/services/*_service.py`에 있다. 기존 금융 모델을 중복 생성하지 않고 연결한다. 이미 존재하던 회원·금융 API의 경로는 각 기존 라우트가 기준이다.

## 2. 공통 계약

- 아래 표의 모든 API는 `/api` 기준이다. 일반 조회, 공개 프로필, 자유 시뮬레이션, 이미지 조회도 로그인이 필요하다.
- `Authorization: Bearer <access_token>` 또는 기존 로그인에서 발급한 JWT 쿠키를 사용한다. 정지·탈퇴 계정과 무효화된 토큰은 이용할 수 없다.
- `/api/admin/*`는 DB의 현재 회원 권한이 `ADMIN`이어야 한다. 화면에서 관리자 메뉴를 숨기는 것과 별도로 서버에서 검사한다.
- JSON 요청은 객체여야 한다. 선언되지 않은 키는 검증 오류다. `user_id`, `role`, 잔액, 거래가격, 완료 상태, 뱃지 보유 여부를 임의로 전송하여 지정할 수 없다.
- 금액·수량 식별자 등 정수 필드는 JSON 정수를 사용한다. 공개 설정 등 boolean은 JSON `true`/`false`만 허용한다. 문자열 `"true"`, 숫자 `1`로 대체하지 않는다.
- 일반 날짜는 `YYYY-MM-DD`, 시간은 UTC ISO 8601 문자열(`Z` 포함)이다. 저축 목표의 오늘 및 스냅샷 날짜는 `Asia/Seoul` 기준이다. Decimal 값(금리, 수량 등)의 응답은 문자열일 수 있다.
- 빈 변경 요청과 공백뿐인 필수 문자열은 거절한다. PATCH에서 생략한 필드는 유지된다. 관리자 상품 수정에는 별도로 `reason`이 필요하다.

성공 응답:

```json
{"success": true, "data": {}, "message": "요청이 성공했습니다."}
```

업무·입력 오류 응답:

```json
{"success": false, "error": {"code": "INVALID_REQUEST", "message": "오류 설명"}}
```

생성은 HTTP 201, 일반 성공은 200이다. 삭제 성공도 JSON 응답의 `data: {}`를 반환한다. 이미지 GET만 JSON이 아닌 이미지 바이트를 반환한다. 주요 오류는 입력 400, 인증 401, 권한 403, 본인 소유가 아니거나 없는 항목 404, 중복·상태 충돌 409, 크기 초과 413, 업무 조건 위반 422, 요청 제한 429다. 시세·환율 오류는 기존 시장 데이터 서비스의 오류 또는 유효하지 않은 데이터에 대한 503으로 반환될 수 있다. 이를 자산 0원으로 표시하지 않는다.

### 목록과 요청 제한

페이지가 있는 목록은 `?page=1&size=20`을 사용한다. `page`는 1~10,000, `size`는 1~100이고 기본값은 각각 1, 20이다.

```json
{"success": true, "data": {"items": [], "page": 1, "size": 20, "total": 0}, "message": "요청이 성공했습니다."}
```

목표 목록과 뱃지 목록은 배열이며 페이지 응답이 아니다. 대시보드는 집계 객체다. 나머지 목록은 아래 표에 별도 표기가 없으면 페이지 응답이다. `total`로 다음 페이지 유무를 판단한다.

추가 API의 제한 카운터는 사용자·엔드포인트별 DB 기반 1분 창을 사용하므로 동일 DB에 연결된 여러 워커 사이에서 공유한다. GET은 기본 분당 120회, 변경 요청은 기본 분당 30회이며 각각 `FEATURE_READ_REQUESTS_PER_MINUTE`, `FEATURE_WRITE_REQUESTS_PER_MINUTE` 환경설정으로 조정한다. 429이면 호출을 멈추고 지연 후 다시 시도한다. 이 제한이 기존 전체 API의 제한까지 대체하는 것은 아니다.

## 3. 목표·대시보드·거래·뱃지

| 메서드 | 경로 | 입력·동작 |
| --- | --- | --- |
| GET | `/goals` | 본인 목표 배열; 조회 시 달성과 뱃지 평가 |
| POST | `/goals` | `goal_name`, `target_amount`, `target_date` |
| GET | `/goals/{goal_id}` | 본인 목표 및 현재 `progress_percent` |
| PATCH | `/goals/{goal_id}` | 생성 필드 중 변경할 필드 |
| DELETE | `/goals/{goal_id}` | 목표만 삭제; 금융자산에는 영향 없음 |
| POST | `/simulations/free` | 자유 시뮬레이션; 아래 상세 계약 참고 |
| POST | `/goals/{goal_id}/simulation` | 본인 목표 기반 가정 계산 |
| GET | `/dashboard` | 본인 자산·손익·목표·뱃지·월 잉여자금·활성 계약·최근 매매 |
| GET | `/dashboard/history` | 일별 자산 기록, 최근 날짜 순 |
| GET | `/transactions` | 원장 거래, 최신 ID 순; 선택 필터 `transaction_type`(50자 이하) |
| GET | `/transactions/{transaction_id}` | 본인 원장 거래와 `entries` |
| GET | `/investments/transactions` | 본인 주식·ETF 거래, 최신 ID 순 |
| GET | `/badges` | 지급 가능한 뱃지 정의 배열 |
| GET | `/badges/me` | 본인의 획득 뱃지 배열; 현재 달성 조건 평가 |

목표명은 1~50자, 목표금액은 1원~10억 원이며 현재 총자산 이상, 목표일은 오늘 이후다. 총자산과 같은 금액으로 생성·수정하면 즉시 완료 처리된다. PRD 본문의 “현재 총자산 이상”을 기준으로 하며, DB 설명에 다른 엄격 부등식이 있더라도 동일 금액을 허용한다. 사용자당 완료 목표를 포함하여 최대 5개다. 완료된 목표는 수정할 수 없고, 삭제할 수 있다. 목표는 특정 금융상품과 연결하지 않는다. 달성률은 `현재 총자산 / 목표금액 × 100`이며 100을 넘을 수 있다. 목표 생성·수정, 대시보드·목표 목록·내 뱃지 조회와 스냅샷 배치에서 목표 완료 및 뱃지 지급을 평가하므로 해당 조회가 완료 상태를 갱신할 수 있다.

```json
{"goal_name": "여행 자금", "target_amount": 20000000, "target_date": "2027-12-31"}
```

대시보드 주요 필드:

| 필드 | 의미 |
| --- | --- |
| `amounts` | `cash`, `deposit`, `saving`, `kr_stock`, `us_stock`, `kr_etf`, `us_etf`별 원화 금액 |
| `total_assets` | 계좌 잔액 + 활성 예금 원금 + 실제 납입 적금 원금 + 시장자산 평가금액 |
| `net_funding` | 원장에 기록된 초기 자산 + 월 수입 − 월 지출 ± 관리자 조정 |
| `total_profit` | 총자산 − 순투입금; 수입이나 관리자 입금을 투자 이익으로 계산하지 않음 |
| `investment_profit` | 현재 시장 평가금액 + 순매도대금 − 수수료 포함 매수대금 |
| `investment_return_percent` | 위 투자 손익 / 누적 매수대금 × 100; 매수가 없으면 `null` |
| `unrealized_profit` | 현재 보유시장자산의 평가금액 − 해당 보유자산 취득원가 |
| `holdings` | 보유 종목, 수량·가격 문자열, 원화 평가액·취득원가·미실현 손익 |
| `allocation_percent`, `valued_at` | 구성 비율과 평가 시각 |
| `monthly_income`, `monthly_expense`, `monthly_surplus` | 설정된 월 수입, 지출, 차액 |
| `active_deposits`, `active_savings`, `recent_trades` | 활성 예·적금과 최근 시장 거래 최대 5개 |
| `goals`, `badges` | 본인 목표와 획득 뱃지 |

만기 전 예·적금의 아직 지급되지 않은 이자는 현재 총자산에 가산하지 않는다. 투자수익률은 현금흐름 시점을 가중하는 연환산 수익률이 아니라 누적 매수대금 기준이다. 이 정의를 프론트엔드 설명과 맞춘다. 스냅샷은 사용자·서울 날짜별 하나이며 같은 날 재실행하면 갱신한다. 기존 과거 시점의 기록을 만들어내지 않으므로 최초 기록 전 날짜는 비어 있다.

현재 자동 뱃지 조건은 `FIRST_GOAL`(목표 1개 완료), `THREE_GOALS`(3개 완료), `SAVING_SIX_PAYMENTS`(같은 적금의 실제 PAID 6회 이상), `INVESTMENT_TEN_PERCENT`(위 정의의 투자수익률 10% 이상)다. 사용자·뱃지 조합에 유일 제약이 있고, 사용자 임의 지급 API는 없다. 카탈로그는 `seed-features` 명령으로 준비한다.

## 4. 미래 자산 시뮬레이션

시뮬레이션 결과의 `is_hypothetical`은 `true`다. 계좌 잔액, 금융 거래, 원장, 실제 예·적금 계약과 주문을 변경하지 않는다. API 접근에 따른 요청 제한 카운터는 별도다.

공통 필수 입력:

| 필드 | 제약 |
| --- | --- |
| `monthly_allocation` | 자산별 월 배분 원화 정수; 각 0~1천만 원; 합계는 월 수입−지출과 동일 |
| `annual_returns` | 가정 연 수익률(%); `saving`, `kr_stock`, `us_stock`, `kr_etf`, `us_etf`만 허용; 생략 항목 0%; 시장자산 −100~100%, `saving` 0~100% |
| `future_exchange_rate` | 미래 USD/KRW 가정, 1~10,000의 유한 숫자 |

자산 배분 키는 `cash`, `saving`, `kr_stock`, `us_stock`, `kr_etf`, `us_etf`다. 월 배분에는 추가로 `existing_saving`이 있다. 이는 기존 적금 납입을 위한 현금 확보 금액이며 현재 현금과 함께 실제 계약 일정의 납입에 사용된다. 자유 시뮬레이션에서는 기존 적금이 없으므로 `existing_saving`은 생략하거나 0이어야 한다.

자유 시뮬레이션에는 다음이 모두 필요하다: `initial_asset`(0~1억 원), `monthly_income`·`monthly_expense`(각 0~1천만 원, 지출≤수입), `months`(1~600), `initial_allocation`(합계=초기 자산), `initial_exchange_rate`(1~10,000). 두 배분 객체는 금액 단위이며 비율이 아니다.

```json
{
  "initial_asset": 10000000,
  "monthly_income": 3000000,
  "monthly_expense": 2000000,
  "months": 24,
  "initial_allocation": {"cash": 5000000, "saving": 3000000, "us_etf": 2000000},
  "monthly_allocation": {"cash": 200000, "saving": 500000, "us_etf": 300000},
  "annual_returns": {"saving": 3.5, "us_etf": 5},
  "initial_exchange_rate": 1350,
  "future_exchange_rate": 1400
}
```

목표 시뮬레이션에서는 현재 자산·계약, 월 수입·지출, 시작 환율, 목표일까지의 기간을 서버에서 조회한다. 자유 시뮬레이션의 추가 6개 입력 필드(`initial_asset`부터 `initial_exchange_rate`까지)는 전송하지 않는다. 목표일은 오늘 이후 600개월 이내여야 한다. 다음 예시의 배분 합계는 본인의 월 잉여자금이 100만 원일 때 유효하다.

```json
{
  "monthly_allocation": {"existing_saving": 300000, "cash": 200000, "us_etf": 500000},
  "annual_returns": {"saving": 3.5, "us_etf": 5},
  "future_exchange_rate": 1400
}
```

계산 가정:

- 이미 반영된 과거 수입·지출을 다시 더하거나 빼지 않는다. 미래 월 잉여자금은 시작일로부터 매월 같은 날짜에 수익 반영 후 투입하며 월말은 기존 날짜 보정 규칙을 따른다.
- 시장자산은 가정 연 유효수익률을 실제 경과일/365로 적용한다. 미국 자산의 달러 수익과 원화 환산 변화를 함께 반영한다.
- 환율은 현재 환율에서 미래 환율까지 날짜에 따라 선형 변화한다고 가정한다. 실제 환율 예측 모델이 아니다.
- 기존 예·적금은 저장된 계약 금리·계산방식·납입 이력·만기일을 사용한다. 기존 적금은 앞으로 도래하는 계약일에 현금을 확인하고 부족하면 미납으로 계산하며 과거 미납을 추가 납입하지 않는다.
- 기존 계약 만기 시 원금과 계산된 세후 이자를 가정 현금에 반영한다. 이미 만기일이 지났지만 ACTIVE인 계약은 가정 첫날 정산하되 이자는 원래 만기일까지 계산한다. 실제 배치를 대신 실행하지 않는다.
- 추가 `saving` 자산은 특정 은행 상품 가입이 아니라 가정 수익률로 성장시키며, 전망 종료 시 양의 이익에 15.4% 세율을 적용하는 계산 모델이다. 실제 상품별 우대조건을 새로 충족한다고 간주하지 않는다.
- 매매 수수료·시장자산 세금은 미래 가정 계산에 포함하지 않는다. `assumptions`에 계산 전제가 들어 있으므로 화면에 전제와 함께 결과를 표시한다.

주요 응답은 `start_date`, `end_date`, `initial_assets`, `future_contributions`, `amounts`, `expected_total_assets`, `expected_interest`, `expected_tax`, `expected_net_interest`, `expected_investment_profit`, `exchange_rate_effect`, `missed_payments`, `timeline`, `assumptions`다. 목표 시뮬레이션에는 `goal_id`, `target_amount`, `difference`, `progress_percent`가 추가된다. `amounts.existing_deposit`와 `amounts.existing_saving`은 종료일까지 만기되지 않은 기존 계약의 원금이다. 현금에 이미 만기입금된 금액과 중복 합산하지 않는다.

## 5. 프로필·공개 설정

| 메서드 | 경로 | 입력·응답 |
| --- | --- | --- |
| GET | `/profiles/me` | 본인 프로필, 공개 설정, 자산 요약·목표·뱃지 |
| PATCH | `/profiles/me` | `nickname`(2~20자), `representative_badge_id`(보유 뱃지 ID 또는 해제용 `null`) 중 하나 이상; 응답은 `user_id`, `nickname`, `representative_badge_id` |
| GET | `/profiles/me/visibility` | 모든 공개 설정 boolean |
| PATCH | `/profiles/me/visibility` | 아래 키 중 변경할 boolean 하나 이상 |
| GET | `/profiles/{target_id}` | 대상의 닉네임과 공개 허용한 요약 정보 |

공개 설정 키: `show_joined_at`, `show_badges`, `show_active_goals`, `show_completed_goals`, `show_goal_progress`, `show_total_assets`, `show_asset_allocation`, `show_investment_return`. 기본값은 전부 `false`다. 비공개 값은 응답에서 생략되므로 필드가 없으면 비공개로 처리한다. 다른 사용자의 프로필에 로그인 아이디·계좌 상세·월 수입·지출·종목별 매수가·거래·신고·운영 처리 내역을 포함하지 않는다. 다른 사용자에게 목표금액은 반환하지 않으며, 공개 허용된 목표 진행률만 반환한다. 목표 목록의 공개 여부와 진행률의 공개 여부는 별도다.

```json
{"show_badges": true, "show_active_goals": true, "show_goal_progress": false, "show_total_assets": false}
```

## 6. 커뮤니티·신고·문의·이미지

| 메서드 | 경로 | 입력·동작 |
| --- | --- | --- |
| GET | `/posts` | 선택 필터 `board_type`, 검색 `q`(100자 이하), 정렬 `sort=latest\|likes\|dislikes` |
| POST | `/posts` | `board_type`, `title`(1~100자), `content`(1~10,000자) |
| GET | `/posts/{post_id}` | 게시글, `reactions: {LIKE, DISLIKE}`, `attachments` |
| PATCH | `/posts/{post_id}` | 본인 게시글의 생성 필드 중 변경할 필드 |
| DELETE | `/posts/{post_id}` | 본인 글 소프트 삭제; 첨부 이미지 제거 |
| GET | `/posts/{post_id}/comments` | 삭제되지 않은 댓글, ID 오름차순 |
| POST | `/posts/{post_id}/comments` | `content`(1~1,000자) |
| PATCH | `/comments/{comment_id}` | 본인 댓글 `content` 수정 |
| DELETE | `/comments/{comment_id}` | 본인 댓글 소프트 삭제 |
| PUT | `/posts/{post_id}/reaction` | `reaction_type`: `LIKE`, `DISLIKE`, `NONE` |
| POST | `/reports` | `target_type`: `POST` 또는 `COMMENT`, 양의 정수 `target_id`, `reason`(1~1,000자) |
| GET | `/reports/me` | 본인이 작성한 신고만, 최신 ID 순 |
| POST | `/inquiries` | `title`(1~100자), `content`(1~5,000자), 선택 `related_ledger_transaction_id`(본인 원장 거래 ID 또는 `null`) |
| GET | `/inquiries` | 본인 문의와 답변·첨부파일, 최신 ID 순 |
| GET | `/inquiries/{inquiry_id}` | 본인 문의 상세 |
| POST | `/posts/{post_id}/images` | 본인 글에 `multipart/form-data`, 반복 필드 `images` |
| POST | `/inquiries/{inquiry_id}/images` | 본인 문의에 같은 이미지 형식 |
| GET | `/attachments/{attachment_id}` | 인증된 이미지 응답 |
| DELETE | `/attachments/{attachment_id}` | 본인 첨부 이미지 삭제 |

게시판은 `FREE`, `KR_STOCK`, `US_STOCK`, `DEPOSIT_SAVING`만 허용한다. 게시글 정렬은 선택한 반응 수 내림차순 후 ID 내림차순이며, `latest`는 ID 내림차순이다. 제목·본문을 문자열로 검색한다. 게시글·댓글 내용은 데이터 문자열이므로 React 텍스트 렌더링 등으로 출력하고 HTML 실행 방식으로 삽입하지 않는다.

한 사용자는 게시글마다 반응 하나만 유지한다. PUT으로 상태를 변경하고 `NONE`은 취소한다. 동일 사용자·동일 게시글/댓글의 신고는 한 번만 가능하며 중복은 409다. 삭제된 게시글·댓글에 수정·댓글 생성·신고할 수 없다. 신고는 `PENDING`에서 관리자 처리로 `RESOLVED` 또는 `REJECTED`가 된다. 신고 해결이 게시글을 자동 삭제하는 것은 아니며 운영 삭제 API가 별도로 있다.

문의는 `PENDING`으로 생성되고 관리자 답변 후 `ANSWERED`가 된다. 관련 거래 ID는 `market_transaction_id`가 아닌 금융 원장의 `ledger_transaction_id`다. 생성 시 작성자 소유 거래인지 확인한다. 문의 수정·삭제 API와 댓글 대댓글 API는 제공하지 않는다.

이미지 정책은 게시글·문의 각각 누적 최대 5장, 파일당 최대 10MB(10×1,024×1,024바이트), 허용 확장자 `.png`, `.jpg`, `.jpeg`, `.webp`다. MIME과 디코딩된 실제 이미지 형식이 일치해야 하고 최대 16,000,000픽셀이다. 원본과 서버 재인코딩 결과 모두 10MB 이하여야 한다. 전체 HTTP 본문 한도는 51MB다. 파일명을 저장 경로로 사용하지 않으며, 서버에서 다시 인코딩한 바이트를 `attachments` 테이블에 저장한다. 업로드가 성공하면 현재 부모 항목의 전체 첨부 목록 `[{attachment_id, url}]`을 반환한다.

### 쿠키·비공개 이미지 연동 예시

기존 쿠키 인증을 사용하는 동일 출처 프론트엔드는 변경 요청에 `csrf_access_token` 쿠키 값을 `X-CSRF-TOKEN` 헤더로 전달한다. 헤더 토큰 인증에서는 Bearer 토큰을 사용한다. 개발 환경은 기존 Vite `/api` 프록시, 배포 환경은 Nginx `/api` 프록시를 유지하면 동일 출처가 된다.

```javascript
function accessCsrf() {
  const part = document.cookie.split("; ").find(v => v.startsWith("csrf_access_token="));
  return part ? decodeURIComponent(part.slice("csrf_access_token=".length)) : "";
}

const response = await fetch("/api/goals", {
  method: "POST",
  credentials: "same-origin",
  headers: {"Content-Type": "application/json", "X-CSRF-TOKEN": accessCsrf()},
  body: JSON.stringify({goal_name: "여행 자금", target_amount: 20000000, target_date: "2027-12-31"})
});
const result = await response.json();
if (!response.ok || !result.success) throw new Error(result.error?.message ?? "요청 실패");
```

```javascript
const form = new FormData();
for (const file of selectedFiles) form.append("images", file);
const response = await fetch(`/api/posts/${postId}/images`, {
  method: "POST",
  credentials: "same-origin",
  headers: {"X-CSRF-TOKEN": accessCsrf()},
  body: form
});
// multipart의 Content-Type은 브라우저가 boundary와 함께 생성하도록 직접 지정하지 않는다.
```

쿠키 인증에서는 응답의 `url`을 동일 출처 `<img src={url}>`에 연결할 수 있다. 게시글 이미지는 로그인 사용자에게, 문의 이미지는 작성자 또는 관리자에게만 반환한다. 이미지 응답은 `Cache-Control: private, no-store` 및 `X-Content-Type-Options: nosniff`를 설정한다. URL만 안다고 비로그인으로 열 수 있는 공개 저장소 주소가 아니다.

Bearer 인증만 사용하는 화면에서 `<img>`는 Authorization 헤더를 붙일 수 없으므로 인증 fetch 후 Blob URL로 표시하고 해제 시 `URL.revokeObjectURL`을 호출한다. 이 경우 프론트 CSP `img-src`에 `blob:` 허용 여부를 먼저 맞춘다. 현재 동일 출처 쿠키 경로에서는 Blob URL이 필요하지 않다.

## 7. 관리자

모든 경로는 `/api/admin` 기준이고 ADMIN 인증이 필요하다. 아래 변경 API의 `reason`은 공백이 아닌 1~1,000자로 필수다. 계좌 조정 사유나 처리 사유에 비밀번호·토큰을 넣지 않는다.

| 메서드 | 경로 | 입력·동작 |
| --- | --- | --- |
| GET | `/users` | 아이디 검색 `q`(100자 이하), 페이지 목록 |
| GET | `/users/{user_id}` | 운영용 회원 정보; 비밀번호 해시·인증 내부 상태 일부 제외 |
| PATCH | `/users/{user_id}/status` | `status=ACTIVE\|SUSPENDED`, `reason` |
| DELETE | `/users/{user_id}` | JSON `reason`; 탈퇴 처리 |
| POST | `/users/{user_id}/adjustments` | 0이 아닌 원화 정수 `amount`(−1억~1억), `reason` |
| GET | `/products` | 기존 금융상품 페이지 목록 |
| GET | `/products/{product_id}` | 상품 상세와 `options` 배열; 상품 및 각 옵션의 `sync_locked` 포함, 비활성 항목도 운영 조회 가능 |
| PATCH | `/products/{product_id}` | `reason`, 선택 `product_name`(1~200자), `description`(1~10,000자), `join_target`(1~255자), `is_active`, `sync_locked` |
| PATCH | `/products/{product_id}/options/{option_id}` | `reason`, 선택 `base_interest_rate`, `max_interest_rate`(0~99.9999, 소수 4자리), `min_amount`, `max_amount`(1~10억 정수), `is_active`, `sync_locked` |
| DELETE | `/products/{product_id}` | JSON `reason`; 실제 삭제 대신 비활성화 |
| GET | `/transactions` | 선택 숫자 문자열 `user_id` 필터, 원장과 상세 entries |
| GET | `/transactions/{transaction_id}` | 특정 원장 거래 상세 |
| GET | `/market-transactions` | 전체 시장 거래, 최신 ID 순 |
| GET | `/posts` | 일반 게시글 목록과 같은 검색·정렬; 삭제된 글 제외 |
| GET | `/comments` | 삭제되지 않은 전체 댓글, 최신 ID 순 |
| DELETE | `/posts/{post_id}` | JSON `reason`; 운영 삭제 |
| DELETE | `/comments/{comment_id}` | JSON `reason`; 운영 삭제 |
| GET | `/reports` | 전체 신고, 최신 ID 순 |
| PATCH | `/reports/{report_id}` | `status=RESOLVED\|REJECTED`, `reason`; 이미 처리된 신고는 409 |
| GET | `/inquiries` | 전체 문의와 첨부 목록, 최신 ID 순 |
| GET | `/inquiries/{inquiry_id}` | 문의 상세 |
| PATCH | `/inquiries/{inquiry_id}/answer` | `answer`(1~5,000자), `reason`; 답변 갱신 가능 |
| GET | `/audit-logs` | 선택 `action`, `target_type` 필터(각 80자 이하), 최신 ID 순 |

계좌 조정은 기존 계좌 잠금 및 입금·출금 서비스를 거쳐 `ADMIN_ADJUSTMENT` 원장과 감사 로그를 같은 트랜잭션으로 남긴다. 음수 잔액을 만들 수 없다. 사용자 자율 입출금 API가 아니며 요청에서 `balance`를 직접 지정하지 않는다. ADMIN 계정과 이미 탈퇴한 계정은 이 회원 상태·탈퇴 API로 변경할 수 없다. 회원 상태가 변경되면 토큰 버전을 올려 기존 토큰을 무효화한다.

상품 옵션은 같은 상품 소속이어야 하고, 최대 금액≥최소 금액 및 최고 금리≥기본 금리를 검사한다. 기존 가입 계약에 저장된 당시 금리와 조건은 별도 계약 데이터이므로 상품 수정으로 과거 계약을 재계산하지 않는다. 상품 신규 수집·등록은 기존 금융감독원 동기화 흐름을 사용한다.

관리자가 상품·옵션을 PATCH하면 기본적으로 해당 행의 `sync_locked=true`를 저장하여 이후 금융감독원 응답에 계속 존재하는 항목의 수정값을 보존한다. `sync_locked`도 엄격한 JSON boolean이다. `{"sync_locked": false, "reason": "공급자 데이터 동기화 재개"}`로 해제하면 다음 동기화부터 원본 데이터로 갱신한다. 상품 DELETE는 비활성화와 동기화 잠금을 함께 설정한다. 공급자 응답에서 사라진 상품·옵션은 잠금 여부와 별개로 기존 판매 종료 비활성화 정책을 따른다. 상품과 옵션의 잠금은 각각 독립적으로 관리한다.

공개 회원가입·프로필 변경·관리자 API에 임의 역할 승격 필드는 없다. 운영 ADMIN 계정 준비는 접근이 통제된 운영 절차에서 별도로 수행한다. `seed-features`는 뱃지 정의만 준비하며 관리자 계정을 만들지 않는다.

## 8. 감사 로그·초기화·탈퇴

감사 로그는 업무 변경과 같은 DB 세션·트랜잭션에 추가된다. 행위자, 대상, 행동, 변경 전후 허용 필드, 사유, 요청 IP 및 UTC 시각을 사용한다. 시스템 배치 등 행위자가 없는 작업은 `actor_user_id`가 `null`일 수 있다. 비밀번호 해시·토큰·소셜 식별자와 게시글·문의 본문을 자동 변경 JSON에 복사하지 않는다. 사유는 운영자가 입력한 문장으로 저장된다.

목표·계좌·금융 계약·원장·뱃지 등의 주요 ORM 변경과 커뮤니티 생성·수정·삭제, 이미지 업로드·삭제, 공개 설정 변경, 관리자 처리에 로그가 생성된다. 감사 로그를 일반 사용자에게 제공하거나 수정·삭제하는 API는 없다. 시스템 외부 SQL 수정까지 추적하는 DB 감사 제품을 구현한 것은 아니다.

시뮬레이션 초기화는 기존 `DELETE /api/simulation/reset` 정책에 추가 금융학습 데이터를 연결한다. 정리 서비스는 `financial_cleanup_service.py`, `simulation_service.py`, `user_service.py`다.

| 대상 | 초기화 정책 |
| --- | --- |
| 회원 계정·닉네임·가입일·권한 | 유지 |
| 계좌 잔액·초기 자산·월 수입·지출 설정 | 0으로 초기화, 최초 자산 재설정 허용 |
| 예금·적금·납입·시장 보유·거래·금융 원장·월 현금흐름 | 제거 |
| 목표·획득 뱃지·대표 뱃지·자산 스냅샷 | 제거 또는 선택 해제; 초기화 이후 새 학습 이력으로 재획득 가능 |
| 커뮤니티 게시글·게시글 이미지·댓글·반응·신고·감사 로그 | 유지 |
| 문의·문의 첨부 이미지 | 제거; 삭제된 금융 원장을 참조하는 문의를 남기지 않음 |
| 공개 설정 | 제거하여 모든 공개 항목을 기본 비공개로 복귀 |

초기화 작업 자체는 `SIMULATION_RESET`으로 감사 로그에 남는다. 이전 획득 뱃지는 현재 프로필의 보유 목록에서 제거되며 감사 이력과 구분된다. 회원 탈퇴는 동일 금융학습 데이터 정리에 더해 계좌·시뮬레이션 설정·소셜 연결을 제거하고 `WITHDRAWN` 상태와 토큰 무효화를 사용한다. 커뮤니티·신고·감사 기록은 유지되며 탈퇴 계정의 프로필과 비공개 API 접근은 차단된다. 비밀번호 변경과 사용자·관리자 탈퇴에도 별도 감사 이벤트가 있다.

## 9. DB·배포 확인

현재 코드는 하나의 `DATABASE_URL`과 SQLAlchemy 세션으로 서비스 데이터·계좌·원장·첨부 이미지·감사 로그를 관리한다. PRD 망 구성의 일반 서비스 DB와 심층망 원장 DB가 물리적으로 분리된 구조를 구현하거나 배포한 것은 아니다. 현재 트랜잭션의 원자성은 이 단일 DB 구성에 의존한다. 두 DB 분리는 별도의 네트워크·권한·트랜잭션 설계가 필요하다.

추가 마이그레이션은 `saving_goals`, `asset_snapshots`, `badges`, `user_badges`, `profile_visibility_settings`, `posts`, `comments`, `post_reactions`, `reports`, `inquiries`, `attachments`, `audit_logs`, `request_buckets`의 13개 테이블, 기존 금융상품·옵션 테이블 각각의 `sync_locked` 열, 기본 뱃지 4개를 추가한다. 이미지 데이터는 새 로컬 디렉터리나 공개 S3 URL 대신 DB에 저장하므로 다중 백엔드 워커가 같은 내용을 조회한다. 운영 DB 용량·백업에는 이 이미지 바이트도 포함된다. 프론트엔드 변경은 업로드를 지원하는 Nginx 본문 크기 설정이며, 추가 기능 화면 구현은 이 백엔드 작업 범위에 포함하지 않는다.

배포 환경의 올바른 DB 설정과 비밀키가 제공된 상태에서 백엔드 디렉터리를 기준으로 실행한다. `.env` 내용이나 운영 DB 데이터는 이 문서에 포함하지 않는다.

```sh
flask --app run.py db upgrade
flask --app run.py seed-features
flask --app run.py snapshots
```

마이그레이션이 기본 뱃지 4개를 준비하며, `seed-features`는 누락된 뱃지 정의를 중복 없이 보충하는 명령이다. `snapshots`는 현재 활성 사용자 자산을 수집하는 명령이며 시장 데이터 접근이 필요할 수 있다. 배치 스케줄러는 서울 시각 매일 23:50에 스냅샷과 오래된 요청 제한 카운터 정리를 실행한다. 일별 실행과 수동 실행이 같은 날 겹쳐도 사용자·날짜별 기록을 유지한다. 개별 시세 실패는 실패 집계와 서버 로그로 확인하고 0원 스냅샷으로 대체하지 않는다. 수동 `snapshots` 명령은 일부 사용자 실패가 있으면 결과를 출력한 뒤 실패 종료한다.

운영 반영 순서:

1. 운영 DB 백업 및 복구 지점을 확보하고, 배포 대상과 같은 DB 엔진의 별도 환경에서 기존 마이그레이션 이력부터 새 revision까지 적용한다. `db.create_all()`로 기존 운영 테이블을 대체하지 않는다.
2. 백엔드 이미지의 신규 의존성과 마이그레이션 파일을 포함한다. Flask 마이그레이션은 스케줄러가 새 테이블을 사용하기 전에 완료한다. 여러 워커에서 동시에 업그레이드를 수행하지 않도록 배포 순서를 맞춘다.
3. 뱃지 카탈로그를 준비하고 API 서버·스케줄러가 같은 `DATABASE_URL`을 사용하는지 확인한다. 하루 스냅샷 생성 시각과 기존 월 수입·지출·만기 배치 순서를 확인한다.
4. Nginx/앞단 프록시의 본문 크기 제한을 이미지 5장과 multipart 오버헤드를 수용하도록 백엔드 총 요청 제한 51MB와 맞춘다. 프론트 Nginx의 `client_max_body_size 51m` 외에 AWS 앞단 프록시가 있으면 그 제한도 확인한다. 더 작은 제한이 있으면 업로드 API에 도달하기 전에 413이 발생한다.
5. HTTPS에서 기존 `JWT_COOKIE_SECURE=true`, 동일 출처 API 프록시와 CSRF 전달을 확인한다. 실제 AWS 도메인의 인증·시세 공급자·금융상품 API 연결은 운영 설정으로 확인한다.
6. 일반 사용자와 관리자 각각으로 목표→대시보드, 프로필 공개 설정, 글·이미지·반응·신고, 본인 거래 문의→관리자 답변, 사유가 있는 계좌 조정→원장·감사 로그 흐름을 확인한다. 별도 테스트 계정으로 초기화 후 보존·삭제 범위를 확인한다.

SQLite에서 통과한 테스트만으로 MySQL의 행 잠금·실제 워커 동시성이나 AWS 배포를 검증했다고 해석하지 않는다. 이 문서는 테스트 통과 결과 또는 AWS 반영 완료를 주장하지 않으며, 실제 실행 결과는 작업 보고와 배포 기록으로 관리한다.
