import { useEffect, useState } from 'react'
import PageShell from '../components/PageShell'
import { showToast } from '../components/Toast'
import { Empty, Loading, Notice } from '../components/Ui'
import { shortDate, won } from '../utils/format'
import {
  MOCKS_ENABLED, getApiError,
  adminAdjustAccount, adminAnswerInquiry, adminDeleteComment, adminDeletePost, adminDeleteUser,
  adminGetAuditLogs, adminGetCommentsAll, adminGetInquiries, adminGetLedger, adminGetMarketTransactions,
  adminDeleteProduct, adminGetProduct, adminGetProducts, adminGetPosts, adminGetReports,
  adminGetUsers, adminPatchOption, adminPatchProduct, adminResolveReport, adminSetUserStatus,
} from '../api/features'

const SECTIONS = [
  ['users', '회원'],
  ['products', '금융상품'],
  ['transactions', '거래'],
  ['community', '커뮤니티'],
  ['reports', '신고'],
  ['inquiries', '문의'],
  ['audit', '감사 로그'],
]

const dt = (value) => {
  if (!value) {
    return '-'
  }

  const normalizedValue =
    /Z$|[+-]\d{2}:\d{2}$/.test(value)
      ? value
      : `${value}Z`

  const date = new Date(normalizedValue)

  if (Number.isNaN(date.getTime())) {
    return '-'
  }

  const parts = new Intl.DateTimeFormat(
    'ko-KR',
    {
      timeZone: 'Asia/Seoul',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    },
  ).formatToParts(date)

  const get = (type) =>
    parts.find((part) => part.type === type)?.value || ''

  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}`
}

function Pager({ page, total, setPage }) {
  const pages = Math.max(1, Math.ceil((total || 0) / 20))
  return (
    <div className="pager">
      <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>이전</button>
      <span>{page} / {pages}</span>
      <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)}>다음</button>
    </div>
  )
}

function usePagedList(fetcher, params = {}) {
  const key = JSON.stringify(params)
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    fetcher({ page, size: 20, ...JSON.parse(key) })
      .then((res) => { if (active) { setResult(res.data); setLoading(false) } })
      .catch((err) => { if (active) { setError(getApiError(err)); setResult(null); setLoading(false) } })
    return () => { active = false }
  }, [page, key, tick]) // fetcher 는 모듈 상수라 의존성에서 제외

  return { result, loading, error, page, setPage, reload: () => setTick((value) => value + 1) }
}

function PromptDialog({ title, body, fields, submitLabel = '확인', onSubmit, onClose }) {
  const [values, setValues] = useState(() => Object.fromEntries(fields.map((field) => [field.name, field.default ?? ''])))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onSubmit(values)
      onClose()
    } catch (submitError) {
      setError(getApiError(submitError))
      setBusy(false)
    }
  }

  const set = (name) => (event) => setValues((prev) => ({ ...prev, [name]: event.target.value }))

  return (
    <div className="confirm-backdrop" onClick={onClose} role="presentation">
      <form className="confirm-dialog admin-dialog" onClick={(event) => event.stopPropagation()} onSubmit={submit}>
        <h2>{title}</h2>
        {body && <p className="admin-dialog-body">{body}</p>}
        {fields.map((field) => (
          <div key={field.name} className="form-group">
            <label>{field.label}</label>
            {field.type === 'select' ? (
              <select value={values[field.name]} onChange={set(field.name)}>
                {field.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            ) : field.type === 'textarea' ? (
              <textarea value={values[field.name]} onChange={set(field.name)} maxLength={field.maxLength} rows={4} />
            ) : (
              <input type={field.type || 'text'} value={values[field.name]} onChange={set(field.name)} />
            )}
          </div>
        ))}
        {error && <Notice type="error">{error}</Notice>}
        <div>
          <button type="button" className="confirm-cancel" onClick={onClose}>취소</button>
          <button type="submit" className="confirm-accept" disabled={busy}>{submitLabel}</button>
        </div>
      </form>
    </div>
  )
}

const REASON_FIELD = { name: 'reason', label: '사유 (필수)', type: 'textarea', maxLength: 1000 }

function TableWrap({ list, columns, rowKey, actions }) {
  if (!list || list.length === 0) return <Empty>표시할 항목이 없습니다.</Empty>
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="admin-table">
        <thead>
          <tr>{columns.map((col) => <th key={col.key}>{col.label}</th>)}{actions && <th>작업</th>}</tr>
        </thead>
        <tbody>
          {list.map((row) => (
            <tr key={row[rowKey]}>
              {columns.map((col) => <td key={col.key}>{col.render ? col.render(row) : String(row[col.key] ?? '-')}</td>)}
              {actions && <td className="admin-actions">{actions(row)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ── 회원 ── */
function UsersSection() {
  const [q, setQ] = useState('')
  const [applied, setApplied] = useState('')
  const { result, loading, error, page, setPage, reload } = usePagedList(adminGetUsers, applied ? { q: applied } : {})
  const [dialog, setDialog] = useState(null)

  const run = (fn, message) => async (values) => { await fn(values); showToast(message); reload() }

  return (
    <>
      <form className="tx-filter" onSubmit={(event) => { event.preventDefault(); setApplied(q.trim()); setPage(1) }}>
        <input type="text" value={q} maxLength={100} onChange={(event) => setQ(event.target.value)} placeholder="아이디 검색" />
        <button type="submit" className="service-secondary-button">검색</button>
        {result && <span className="tx-count">전체 {result.total}명</span>}
      </form>
      <Notice type="error">{error}</Notice>
      {loading ? <Loading /> : (
        <>
          <TableWrap
            list={result?.items}
            rowKey="user_id"
            columns={[
              { key: 'user_id', label: 'ID' },
              { key: 'username', label: '아이디' },
              { key: 'nickname', label: '닉네임' },
              { key: 'role', label: '권한' },
              { key: 'status', label: '상태', render: (row) => <span className={`goal-state ${row.status === 'ACTIVE' ? 'active' : 'done'}`}>{row.status}</span> },
              { key: 'created_at', label: '가입일', render: (row) => shortDate(row.created_at) },
            ]}
            actions={(row) => row.role === 'ADMIN' ? <span className="mini-sub">-</span> : (
              <>
                <button type="button" onClick={() => setDialog({
                  title: `${row.nickname} 상태 변경`,
                  fields: [{ name: 'status', label: '상태', type: 'select', options: [['ACTIVE', 'ACTIVE (해제)'], ['SUSPENDED', 'SUSPENDED (정지)']], default: row.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE' }, REASON_FIELD],
                  submit: run((values) => adminSetUserStatus(row.user_id, values), '상태를 변경했습니다.'),
                })}>정지/해제</button>
                <button type="button" onClick={() => setDialog({
                  title: `${row.nickname} 잔액 조정`,
                  fields: [{ name: 'amount', label: '조정 금액 (음수 가능, ±1억)', type: 'number' }, REASON_FIELD],
                  submit: run((values) => adminAdjustAccount(row.user_id, { amount: Number(values.amount), reason: values.reason }), '계좌를 조정했습니다.'),
                })}>잔액 조정</button>
                <button type="button" className="btn-danger" onClick={() => setDialog({
                  title: `${row.nickname} 탈퇴 처리`,
                  fields: [REASON_FIELD],
                  submit: run((values) => adminDeleteUser(row.user_id, values.reason), '탈퇴 처리했습니다.'),
                })}>탈퇴</button>
              </>
            )}
          />
          <Pager page={page} total={result?.total} setPage={setPage} />
        </>
      )}
      {dialog && (
        <PromptDialog title={dialog.title} fields={dialog.fields} onSubmit={dialog.submit} onClose={() => setDialog(null)} />
      )}
    </>
  )
}

/* ── 금융상품 ── */
function ProductsSection() {
  const { result, loading, error, page, setPage, reload } = usePagedList(adminGetProducts)
  const [detail, setDetail] = useState(null)
  const [dialog, setDialog] = useState(null)

  const openDetail = async (productId) => {
    try { const res = await adminGetProduct(productId); setDetail(res.data) } catch (err) { showToast(getApiError(err), 'error') }
  }
  const run = (fn, message) => async (values) => { await fn(values); showToast(message); reload(); if (detail) openDetail(detail.product_id) }

  return (
    <>
      <Notice type="error">{error}</Notice>
      {loading ? <Loading /> : (
        <>
          <TableWrap
            list={result?.items}
            rowKey="product_id"
            columns={[
              { key: 'product_id', label: 'ID' },
              { key: 'bank_name', label: '은행' },
              { key: 'product_name', label: '상품명' },
              { key: 'product_type', label: '유형' },
              { key: 'is_active', label: '판매', render: (row) => (row.is_active ? '판매중' : '중지') },
              { key: 'sync_locked', label: '동기화잠금', render: (row) => (row.sync_locked ? '잠김' : '-') },
            ]}
            actions={(row) => (
              <>
                <button type="button" onClick={() => openDetail(row.product_id)}>옵션</button>
                <button type="button" onClick={() => setDialog({
                  title: `${row.product_name} 수정`,
                  fields: [
                    { name: 'product_name', label: '상품명', default: row.product_name },
                    { name: 'join_target', label: '가입 대상', default: row.join_target || '' },
                    { name: 'is_active', label: '판매 상태', type: 'select', options: [['true', '판매중'], ['false', '판매중지']], default: String(row.is_active) },
                    REASON_FIELD,
                  ],
                  submit: run((values) => adminPatchProduct(row.product_id, {
                    product_name: values.product_name, join_target: values.join_target,
                    is_active: values.is_active === 'true', reason: values.reason,
                  }), '상품을 수정했습니다.'),
                })}>수정</button>
                <button type="button" className="btn-danger" onClick={() => setDialog({
                  title: `${row.product_name} 비활성화`,
                  fields: [REASON_FIELD],
                  submit: run((values) => adminDeleteProduct(row.product_id, values.reason), '상품을 비활성화했습니다.'),
                })}>비활성화</button>
              </>
            )}
          />
          <Pager page={page} total={result?.total} setPage={setPage} />
        </>
      )}

      {detail && (
        <section className="service-card" style={{ marginTop: 18 }}>
          <div className="goal-row-head">
            <strong>{detail.bank_name} · {detail.product_name} 옵션</strong>
            <button type="button" className="btn-neutral" onClick={() => setDetail(null)}>닫기</button>
          </div>
          <TableWrap
            list={detail.options}
            rowKey="option_id"
            columns={[
              { key: 'option_id', label: 'ID' },
              { key: 'term_months', label: '기간(개월)' },
              { key: 'base_interest_rate', label: '기본금리' },
              { key: 'max_interest_rate', label: '최고금리' },
              { key: 'is_active', label: '활성', render: (row) => (row.is_active ? 'Y' : 'N') },
            ]}
            actions={(row) => (
              <button type="button" onClick={() => setDialog({
                title: `옵션 ${row.option_id} 수정`,
                fields: [
                  { name: 'base_interest_rate', label: '기본 금리(%)', type: 'number', default: row.base_interest_rate },
                  { name: 'max_interest_rate', label: '최고 금리(%)', type: 'number', default: row.max_interest_rate },
                  REASON_FIELD,
                ],
                submit: run((values) => adminPatchOption(detail.product_id, row.option_id, {
                  base_interest_rate: Number(values.base_interest_rate),
                  max_interest_rate: Number(values.max_interest_rate),
                  reason: values.reason,
                }), '옵션을 수정했습니다.'),
              })}>수정</button>
            )}
          />
        </section>
      )}

      {dialog && (
        <PromptDialog title={dialog.title} fields={dialog.fields} onSubmit={dialog.submit} onClose={() => setDialog(null)} />
      )}
    </>
  )
}

/* ── 거래 ── */
function TransactionsSection() {
  const [mode, setMode] = useState('ledger')
  const [uid, setUid] = useState('')
  const [applied, setApplied] = useState('')
  const ledger = usePagedList(adminGetLedger, applied ? { user_id: applied } : {})
  const market = usePagedList(adminGetMarketTransactions)
  const view = mode === 'ledger' ? ledger : market

  return (
    <>
      <div className="tab-bar">
        <button className={mode === 'ledger' ? 'active' : ''} onClick={() => setMode('ledger')}>금융 원장</button>
        <button className={mode === 'market' ? 'active' : ''} onClick={() => setMode('market')}>주식·ETF 거래</button>
      </div>
      {mode === 'ledger' && (
        <form className="tx-filter" onSubmit={(event) => { event.preventDefault(); setApplied(uid.trim()); ledger.setPage(1) }}>
          <input type="number" value={uid} onChange={(event) => setUid(event.target.value)} placeholder="회원 ID 필터" />
          <button type="submit" className="service-secondary-button">적용</button>
        </form>
      )}
      <Notice type="error">{view.error}</Notice>
      {view.loading ? <Loading /> : mode === 'ledger' ? (
        <TableWrap
          list={ledger.result?.items}
          rowKey="ledger_transaction_id"
          columns={[
            { key: 'ledger_transaction_id', label: 'ID' },
            { key: 'user_id', label: '회원' },
            { key: 'transaction_type', label: '종류' },
            { key: 'amount', label: '금액', render: (row) => won(row.amount) },
            { key: 'balance_after', label: '거래후잔액', render: (row) => won(row.balance_after) },
            { key: 'created_at', label: '시각', render: (row) => dt(row.created_at) },
          ]}
        />
      ) : (
        <TableWrap
          list={market.result?.items}
          rowKey="market_transaction_id"
          columns={[
            { key: 'market_transaction_id', label: 'ID' },
            { key: 'user_id', label: '회원' },
            { key: 'side', label: '구분' },
            { key: 'quantity', label: '수량' },
            { key: 'amount_krw', label: '거래금액', render: (row) => won(row.amount_krw) },
            { key: 'executed_at', label: '체결시각', render: (row) => dt(row.executed_at) },
          ]}
        />
      )}
      <Pager page={view.page} total={view.result?.total} setPage={view.setPage} />
    </>
  )
}

/* ── 커뮤니티 ── */
function CommunitySection() {
  const [mode, setMode] = useState('posts')
  const posts = usePagedList(adminGetPosts)
  const comments = usePagedList(adminGetCommentsAll)
  const view = mode === 'posts' ? posts : comments
  const [dialog, setDialog] = useState(null)
  const del = (fn, message) => async (values) => { await fn(values.reason); showToast(message); view.reload() }

  return (
    <>
      <div className="tab-bar">
        <button className={mode === 'posts' ? 'active' : ''} onClick={() => setMode('posts')}>게시글</button>
        <button className={mode === 'comments' ? 'active' : ''} onClick={() => setMode('comments')}>댓글</button>
      </div>
      <Notice type="error">{view.error}</Notice>
      {view.loading ? <Loading /> : mode === 'posts' ? (
        <TableWrap
          list={posts.result?.items}
          rowKey="post_id"
          columns={[
            { key: 'post_id', label: 'ID' },
            { key: 'board_type', label: '게시판' },
            { key: 'title', label: '제목' },
            { key: 'user_id', label: '작성자' },
            { key: 'created_at', label: '작성', render: (row) => dt(row.created_at) },
          ]}
          actions={(row) => (
            <button type="button" className="btn-danger" onClick={() => setDialog({
              title: `게시글 #${row.post_id} 삭제`, fields: [REASON_FIELD],
              submit: del((reason) => adminDeletePost(row.post_id, reason), '게시글을 삭제했습니다.'),
            })}>운영 삭제</button>
          )}
        />
      ) : (
        <TableWrap
          list={comments.result?.items}
          rowKey="comment_id"
          columns={[
            { key: 'comment_id', label: 'ID' },
            { key: 'post_id', label: '글' },
            { key: 'content', label: '내용' },
            { key: 'user_id', label: '작성자' },
            { key: 'created_at', label: '작성', render: (row) => dt(row.created_at) },
          ]}
          actions={(row) => (
            <button type="button" className="btn-danger" onClick={() => setDialog({
              title: `댓글 #${row.comment_id} 삭제`, fields: [REASON_FIELD],
              submit: del((reason) => adminDeleteComment(row.comment_id, reason), '댓글을 삭제했습니다.'),
            })}>운영 삭제</button>
          )}
        />
      )}
      <Pager page={view.page} total={view.result?.total} setPage={view.setPage} />
      {dialog && <PromptDialog title={dialog.title} fields={dialog.fields} onSubmit={dialog.submit} onClose={() => setDialog(null)} />}
    </>
  )
}

/* ── 신고 ── */
function ReportsSection() {
  const { result, loading, error, page, setPage, reload } = usePagedList(adminGetReports)
  const [dialog, setDialog] = useState(null)

  return (
    <>
      <Notice type="error">{error}</Notice>
      {loading ? <Loading /> : (
        <>
          <TableWrap
            list={result?.items}
            rowKey="report_id"
            columns={[
              { key: 'report_id', label: 'ID' },
              { key: 'target_type', label: '대상' },
              { key: 'target_id', label: '대상 ID' },
              { key: 'reason', label: '사유' },
              { key: 'status', label: '상태' },
              { key: 'created_at', label: '접수', render: (row) => dt(row.created_at) },
            ]}
            actions={(row) => row.status !== 'PENDING' ? <span className="mini-sub">{row.status}</span> : (
              <button type="button" onClick={() => setDialog({
                title: `신고 #${row.report_id} 처리`,
                fields: [
                  { name: 'status', label: '처리', type: 'select', options: [['RESOLVED', '조치 완료'], ['REJECTED', '반려']], default: 'RESOLVED' },
                  REASON_FIELD,
                ],
                submit: async (values) => { await adminResolveReport(row.report_id, values); showToast('신고를 처리했습니다.'); reload() },
              })}>처리</button>
            )}
          />
          <Pager page={page} total={result?.total} setPage={setPage} />
        </>
      )}
      {dialog && <PromptDialog title={dialog.title} fields={dialog.fields} onSubmit={dialog.submit} onClose={() => setDialog(null)} />}
    </>
  )
}

/* ── 문의 ── */
function InquiriesSection() {
  const { result, loading, error, page, setPage, reload } = usePagedList(adminGetInquiries)
  const [dialog, setDialog] = useState(null)

  return (
    <>
      <Notice type="error">{error}</Notice>
      {loading ? <Loading /> : (
        <>
          <TableWrap
            list={result?.items}
            rowKey="inquiry_id"
            columns={[
              { key: 'inquiry_id', label: 'ID' },
              { key: 'user_id', label: '회원' },
              { key: 'title', label: '제목' },
              { key: 'related_ledger_transaction_id', label: '관련 거래' },
              { key: 'status', label: '상태' },
              { key: 'created_at', label: '접수', render: (row) => dt(row.created_at) },
            ]}
            actions={(row) => (
              <button type="button" onClick={() => setDialog({
                title: `문의 #${row.inquiry_id} 답변`,
                body: row.content,
                fields: [
                  { name: 'answer', label: '답변', type: 'textarea', maxLength: 5000, default: row.admin_answer || '' },
                  REASON_FIELD,
                ],
                submit: async (values) => { await adminAnswerInquiry(row.inquiry_id, values); showToast('답변을 등록했습니다.'); reload() },
              })}>답변</button>
            )}
          />
          <Pager page={page} total={result?.total} setPage={setPage} />
        </>
      )}
      {dialog && (
        <PromptDialog
          title={dialog.title}
          body={dialog.body}
          fields={dialog.fields}
          submitLabel="답변 등록"
          onSubmit={dialog.submit}
          onClose={() => setDialog(null)}
        />
      )}
    </>
  )
}

/* ── 감사 로그 ── */
function AuditSection() {
  const [action, setAction] = useState('')
  const [targetType, setTargetType] = useState('')
  const params = {}
  if (action) params.action = action
  if (targetType) params.target_type = targetType
  const { result, loading, error, page, setPage } = usePagedList(adminGetAuditLogs, params)

  return (
    <>
      <div className="tx-filter">
        <input type="text" value={action} onChange={(event) => { setAction(event.target.value); setPage(1) }} placeholder="action 필터" />
        <input type="text" value={targetType} onChange={(event) => { setTargetType(event.target.value); setPage(1) }} placeholder="target_type 필터" />
        {result && <span className="tx-count">전체 {result.total}건</span>}
      </div>
      <Notice type="error">{error}</Notice>
      {loading ? <Loading /> : (
        <>
          <TableWrap
            list={result?.items}
            rowKey="audit_log_id"
            columns={[
              { key: 'audit_log_id', label: 'ID' },
              { key: 'created_at', label: '시각', render: (row) => dt(row.created_at) },
              { key: 'actor_user_id', label: '행위자', render: (row) => (row.actor_user_id == null ? '시스템' : `#${row.actor_user_id}`) },
              { key: 'action', label: 'action' },
              { key: 'target_type', label: '대상', render: (row) => `${row.target_type} #${row.target_id}` },
              { key: 'before_value', label: '변경 전', render: (row) => (row.before_value ? JSON.stringify(row.before_value) : '-') },
              { key: 'after_value', label: '변경 후', render: (row) => (row.after_value ? JSON.stringify(row.after_value) : '-') },
              { key: 'reason', label: '사유', render: (row) => row.reason || '-' },
            ]}
          />
          <Pager page={page} total={result?.total} setPage={setPage} />
        </>
      )}
    </>
  )
}

const SECTION_COMPONENT = {
  users: UsersSection,
  products: ProductsSection,
  transactions: TransactionsSection,
  community: CommunitySection,
  reports: ReportsSection,
  inquiries: InquiriesSection,
  audit: AuditSection,
}

function AdminPage() {
  const [section, setSection] = useState('users')
  const [gate, setGate] = useState('checking') // checking | ok | denied | error

  useEffect(() => {
    adminGetUsers({ size: 1 })
      .then(() => setGate('ok'))
      .catch((err) => {
        const code = err?.response?.data?.error?.code
        setGate(code === 'FORBIDDEN' || err?.response?.status === 403 ? 'denied' : 'error')
      })
  }, [])

  const Section = SECTION_COMPONENT[section]

  return (
    <PageShell eyebrow="운영" title="관리자" description="회원·금융상품·거래·커뮤니티·신고·문의·감사 로그를 관리합니다.">
      {MOCKS_ENABLED && (
        <div className="mock-banner">목(mock) 데이터 표시 중 · 관리자 API는 표본 데이터로 동작</div>
      )}

      {gate === 'checking' && <Loading />}
      {gate === 'denied' && <Notice type="error">관리자 권한이 필요합니다.</Notice>}
      {gate === 'error' && <Notice type="error">관리자 정보를 불러오지 못했습니다.</Notice>}

      {gate === 'ok' && (
        <>
          <div className="tab-bar admin-nav">
            {SECTIONS.map(([key, label]) => (
              <button key={key} className={section === key ? 'active' : ''} onClick={() => setSection(key)}>{label}</button>
            ))}
          </div>
          <Section />
        </>
      )}
    </PageShell>
  )
}

export default AdminPage
