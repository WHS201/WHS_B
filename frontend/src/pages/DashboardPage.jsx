import { goalPercent } from '../utils/presentation'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageShell from '../components/PageShell'
import { Empty, Loading, Notice } from '../components/Ui'
import AssetAllocationBar from '../components/AssetAllocationBar'
import AssetHistoryChart from '../components/AssetHistoryChart'
import { rate, shortDate, won } from '../utils/format'
import { MOCKS_ENABLED, getApiError, getDashboard } from '../api/features'

const signed = (value) => `${Number(value) >= 0 ? '+' : ''}${won(value)}`
const profitClass = (value) => (Number(value) >= 0 ? 'profit-up' : 'profit-down')

function DashboardPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let ignore = false

    getDashboard()
      .then((result) => {
        if (ignore) return
        setData(result.data)
        setLoading(false)
      })
      .catch((loadError) => {
        if (ignore) return
        setError(getApiError(loadError))
        setLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [])

  const assetById = {}
  ;(data?.holdings || []).forEach((holding) => { assetById[holding.asset_id] = holding })

  const contractCount = (data?.active_deposits || []).length + (data?.active_savings || []).length

  return (
    <PageShell
      eyebrow="내 재테크"
      title="대시보드"
      description="총자산, 손익, 목표 달성률과 최근 거래를 한눈에 확인하세요."
    >
      {MOCKS_ENABLED && (
        <div className="mock-banner">
          목(mock) 데이터 표시 중 · 백엔드 연결 시 <code>VITE_USE_MOCKS=false</code> 로 전환
        </div>
      )}

      <Notice type="error">{error}</Notice>

      {loading ? <Loading /> : !data ? <Empty /> : (
        <>
          <div className="dash-metrics">
            <div className="metric-card">
              <span>총자산</span>
              <strong>{won(data.total_assets)}</strong>
              <small>계좌 잔액 {won(data.amounts?.cash)}</small>
            </div>
            <div className="metric-card">
              <span>전체 손익</span>
              <strong className={profitClass(data.total_profit)}>{signed(data.total_profit)}</strong>
              <small>투입 원금 {won(data.net_funding)}</small>
            </div>
            <div className="metric-card">
              <span>투자 손익</span>
              <strong className={profitClass(data.investment_profit)}>{signed(data.investment_profit)}</strong>
              <small>{data.investment_return_percent == null ? '수익률 -' : `수익률 ${rate(data.investment_return_percent)}`}</small>
            </div>
            <div className="metric-card">
              <span>이번 달 잉여자금</span>
              <strong>{won(data.monthly_surplus)}</strong>
              <small>수입 {won(data.monthly_income)} · 지출 {won(data.monthly_expense)}</small>
            </div>
          </div>

          <AssetHistoryChart />

          <div className="dash-section">
            <h2>자산 구성</h2>
            <AssetAllocationBar allocation={data.allocation_percent} amounts={data.amounts} />
          </div>

          <div className="dash-section">
            <h2>목표 달성률</h2>
            {(data.goals || []).length === 0 ? <Empty>등록된 저축 목표가 없습니다.</Empty> : data.goals.map((goal) => {
              const percent = goalPercent(goal)
              const done = goal.status === 'COMPLETED'
              return (
                <div key={goal.goal_id} className="goal-row">
                  <div className="goal-row-head">
                    <strong>{goal.goal_name}</strong>
                    <span>{done ? '달성' : `목표일 ${shortDate(goal.target_date)}`}</span>
                  </div>
                  <div className="goal-progress-track">
                    <div
                      className={`goal-progress-fill${done ? ' is-done' : ''}`}
                      style={{ width: `${Math.min(percent, 100)}%` }}
                    />
                  </div>
                  <div className="goal-meta">{rate(percent)} · 목표 {won(goal.target_amount)}</div>
                </div>
              )
            })}
          </div>

          <div className="dash-grid">
            <div className="dash-section">
              <h2>보유 주식</h2>
              {(data.holdings || []).length === 0 ? <Empty>보유 중인 주식이 없습니다.</Empty> : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="mini-table">
                    <thead>
                      <tr><th>종목</th><th>수량</th><th>평가금액</th><th>평가손익</th></tr>
                    </thead>
                    <tbody>
                      {data.holdings.map((holding) => (
                        <tr key={holding.asset_id}>
                          <td>
                            {holding.name}
                            <br />
                            <span className="mini-sub">{holding.symbol} · {holding.market}</span>
                          </td>
                          <td>{holding.quantity}</td>
                          <td>{won(holding.value_krw)}</td>
                          <td className={profitClass(holding.unrealized_profit_krw)}>{signed(holding.unrealized_profit_krw)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="dash-section">
              <h2>최근 주식 거래</h2>
              {(data.recent_trades || []).length === 0 ? <Empty>최근 거래가 없습니다.</Empty> : (
                <ul className="trade-list">
                  {data.recent_trades.map((trade) => {
                    const asset = assetById[trade.asset_id]
                    const buy = trade.side === 'BUY'
                    return (
                      <li key={trade.market_transaction_id}>
                        <span>
                          <span className={`trade-side ${buy ? 'is-buy' : 'is-sell'}`}>{buy ? '매수' : '매도'}</span>
                          {' '}{asset ? asset.name : `자산 #${trade.asset_id}`}
                        </span>
                        <span className="trade-right">
                          {won(trade.amount_krw)}
                          <br />
                          <span className="mini-sub">{shortDate(trade.executed_at)}</span>
                        </span>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </div>

          <div className="dash-grid">
            <div className="dash-section">
              <h2>진행 중인 예·적금</h2>
              {contractCount === 0 ? <Empty>진행 중인 예·적금이 없습니다.</Empty> : (
                <ul className="contract-mini-list">
                  {(data.active_deposits || []).map((deposit) => (
                    <li key={`d${deposit.deposit_id}`}>
                      <span>{deposit.product_name}<br /><span className="mini-sub">{deposit.bank_name} · 예금</span></span>
                      <span className="trade-right">{won(deposit.principal)}<br /><span className="mini-sub">만기 {shortDate(deposit.maturity_date)}</span></span>
                    </li>
                  ))}
                  {(data.active_savings || []).map((saving) => (
                    <li key={`s${saving.saving_id}`}>
                      <span>{saving.product_name}<br /><span className="mini-sub">{saving.bank_name} · 적금</span></span>
                      <span className="trade-right">월 {won(saving.monthly_amount)}<br /><span className="mini-sub">만기 {shortDate(saving.maturity_date)}</span></span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="dash-section">
              <div className="goal-row-head" style={{ marginBottom: 12 }}>
                <h2 style={{ margin: 0 }}>획득한 뱃지</h2>
                <Link to="/badges" className="detail-link">전체 보기</Link>
              </div>
              {(data.badges || []).length === 0 ? <Empty>아직 획득한 뱃지가 없습니다.</Empty> : (
                <div className="badge-chip-row">
                  {data.badges.map((badge) => (
                    <span key={badge.badge_id} className="badge-chip" title={badge.description}>🏅 {badge.name}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </PageShell>
  )
}

export default DashboardPage
