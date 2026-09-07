import { useEffect, useState } from 'react'
import PageShell from '../components/PageShell'
import { Empty, Loading, Notice } from '../components/Ui'
import AssetAllocationBar from '../components/AssetAllocationBar'
import { rate, won } from '../utils/format'
import {
  MOCKS_ENABLED, getApiError, getDashboard, getGoals, runFreeProjection, runGoalProjection,
} from '../api/features'

const RETURN_ROWS = [
  ['saving', '적금 금리'],
  ['kr_stock', '국내주식'],
  ['us_stock', '미국주식'],
  ['kr_etf', '국내 ETF'],
  ['us_etf', '미국 ETF'],
]
const GOAL_ALLOC_ROWS = [
  ['existing_saving', '기존 적금 납입'],
  ['saving', '추가 적금'],
  ['kr_stock', '국내주식'],
  ['us_stock', '미국주식'],
  ['kr_etf', '국내 ETF'],
  ['us_etf', '미국 ETF'],
  ['cash', '현금'],
]
const FREE_ALLOC_ROWS = [
  ['cash', '현금'],
  ['saving', '적금'],
  ['kr_stock', '국내주식'],
  ['us_stock', '미국주식'],
  ['kr_etf', '국내 ETF'],
  ['us_etf', '미국 ETF'],
]
const DEFAULT_RETURNS = { saving: '3', kr_stock: '6', us_stock: '8', kr_etf: '6', us_etf: '8' }

const toNumbers = (obj) => Object.fromEntries(Object.entries(obj).map(([key, value]) => [key, Number(value || 0)]))
const sumObj = (obj, keys) => keys.reduce((acc, key) => acc + Number(obj[key] || 0), 0)
const signed = (value) => `${Number(value) >= 0 ? '+' : ''}${won(value)}`
const profitClass = (value) => (Number(value) >= 0 ? 'profit-up' : 'profit-down')

function AllocationField({ title, hint, rows, values, target, onChange }) {
  const used = sumObj(values, rows.map(([key]) => key))
  const remaining = target - used
  return (
    <div className="alloc-field">
      <div className="alloc-field-head">
        <strong>{title}</strong>
        <span className={remaining === 0 ? 'profit-up' : 'profit-down'}>
          배분 {won(used)} / {won(target)} · 남은 금액 {won(remaining)}
        </span>
      </div>
      {hint && <p className="field-hint">{hint}</p>}
      <div className="alloc-field-grid">
        {rows.map(([key, label]) => (
          <label key={key}>
            <span>{label}</span>
            <input
              type="number"
              min="0"
              step="10000"
              value={values[key]}
              onChange={(event) => onChange(key, event.target.value)}
            />
          </label>
        ))}
      </div>
    </div>
  )
}

function ReturnsField({ values, onChange }) {
  return (
    <div className="alloc-field">
      <div className="alloc-field-head"><strong>연 수익률 가정 (%)</strong></div>
      <p className="field-hint">사용자가 가정하는 값이며 예측이 아닙니다. 적금 금리는 0 이상이어야 합니다.</p>
      <div className="alloc-field-grid">
        {RETURN_ROWS.map(([key, label]) => (
          <label key={key}>
            <span>{label}</span>
            <input
              type="number"
              step="0.1"
              min={key === 'saving' ? '0' : undefined}
              value={values[key]}
              onChange={(event) => onChange(key, event.target.value)}
            />
          </label>
        ))}
      </div>
    </div>
  )
}

function MiniLineChart({ timeline, target }) {
  if (!timeline || timeline.length < 2) return null
  const values = timeline.map((point) => point.total_assets)
  const min = Math.min(...values, target != null ? target : Infinity)
  const max = Math.max(...values, target != null ? target : -Infinity)
  const width = 600
  const height = 160
  const pad = 6
  const xAt = (index) => pad + (index / (values.length - 1)) * (width - pad * 2)
  const yAt = (value) => height - pad - ((value - min) / (max - min || 1)) * (height - pad * 2)
  const linePoints = values.map((value, index) => `${xAt(index).toFixed(1)},${yAt(value).toFixed(1)}`).join(' ')
  const areaPoints = `${xAt(0)},${height - pad} ${linePoints} ${xAt(values.length - 1)},${height - pad}`
  return (
    <div style={{ overflowX: 'auto' }}>
      <svg className="sim-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label="예상 자산 추이">
        <polygon points={areaPoints} fill="rgba(8,126,208,.10)" />
        <polyline points={linePoints} fill="none" stroke="#087ed0" strokeWidth="2" />
        {target != null && (
          <line x1={pad} x2={width - pad} y1={yAt(target)} y2={yAt(target)} stroke="#dc5555" strokeWidth="1.5" strokeDasharray="5 4" />
        )}
      </svg>
    </div>
  )
}

function barInputs(amounts) {
  const bar = {
    cash: amounts.cash,
    deposit: amounts.existing_deposit || 0,
    saving: (amounts.saving || 0) + (amounts.existing_saving || 0),
    kr_stock: amounts.kr_stock,
    us_stock: amounts.us_stock,
    kr_etf: amounts.kr_etf,
    us_etf: amounts.us_etf,
  }
  const total = Object.values(bar).reduce((acc, value) => acc + Number(value || 0), 0)
  const allocation = Object.fromEntries(Object.entries(bar).map(([key, value]) => [key, total ? (Number(value) / total) * 100 : 0]))
  return { bar, allocation }
}

function ResultView({ result }) {
  const goalMode = result.goal_id != null
  const { bar, allocation } = barInputs(result.amounts)
  return (
    <section className="service-card">
      <span className="card-label">시뮬레이션 결과 (가정치)</span>

      <div className="dash-metrics">
        <div className="metric-card">
          <span>{goalMode ? '목표일 예상 총자산' : '예상 총자산'}</span>
          <strong>{won(result.expected_total_assets)}</strong>
          <small>초기 {won(result.initial_assets)} · 추가 납입 {won(result.future_contributions)}</small>
        </div>
        <div className="metric-card">
          <span>예상 투자 손익</span>
          <strong className={profitClass(result.expected_investment_profit)}>{signed(result.expected_investment_profit)}</strong>
          <small>환율 효과 {signed(result.exchange_rate_effect)}</small>
        </div>
        <div className="metric-card">
          <span>예상 예·적금 이자(세후)</span>
          <strong>{won(result.expected_net_interest)}</strong>
          <small>이자 {won(result.expected_interest)} · 세금 {won(result.expected_tax)}</small>
        </div>
        <div className="metric-card">
          <span>기간</span>
          <strong>{result.start_date}</strong>
          <small>~ {result.end_date}</small>
        </div>
      </div>

      {goalMode && (
        <div className="dash-metrics">
          <div className="metric-card"><span>목표 금액</span><strong>{won(result.target_amount)}</strong></div>
          <div className="metric-card">
            <span>목표금액과의 차이</span>
            <strong className={profitClass(result.difference)}>{signed(result.difference)}</strong>
          </div>
          <div className="metric-card"><span>예상 목표 달성률</span><strong>{rate(result.progress_percent)}</strong></div>
          <div className="metric-card"><span>누락된 예상 납입</span><strong>{result.missed_payments}회</strong></div>
        </div>
      )}

      <div className="dash-section">
        <h2>예상 자산 추이</h2>
        <MiniLineChart timeline={result.timeline} target={goalMode ? result.target_amount : null} />
        {goalMode && <p className="mini-sub" style={{ marginTop: 8 }}>붉은 점선 = 목표 금액</p>}
      </div>

      <div className="dash-section">
        <h2>{goalMode ? '목표일' : '종료 시점'} 자산 구성</h2>
        <AssetAllocationBar allocation={allocation} amounts={bar} />
        {(result.amounts.existing_deposit > 0 || result.amounts.existing_saving > 0) && (
          <p className="mini-sub" style={{ marginTop: 10 }}>
            기존 예금 {won(result.amounts.existing_deposit)} · 기존 적금 {won(result.amounts.existing_saving)} 포함
          </p>
        )}
      </div>

      {result.missed_payments > 0 && (
        <Notice type="info">현금이 부족해 예상 적금 납입 {result.missed_payments}회가 누락됩니다.</Notice>
      )}
      <p className="mini-sub">※ 미래 수익률·환율은 사용자가 입력한 가정이며, 매매 수수료는 포함하지 않습니다.</p>
    </section>
  )
}

function GoalSimForm() {
  const [goalList, setGoalList] = useState([])
  const [dash, setDash] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [goalId, setGoalId] = useState('')
  const [alloc, setAlloc] = useState({ existing_saving: '', saving: '', kr_stock: '', us_stock: '', kr_etf: '', us_etf: '', cash: '' })
  const [returns, setReturns] = useState(DEFAULT_RETURNS)
  const [futureFx, setFutureFx] = useState('')

  const [result, setResult] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([getGoals(), getDashboard()])
      .then(([goalRes, dashRes]) => {
        if (!active) return
        setGoalList(goalRes.data.filter((goal) => goal.status === 'ACTIVE'))
        setDash(dashRes.data)
        setFutureFx(String(Math.round(Number(dashRes.data.exchange_rate) || 1385)))
        setLoading(false)
      })
      .catch((err) => { if (active) { setLoadError(getApiError(err)); setLoading(false) } })
    return () => { active = false }
  }, [])

  if (loading) return <Loading />
  if (loadError) return <Notice type="error">{loadError}</Notice>
  if (goalList.length === 0) return <Empty>진행 중인 저축 목표가 없습니다. 먼저 목표를 만들어 주세요.</Empty>

  const surplus = dash ? dash.monthly_income - dash.monthly_expense : 0
  const goal = goalList.find((item) => String(item.goal_id) === goalId)

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (!goalId) { setError('목표를 선택해 주세요.'); return }
    setSubmitting(true)
    try {
      const res = await runGoalProjection(Number(goalId), {
        monthly_allocation: toNumbers(alloc),
        annual_returns: toNumbers(returns),
        future_exchange_rate: Number(futureFx),
      })
      setResult(res.data)
    } catch (submitError) {
      setError(getApiError(submitError))
      setResult(null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <form className="service-card" onSubmit={submit}>
        <span className="card-label">목표 달성 시뮬레이션</span>
        <p>현재 총자산 · 월 수입/지출 · 목표 금액/기간은 서버에서 자동으로 반영됩니다. 월 잉여자금 배분과 가정치만 입력하세요.</p>

        <label className="field-label" htmlFor="sim_goal">목표</label>
        <select id="sim_goal" value={goalId} onChange={(event) => setGoalId(event.target.value)}>
          <option value="">목표 선택</option>
          {goalList.map((item) => (
            <option key={item.goal_id} value={item.goal_id}>{item.goal_name} · 목표 {won(item.target_amount)}</option>
          ))}
        </select>

        {dash && (
          <div className="sim-context">
            <span>현재 총자산 <strong>{won(dash.total_assets)}</strong></span>
            <span>월 수입 <strong>{won(dash.monthly_income)}</strong></span>
            <span>월 지출 <strong>{won(dash.monthly_expense)}</strong></span>
            <span>월 잉여자금 <strong>{won(surplus)}</strong></span>
            {goal && <span>목표일 <strong>{goal.target_date?.slice(0, 10)}</strong></span>}
          </div>
        )}

        <AllocationField
          title="월 잉여자금 배분"
          hint="7개 항목의 합계가 월 잉여자금과 같아야 합니다."
          rows={GOAL_ALLOC_ROWS}
          values={alloc}
          target={surplus}
          onChange={(key, value) => setAlloc((prev) => ({ ...prev, [key]: value }))}
        />

        <ReturnsField values={returns} onChange={(key, value) => setReturns((prev) => ({ ...prev, [key]: value }))} />

        <label className="field-label" htmlFor="sim_fx">미래 환율 가정 (원/달러)</label>
        <input id="sim_fx" type="number" min="1" max="10000" step="1" value={futureFx} onChange={(event) => setFutureFx(event.target.value)} />

        <Notice type="error">{error}</Notice>
        <button type="submit" className="service-primary-button" disabled={submitting}>시뮬레이션 실행</button>
      </form>

      {result && <ResultView result={result} />}
    </>
  )
}

function FreeSimForm() {
  const [basics, setBasics] = useState({ initial_asset: '10000000', monthly_income: '3000000', monthly_expense: '2000000', months: '60' })
  const [initAlloc, setInitAlloc] = useState({ cash: '', saving: '', kr_stock: '', us_stock: '', kr_etf: '', us_etf: '' })
  const [monthlyAlloc, setMonthlyAlloc] = useState({ cash: '', saving: '', kr_stock: '', us_stock: '', kr_etf: '', us_etf: '' })
  const [returns, setReturns] = useState(DEFAULT_RETURNS)
  const [fx, setFx] = useState({ initial: '1385', future: '1400' })

  const [result, setResult] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const surplus = Number(basics.monthly_income || 0) - Number(basics.monthly_expense || 0)

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const res = await runFreeProjection({
        initial_asset: Number(basics.initial_asset || 0),
        monthly_income: Number(basics.monthly_income || 0),
        monthly_expense: Number(basics.monthly_expense || 0),
        months: Number(basics.months || 0),
        initial_allocation: toNumbers(initAlloc),
        monthly_allocation: toNumbers(monthlyAlloc),
        annual_returns: toNumbers(returns),
        initial_exchange_rate: Number(fx.initial),
        future_exchange_rate: Number(fx.future),
      })
      setResult(res.data)
    } catch (submitError) {
      setError(getApiError(submitError))
      setResult(null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <form className="service-card" onSubmit={submit}>
        <span className="card-label">자유 재테크 시뮬레이션</span>
        <p>가상의 재무 조건을 직접 입력해 미래 자산을 계산합니다.</p>

        <div className="compact-fields">
          <div><label className="field-label">초기 자산</label><input type="number" min="0" max="100000000" step="10000" value={basics.initial_asset} onChange={(event) => setBasics((prev) => ({ ...prev, initial_asset: event.target.value }))} required /></div>
          <div><label className="field-label">기간 (개월)</label><input type="number" min="1" max="600" value={basics.months} onChange={(event) => setBasics((prev) => ({ ...prev, months: event.target.value }))} required /></div>
          <div><label className="field-label">월 정기 수입</label><input type="number" min="0" max="10000000" step="10000" value={basics.monthly_income} onChange={(event) => setBasics((prev) => ({ ...prev, monthly_income: event.target.value }))} required /></div>
          <div><label className="field-label">월 예상 지출</label><input type="number" min="0" max="10000000" step="10000" value={basics.monthly_expense} onChange={(event) => setBasics((prev) => ({ ...prev, monthly_expense: event.target.value }))} required /></div>
        </div>

        <AllocationField
          title="초기 자산 배분"
          hint="6개 항목의 합계가 초기 자산과 같아야 합니다."
          rows={FREE_ALLOC_ROWS}
          values={initAlloc}
          target={Number(basics.initial_asset || 0)}
          onChange={(key, value) => setInitAlloc((prev) => ({ ...prev, [key]: value }))}
        />

        <AllocationField
          title="월 잉여자금 배분"
          hint="합계가 월 수입에서 지출을 뺀 금액과 같아야 합니다."
          rows={FREE_ALLOC_ROWS}
          values={monthlyAlloc}
          target={surplus}
          onChange={(key, value) => setMonthlyAlloc((prev) => ({ ...prev, [key]: value }))}
        />

        <ReturnsField values={returns} onChange={(key, value) => setReturns((prev) => ({ ...prev, [key]: value }))} />

        <div className="compact-fields">
          <div><label className="field-label">현재 환율 (원/달러)</label><input type="number" min="1" max="10000" value={fx.initial} onChange={(event) => setFx((prev) => ({ ...prev, initial: event.target.value }))} required /></div>
          <div><label className="field-label">미래 환율 (원/달러)</label><input type="number" min="1" max="10000" value={fx.future} onChange={(event) => setFx((prev) => ({ ...prev, future: event.target.value }))} required /></div>
        </div>

        <Notice type="error">{error}</Notice>
        <button type="submit" className="service-primary-button" disabled={submitting}>시뮬레이션 실행</button>
      </form>

      {result && <ResultView result={result} />}
    </>
  )
}

function SimulationPage() {
  const [tab, setTab] = useState('GOAL')

  return (
    <PageShell
      eyebrow="내 재테크"
      title="미래 자산 시뮬레이션"
      description="현재 또는 가상의 재무 상황을 기준으로 앞으로 자산이 어떻게 변할지 계산합니다. 실제 계좌·거래에는 영향을 주지 않습니다."
    >
      {MOCKS_ENABLED && (
        <div className="mock-banner">
          목(mock) 데이터 표시 중 · 결과 계산도 목이며 실제 projection_service 계산과 다를 수 있습니다.
        </div>
      )}

      <div className="tab-bar">
        <button className={tab === 'GOAL' ? 'active' : ''} onClick={() => setTab('GOAL')}>목표 달성 시뮬레이션</button>
        <button className={tab === 'FREE' ? 'active' : ''} onClick={() => setTab('FREE')}>자유 재테크 시뮬레이션</button>
      </div>

      {tab === 'GOAL' ? <GoalSimForm /> : <FreeSimForm />}
    </PageShell>
  )
}

export default SimulationPage
