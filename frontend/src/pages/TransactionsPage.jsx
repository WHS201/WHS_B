import { useEffect, useState } from 'react'
import PageShell from '../components/PageShell'
import { Empty, Loading, Notice } from '../components/Ui'
import { won } from '../utils/format'
import { MOCKS_ENABLED, getApiError, getInvestmentTransactions, getLedgerTransactions } from '../api/features'

const PAGE_SIZE = 10

// backend app/constants.py TransactionType
const LEDGER_TYPE_LABELS = {
  INITIAL_ASSET: '초기 자산',
  MONTHLY_INCOME: '월 정기 수입',
  MONTHLY_EXPENSE: '월 예상 지출',
  STOCK_BUY: '주식·ETF 매수',
  STOCK_SELL: '주식·ETF 매도',
  DEPOSIT_JOIN: '예금 가입',
  DEPOSIT_CANCEL: '예금 중도해지',
  DEPOSIT_MATURITY: '예금 만기',
  SAVING_PAYMENT: '적금 납입',
  SAVING_CANCEL: '적금 중도해지',
  SAVING_MATURITY: '적금 만기',
}
const TYPE_OPTIONS = [['', '전체'], ...Object.entries(LEDGER_TYPE_LABELS)]

const dateTime = (value) => (value ? value.slice(0, 16).replace('T', ' ') : '-')
const signed = (value) => `${Number(value) >= 0 ? '+' : ''}${won(value)}`
const netClass = (value) => (Number(value) >= 0 ? 'profit-up' : 'profit-down')
const ledgerNet = (row) => (row.entries || []).reduce(
  (sum, entry) => sum + (entry.entry_type === 'CREDIT' ? Number(entry.amount) : -Number(entry.amount)),
  0,
)

function TransactionsPage() {
  const [tab, setTab] = useState('LEDGER') // LEDGER | MARKET
  const [typeFilter, setTypeFilter] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null) // { items, page, size, total }
  const [openId, setOpenId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    const params = { page, size: PAGE_SIZE }
    const request = tab === 'LEDGER'
      ? getLedgerTransactions(typeFilter ? { ...params, transaction_type: typeFilter } : params)
      : getInvestmentTransactions(params)

    request
      .then((response) => {
        if (!active) return
        setResult(response.data)
        setLoading(false)
      })
      .catch((loadError) => {
        if (!active) return
        setError(getApiError(loadError))
        setResult(null)
        setLoading(false)
      })

    return () => { active = false }
  }, [tab, typeFilter, page])

  const changeTab = (next) => {
    if (next === tab) return
    setTab(next)
    setPage(1)
    setTypeFilter('')
    setOpenId(null)
    setResult(null)
  }

  const changeFilter = (value) => {
    setTypeFilter(value)
    setPage(1)
    setOpenId(null)
  }

  const totalPages = result ? Math.max(1, Math.ceil(result.total / PAGE_SIZE)) : 1
  const items = result?.items || []

  return (
    <PageShell
      eyebrow="내 재테크"
      title="거래 내역"
      description="가상 계좌의 금액 이동(원장)과 주식·ETF 체결 내역을 확인하세요."
    >
      {MOCKS_ENABLED && (
        <div className="mock-banner">
          목(mock) 데이터 표시 중 · 백엔드 연결 시 <code>VITE_USE_MOCKS=false</code> 로 전환
        </div>
      )}

      <div className="tab-bar">
        <button className={tab === 'LEDGER' ? 'active' : ''} onClick={() => changeTab('LEDGER')}>금융 원장</button>
        <button className={tab === 'MARKET' ? 'active' : ''} onClick={() => changeTab('MARKET')}>주식·ETF 거래</button>
      </div>

      {tab === 'LEDGER' && (
        <div className="tx-filter">
          <select value={typeFilter} onChange={(event) => changeFilter(event.target.value)}>
            {TYPE_OPTIONS.map(([value, label]) => (
              <option key={value || 'all'} value={value}>{label}</option>
            ))}
          </select>
          {result && <span className="tx-count">전체 {result.total}건</span>}
        </div>
      )}

      <Notice type="error">{error}</Notice>

      {loading ? <Loading /> : items.length === 0 ? <Empty>표시할 거래 내역이 없습니다.</Empty> : (
        <>
          {tab === 'LEDGER' ? (
            <ul className="tx-list">
              {items.map((row) => {
                const net = ledgerNet(row)
                const open = openId === row.ledger_transaction_id
                return (
                  <li key={row.ledger_transaction_id} className="tx-item">
                    <button
                      type="button"
                      className="tx-main"
                      onClick={() => setOpenId(open ? null : row.ledger_transaction_id)}
                    >
                      <span>
                        <span className="tx-type">{LEDGER_TYPE_LABELS[row.transaction_type] || row.transaction_type}</span>
                        <span className="tx-sub">{dateTime(row.created_at)}</span>
                      </span>
                      <span className={`tx-amount ${netClass(net)}`}>{signed(net)}</span>
                      <span className="tx-balance">잔액 {won(row.balance_after)}</span>
                      <span className="tx-caret">{open ? '▲' : '▼'}</span>
                    </button>

                    {open && (
                      <div className="tx-detail">
                        <div>원본 참조: {row.reference_type} #{row.reference_id}</div>
                        <table>
                          <tbody>
                            {(row.entries || []).map((entry) => (
                              <tr key={entry.ledger_entry_id}>
                                <td>{entry.entry_type === 'CREDIT' ? '입금 (CREDIT)' : '출금 (DEBIT)'}</td>
                                <td style={{ textAlign: 'right' }}>{won(entry.amount)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="mini-table">
                <thead>
                  <tr><th>구분</th><th>수량</th><th>단가</th><th>거래금액</th><th>수수료·세금</th><th>체결시각</th></tr>
                </thead>
                <tbody>
                  {items.map((trade) => (
                    <tr key={trade.market_transaction_id}>
                      <td>
                        <span className={`trade-side ${trade.side === 'BUY' ? 'is-buy' : 'is-sell'}`}>
                          {trade.side === 'BUY' ? '매수' : '매도'}
                        </span>
                        {' '}
                        <span className="mini-sub">자산 #{trade.asset_id}</span>
                      </td>
                      <td>{trade.quantity}</td>
                      <td>{trade.exchange_rate ? `$${trade.price}` : won(trade.price)}</td>
                      <td>{won(trade.amount_krw)}</td>
                      <td>{won(Number(trade.fee) + Number(trade.tax))}</td>
                      <td>{dateTime(trade.executed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="pager">
            <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>이전</button>
            <span>{page} / {totalPages}</span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>다음</button>
          </div>
        </>
      )}
    </PageShell>
  )
}

export default TransactionsPage
