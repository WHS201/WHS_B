import { useEffect, useId, useState } from 'react'
import { getApiError, getDashboardHistory } from '../api/features'
import { Empty, Loading, Notice } from './Ui'
import { won } from '../utils/format'

const PAGE_SIZE = 30
const axisAmount = new Intl.NumberFormat('ko-KR', {
  notation: 'compact',
  maximumFractionDigits: 2,
})
const buttonStyle = {
  padding: '8px 12px',
  border: '1px solid #ccd8df',
  borderRadius: 7,
  color: '#40525f',
  background: '#fff',
}

// 서버 응답의 날짜와 총자산을 확인하고 오래된 날짜부터 정렬합니다.
function readHistory(result) {
  const data = result?.data
  if (!Array.isArray(data?.items) || !Number.isInteger(data.total) || data.total < 0) {
    throw new Error('자산 기록을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')
  }

  const items = data.items.map((item) => {
    const date = item.snapshot_date
    const timestamp = typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)
      ? Date.parse(`${date}T00:00:00Z`)
      : NaN
    const amount = item.total_assets

    if (!Number.isFinite(timestamp) || !Number.isFinite(amount)
      || new Date(timestamp).toISOString().slice(0, 10) !== date) {
      throw new Error('자산 기록을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.')
    }

    return { date, timestamp, amount }
  }).sort((a, b) => a.timestamp - b.timestamp)

  return { items, total: data.total }
}

function HistoryPlot({ items }) {
  const titleId = useId()
  const first = items[0]
  const last = items[items.length - 1]
  const change = last.amount - first.amount
  const width = 760
  const height = 270
  const left = 86
  const right = 24
  const top = 28
  const bottom = 40
  const plotWidth = width - left - right
  const plotHeight = height - top - bottom
  const minimum = Math.min(...items.map((item) => item.amount))
  const maximum = Math.max(...items.map((item) => item.amount))
  const padding = Math.max((maximum - minimum) * 0.15, Math.abs(maximum) * 0.01, 1)
  const yMin = minimum >= 0 ? Math.max(0, minimum - padding) : minimum - padding
  const yMax = maximum + padding
  const timeSpan = last.timestamp - first.timestamp
  const points = items.map((item) => ({
    ...item,
    x: timeSpan ? left + (item.timestamp - first.timestamp) / timeSpan * plotWidth : left + plotWidth / 2,
    y: top + (yMax - item.amount) / (yMax - yMin) * plotHeight,
  }))
  const dateIndexes = [...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])]

  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px 28px', marginBottom: 16 }}>
        <div>
          <span style={{ display: 'block', color: '#657984', fontSize: 12 }}>구간 마지막 총자산</span>
          <strong style={{ fontSize: 21, color: '#173b54' }}>{won(last.amount)}</strong>
        </div>
        {items.length > 1 && (
          <div>
            <span style={{ display: 'block', color: '#657984', fontSize: 12 }}>기록 구간 변화</span>
            <strong className={change >= 0 ? 'profit-up' : 'profit-down'} style={{ fontSize: 21 }}>
              {change >= 0 ? '+' : ''}{won(change)}
            </strong>
          </div>
        )}
      </div>
      <p style={{ margin: '0 0 8px', fontSize: 13, color: '#657984' }}>
        {first.date} ~ {last.date} · {items.length}개 기록
      </p>

      <div style={{ overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-labelledby={titleId}
          style={{ display: 'block', width: '100%', minWidth: 560, height: 'auto' }}
        >
          <title id={titleId}>
            {`${first.date}부터 ${last.date}까지의 일별 총자산 변화. 날짜별 정확한 금액은 아래 표에서 확인할 수 있습니다.`}
          </title>
          <text x={left - 10} y={14} textAnchor="end" fill="#657984" fontSize="12">단위: 원</text>
          {Array.from({ length: 5 }, (_, index) => {
            const value = yMin + (yMax - yMin) * index / 4
            const y = top + plotHeight - plotHeight * index / 4
            return (
              <g key={index}>
                <line x1={left} x2={width - right} y1={y} y2={y} stroke="#e7edf1" />
                <text x={left - 10} y={y + 4} textAnchor="end" fill="#657984" fontSize="12">
                  {axisAmount.format(value)}
                </text>
              </g>
            )
          })}
          {points.length > 1 && (
            <polyline
              points={points.map((point) => `${point.x},${point.y}`).join(' ')}
              fill="none"
              stroke="#1a5f8f"
              strokeWidth="3"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}
          {points.map((point) => (
            <circle key={point.date} cx={point.x} cy={point.y} r={points.length === 1 ? 5 : 3.5} fill="#1a5f8f">
              <title>{`${point.date}: ${won(point.amount)}`}</title>
            </circle>
          ))}
          {dateIndexes.map((index) => (
            <text key={index} x={points[index].x} y={height - 12} textAnchor="middle" fill="#657984" fontSize="12">
              {points[index].date.slice(5).replace('-', '/')}
            </text>
          ))}
        </svg>
      </div>

      {items.length === 1 && (
        <p style={{ fontSize: 13, color: '#657984' }}>
          아직 기록이 1개라 점으로 표시됩니다. 기록이 더 쌓이면 선 그래프가 표시됩니다.
        </p>
      )}
      <p style={{ fontSize: 12, color: '#657984' }}>
        기록이 있는 날짜만 표시하며, 수입·지출과 투자 평가금액 변화가 함께 반영됩니다.
      </p>

      <details>
        <summary style={{ cursor: 'pointer', color: '#1a5f8f', fontSize: 13 }}>날짜별 금액 보기</summary>
        <div style={{ maxHeight: 260, overflow: 'auto', marginTop: 8 }}>
          <table className="mini-table">
            <thead><tr><th scope="col">기록일</th><th scope="col">총자산</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.date}><td>{item.date}</td><td>{won(item.amount)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}

function AssetHistoryChart() {
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [history, setHistory] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // 대시보드 본문과 별도로 조회하여 그래프 오류가 다른 정보를 가리지 않도록 합니다.
  useEffect(() => {
    let ignore = false
    setLoading(true)
    setError('')

    getDashboardHistory({ page, size: PAGE_SIZE })
      .then((result) => {
        if (ignore) return
        setHistory(readHistory(result))
      })
      .catch((loadError) => {
        if (ignore) return
        setError(getApiError(loadError))
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })

    return () => { ignore = true }
  }, [page, reload])

  const pageCount = Math.max(1, Math.ceil(history.total / PAGE_SIZE))

  return (
    <section className="dash-section" aria-label="일별 자산 변화" aria-busy={loading}>
      <h2>일별 자산 변화</h2>
      <p style={{ margin: '-6px 0 18px', fontSize: 13, color: '#657984' }}>
        하루 한 번 저장된 총자산을 최근 기록부터 30개씩 확인합니다.
      </p>

      {loading ? <Loading /> : error ? (
        <div>
          <Notice type="error">{error}</Notice>
          <button type="button" style={buttonStyle} onClick={() => setReload((value) => value + 1)}>다시 불러오기</button>
        </div>
      ) : history.items.length === 0 ? (
        <Empty>아직 저장된 자산 기록이 없습니다. 일별 기록이 쌓이면 그래프가 표시됩니다.</Empty>
      ) : <HistoryPlot items={history.items} />}

      {(history.total > PAGE_SIZE || page > 1) && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12, marginTop: 18 }}>
          <button type="button" style={buttonStyle} disabled={loading || page <= 1} onClick={() => setPage((value) => value - 1)}>
            더 최근 기록
          </button>
          <span style={{ color: '#657984', fontSize: 13 }}>{page} / {Math.max(page, pageCount)}</span>
          <button type="button" style={buttonStyle} disabled={loading || Boolean(error) || page >= pageCount} onClick={() => setPage((value) => value + 1)}>
            더 오래된 기록
          </button>
        </div>
      )}
    </section>
  )
}

export default AssetHistoryChart
