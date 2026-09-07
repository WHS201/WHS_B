import { useEffect, useState } from 'react'
import PageShell from '../components/PageShell'
import { showToast } from '../components/Toast'
import { Empty, Loading, Notice } from '../components/Ui'
import { shortDate } from '../utils/format'
import {
  MOCKS_ENABLED, createInquiry, getApiError, getInquiries, getMyReports,
} from '../api/features'

const dt = (value) => (value ? value.slice(0, 16).replace('T', ' ') : '-')
const INQUIRY_LABEL = { PENDING: '접수됨', ANSWERED: '답변 완료' }
const REPORT_LABEL = { PENDING: '접수됨', RESOLVED: '조치 완료', REJECTED: '반려' }

function InquiryTab() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', content: '', related_ledger_transaction_id: '' })
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => {
    setLoading(true)
    setError('')
    getInquiries({ page: 1, size: 50 })
      .then((res) => { setList(res.data.items); setLoading(false) })
      .catch((err) => { setError(getApiError(err)); setLoading(false) })
  }

  useEffect(load, [])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    const payload = { title: form.title.trim(), content: form.content.trim() }
    if (form.related_ledger_transaction_id.trim()) {
      payload.related_ledger_transaction_id = Number(form.related_ledger_transaction_id)
    }
    try {
      await createInquiry(payload)
      setShowForm(false)
      setForm({ title: '', content: '', related_ledger_transaction_id: '' })
      showToast('문의를 접수했습니다.')
      load()
    } catch (submitError) {
      setFormError(getApiError(submitError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="goal-row-head" style={{ marginBottom: 14 }}>
        <span className="mini-sub">시뮬레이션 중 발생한 거래 문제를 관리자에게 문의할 수 있습니다.</span>
        <button type="button" className="service-primary-button" onClick={() => { setShowForm((v) => !v); setFormError('') }}>
          {showForm ? '작성 닫기' : '새 문의'}
        </button>
      </div>

      {showForm && (
        <form className="service-card" onSubmit={submit}>
          <span className="card-label">새 문의</span>
          <label className="field-label" htmlFor="iq_title">제목</label>
          <input id="iq_title" type="text" maxLength={100} required value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
          <label className="field-label" htmlFor="iq_content">내용</label>
          <textarea id="iq_content" maxLength={5000} required rows={5} value={form.content} onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))} />
          <label className="field-label" htmlFor="iq_ref">관련 원장 거래 ID (선택)</label>
          <input id="iq_ref" type="number" min="1" value={form.related_ledger_transaction_id} onChange={(e) => setForm((f) => ({ ...f, related_ledger_transaction_id: e.target.value }))} placeholder="거래 내역 > 금융 원장의 거래 번호" />
          <Notice type="error">{formError}</Notice>
          <button type="submit" className="service-primary-button" disabled={busy}>문의 접수</button>
        </form>
      )}

      <Notice type="error">{error}</Notice>

      {loading ? <Loading /> : list.length === 0 ? <Empty>접수한 문의가 없습니다.</Empty> : (
        <ul className="tx-list">
          {list.map((inquiry) => {
            const open = selected === inquiry.inquiry_id
            return (
              <li key={inquiry.inquiry_id} className="tx-item">
                <button type="button" className="tx-main" style={{ gridTemplateColumns: '1fr auto 24px' }} onClick={() => setSelected(open ? null : inquiry.inquiry_id)}>
                  <span>
                    <span className="tx-type">{inquiry.title}</span>
                    <span className="tx-sub">{dt(inquiry.created_at)}{inquiry.related_ledger_transaction_id ? ` · 거래 #${inquiry.related_ledger_transaction_id}` : ''}</span>
                  </span>
                  <span className={`goal-state ${inquiry.status === 'ANSWERED' ? 'done' : 'active'}`}>{INQUIRY_LABEL[inquiry.status] || inquiry.status}</span>
                  <span className="tx-caret">{open ? '▲' : '▼'}</span>
                </button>
                {open && (
                  <div className="tx-detail">
                    <p style={{ whiteSpace: 'pre-wrap', margin: '0 0 12px' }}>{inquiry.content}</p>
                    {inquiry.status === 'ANSWERED' ? (
                      <div className="inquiry-answer">
                        <strong>관리자 답변</strong>
                        <p style={{ whiteSpace: 'pre-wrap' }}>{inquiry.admin_answer}</p>
                        <span className="mini-sub">{dt(inquiry.answered_at)}</span>
                      </div>
                    ) : <span className="mini-sub">아직 답변이 등록되지 않았습니다.</span>}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}

function ReportTab() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getMyReports({ page: 1, size: 50 })
      .then((res) => { setList(res.data.items); setLoading(false) })
      .catch((err) => { setError(getApiError(err)); setLoading(false) })
  }, [])

  if (loading) return <Loading />
  if (error) return <Notice type="error">{error}</Notice>
  if (list.length === 0) return <Empty>접수한 신고가 없습니다.</Empty>

  return (
    <ul className="tx-list">
      {list.map((report) => (
        <li key={report.report_id} className="tx-item">
          <div className="tx-main" style={{ gridTemplateColumns: '1fr auto', cursor: 'default' }}>
            <span>
              <span className="tx-type">{report.target_type === 'POST' ? '게시글' : '댓글'} #{report.target_id}</span>
              <span className="tx-sub">{report.reason}</span>
              <span className="tx-sub">{shortDate(report.created_at)}{report.resolution_reason ? ` · 처리 사유: ${report.resolution_reason}` : ''}</span>
            </span>
            <span className={`goal-state ${report.status === 'RESOLVED' ? 'done' : report.status === 'REJECTED' ? 'active' : 'active'}`}>
              {REPORT_LABEL[report.status] || report.status}
            </span>
          </div>
        </li>
      ))}
    </ul>
  )
}

function SupportPage() {
  const [tab, setTab] = useState('inquiry')

  return (
    <PageShell
      eyebrow="고객지원"
      title="문의·신고"
      description="거래 오류 문의 접수 상황과 내가 접수한 신고 처리 상태를 확인합니다."
    >
      {MOCKS_ENABLED && (
        <div className="mock-banner">목(mock) 데이터 표시 중 · 백엔드 연결 시 <code>VITE_USE_MOCKS=false</code> 로 전환</div>
      )}

      <div className="tab-bar">
        <button className={tab === 'inquiry' ? 'active' : ''} onClick={() => setTab('inquiry')}>거래 오류 문의</button>
        <button className={tab === 'report' ? 'active' : ''} onClick={() => setTab('report')}>내 신고 내역</button>
      </div>

      {tab === 'inquiry' ? <InquiryTab /> : <ReportTab />}
    </PageShell>
  )
}

export default SupportPage
