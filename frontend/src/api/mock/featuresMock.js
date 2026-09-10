// 신규 기능(대시보드 / 저축목표 / 뱃지 등) 백엔드(features_bp)가 아직 Flask 에
// 등록되지 않아, 이 목 데이터로 프론트를 개발한다.
// 실제 API 가 붙으면 .env 에서 VITE_USE_MOCKS=false 로 바꾸면
// src/api/features.js 가 자동으로 실제 /api 호출로 전환된다.
// 응답 형태는 backend.zip 의 서비스 코드(portfolio_service.py 등) 기준으로 맞춰 둠.

export const MOCKS_ENABLED = import.meta.env.VITE_USE_MOCKS === 'true'

const delay = (ms = 200) => new Promise((resolve) => setTimeout(resolve, ms))

const ok = (data, message = '요청이 성공했습니다.') => ({ success: true, data, message })

const reject = (code, message, status = 400) =>
  Promise.reject({ response: { status, data: { success: false, error: { code, message } } } })

const TOTAL_ASSETS = 25680000
const TODAY = new Date().toISOString().slice(0, 10)

let goals = [
  { goal_id: 1, user_id: 1, goal_name: '유럽 여행 자금', target_amount: 30000000, target_date: '2027-06-30', status: 'ACTIVE', completed_at: null, created_at: '2026-07-01T09:00:00Z', updated_at: '2026-08-20T09:00:00Z' },
  { goal_id: 2, user_id: 1, goal_name: '비상금 마련', target_amount: 20000000, target_date: '2026-12-31', status: 'COMPLETED', completed_at: '2026-08-15T12:00:00Z', created_at: '2026-05-10T09:00:00Z', updated_at: '2026-08-15T12:00:00Z' },
]
let nextGoalId = 3

// 서버 goal_data(): progress_percent = round(total_assets / target_amount * 100, 4)
const goalData = (goal) => ({
  ...goal,
  progress_percent: Math.round((TOTAL_ASSETS / goal.target_amount) * 1000000) / 10000,
})

const BADGE_CATALOG = [
  { badge_id: 1, code: 'FIRST_GOAL', name: '첫 목표 달성', description: '저축 목표를 처음으로 달성했습니다.', badge_type: 'GOAL' },
  { badge_id: 2, code: 'THREE_GOALS', name: '목표 3개 달성', description: '저축 목표를 3개 이상 달성했습니다.', badge_type: 'GOAL' },
  { badge_id: 3, code: 'SAVING_SIX_PAYMENTS', name: '적금 6회 납입', description: '한 적금에 6회 이상 납입했습니다.', badge_type: 'SAVING' },
  { badge_id: 4, code: 'INVESTMENT_TEN_PERCENT', name: '수익률 10%', description: '투자 원금 대비 10% 이상 수익을 달성했습니다.', badge_type: 'INVESTMENT' },
]

const MY_BADGES = [
  { ...BADGE_CATALOG[0], acquired_at: '2026-08-15T12:00:00Z' },
  { ...BADGE_CATALOG[3], acquired_at: '2026-09-01T00:00:00Z' },
]

const HOLDINGS = [
  { asset_id: 1, symbol: '005930', name: '삼성전자', market: 'KR', asset_type: 'STOCK', quantity: '50', price: '83600', value_krw: 4180000, acquisition_cost_krw: 3900000, unrealized_profit_krw: 280000 },
  { asset_id: 2, symbol: 'AAPL', name: 'Apple Inc.', market: 'US', asset_type: 'STOCK', quantity: '18', price: '232.10', value_krw: 6250000, acquisition_cost_krw: 5600000, unrealized_profit_krw: 650000 },
  { asset_id: 3, symbol: 'QQQ', name: 'Invesco QQQ Trust', market: 'US', asset_type: 'ETF', quantity: '4', price: '498.30', value_krw: 2750000, acquisition_cost_krw: 2600000, unrealized_profit_krw: 150000 },
  { asset_id: 4, symbol: '360750', name: 'TIGER 미국S&P500', market: 'KR', asset_type: 'ETF', quantity: '110', price: '17300', value_krw: 1900000, acquisition_cost_krw: 1830000, unrealized_profit_krw: 70000 },
]

const dashboard = () => ({
  amounts: { cash: 3200000, deposit: 5000000, saving: 2400000, kr_stock: 4180000, us_stock: 6250000, kr_etf: 1900000, us_etf: 2750000 },
  total_assets: TOTAL_ASSETS,
  net_funding: 22000000,
  total_profit: 3680000,
  investment_profit: 1420000,
  investment_return_percent: 9.86,
  unrealized_profit: 1150000,
  holdings: HOLDINGS,
  exchange_rate: '1385.40',
  allocation_percent: { cash: 12.4611, deposit: 19.4704, saving: 9.3458, kr_stock: 16.2773, us_stock: 24.338, kr_etf: 7.3988, us_etf: 10.7087 },
  valued_at: '2026-09-07T01:30:00Z',
  goals: goals.map(goalData),
  badges: MY_BADGES,
  monthly_income: 3200000,
  monthly_expense: 2100000,
  monthly_surplus: 1100000,
  active_deposits: [
    { deposit_id: 7, bank_name: '우리은행', product_name: 'WON플러스예금', principal: 5000000, applied_interest_rate: '3.5500', start_date: '2026-06-01', maturity_date: '2026-12-01', status: 'ACTIVE' },
  ],
  active_savings: [
    { saving_id: 4, bank_name: '카카오뱅크', product_name: '자유적금', monthly_amount: 300000, total_paid_principal: 2400000, applied_interest_rate: '3.9000', start_date: '2026-01-10', maturity_date: '2026-12-10', status: 'ACTIVE' },
  ],
  recent_trades: [
    { market_transaction_id: 61, user_id: 1, asset_id: 2, side: 'BUY', quantity: '3', price: '231.40', exchange_rate: '1384.20', amount: '694.20', amount_krw: 960900, market_session: 'REGULAR', fee: 672, tax: 0, executed_at: '2026-09-05T14:12:00Z' },
    { market_transaction_id: 58, user_id: 1, asset_id: 1, side: 'SELL', quantity: '10', price: '84100', exchange_rate: null, amount: '841000', amount_krw: 841000, market_session: 'REGULAR', fee: 126, tax: 1513, executed_at: '2026-09-03T01:20:00Z' },
    { market_transaction_id: 55, user_id: 1, asset_id: 4, side: 'BUY', quantity: '30', price: '17250', exchange_rate: null, amount: '517500', amount_krw: 517500, market_session: 'REGULAR', fee: 77, tax: 0, executed_at: '2026-08-29T02:05:00Z' },
    { market_transaction_id: 51, user_id: 1, asset_id: 3, side: 'BUY', quantity: '1', price: '495.10', exchange_rate: '1381.00', amount: '495.10', amount_krw: 683732, market_session: 'REGULAR', fee: 478, tax: 0, executed_at: '2026-08-25T13:40:00Z' },
  ],
})

const history = () => ({
  items: [
    { snapshot_id: 30, user_id: 1, snapshot_date: '2026-09-06', total_assets: 25510000, amounts: {}, recorded_at: '2026-09-06T15:10:00Z' },
    { snapshot_id: 29, user_id: 1, snapshot_date: '2026-09-05', total_assets: 25320000, amounts: {}, recorded_at: '2026-09-05T15:10:00Z' },
    { snapshot_id: 28, user_id: 1, snapshot_date: '2026-09-04', total_assets: 25040000, amounts: {}, recorded_at: '2026-09-04T15:10:00Z' },
  ],
  page: 1,
  size: 20,
  total: 3,
})

// 원장 거래: ledger_data() = serialize(LedgerTransaction) + entries[serialize(LedgerEntry)]
// 최신순(ledger_transaction_id DESC)으로 나열
const credit = (id, amount) => [{ ledger_entry_id: id * 2, ledger_transaction_id: id, entry_type: 'CREDIT', amount, created_at: null }]
const debit = (id, amount) => [{ ledger_entry_id: id * 2, ledger_transaction_id: id, entry_type: 'DEBIT', amount, created_at: null }]

const LEDGER = [
  { ledger_transaction_id: 12, account_id: 1, user_id: 1, transaction_type: 'DEPOSIT_MATURITY', amount: 5120000, balance_after: 7420100, reference_type: 'DEPOSIT', reference_id: 5, created_at: '2026-09-06T00:05:00Z', entries: credit(12, 5120000) },
  { ledger_transaction_id: 11, account_id: 1, user_id: 1, transaction_type: 'SAVING_PAYMENT', amount: 300000, balance_after: 2300100, reference_type: 'SAVING', reference_id: 4, created_at: '2026-09-05T00:10:00Z', entries: debit(11, 300000) },
  { ledger_transaction_id: 10, account_id: 1, user_id: 1, transaction_type: 'STOCK_BUY', amount: 960900, balance_after: 2600100, reference_type: 'MARKET_TRANSACTION', reference_id: 61, created_at: '2026-09-05T14:12:00Z', entries: debit(10, 960900) },
  { ledger_transaction_id: 9, account_id: 1, user_id: 1, transaction_type: 'MONTHLY_EXPENSE', amount: 2100000, balance_after: 3561000, reference_type: 'MONTHLY_CASH_FLOW', reference_id: 4, created_at: '2026-09-01T00:00:00Z', entries: debit(9, 2100000) },
  { ledger_transaction_id: 8, account_id: 1, user_id: 1, transaction_type: 'MONTHLY_INCOME', amount: 3200000, balance_after: 5661000, reference_type: 'MONTHLY_CASH_FLOW', reference_id: 3, created_at: '2026-09-01T00:00:00Z', entries: credit(8, 3200000) },
  { ledger_transaction_id: 7, account_id: 1, user_id: 1, transaction_type: 'STOCK_SELL', amount: 841000, balance_after: 2461000, reference_type: 'MARKET_TRANSACTION', reference_id: 58, created_at: '2026-09-03T01:20:00Z', entries: credit(7, 841000) },
  { ledger_transaction_id: 6, account_id: 1, user_id: 1, transaction_type: 'SAVING_PAYMENT', amount: 300000, balance_after: 1620000, reference_type: 'SAVING', reference_id: 4, created_at: '2026-08-10T00:10:00Z', entries: debit(6, 300000) },
  { ledger_transaction_id: 5, account_id: 1, user_id: 1, transaction_type: 'STOCK_BUY', amount: 4180000, balance_after: 1920000, reference_type: 'MARKET_TRANSACTION', reference_id: 51, created_at: '2026-08-25T13:40:00Z', entries: debit(5, 4180000) },
  { ledger_transaction_id: 4, account_id: 1, user_id: 1, transaction_type: 'DEPOSIT_JOIN', amount: 5000000, balance_after: 6100000, reference_type: 'DEPOSIT', reference_id: 7, created_at: '2026-08-05T09:00:00Z', entries: debit(4, 5000000) },
  { ledger_transaction_id: 3, account_id: 1, user_id: 1, transaction_type: 'MONTHLY_EXPENSE', amount: 2100000, balance_after: 11100000, reference_type: 'MONTHLY_CASH_FLOW', reference_id: 2, created_at: '2026-08-01T00:00:00Z', entries: debit(3, 2100000) },
  { ledger_transaction_id: 2, account_id: 1, user_id: 1, transaction_type: 'MONTHLY_INCOME', amount: 3200000, balance_after: 13200000, reference_type: 'MONTHLY_CASH_FLOW', reference_id: 1, created_at: '2026-08-01T00:00:00Z', entries: credit(2, 3200000) },
  { ledger_transaction_id: 1, account_id: 1, user_id: 1, transaction_type: 'INITIAL_ASSET', amount: 10000000, balance_after: 10000000, reference_type: 'SIMULATION_SETTING', reference_id: 1, created_at: '2026-07-01T09:00:00Z', entries: credit(1, 10000000) },
]

const MARKET_TX = [
  { market_transaction_id: 61, user_id: 1, asset_id: 2, side: 'BUY', quantity: '3', price: '231.40', exchange_rate: '1384.20', amount: '694.20', amount_krw: 960900, market_session: 'REGULAR', fee: 672, tax: 0, executed_at: '2026-09-05T14:12:00Z' },
  { market_transaction_id: 58, user_id: 1, asset_id: 1, side: 'SELL', quantity: '10', price: '84100', exchange_rate: null, amount: '841000', amount_krw: 841000, market_session: 'REGULAR', fee: 126, tax: 1513, executed_at: '2026-09-03T01:20:00Z' },
  { market_transaction_id: 55, user_id: 1, asset_id: 4, side: 'BUY', quantity: '30', price: '17250', exchange_rate: null, amount: '517500', amount_krw: 517500, market_session: 'REGULAR', fee: 77, tax: 0, executed_at: '2026-08-29T02:05:00Z' },
  { market_transaction_id: 51, user_id: 1, asset_id: 3, side: 'BUY', quantity: '1', price: '495.10', exchange_rate: '1381.00', amount: '495.10', amount_krw: 683732, market_session: 'REGULAR', fee: 478, tax: 0, executed_at: '2026-08-25T13:40:00Z' },
  { market_transaction_id: 47, user_id: 1, asset_id: 2, side: 'BUY', quantity: '15', price: '228.90', exchange_rate: '1379.50', amount: '3433.50', amount_krw: 4736564, market_session: 'REGULAR', fee: 3315, tax: 0, executed_at: '2026-08-20T13:55:00Z' },
  { market_transaction_id: 40, user_id: 1, asset_id: 1, side: 'BUY', quantity: '60', price: '82000', exchange_rate: null, amount: '4920000', amount_krw: 4920000, market_session: 'REGULAR', fee: 738, tax: 0, executed_at: '2026-08-11T00:40:00Z' },
]

const paginate = (list, params = {}) => {
  const page = Math.max(1, Number(params.page || 1))
  const size = Math.min(100, Math.max(1, Number(params.size || 20)))
  const start = (page - 1) * size
  return { items: list.slice(start, start + size), page, size, total: list.length }
}

// --- 커뮤니티 ---
const MY_USER_ID = 1
const USER_NICKNAMES = { 1: '민재', 2: '하나', 3: '준서', 4: '서연' }
const nickname = (id) => USER_NICKNAMES[id] || `사용자 #${id}`
const BOARD_TYPES = ['FREE', 'KR_STOCK', 'US_STOCK', 'DEPOSIT_SAVING']

let posts = [
  { post_id: 5, user_id: 1, board_type: 'US_STOCK', title: '엔비디아 실적 발표 후 절반 익절했습니다', content: '이번 분기 실적 보고 절반 정리했어요. 환율도 애매해서 조금 보수적으로 갑니다.\n\n다들 어떻게 대응하셨나요?', created_at: '2026-09-04T11:20:00Z', updated_at: '2026-09-04T11:20:00Z' },
  { post_id: 4, user_id: 2, board_type: 'FREE', title: '가상자산 시뮬레이션 한 달 써본 후기', content: '예적금이랑 주식 같이 굴려보니 감이 잡히네요. 목표 달성률 보는 재미가 있습니다.', created_at: '2026-09-03T09:05:00Z', updated_at: '2026-09-03T09:05:00Z' },
  { post_id: 3, user_id: 3, board_type: 'KR_STOCK', title: '삼성전자 배당 재투자 고민', content: '배당금 들어오면 다시 매수할지 현금으로 둘지 고민입니다.', created_at: '2026-09-01T14:40:00Z', updated_at: '2026-09-02T02:10:00Z' },
  { post_id: 2, user_id: 2, board_type: 'DEPOSIT_SAVING', title: '적금 금리 비교표 공유합니다', content: '8개 은행 적금 금리를 정리했습니다. 우대조건 빼면 큰 차이는 없네요.', created_at: '2026-08-28T07:15:00Z', updated_at: '2026-08-28T07:15:00Z' },
  { post_id: 1, user_id: 4, board_type: 'FREE', title: '가입 인사드립니다', content: '재테크 공부하러 왔습니다. 잘 부탁드려요!', created_at: '2026-08-25T05:00:00Z', updated_at: '2026-08-25T05:00:00Z' },
]
let nextPostId = 6

// { [post_id]: { [user_id]: 'LIKE' | 'DISLIKE' } }
const postReactions = {
  5: { 1: 'LIKE', 2: 'LIKE', 3: 'DISLIKE' },
  4: { 1: 'LIKE', 2: 'LIKE', 3: 'LIKE', 4: 'LIKE' },
  3: { 3: 'LIKE' },
}

let comments = [
  { comment_id: 1, post_id: 5, user_id: 2, content: '저도 일부 익절했어요. 환율 1400 넘으면 더 줄일 생각입니다.', created_at: '2026-09-04T12:00:00Z', updated_at: '2026-09-04T12:00:00Z' },
  { comment_id: 2, post_id: 5, user_id: 3, content: '홀딩 중인데 다음 분기까지는 볼 생각이에요.', created_at: '2026-09-04T13:30:00Z', updated_at: '2026-09-04T13:30:00Z' },
  { comment_id: 3, post_id: 4, user_id: 1, content: '목표 달성률 보는 재미 공감합니다.', created_at: '2026-09-03T10:00:00Z', updated_at: '2026-09-03T10:00:00Z' },
]
let nextCommentId = 4

const reports = []
let nextReportId = 1

// --- 거래 오류 문의 ---
let inquiries = [
  { inquiry_id: 1, user_id: MY_USER_ID, related_ledger_transaction_id: 10, title: '주식 매수 수수료가 이상합니다', content: '체결 금액 대비 수수료가 예상보다 큰 것 같아요. 확인 부탁드립니다.', status: 'ANSWERED', admin_answer: '국내 주식 수수료 0.015%가 정상 적용된 건으로 확인됩니다. 추가 문의 주세요.', answered_at: '2026-09-06T02:00:00Z', answered_by: 99, created_at: '2026-09-05T15:00:00Z', updated_at: '2026-09-06T02:00:00Z' },
]
let nextInquiryId = 2
const inquiryData = (row) => ({ ...row, attachments: [], related_transaction: LEDGER.find((entry) => entry.ledger_transaction_id === row.related_ledger_transaction_id && entry.user_id === row.user_id) || null })

// --- 관리자 표본 데이터 ---
const ADMIN_USERS = [
  { user_id: 1, username: 'minjae', nickname: '민재', role: 'USER', status: 'ACTIVE', representative_badge_id: 1, created_at: '2026-07-01T09:00:00Z' },
  { user_id: 2, username: 'hana01', nickname: '하나', role: 'USER', status: 'ACTIVE', representative_badge_id: null, created_at: '2026-07-11T09:00:00Z' },
  { user_id: 3, username: 'junseo', nickname: '준서', role: 'USER', status: 'SUSPENDED', representative_badge_id: null, created_at: '2026-07-20T09:00:00Z' },
  { user_id: 99, username: 'admin', nickname: '관리자', role: 'ADMIN', status: 'ACTIVE', representative_badge_id: null, created_at: '2026-06-01T09:00:00Z' },
]
const ADMIN_PRODUCTS = [
  { product_id: 1, external_product_code: 'WR0001B', bank_name: '우리은행', product_name: 'WON플러스예금', product_type: 'DEPOSIT', description: '', join_target: '실명의 개인', is_active: true, sync_locked: false },
  { product_id: 2, external_product_code: 'KB0007S', bank_name: '국민은행', product_name: 'KB내맘대로적금', product_type: 'SAVING', description: '', join_target: '개인', is_active: true, sync_locked: false },
]
const ADMIN_OPTIONS = {
  1: [{ option_id: 11, product_id: 1, term_months: 12, base_interest_rate: '3.1500', max_interest_rate: '3.5500', min_amount: 10000, max_amount: 1000000000, is_active: true, sync_locked: false }],
  2: [{ option_id: 21, product_id: 2, term_months: 12, base_interest_rate: '3.4000', max_interest_rate: '4.1000', min_amount: 10000, max_amount: 3000000, is_active: true, sync_locked: false }],
}
let AUDIT_LOGS = [
  { audit_log_id: 3, actor_user_id: 99, action: 'ADMIN_USER_STATUS', target_type: 'users', target_id: 3, before_value: { status: 'ACTIVE' }, after_value: { status: 'SUSPENDED' }, reason: '커뮤니티 도배', ip_address: '127.0.0.1', created_at: '2026-09-06T05:00:00Z' },
  { audit_log_id: 2, actor_user_id: 1, action: 'CREATE', target_type: 'saving_goals', target_id: 1, before_value: null, after_value: { goal_name: '유럽 여행 자금', target_amount: '30000000', status: 'ACTIVE' }, reason: null, ip_address: '127.0.0.1', created_at: '2026-07-01T09:00:00Z' },
  { audit_log_id: 1, actor_user_id: 1, action: 'SIMULATION_RESET', target_type: 'users', target_id: 1, before_value: { balance: '250000' }, after_value: { balance: '0' }, reason: null, ip_address: '127.0.0.1', created_at: '2026-06-30T00:00:00Z' },
]
let nextAuditId = 4
const pushAudit = (entry) => { AUDIT_LOGS = [{ audit_log_id: nextAuditId++, actor_user_id: 99, ip_address: '127.0.0.1', created_at: new Date().toISOString(), before_value: null, after_value: null, reason: null, ...entry }, ...AUDIT_LOGS] }

const postData = (post) => {
  const reactionMap = postReactions[post.post_id] || {}
  const counts = { LIKE: 0, DISLIKE: 0 }
  Object.values(reactionMap).forEach((kind) => { counts[kind] += 1 })
  return {
    post_id: post.post_id,
    user_id: post.user_id,
    board_type: post.board_type,
    title: post.title,
    content: post.content,
    created_at: post.created_at,
    updated_at: post.updated_at,
    reactions: counts,
    attachments: [],
    // 아래 2개는 실제 백엔드 post_data() 에는 아직 없는 데모 편의 필드
    author_nickname: nickname(post.user_id),
    my_reaction: reactionMap[MY_USER_ID] || null,
  }
}

const commentData = (comment) => ({
  comment_id: comment.comment_id,
  post_id: comment.post_id,
  user_id: comment.user_id,
  content: comment.content,
  created_at: comment.created_at,
  updated_at: comment.updated_at,
  author_nickname: nickname(comment.user_id), // 데모 편의 필드
})

const findPost = (id) => posts.find((item) => item.post_id === Number(id))

// --- 프로필 / 공개 설정 (profile_service.py) ---
const profileState = { nickname: '민재', representative_badge_id: 1, created_at: '2026-07-01T09:00:00Z' }
const VISIBILITY_KEYS = [
  'show_joined_at', 'show_badges', 'show_active_goals', 'show_completed_goals',
  'show_goal_progress', 'show_total_assets', 'show_asset_allocation', 'show_investment_return',
]
const visibilityState = {
  show_joined_at: true,
  show_badges: true,
  show_active_goals: false,
  show_completed_goals: true,
  show_goal_progress: false,
  show_total_assets: false,
  show_asset_allocation: false,
  show_investment_return: true,
}

const buildProfile = (own, targetId = MY_USER_ID) => {
  const flags = { ...visibilityState }
  const dash = dashboard()
  const result = { user_id: targetId, nickname: own ? profileState.nickname : nickname(targetId) }
  if (own) result.visibility = flags
  if (own || flags.show_joined_at) result.created_at = profileState.created_at
  if (own || flags.show_badges) {
    result.badges = MY_BADGES
    result.representative_badge_id = profileState.representative_badge_id
  }
  if (own || flags.show_total_assets) result.total_assets = dash.total_assets
  if (own || flags.show_asset_allocation) result.allocation_percent = dash.allocation_percent
  if (own || flags.show_investment_return) result.investment_return_percent = dash.investment_return_percent

  const goalRows = (state) => goals.filter((goal) => goal.status === state).map((goal) => {
    const item = { goal_id: goal.goal_id, goal_name: goal.goal_name, status: goal.status, target_date: goal.target_date }
    if (own) item.target_amount = goal.target_amount
    if (own || flags.show_goal_progress) {
      item.progress_percent = Math.round((dash.total_assets / goal.target_amount) * 1000000) / 10000
    }
    return item
  })
  if (own || flags.show_active_goals) result.active_goals = goalRows('ACTIVE')
  if (own || flags.show_completed_goals) result.completed_goals = goalRows('COMPLETED')
  return result
}

// --- 미래 자산 시뮬레이션 (projection_service.py project() 의 단순화 근사) ---
const SIM_ASSETS = ['cash', 'saving', 'kr_stock', 'us_stock', 'kr_etf', 'us_etf']
const sumValues = (arr) => arr.reduce((acc, value) => acc + Number(value || 0), 0)

const addMonthsIso = (isoDate, count) => {
  const date = new Date(`${isoDate}T00:00:00Z`)
  date.setUTCMonth(date.getUTCMonth() + count)
  return date.toISOString().slice(0, 10)
}
const monthsBetween = (fromIso, toIso) => {
  const from = new Date(`${fromIso}T00:00:00Z`)
  const to = new Date(`${toIso}T00:00:00Z`)
  return (to.getUTCFullYear() - from.getUTCFullYear()) * 12 + (to.getUTCMonth() - from.getUTCMonth())
}

function simulateProjection(payload, goal) {
  const goalMode = Boolean(goal)
  const dash = dashboard()
  const start = TODAY
  const returns = payload.annual_returns || {}
  const alloc = payload.monthly_allocation || {}
  const futureFx = Number(payload.future_exchange_rate)

  if (Number(returns.saving || 0) < 0) return reject('INVALID_REQUEST', '적금 가정 금리는 0 이상이어야 합니다.')
  if (!futureFx || futureFx < 1 || futureFx > 10000) return reject('INVALID_REQUEST', '미래 환율 가정이 필요합니다.')

  let months
  let initial
  let income
  let expense
  let initialFx
  const balances = {}
  const existingDeposit = goalMode ? sumValues(dash.active_deposits.map((d) => d.principal)) : 0
  const existingSaving = goalMode ? sumValues(dash.active_savings.map((s) => s.total_paid_principal)) : 0

  if (goalMode) {
    months = monthsBetween(start, goal.target_date)
    if (months <= 0 || months > 600) return reject('INVALID_PERIOD', '미래 600개월 이내의 목표가 필요합니다.', 422)
    income = dash.monthly_income
    expense = dash.monthly_expense
    initial = dash.total_assets
    SIM_ASSETS.forEach((key) => { balances[key] = key === 'saving' ? 0 : Number(dash.amounts[key] || 0) })
    initialFx = Number(dash.exchange_rate) || 1385
  } else {
    months = Number(payload.months)
    initial = Number(payload.initial_asset)
    income = Number(payload.monthly_income)
    expense = Number(payload.monthly_expense)
    initialFx = Number(payload.initial_exchange_rate)
    if (!months || months < 1 || months > 600) return reject('INVALID_REQUEST', '기간은 1~600개월이어야 합니다.')
    if (!initialFx || initialFx < 1) return reject('INVALID_REQUEST', '현재 환율 가정이 필요합니다.')
    SIM_ASSETS.forEach((key) => { balances[key] = Number(payload.initial_allocation?.[key] || 0) })
    if (sumValues(Object.values(balances)) !== initial) {
      return reject('ALLOCATION_MISMATCH', '초기 배분 합계가 초기 자산과 일치해야 합니다.', 422)
    }
    if (Number(alloc.existing_saving || 0)) return reject('INVALID_REQUEST', '자유 시뮬레이션에는 기존 적금이 없습니다.')
  }

  const surplus = income - expense
  if (expense > income || sumValues(Object.values(alloc)) !== surplus) {
    return reject('ALLOCATION_MISMATCH', '월 배분 합계가 수입에서 지출을 뺀 금액과 일치해야 합니다.', 422)
  }

  const end = addMonthsIso(start, months)
  let grossInterest = 0
  let fxEffect = 0
  let contributions = 0
  const timeline = []

  for (let month = 1; month <= months; month += 1) {
    const fxPrev = initialFx + (futureFx - initialFx) * ((month - 1) / months)
    const fxNow = initialFx + (futureFx - initialFx) * (month / months)
    SIM_ASSETS.forEach((key) => {
      const monthlyGrowth = Math.pow(1 + Number(returns[key] || 0) / 100, 1 / 12)
      const before = balances[key]
      balances[key] = before * monthlyGrowth
      if (key === 'saving') grossInterest += balances[key] - before
      if (key === 'us_stock' || key === 'us_etf') {
        const beforeFx = balances[key]
        balances[key] *= fxNow / fxPrev
        fxEffect += balances[key] - beforeFx
      }
    })
    contributions += surplus
    SIM_ASSETS.forEach((key) => { balances[key] += Number(alloc[key] || 0) })
    balances.cash += Number(alloc.existing_saving || 0)
    const runningTotal = Math.round(sumValues(SIM_ASSETS.map((key) => balances[key])) + existingDeposit + existingSaving)
    timeline.push({ date: addMonthsIso(start, month), total_assets: runningTotal })
  }

  const savingPrincipal = (goalMode ? 0 : Number(payload.initial_allocation?.saving || 0)) + Number(alloc.saving || 0) * months
  const savingTax = Math.max(0, Math.round((balances.saving - savingPrincipal) * 0.154))
  balances.saving -= savingTax
  const tax = savingTax

  const amounts = {}
  SIM_ASSETS.forEach((key) => { amounts[key] = Math.round(balances[key]) })
  amounts.existing_deposit = existingDeposit
  amounts.existing_saving = existingSaving
  const total = sumValues(Object.values(amounts))
  if (timeline.length) timeline[timeline.length - 1].total_assets = total

  const result = {
    is_hypothetical: true,
    start_date: start,
    end_date: end,
    initial_assets: initial,
    future_contributions: Math.round(contributions),
    amounts,
    expected_total_assets: total,
    expected_interest: Math.round(grossInterest),
    expected_tax: Math.round(tax),
    expected_net_interest: Math.round(grossInterest - tax),
    expected_investment_profit: total - initial - Math.round(contributions) - Math.round(grossInterest - tax),
    exchange_rate_effect: Math.round(fxEffect),
    missed_payments: 0,
    timeline,
    assumptions: {
      annual_returns: returns,
      initial_exchange_rate: String(initialFx),
      future_exchange_rate: String(futureFx),
      contribution_timing: 'monthly anniversary, after growth',
      fx_path: 'linear',
      new_savings: 'assumed effective annual growth; tax at horizon',
      trading_fees: 'not included',
      future_returns_are_predictions: false,
    },
  }
  if (goalMode) {
    result.goal_id = goal.goal_id
    result.target_amount = goal.target_amount
    result.difference = total - goal.target_amount
    result.progress_percent = Math.round((total / goal.target_amount) * 1000000) / 10000
  }
  return ok(result)
}

const pickGoalFields = (data = {}) => {
  const out = {}
  if (data.goal_name !== undefined) out.goal_name = data.goal_name
  if (data.target_amount !== undefined) out.target_amount = Number(data.target_amount)
  if (data.target_date !== undefined) out.target_date = data.target_date
  return out
}

// 서버 save_goal() 의 비즈니스 규칙을 흉내 내 UI 의 에러 처리 경로를 확인할 수 있게 한다.
// 목표 금액은 현재 총자산보다 커야 한다.
function validateGoal(goal) {
  if (!goal.goal_name || !goal.goal_name.trim()) return reject('INVALID_REQUEST', '목표명을 입력해 주세요.')
  if (!(goal.target_amount > 0 && goal.target_amount <= 1000000000)) return reject('INVALID_REQUEST', '목표 금액은 1원 이상 10억 원 이하여야 합니다.')
  if (!goal.target_date || goal.target_date <= TODAY) return reject('INVALID_TARGET_DATE', '목표일은 오늘 이후여야 합니다.', 422)
  if (goal.target_amount <= TOTAL_ASSETS) return reject('INVALID_TARGET_AMOUNT', '목표 금액은 현재 총자산보다 커야 합니다.', 422)
  return null
}

// 총자산 이상 달성 시 즉시 완료 처리 (서버 refresh_achievements 근사)
function applyCompletion(goal) {
  if (goal.status === 'ACTIVE' && TOTAL_ASSETS >= goal.target_amount) {
    goal.status = 'COMPLETED'
    goal.completed_at = new Date().toISOString()
  }
  return goal
}

async function mockRequest(method, url, { params = {}, data } = {}) {
  await delay()
  const verb = method.toUpperCase()
  const path = url.split('?')[0]

  if (verb === 'GET' && path === '/dashboard') return ok(dashboard())
  if (verb === 'GET' && path === '/dashboard/history') return ok(history())
  if (verb === 'GET' && path === '/goals') return ok(goals.map(goalData))
  if (verb === 'GET' && path === '/badges') return ok(BADGE_CATALOG)
  if (verb === 'GET' && path === '/badges/me') return ok(MY_BADGES)

  if (verb === 'POST' && path === '/simulations/free') {
    return simulateProjection(data || {}, null)
  }
  const goalSimMatch = path.match(/^\/goals\/(\d+)\/simulation$/)
  if (goalSimMatch && verb === 'POST') {
    const goal = goals.find((item) => item.goal_id === Number(goalSimMatch[1]))
    if (!goal) return reject('NOT_FOUND', '항목을 찾을 수 없습니다.', 404)
    return simulateProjection(data || {}, goal)
  }

  if (verb === 'GET' && path === '/transactions') {
    const filtered = params.transaction_type
      ? LEDGER.filter((row) => row.transaction_type === params.transaction_type)
      : LEDGER
    return ok(paginate(filtered, params))
  }
  if (verb === 'GET' && path === '/investments/transactions') {
    return ok(paginate(MARKET_TX, params))
  }
  const txMatch = path.match(/^\/transactions\/(\d+)$/)
  if (verb === 'GET' && txMatch) {
    const row = LEDGER.find((item) => item.ledger_transaction_id === Number(txMatch[1]))
    return row ? ok(row) : reject('NOT_FOUND', '항목을 찾을 수 없습니다.', 404)
  }

  const goalMatch = path.match(/^\/goals\/(\d+)$/)
  if (goalMatch) {
    const id = Number(goalMatch[1])
    const goal = goals.find((item) => item.goal_id === id)
    if (verb === 'GET') return goal ? ok(goalData(goal)) : reject('NOT_FOUND', '항목을 찾을 수 없습니다.', 404)
    if (verb === 'PATCH') {
      if (!goal) return reject('NOT_FOUND', '항목을 찾을 수 없습니다.', 404)
      if (goal.status !== 'ACTIVE') return reject('GOAL_COMPLETED', '완료된 목표는 수정할 수 없습니다.', 409)
      const candidate = { ...goal, ...pickGoalFields(data) }
      const problem = validateGoal(candidate)
      if (problem) return problem
      Object.assign(goal, candidate, { updated_at: new Date().toISOString() })
      applyCompletion(goal)
      return ok(goalData(goal))
    }
    if (verb === 'DELETE') {
      goals = goals.filter((item) => item.goal_id !== id)
      return ok({})
    }
  }

  if (verb === 'POST' && path === '/goals') {
    if (goals.length >= 5) return reject('GOAL_LIMIT', '저축 목표는 최대 5개입니다.', 422)
    const goal = {
      goal_id: nextGoalId++,
      user_id: 1,
      status: 'ACTIVE',
      completed_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      ...pickGoalFields(data),
    }
    const problem = validateGoal(goal)
    if (problem) return problem
    applyCompletion(goal)
    goals.push(goal)
    return ok(goalData(goal))
  }

  if (path === '/profiles/me' && verb === 'GET') return ok(buildProfile(true))
  if (path === '/profiles/me' && verb === 'PATCH') {
    if (data?.nickname !== undefined) {
      const value = String(data.nickname).trim()
      if (value.length < 2 || value.length > 20) return reject('INVALID_REQUEST', '닉네임은 2~20자여야 합니다.')
      profileState.nickname = value
    }
    if (data?.representative_badge_id !== undefined) {
      const badgeId = data.representative_badge_id
      if (badgeId !== null && !MY_BADGES.some((badge) => badge.badge_id === badgeId)) {
        return reject('BADGE_NOT_OWNED', '획득한 뱃지만 대표 뱃지로 선택할 수 있습니다.', 422)
      }
      profileState.representative_badge_id = badgeId
    }
    return ok(buildProfile(true))
  }
  if (path === '/profiles/me/visibility' && verb === 'GET') return ok({ ...visibilityState })
  if (path === '/profiles/me/visibility' && verb === 'PATCH') {
    for (const key of VISIBILITY_KEYS) {
      if (data?.[key] !== undefined) {
        if (typeof data[key] !== 'boolean') return reject('INVALID_REQUEST', 'true 또는 false만 허용합니다.')
        visibilityState[key] = data[key]
      }
    }
    return ok({ ...visibilityState })
  }
  const profileMatch = path.match(/^\/profiles\/(\d+)$/)
  if (profileMatch && verb === 'GET') {
    const targetId = Number(profileMatch[1])
    return ok(buildProfile(targetId === MY_USER_ID, targetId))
  }

  if (path === '/posts' && verb === 'GET') {
    let list = posts.slice()
    if (params.board_type) list = list.filter((item) => item.board_type === params.board_type)
    const search = (params.q || '').trim().toLowerCase()
    if (search) list = list.filter((item) => item.title.toLowerCase().includes(search) || item.content.toLowerCase().includes(search))
    if (params.sort === 'likes') list.sort((a, b) => postData(b).reactions.LIKE - postData(a).reactions.LIKE)
    else if (params.sort === 'dislikes') list.sort((a, b) => postData(b).reactions.DISLIKE - postData(a).reactions.DISLIKE)
    else list.sort((a, b) => b.post_id - a.post_id)
    const sliced = paginate(list, params)
    return ok({ ...sliced, items: sliced.items.map(postData) })
  }
  if (path === '/posts' && verb === 'POST') {
    if (!BOARD_TYPES.includes(data?.board_type)) return reject('INVALID_REQUEST', '게시판을 선택해 주세요.')
    if (!data?.title?.trim()) return reject('INVALID_REQUEST', '제목을 입력해 주세요.')
    if (!data?.content?.trim()) return reject('INVALID_REQUEST', '내용을 입력해 주세요.')
    const now = new Date().toISOString()
    const post = { post_id: nextPostId++, user_id: MY_USER_ID, board_type: data.board_type, title: data.title.trim(), content: data.content.trim(), created_at: now, updated_at: now }
    posts.unshift(post)
    return ok(postData(post))
  }

  const commentsMatch = path.match(/^\/posts\/(\d+)\/comments$/)
  if (commentsMatch) {
    const postId = Number(commentsMatch[1])
    if (!findPost(postId)) return reject('NOT_FOUND', '게시글을 찾을 수 없습니다.', 404)
    if (verb === 'GET') {
      const list = comments.filter((item) => item.post_id === postId).sort((a, b) => a.comment_id - b.comment_id)
      const sliced = paginate(list, params)
      return ok({ ...sliced, items: sliced.items.map(commentData) })
    }
    if (verb === 'POST') {
      if (!data?.content?.trim()) return reject('INVALID_REQUEST', '댓글 내용을 입력해 주세요.')
      const now = new Date().toISOString()
      const comment = { comment_id: nextCommentId++, post_id: postId, user_id: MY_USER_ID, content: data.content.trim(), created_at: now, updated_at: now }
      comments.push(comment)
      return ok(commentData(comment))
    }
  }

  const reactionMatch = path.match(/^\/posts\/(\d+)\/reaction$/)
  if (reactionMatch && verb === 'PUT') {
    const postId = Number(reactionMatch[1])
    if (!findPost(postId)) return reject('NOT_FOUND', '게시글을 찾을 수 없습니다.', 404)
    const kind = data?.reaction_type
    if (!['LIKE', 'DISLIKE', 'NONE'].includes(kind)) return reject('INVALID_REQUEST', '허용하지 않는 반응입니다.')
    postReactions[postId] = postReactions[postId] || {}
    if (kind === 'NONE') delete postReactions[postId][MY_USER_ID]
    else postReactions[postId][MY_USER_ID] = kind
    return ok({ reaction_type: kind })
  }

  const postMatch = path.match(/^\/posts\/(\d+)$/)
  if (postMatch) {
    const postId = Number(postMatch[1])
    const post = findPost(postId)
    if (!post) return reject('NOT_FOUND', '게시글을 찾을 수 없습니다.', 404)
    if (verb === 'GET') return ok(postData(post))
    if (post.user_id !== MY_USER_ID) return reject('NOT_FOUND', '게시글을 찾을 수 없습니다.', 404)
    if (verb === 'PATCH') {
      if (data?.board_type !== undefined) {
        if (!BOARD_TYPES.includes(data.board_type)) return reject('INVALID_REQUEST', '게시판을 선택해 주세요.')
        post.board_type = data.board_type
      }
      if (data?.title !== undefined) post.title = String(data.title).trim()
      if (data?.content !== undefined) post.content = String(data.content).trim()
      post.updated_at = new Date().toISOString()
      return ok(postData(post))
    }
    if (verb === 'DELETE') {
      posts = posts.filter((item) => item.post_id !== postId)
      comments = comments.filter((item) => item.post_id !== postId)
      return ok({})
    }
  }

  const commentMatch = path.match(/^\/comments\/(\d+)$/)
  if (commentMatch) {
    const commentId = Number(commentMatch[1])
    const comment = comments.find((item) => item.comment_id === commentId)
    if (!comment || comment.user_id !== MY_USER_ID) return reject('NOT_FOUND', '댓글을 찾을 수 없습니다.', 404)
    if (verb === 'PATCH') {
      if (!data?.content?.trim()) return reject('INVALID_REQUEST', '댓글 내용을 입력해 주세요.')
      comment.content = data.content.trim()
      comment.updated_at = new Date().toISOString()
      return ok(commentData(comment))
    }
    if (verb === 'DELETE') {
      comments = comments.filter((item) => item.comment_id !== commentId)
      return ok({})
    }
  }

  if (path === '/reports' && verb === 'POST') {
    if (!['POST', 'COMMENT'].includes(data?.target_type)) return reject('INVALID_REQUEST', '신고 대상이 올바르지 않습니다.')
    if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '신고 사유를 입력해 주세요.')
    const now = new Date().toISOString()
    const report = { report_id: nextReportId++, reporter_user_id: MY_USER_ID, target_type: data.target_type, target_id: Number(data.target_id), reason: data.reason.trim(), status: 'PENDING', resolution_reason: null, created_at: now, resolved_at: null, resolved_by: null }
    reports.push(report)
    return ok(report)
  }

  if (path === '/reports/me' && verb === 'GET') {
    return ok(paginate(reports.filter((r) => r.reporter_user_id === MY_USER_ID).slice().reverse(), params))
  }

  // 거래 오류 문의
  if (path === '/inquiries' && verb === 'GET') {
    return ok(paginate(inquiries.slice().reverse().map(inquiryData), params))
  }
  if (path === '/inquiries' && verb === 'POST') {
    if (!data?.title?.trim()) return reject('INVALID_REQUEST', '제목을 입력해 주세요.')
    if (!data?.content?.trim()) return reject('INVALID_REQUEST', '내용을 입력해 주세요.')
    const now = new Date().toISOString()
    const row = {
      inquiry_id: nextInquiryId++,
      user_id: MY_USER_ID,
      related_ledger_transaction_id: data.related_ledger_transaction_id ?? null,
      title: data.title.trim(),
      content: data.content.trim(),
      status: 'PENDING',
      admin_answer: null,
      answered_at: null,
      answered_by: null,
      created_at: now,
      updated_at: now,
    }
    inquiries.push(row)
    return ok(inquiryData(row))
  }
  const inquiryMatch = path.match(/^\/inquiries\/(\d+)$/)
  if (inquiryMatch && verb === 'GET') {
    const row = inquiries.find((item) => item.inquiry_id === Number(inquiryMatch[1]))
    return row ? ok(inquiryData(row)) : reject('NOT_FOUND', '문의를 찾을 수 없습니다.', 404)
  }
  if (verb === 'POST' && /^\/(posts|inquiries)\/\d+\/images$/.test(path)) {
    return ok([{ attachment_id: 'mock' + Date.now().toString(16), url: '/api/attachments/mock' }])
  }

  // --- 관리자 ---
  if (path === '/admin/users' && verb === 'GET') {
    const search = (params.q || '').toLowerCase()
    const list = search ? ADMIN_USERS.filter((u) => u.username.toLowerCase().includes(search)) : ADMIN_USERS
    return ok(paginate(list, params))
  }
  const adminUserMatch = path.match(/^\/admin\/users\/(\d+)$/)
  if (adminUserMatch) {
    const uid = Number(adminUserMatch[1])
    const user = ADMIN_USERS.find((u) => u.user_id === uid)
    if (!user) return reject('NOT_FOUND', '회원을 찾을 수 없습니다.', 404)
    if (verb === 'GET') return ok(user)
    if (verb === 'DELETE') {
      if (user.role === 'ADMIN') return reject('INVALID_USER_STATE', '관리자 계정은 변경할 수 없습니다.', 409)
      user.status = 'WITHDRAWN'
      pushAudit({ action: 'ADMIN_USER_WITHDRAW', target_type: 'users', target_id: uid, reason: data?.reason })
      return ok({})
    }
  }
  const adminStatusMatch = path.match(/^\/admin\/users\/(\d+)\/status$/)
  if (adminStatusMatch && verb === 'PATCH') {
    const user = ADMIN_USERS.find((u) => u.user_id === Number(adminStatusMatch[1]))
    if (!user) return reject('NOT_FOUND', '회원을 찾을 수 없습니다.', 404)
    if (user.role === 'ADMIN' || user.status === 'WITHDRAWN') return reject('INVALID_USER_STATE', '관리자 또는 탈퇴한 계정은 변경할 수 없습니다.', 409)
    if (!['ACTIVE', 'SUSPENDED'].includes(data?.status)) return reject('INVALID_REQUEST', '상태 값이 올바르지 않습니다.')
    if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '사유를 입력해 주세요.')
    const before = user.status
    user.status = data.status
    pushAudit({ action: 'ADMIN_USER_STATUS', target_type: 'users', target_id: user.user_id, before_value: { status: before }, after_value: { status: data.status }, reason: data.reason })
    return ok(user)
  }
  const adminAdjMatch = path.match(/^\/admin\/users\/(\d+)\/adjustments$/)
  if (adminAdjMatch && verb === 'POST') {
    if (!data?.amount || data.amount === 0) return reject('INVALID_ADJUSTMENT', '0원 조정은 허용하지 않습니다.', 422)
    if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '사유를 입력해 주세요.')
    pushAudit({ action: 'ADMIN_ACCOUNT_ADJUSTMENT', target_type: 'ledger_transactions', target_id: 900 + nextAuditId, after_value: { amount: data.amount }, reason: data.reason })
    return ok({ ledger_transaction_id: 900 + nextAuditId, balance_after: 1000000 + Number(data.amount) })
  }
  if (path === '/admin/products' && verb === 'GET') return ok(paginate(ADMIN_PRODUCTS, params))
  const adminProductMatch = path.match(/^\/admin\/products\/(\d+)$/)
  if (adminProductMatch) {
    const pid = Number(adminProductMatch[1])
    const product = ADMIN_PRODUCTS.find((p) => p.product_id === pid)
    if (!product) return reject('NOT_FOUND', '상품을 찾을 수 없습니다.', 404)
    if (verb === 'GET') return ok({ ...product, options: ADMIN_OPTIONS[pid] || [] })
    if (verb === 'PATCH' || verb === 'DELETE') {
      if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '사유(reason)가 필요합니다.')
      Object.assign(product, { sync_locked: true }, verb === 'DELETE' ? { is_active: false } : {})
      for (const key of ['product_name', 'description', 'join_target', 'is_active', 'sync_locked']) {
        if (data[key] !== undefined) product[key] = data[key]
      }
      pushAudit({ action: 'ADMIN_PRODUCT_UPDATE', target_type: 'financial_products', target_id: pid, reason: data.reason })
      return ok(product)
    }
  }
  const adminOptionMatch = path.match(/^\/admin\/products\/(\d+)\/options\/(\d+)$/)
  if (adminOptionMatch && verb === 'PATCH') {
    const pid = Number(adminOptionMatch[1])
    const option = (ADMIN_OPTIONS[pid] || []).find((o) => o.option_id === Number(adminOptionMatch[2]))
    if (!option) return reject('NOT_FOUND', '상품 옵션을 찾을 수 없습니다.', 404)
    if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '사유(reason)가 필요합니다.')
    for (const key of ['base_interest_rate', 'max_interest_rate', 'min_amount', 'max_amount', 'is_active', 'sync_locked']) {
      if (data[key] !== undefined) option[key] = data[key]
    }
    option.sync_locked = data.sync_locked ?? true
    pushAudit({ action: 'ADMIN_PRODUCT_UPDATE', target_type: 'financial_product_options', target_id: option.option_id, reason: data.reason })
    return ok(option)
  }
  if (path === '/admin/transactions' && verb === 'GET') {
    const list = params.user_id ? LEDGER.filter((row) => String(row.user_id) === String(params.user_id)) : LEDGER
    return ok(paginate(list, params))
  }
  if (path === '/admin/market-transactions' && verb === 'GET') return ok(paginate(MARKET_TX, params))
  if (path === '/admin/posts' && verb === 'GET') {
    return ok(paginate(posts.slice().sort((a, b) => b.post_id - a.post_id).map(postData), params))
  }
  if (path === '/admin/comments' && verb === 'GET') {
    return ok(paginate(comments.slice().sort((a, b) => b.comment_id - a.comment_id).map(commentData), params))
  }
  const adminDelPostMatch = path.match(/^\/admin\/posts\/(\d+)$/)
  if (adminDelPostMatch && verb === 'DELETE') {
    if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '사유(reason)가 필요합니다.')
    posts = posts.filter((p) => p.post_id !== Number(adminDelPostMatch[1]))
    pushAudit({ action: 'CONTENT_DELETE', target_type: 'posts', target_id: Number(adminDelPostMatch[1]), reason: data.reason })
    return ok({})
  }
  const adminDelCommentMatch = path.match(/^\/admin\/comments\/(\d+)$/)
  if (adminDelCommentMatch && verb === 'DELETE') {
    if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '사유(reason)가 필요합니다.')
    comments = comments.filter((c) => c.comment_id !== Number(adminDelCommentMatch[1]))
    pushAudit({ action: 'CONTENT_DELETE', target_type: 'comments', target_id: Number(adminDelCommentMatch[1]), reason: data.reason })
    return ok({})
  }
  if (path === '/admin/reports' && verb === 'GET') return ok(paginate(reports.slice().reverse(), params))
  const adminReportMatch = path.match(/^\/admin\/reports\/(\d+)$/)
  if (adminReportMatch && verb === 'GET') {
    const row = reports.find((r) => r.report_id === Number(adminReportMatch[1]))
    if (!row) return reject('NOT_FOUND', '신고를 찾을 수 없습니다.', 404)
    const target = (row.target_type === 'POST' ? posts : comments).find((item) => (row.target_type === 'POST' ? item.post_id : item.comment_id) === row.target_id)
    const parent = row.target_type === 'POST' ? target : posts.find((item) => item.post_id === target?.post_id)
    return ok({ ...row, target: { deleted: !target || !parent, post_id: parent?.post_id, title: parent?.title, content: target?.content } })
  }
  if (adminReportMatch && verb === 'PATCH') {
    const row = reports.find((r) => r.report_id === Number(adminReportMatch[1]))
    if (!row) return reject('NOT_FOUND', '신고를 찾을 수 없습니다.', 404)
    if (row.status !== 'PENDING') return reject('ALREADY_RESOLVED', '이미 처리된 신고입니다.', 409)
    if (!['RESOLVED', 'REJECTED'].includes(data?.status)) return reject('INVALID_REQUEST', '상태 값이 올바르지 않습니다.')
    if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '사유를 입력해 주세요.')
    Object.assign(row, { status: data.status, resolution_reason: data.reason, resolved_at: new Date().toISOString(), resolved_by: 99 })
    pushAudit({ action: 'REPORT_RESOLVE', target_type: 'reports', target_id: row.report_id, after_value: { status: row.status }, reason: data.reason })
    return ok(row)
  }
  if (path === '/admin/inquiries' && verb === 'GET') {
    return ok(paginate(inquiries.slice().reverse().map(inquiryData), params))
  }
  const adminInquiryMatch = path.match(/^\/admin\/inquiries\/(\d+)$/)
  if (adminInquiryMatch && verb === 'GET') {
    const row = inquiries.find((item) => item.inquiry_id === Number(adminInquiryMatch[1]))
    return row ? ok(inquiryData(row)) : reject('NOT_FOUND', '문의를 찾을 수 없습니다.', 404)
  }
  const adminAnswerMatch = path.match(/^\/admin\/inquiries\/(\d+)\/answer$/)
  if (adminAnswerMatch && verb === 'PATCH') {
    const row = inquiries.find((item) => item.inquiry_id === Number(adminAnswerMatch[1]))
    if (!row) return reject('NOT_FOUND', '문의를 찾을 수 없습니다.', 404)
    if (!data?.answer?.trim()) return reject('INVALID_REQUEST', '답변을 입력해 주세요.')
    if (!data?.reason?.trim()) return reject('INVALID_REQUEST', '사유를 입력해 주세요.')
    Object.assign(row, { status: 'ANSWERED', admin_answer: data.answer.trim(), answered_at: new Date().toISOString(), answered_by: 99, updated_at: new Date().toISOString() })
    pushAudit({ action: 'INQUIRY_ANSWER', target_type: 'inquiries', target_id: row.inquiry_id, reason: data.reason })
    return ok(row)
  }
  if (path === '/admin/audit-logs' && verb === 'GET') {
    let list = AUDIT_LOGS
    if (params.action) list = list.filter((row) => row.action === params.action)
    if (params.target_type) list = list.filter((row) => row.target_type === params.target_type)
    return ok(paginate(list, params))
  }

  return reject('NOT_FOUND', `목 응답이 정의되지 않은 경로입니다: ${verb} ${path}`, 404)
}

export default mockRequest
