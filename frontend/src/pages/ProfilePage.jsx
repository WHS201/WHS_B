import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import PageShell from '../components/PageShell'
import { showToast } from '../components/Toast'
import { Empty, Loading, Notice } from '../components/Ui'
import AssetAllocationBar from '../components/AssetAllocationBar'
import { rate, shortDate, won } from '../utils/format'
import {
  MOCKS_ENABLED, getApiError, getMyProfile, getProfile, updateMyProfile, updateMyVisibility,
} from '../api/features'

const VISIBILITY_FIELDS = [
  ['show_joined_at', '가입일'],
  ['show_badges', '뱃지'],
  ['show_active_goals', '진행 중인 목표'],
  ['show_completed_goals', '달성한 목표'],
  ['show_goal_progress', '목표 달성률(%)'],
  ['show_total_assets', '총자산'],
  ['show_asset_allocation', '자산 구성'],
  ['show_investment_return', '투자 수익률'],
]

function GoalMiniList({ goals }) {
  if (!goals || goals.length === 0) return <Empty>표시할 목표가 없습니다.</Empty>
  return (
    <ul className="contract-mini-list">
      {goals.map((goal) => (
        <li key={goal.goal_id}>
          <span>{goal.goal_name}<br /><span className="mini-sub">목표일 {shortDate(goal.target_date)}</span></span>
          {goal.progress_percent != null && <span className="trade-right">{Number(goal.progress_percent).toFixed(1)}%</span>}
        </li>
      ))}
    </ul>
  )
}

function BadgeChips({ badges, repId }) {
  if (!badges || badges.length === 0) return <Empty>획득한 뱃지가 없습니다.</Empty>
  return (
    <div className="badge-chip-row">
      {badges.map((badge) => (
        <span key={badge.badge_id} className="badge-chip" title={badge.description}>
          🏅 {badge.name}{badge.badge_id === repId ? ' · 대표' : ''}
        </span>
      ))}
    </div>
  )
}

const PUBLIC_BLOCKS = [
  { flag: 'show_total_assets', title: '총자산', has: (p) => p.total_assets !== undefined, render: (p) => <p className="preview-value">{won(p.total_assets)}</p> },
  { flag: 'show_asset_allocation', title: '자산 구성', has: (p) => Boolean(p.allocation_percent), render: (p) => <AssetAllocationBar allocation={p.allocation_percent} showAmounts={false} /> },
  { flag: 'show_investment_return', title: '투자 수익률', has: (p) => p.investment_return_percent !== undefined, render: (p) => <p className="preview-value">{p.investment_return_percent == null ? '-' : rate(p.investment_return_percent)}</p> },
  { flag: 'show_active_goals', title: '진행 중인 목표', has: (p) => Boolean(p.active_goals), render: (p) => <GoalMiniList goals={p.active_goals} /> },
  { flag: 'show_completed_goals', title: '달성한 목표', has: (p) => Boolean(p.completed_goals), render: (p) => <GoalMiniList goals={p.completed_goals} /> },
  { flag: 'show_badges', title: '뱃지', has: (p) => Boolean(p.badges), render: (p) => <BadgeChips badges={p.badges} repId={p.representative_badge_id} /> },
]

function ProfilePage() {
  const { userId } = useParams()
  const viewingOther = userId !== undefined

  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [nickname, setNickname] = useState('')
  const [repBadge, setRepBadge] = useState('')
  const [visForm, setVisForm] = useState({})
  const [infoError, setInfoError] = useState('')
  const [savingInfo, setSavingInfo] = useState(false)
  const [savingVis, setSavingVis] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    const request = viewingOther ? getProfile(userId) : getMyProfile()
    request
      .then((res) => {
        if (!active) return
        setProfile(res.data)
        if (!viewingOther) {
          setNickname(res.data.nickname || '')
          setRepBadge(res.data.representative_badge_id ? String(res.data.representative_badge_id) : '')
          setVisForm(res.data.visibility || {})
        }
        setLoading(false)
      })
      .catch((loadError) => {
        if (!active) return
        setError(getApiError(loadError))
        setLoading(false)
      })

    return () => { active = false }
  }, [userId, viewingOther])

  const saveInfo = async (event) => {
    event.preventDefault()
    setSavingInfo(true)
    setInfoError('')
    try {
      await updateMyProfile({
        nickname: nickname.trim(),
        representative_badge_id: repBadge ? Number(repBadge) : null,
      })
      // PATCH /profiles/me 응답은 {user_id, nickname, representative_badge_id} 뿐이므로
      // 미리보기에 필요한 전체 프로필을 다시 불러온다.
      const fresh = await getMyProfile()
      setProfile(fresh.data)
      setNickname(fresh.data.nickname || '')
      setRepBadge(fresh.data.representative_badge_id ? String(fresh.data.representative_badge_id) : '')
      setVisForm(fresh.data.visibility || {})
      showToast('프로필을 저장했습니다.')
    } catch (saveError) {
      setInfoError(getApiError(saveError))
    } finally {
      setSavingInfo(false)
    }
  }

  const saveVisibility = async () => {
    setSavingVis(true)
    setError('')
    try {
      const res = await updateMyVisibility(visForm)
      setVisForm(res.data)
      setProfile((prev) => ({ ...prev, visibility: res.data }))
      showToast('공개 설정을 저장했습니다.')
    } catch (saveError) {
      setError(getApiError(saveError))
    } finally {
      setSavingVis(false)
    }
  }

  const toggleVis = (key) => setVisForm((prev) => ({ ...prev, [key]: !prev[key] }))

  return (
    <PageShell
      eyebrow="커뮤니티"
      title={viewingOther ? '사용자 프로필' : '내 프로필'}
      description={viewingOther
        ? '다른 사용자가 공개한 정보만 표시됩니다.'
        : '닉네임과 대표 뱃지를 설정하고, 다른 사용자에게 보여줄 항목을 선택하세요.'}
    >
      {MOCKS_ENABLED && (
        <div className="mock-banner">
          목(mock) 데이터 표시 중 · 백엔드 연결 시 <code>VITE_USE_MOCKS=false</code> 로 전환
        </div>
      )}

      <Notice type="error">{error}</Notice>

      {loading ? <Loading /> : !profile ? <Empty /> : (
        <>
          <div className="profile-head">
            <span className="profile-avatar">🙂</span>
            <div>
              <h2>{profile.nickname}</h2>
              <p>
                {profile.created_at ? `가입일 ${shortDate(profile.created_at)}` : '가입일 비공개'}
                {profile.badges && profile.representative_badge_id
                  ? ` · 대표 뱃지 ${profile.badges.find((badge) => badge.badge_id === profile.representative_badge_id)?.name || '-'}`
                  : ''}
              </p>
            </div>
          </div>

          {!viewingOther && (
            <>
              <form className="service-card" onSubmit={saveInfo}>
                <span className="card-label">기본 정보</span>
                <label className="field-label" htmlFor="nickname">닉네임</label>
                <input
                  id="nickname"
                  type="text"
                  minLength={2}
                  maxLength={20}
                  required
                  value={nickname}
                  onChange={(event) => setNickname(event.target.value)}
                />

                <label className="field-label" htmlFor="rep_badge">대표 뱃지</label>
                <select id="rep_badge" value={repBadge} onChange={(event) => setRepBadge(event.target.value)}>
                  <option value="">선택 안 함</option>
                  {(profile.badges || []).map((badge) => (
                    <option key={badge.badge_id} value={badge.badge_id}>{badge.name}</option>
                  ))}
                </select>

                <Notice type="error">{infoError}</Notice>
                <button type="submit" className="service-primary-button" disabled={savingInfo}>기본 정보 저장</button>
              </form>

              <section className="service-card">
                <span className="card-label">공개 설정</span>
                <h2>다른 사용자에게 보여줄 항목</h2>
                <p>체크한 항목만 다른 사용자의 프로필 화면에 표시됩니다.</p>
                <div className="visibility-grid">
                  {VISIBILITY_FIELDS.map(([key, label]) => (
                    <label key={key}>
                      <input type="checkbox" checked={Boolean(visForm[key])} onChange={() => toggleVis(key)} />
                      {label}
                    </label>
                  ))}
                </div>
                <button type="button" className="service-primary-button" onClick={saveVisibility} disabled={savingVis}>
                  공개 설정 저장
                </button>
              </section>
            </>
          )}

          <section className="service-card">
            <span className="card-label">{viewingOther ? '공개된 정보' : '미리보기'}</span>
            <h2>{viewingOther ? `${profile.nickname} 님의 프로필` : '다른 사용자에게 보이는 내 정보'}</h2>
            {!viewingOther && <p>공개로 설정한 항목은 초록색, 비공개는 회색으로 표시됩니다.</p>}

            {PUBLIC_BLOCKS.map((block) => {
              if (viewingOther && !block.has(profile)) return null
              const visible = viewingOther ? true : Boolean(visForm[block.flag])
              return (
                <div key={block.flag} className="preview-item">
                  <div className="preview-head">
                    <strong>{block.title}</strong>
                    {!viewingOther && (
                      <span className={`preview-flag ${visible ? 'on' : 'off'}`}>{visible ? '공개' : '비공개'}</span>
                    )}
                  </div>
                  {block.render(profile)}
                </div>
              )
            })}

            {viewingOther && !PUBLIC_BLOCKS.some((block) => block.has(profile)) && (
              <Empty>이 사용자가 공개한 정보가 없습니다.</Empty>
            )}
          </section>
        </>
      )}
    </PageShell>
  )
}

export default ProfilePage
