import { Link } from 'react-router-dom'
import { auditValue, label, ledgerLabel, ledgerNet, memberLabel, signedWon } from '../utils/presentation'
import { useEffect, useState } from 'react'
import PageShell from '../components/PageShell'
import { showToast } from '../components/Toast'
import { Empty, Loading, Notice } from '../components/Ui'
import { shortDate, won } from '../utils/format'
import {
  MOCKS_ENABLED, getApiError,
  adminAdjustAccount, adminAnswerInquiry, adminDeleteComment, adminDeletePost, adminDeleteUser,
  adminGetAuditLogs, adminGetCommentsAll, adminGetInquiries, adminGetLedger, adminGetMarketTransactions,
  adminDeleteProduct, adminGetProduct, adminGetProducts, adminGetPosts, adminGetReports, adminGetReport, adminGetInquiry,
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
    if (busy || fields.length === 0) return
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
    <div className="confirm-backdrop" onClick={() => { if (!busy) onClose() }} role="presentation">
      <form role="dialog" aria-modal="true" aria-label={title} className="confirm-dialog admin-dialog" onClick={(event) => event.stopPropagation()} onSubmit={submit}>
        <h2>{title}</h2>
        {body && <div className="admin-dialog-body full-content">{body}</div>}
        {fields.map((field) => (
          <div key={field.name} className="form-group">
            <label htmlFor={`admin_${field.name}`}>{field.label}</label>
            {field.type === 'select' ? (
              <select id={`admin_${field.name}`} disabled={busy} value={values[field.name]} onChange={set(field.name)}>
                {field.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            ) : field.type === 'textarea' ? (
              <textarea id={`admin_${field.name}`} disabled={busy} required={field.required !== false} value={values[field.name]} onChange={set(field.name)} maxLength={field.maxLength} rows={4} />
            ) : (
              <input id={`admin_${field.name}`} disabled={busy} step={field.step} type={field.type || 'text'} value={values[field.name]} onChange={set(field.name)} />
            )}
          </div>
        ))}
        {error && <Notice type="error">{error}</Notice>}
        <div>
          <button type="button" className="confirm-cancel" disabled={busy} onClick={onClose}>{fields.length ? "취소" : "닫기"}</button>
          {fields.length > 0 && <button type="submit" className="confirm-accept" disabled={busy}>{submitLabel}</button>}
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
              { key: 'role', label: '권한', render: (row) => label(row.role) },
              { key: 'status', label: '상태', render: (row) => <span className={`goal-state ${row.status === 'ACTIVE' ? 'active' : 'done'}`}>{label(row.status)}</span> },
              { key: 'created_at', label: '가입일', render: (row) => shortDate(row.created_at) },
            ]}
            actions={(row) => row.role === 'ADMIN' ? <span className="mini-sub">-</span> : (
              <>
                <button type="button" onClick={() => setDialog({
                  title: `${row.nickname} 상태 변경`,
                  fields: [{ name: 'status', label: '상태', type: 'select', options: [['ACTIVE', '이용 중 (정지 해제)'], ['SUSPENDED', '정지']], default: row.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE' }, REASON_FIELD],
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
        <PromptDialog title={dialog.title} body={dialog.body} fields={dialog.fields} onSubmit={dialog.submit} onClose={() => setDialog(null)} />
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
              { key: 'product_type', label: '유형', render: (row) => label(row.product_type) },
              { key: 'is_active', label: '판매', render: (row) => (row.is_active ? '판매중' : '중지') },
              { key: 'sync_locked', label: '자동 갱신', render: (row) => <span title="관리자가 수정한 상품은 외부 상품 데이터로 덮어쓰지 않습니다.">{row.sync_locked ? '제외 (관리자 수정 보호)' : '사용'}</span> },
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
              { key: 'is_active', label: '활성', render: (row) => (row.is_active ? '활성' : '비활성') },
            ]}
            actions={(row) => (
              <button type="button" onClick={() => setDialog({
                title: `옵션 ${row.option_id} 수정`,
                fields: [
                  { name: 'base_interest_rate', label: '기본 금리(%)', type: 'number', step: 'any', default: row.base_interest_rate },
                  { name: 'max_interest_rate', label: '최고 금리(%)', type: 'number', step: 'any', default: row.max_interest_rate },
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
        <PromptDialog title={dialog.title} body={dialog.body} fields={dialog.fields} onSubmit={dialog.submit} onClose={() => setDialog(null)} />
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
            { key: 'user_id', label: '회원', render: (row) => memberLabel(row.member, row.user_id) },
            { key: 'transaction_type', label: '종류', render: (row) => label(row.transaction_type) },
            { key: 'amount', label: '입·출금', render: (row) => <span className={ledgerNet(row) >= 0 ? 'profit-up' : 'profit-down'}>{signedWon(ledgerNet(row))}</span> },
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
            { key: 'user_id', label: '회원', render: (row) => memberLabel(row.member, row.user_id) },
            { key: 'side', label: '구분', render: (row) => label(row.side) },
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
            { key: 'board_type', label: '게시판', render: (row) => label(row.board_type) },
            { key: 'title', label: '제목' },
            { key: 'user_id', label: '작성자', render: (row) => memberLabel(row.member, row.user_id) },
            { key: 'created_at', label: '작성', render: (row) => dt(row.created_at) },
          ]}
          actions={(row) => (
            <>
            <button type="button" onClick={() => setDialog({ title: `게시글 #${row.post_id}`, body: <><h3>{row.title}</h3><p>{row.content}</p><Link to={`/community/posts/${row.post_id}`}>게시글 열기</Link></>, fields: [] })}>상세</button>
            <button type="button" className="btn-danger" onClick={() => setDialog({
              title: `게시글 #${row.post_id} 삭제`, fields: [REASON_FIELD],
              submit: del((reason) => adminDeletePost(row.post_id, reason), '게시글을 삭제했습니다.'),
            })}>운영 삭제</button>
            </>
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
            { key: 'user_id', label: '작성자', render: (row) => memberLabel(row.member, row.user_id) },
            { key: 'created_at', label: '작성', render: (row) => dt(row.created_at) },
          ]}
          actions={(row) => (
            <>
            <button type="button" onClick={() => setDialog({ title: `댓글 #${row.comment_id}`, body: <><p>{row.content}</p><Link to={`/community/posts/${row.post_id}`}>원문 게시글 열기</Link></>, fields: [] })}>상세</button>
            <button type="button" className="btn-danger" onClick={() => setDialog({
              title: `댓글 #${row.comment_id} 삭제`, fields: [REASON_FIELD],
              submit: del((reason) => adminDeleteComment(row.comment_id, reason), '댓글을 삭제했습니다.'),
            })}>운영 삭제</button>
            </>
          )}
        />
      )}
      <Pager page={view.page} total={view.result?.total} setPage={view.setPage} />
      {dialog && <PromptDialog title={dialog.title} body={dialog.body} fields={dialog.fields} onSubmit={dialog.submit} onClose={() => setDialog(null)} />}
    </>
  )
}

/* ── 신고 ── */
function ReportsSection() {
  const { result, loading, error, page, setPage, reload } = usePagedList(adminGetReports)
  const [dialog, setDialog] = useState(null)
  const openReport = async (row) => {
    try {
      const { data: report } = await adminGetReport(row.report_id)
      const pending = report.status === 'PENDING'
      setDialog({
        title: `신고 #${report.report_id} ${pending ? '검토 및 처리' : '처리 내역'}`,
        body: <>
          <p>신고자: {memberLabel(report.member, report.reporter_user_id)}</p>
          <h3>신고 사유</h3><p>{report.reason}</p>
          <h3>신고 대상: {label(report.target_type)} #{report.target_id}</h3>
          {report.target?.deleted ? <p>삭제된 {label(report.target_type)}</p> : <>
            {report.target?.title && <h4>{report.target.title}</h4>}
            <p>{report.target?.content || '대상 내용을 확인할 수 없습니다.'}</p>
            {report.target?.post_id && <Link to={`/community/posts/${report.target.post_id}`}>원문 게시글 열기</Link>}
          </>}
          {!pending && <><h3>{label(report.status)}</h3><p>{report.resolution_reason || '-'}</p></>}
        </>,
        fields: pending ? [
          { name: 'status', label: '처리 결과', type: 'select', options: [['RESOLVED', '조치 완료'], ['REJECTED', '반려']], default: 'RESOLVED' },
          { ...REASON_FIELD, label: '신고 처리 사유 (필수)' },
        ] : [],
        submit: async (values) => { await adminResolveReport(report.report_id, values); showToast('신고를 처리했습니다.'); reload() },
      })
    } catch (err) { showToast(getApiError(err), 'error') }
  }
  return <>
    <Notice type="error">{error}</Notice>
    {loading ? <Loading /> : <>
      <TableWrap list={result?.items} rowKey="report_id" columns={[
        { key: 'report_id', label: '신고 번호' },
        { key: 'reporter_user_id', label: '신고자', render: (row) => memberLabel(row.member, row.reporter_user_id) },
        { key: 'target_type', label: '대상', render: (row) => `${label(row.target_type)} #${row.target_id}${row.target?.deleted ? ' (삭제됨)' : ''}` },
        { key: 'reason', label: '신고 사유' },
        { key: 'status', label: '상태', render: (row) => label(row.status) },
        { key: 'created_at', label: '접수', render: (row) => dt(row.created_at) },
      ]} actions={(row) => <button type="button" onClick={() => openReport(row)}>{row.status === 'PENDING' ? '상세·처리' : '상세'}</button>} />
      <Pager page={page} total={result?.total} setPage={setPage} />
    </>}
    {dialog && <PromptDialog title={dialog.title} body={dialog.body} fields={dialog.fields} onSubmit={dialog.submit} onClose={() => setDialog(null)} />}
  </>
}

/* ── 문의 ── */
function InquiriesSection() {
  const { result, loading, error, page, setPage, reload } = usePagedList(adminGetInquiries)
  const [dialog, setDialog] = useState(null)
  const openInquiry = async (row) => {
    try {
      const { data: inquiry } = await adminGetInquiry(row.inquiry_id)
      setDialog({
        title: `문의 #${inquiry.inquiry_id} 답변`,
        body: <>
          <p>작성자: {memberLabel(inquiry.member, inquiry.user_id)}</p>
          <h3>{inquiry.title}</h3><p>{inquiry.content}</p>
          <h3>관련 금융 원장 거래</h3>
          <p>{inquiry.related_transaction ? ledgerLabel(inquiry.related_transaction)
            : inquiry.related_ledger_transaction_id ? `거래 #${inquiry.related_ledger_transaction_id} (현재 조회할 수 없는 거래)` : '연결된 거래 없음'}</p>
          {inquiry.related_transaction && <p>거래 후 잔액: {won(inquiry.related_transaction.balance_after)}</p>}
          {(inquiry.attachments || []).map((image) => <img className="inquiry-image" key={image.attachment_id} src={image.url} alt="문의 첨부 이미지" />)}
        </>,
        fields: [
          { name: 'answer', label: '사용자에게 전달할 답변 (필수)', type: 'textarea', maxLength: 5000, default: inquiry.admin_answer || '' },
          { ...REASON_FIELD, label: '감사 로그에 남길 내부 처리 사유 (필수)' },
        ],
        submit: async (values) => { await adminAnswerInquiry(inquiry.inquiry_id, values); showToast('답변을 등록했습니다.'); reload() },
      })
    } catch (err) { showToast(getApiError(err), 'error') }
  }
  return <>
    <Notice type="error">{error}</Notice>
    {loading ? <Loading /> : <>
      <TableWrap list={result?.items} rowKey="inquiry_id" columns={[
        { key: 'inquiry_id', label: '문의 번호' },
        { key: 'user_id', label: '회원', render: (row) => memberLabel(row.member, row.user_id) },
        { key: 'title', label: '제목' },
        { key: 'related_ledger_transaction_id', label: '관련 거래', render: (row) => row.related_transaction ? ledgerLabel(row.related_transaction) : row.related_ledger_transaction_id ? `거래 #${row.related_ledger_transaction_id} (조회 불가)` : '-' },
        { key: 'status', label: '상태', render: (row) => label(row.status) },
        { key: 'created_at', label: '접수', render: (row) => dt(row.created_at) },
      ]} actions={(row) => <button type="button" onClick={() => openInquiry(row)}>상세·답변</button>} />
      <Pager page={page} total={result?.total} setPage={setPage} />
    </>}
    {dialog && <PromptDialog title={dialog.title} body={dialog.body} fields={dialog.fields} submitLabel="답변 등록" onSubmit={dialog.submit} onClose={() => setDialog(null)} />}
  </>
}

/* ── 감사 로그 ── */
function AuditSection() {
  const [action, setAction] = useState('')
  const [targetType, setTargetType] = useState('')
  const [detail, setDetail] = useState(null)
  const params = {}
  if (action) params.action = action
  if (targetType) params.target_type = targetType
  const { result, loading, error, page, setPage } = usePagedList(adminGetAuditLogs, params)

  return (
    <>
      <p className="mini-sub">운영 조치는 처리 목적·사유를, 자동 변경 기록은 실제 저장값 변화를 남깁니다. 같은 조치에 두 기록이 함께 나타날 수 있습니다.</p>
      <div className="tx-filter">
        <input type="text" aria-label="조치 코드 필터" value={action} onChange={(event) => { setAction(event.target.value); setPage(1) }} placeholder="조치 코드 필터 (예: UPDATE)" />
        <input type="text" value={targetType} onChange={(event) => { setTargetType(event.target.value); setPage(1) }} placeholder="대상 코드 필터 (예: users)" aria-label="대상 코드 필터" />
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
              { key: 'actor_user_id', label: '행위자', render: (row) => memberLabel(row.member, row.actor_user_id) },
              { key: 'record_kind', label: '기록 구분', render: (row) => ['CREATE', 'UPDATE', 'DELETE'].includes(row.action) ? '자동 변경 기록' : '운영 조치' },
              { key: 'action', label: '조치', render: (row) => label(row.action) },
              { key: 'target_type', label: '대상', render: (row) => `${label(row.target_type)} #${row.target_id}` },
              { key: 'before_value', label: '변경 전', render: (row) => auditValue(row.before_value) },
              { key: 'after_value', label: '변경 후', render: (row) => auditValue(row.after_value) },
              { key: 'reason', label: '사유', render: (row) => row.reason || '-' },
            ]}
            actions={(row) => <button type="button" onClick={() => setDetail(row)}>상세</button>}
          />
          <Pager page={page} total={result?.total} setPage={setPage} />
        </>
      )}
      {detail && <PromptDialog title={`감사 기록 #${detail.audit_log_id}`} fields={[]} onClose={() => setDetail(null)} body={<>
        <p>{label(detail.action)} · {memberLabel(detail.member, detail.actor_user_id)}</p>
        <p>{['CREATE', 'UPDATE', 'DELETE'].includes(detail.action) ? '자동 변경 기록' : '운영 조치'} · {label(detail.target_type)} #{detail.target_id}</p>
        <h3>변경 전</h3><p>{auditValue(detail.before_value)}</p>
        <h3>변경 후</h3><p>{auditValue(detail.after_value)}</p>
        <h3>처리 사유</h3><p>{detail.reason || '자동 기록으로 별도 사유 없음'}</p>
      </>} />}
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
