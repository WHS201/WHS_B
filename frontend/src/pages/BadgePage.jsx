import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageShell from '../components/PageShell'
import { Empty, Loading, Notice } from '../components/Ui'
import { shortDate } from '../utils/format'
import { MOCKS_ENABLED, getApiError, getBadgeCatalog, getMyBadges } from '../api/features'
import { GOAL_BADGE_WAIT_NOTICE } from '../utils/goalBadgePolicy'

const BADGE_ICON = { GOAL: '🎯', SAVING: '🐖', INVESTMENT: '📈' }
const TYPE_LABEL = { GOAL: '목표', SAVING: '적금', INVESTMENT: '투자' }

function BadgePage() {
  const [catalog, setCatalog] = useState([])
  const [mine, setMine] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    Promise.all([getBadgeCatalog(), getMyBadges()])
      .then(([catalogRes, mineRes]) => {
        if (!active) return
        setCatalog(catalogRes.data)
        setMine(mineRes.data)
        setLoading(false)
      })
      .catch((loadError) => {
        if (!active) return
        setError(getApiError(loadError))
        setLoading(false)
      })

    return () => { active = false }
  }, [])

  const acquiredById = {}
  mine.forEach((badge) => { acquiredById[badge.badge_id] = badge })
  const acquiredCount = catalog.filter((badge) => acquiredById[badge.badge_id]).length
  const percent = catalog.length ? Math.round((acquiredCount / catalog.length) * 100) : 0

  return (
    <PageShell
      eyebrow="내 재테크"
      title="뱃지"
      description="금융 활동과 목표 달성 결과에 따라 뱃지를 획득합니다. 대표 뱃지는 프로필에서 설정할 수 있습니다."
    >
      {MOCKS_ENABLED && (
        <div className="mock-banner">
          목(mock) 데이터 표시 중 · 백엔드 연결 시 <code>VITE_USE_MOCKS=false</code> 로 전환
        </div>
      )}

      <Notice type="error">{error}</Notice>
      <Notice type="info">
        생성 당시 총자산이 0원보다 크고, 그 자산의 105% 이상인 목표금액과 7일 이상의 목표기간을 모두 만족해야 합니다.
        {GOAL_BADGE_WAIT_NOTICE}
        인정되는 목표가 1개·3개일 때 각각 지급됩니다. 생성 당시 자산이 0원이거나 기록이 없는 목표는 제외되며, 이미 획득한 뱃지는 유지됩니다.
      </Notice>

      {loading ? <Loading /> : catalog.length === 0 ? <Empty>등록된 뱃지가 없습니다.</Empty> : (
        <>
          <section className="service-card">
            <div className="goal-row-head" style={{ marginBottom: 12 }}>
              <strong>획득 {acquiredCount} / 전체 {catalog.length}</strong>
              <Link to="/profile" className="detail-link">대표 뱃지 설정</Link>
            </div>
            <div className="goal-progress-track">
              <div className="goal-progress-fill" style={{ width: `${percent}%` }} />
            </div>
          </section>

          <div className="badge-grid">
            {catalog.map((badge) => {
              const owned = acquiredById[badge.badge_id]
              return (
                <div key={badge.badge_id} className={`badge-tile${owned ? '' : ' locked'}`}>
                  <div className="badge-tile-icon">{owned ? (BADGE_ICON[badge.badge_type] || '🏅') : '🔒'}</div>
                  <h3>{badge.name}</h3>
                  <span className="board-chip">{TYPE_LABEL[badge.badge_type] || badge.badge_type}</span>
                  <p>{badge.description}</p>
                  <span className={`badge-status ${owned ? 'on' : 'off'}`}>
                    {owned ? `획득 · ${shortDate(owned.acquired_at)}` : '미획득'}
                  </span>
                </div>
              )
            })}
          </div>
        </>
      )}
    </PageShell>
  )
}

export default BadgePage
