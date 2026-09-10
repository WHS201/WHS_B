import { dateTimeKST, won } from './format.js'

export const goalPercent = (goal) => {
  if (goal.status === 'COMPLETED') return 100
  const value = Number(goal.progress_percent)
  return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0
}

export const LABELS = {
  USER: '일반 회원', ADMIN: '관리자', ACTIVE: '이용 중', SUSPENDED: '정지', WITHDRAWN: '탈퇴',
  POST: '게시글', COMMENT: '댓글', PENDING: '접수됨', ANSWERED: '답변 완료',
  RESOLVED: '조치 완료', REJECTED: '반려', FREE: '자유', KR_STOCK: '국내주식',
  US_STOCK: '미국주식', DEPOSIT_SAVING: '예·적금', DEPOSIT: '예금', SAVING: '적금',
  BUY: '매수', SELL: '매도', CREDIT: '입금', DEBIT: '출금', COMPLETED: '달성',
  CREATE: '저장 항목 생성', UPDATE: '저장값 변경', DELETE: '저장 항목 삭제',
  ADMIN_USER_STATUS: '회원 정지·해제', ADMIN_USER_WITHDRAW: '회원 탈퇴 처리',
  ADMIN_ACCOUNT_ADJUSTMENT: '계좌 잔액 조정', ADMIN_PRODUCT_UPDATE: '금융상품 수정',
  REPORT_RESOLVE: '신고 처리', INQUIRY_ANSWER: '문의 답변',
  PROFILE_VISIBILITY_UPDATE: '프로필 공개 설정 변경', SIMULATION_RESET: '시뮬레이션 초기화',
  IMAGE_UPLOAD: '이미지 첨부', IMAGE_DELETE: '이미지 삭제',
  POST_CREATE: '게시글 작성', POST_UPDATE: '게시글 수정', POST_DELETE: '게시글 삭제',
  COMMENT_CREATE: '댓글 작성', COMMENT_UPDATE: '댓글 수정', COMMENT_DELETE: '댓글 삭제',
  CONTENT_DELETE: '게시글·댓글 삭제', REPORT_CREATE: '신고 접수', INQUIRY_CREATE: '문의 접수',
  PASSWORD_CHANGE: '비밀번호 변경', USER_WITHDRAW: '회원 탈퇴',
  users: '회원', accounts: '계좌', simulation_settings: '시뮬레이션 설정', saving_goals: '저축 목표',
  deposits: '예금 계약', savings: '적금 계약', market_transactions: '주식·ETF 거래',
  ledger_transactions: '금융 원장 거래', user_badges: '획득 뱃지',
  posts: '게시글', comments: '댓글', reports: '신고', inquiries: '문의',
  financial_products: '금융상품', financial_product_options: '상품 조건',
}

export const LEDGER_TYPE_LABELS = {
  INITIAL_ASSET: '초기 자산', MONTHLY_INCOME: '월 정기 수입', MONTHLY_EXPENSE: '월 예상 지출',
  STOCK_BUY: '주식·ETF 매수', STOCK_SELL: '주식·ETF 매도',
  DEPOSIT_JOIN: '예금 가입', DEPOSIT_CANCEL: '예금 중도해지', DEPOSIT_MATURITY: '예금 만기',
  SAVING_PAYMENT: '적금 납입', SAVING_CANCEL: '적금 중도해지', SAVING_MATURITY: '적금 만기',
  ADMIN_ADJUSTMENT: '관리자 잔액 조정',
}

export const label = (value) => value == null || value === '' ? '-' : LABELS[value] || LEDGER_TYPE_LABELS[value] || value
export const memberLabel = (member, fallback) => member
  ? `${member.nickname} (${member.username}) · #${member.user_id}`
  : fallback == null ? '시스템' : `회원 #${fallback}`
export const ledgerNet = (row) => (row.entries || []).reduce(
  (sum, entry) => sum + (entry.entry_type === 'CREDIT' ? Number(entry.amount) : -Number(entry.amount)), 0,
)
export const signedWon = (value) => `${Number(value) > 0 ? '+' : ''}${won(value)}`
export const ledgerLabel = (row) => row
  ? `거래 #${row.ledger_transaction_id} · ${label(row.transaction_type)} · ${signedWon(ledgerNet(row))} · ${dateTimeKST(row.created_at)}`
  : '연결된 거래 없음'

const FIELD_LABELS = {
  nickname: '닉네임', role: '권한', status: '상태', balance: '잔액', balance_after: '거래 후 잔액',
  amount: '금액', initial_asset: '초기 자산', monthly_income: '월 수입', monthly_expense: '월 지출',
  is_initial_asset_set: '초기 자산 설정 완료', goal_name: '목표명', target_amount: '목표 금액',
  target_date: '목표일', principal: '원금', payout_amount: '지급 금액', total_paid_principal: '납입 원금',
  side: '매매 구분', quantity: '수량', amount_krw: '원화 금액', transaction_type: '거래 종류',
  badge_id: '뱃지 번호', representative_badge_id: '대표 뱃지 번호', sync_locked: '자동 갱신 제외',
}
export const auditValue = (value) => {
  if (value == null) return '기록 없음'
  return Object.entries(value).map(([key, item]) => {
    const text = item == null ? '없음' : typeof item === 'boolean' ? (item ? '예' : '아니요')
      : typeof item === 'object' ? JSON.stringify(item) : label(item)
    return `${FIELD_LABELS[key] || key}: ${text}`
  }).join('\n')
}
