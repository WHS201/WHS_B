import { Empty } from './Ui'
import { won } from '../utils/format'

// 서버 valuation() 의 amounts / allocation_percent 키와 일치
const ASSET_META = [
  ['cash', '현금', '#64748b'],
  ['deposit', '예금', '#0ea5e9'],
  ['saving', '적금', '#14b8a6'],
  ['kr_stock', '국내주식', '#6366f1'],
  ['us_stock', '미국주식', '#8b5cf6'],
  ['kr_etf', '국내 ETF', '#f59e0b'],
  ['us_etf', '미국 ETF', '#ef4444'],
]

function AssetAllocationBar({ allocation = {}, amounts = {}, showAmounts = true }) {
  const rows = ASSET_META
    .map(([key, label, color]) => ({
      key,
      label,
      color,
      percent: Number(allocation[key] || 0),
      amount: Number(amounts[key] || 0),
    }))
    .filter((row) => row.percent > 0 || row.amount > 0)

  if (rows.length === 0) return <Empty>보유 중인 자산이 없습니다.</Empty>

  return (
    <div>
      <div className="alloc-bar">
        {rows.map((row) => (
          <span
            key={row.key}
            className="alloc-seg"
            style={{ width: `${row.percent}%`, background: row.color }}
            title={`${row.label} ${row.percent.toFixed(1)}%`}
          />
        ))}
      </div>

      <ul className="alloc-legend">
        {rows.map((row) => (
          <li key={row.key}>
            <span className="alloc-dot" style={{ background: row.color }} />
            <span className="alloc-legend-label">{row.label}</span>
            <strong>{row.percent.toFixed(1)}%</strong>
            {showAmounts && <span className="alloc-legend-amount">{won(row.amount)}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default AssetAllocationBar
