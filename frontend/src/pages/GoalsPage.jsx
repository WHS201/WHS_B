import { goalPercent } from '../utils/presentation'
import { useEffect, useState } from 'react'
import PageShell from '../components/PageShell'
import { confirmAction, showToast } from '../components/Toast'
import { Empty, Loading, Notice } from '../components/Ui'
import { shortDate, won } from '../utils/format'
import { MOCKS_ENABLED, createGoal, deleteGoal, getApiError, getDashboard, updateGoal } from '../api/features'
import { addCalendarDays, formBadgeCriteria, goalBadgeMessage, GOAL_BADGE_WAIT_NOTICE, koreanToday } from '../utils/goalBadgePolicy'

const MAX_GOALS = 5
const emptyForm = { goal_name: '', target_amount: '', target_date: '' }

function GoalsPage() {
  const [goals, setGoals] = useState([])
  const [currentAssets, setCurrentAssets] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try {
      const result = await getDashboard()
      setGoals(result.data.goals)
      setCurrentAssets(result.data.total_assets)
      setError('')
    } catch (loadError) {
      setError(getApiError(loadError))
    }
  }

  useEffect(() => {
    let ignore = false

    getDashboard()
      .then((result) => {
        if (ignore) return
        setGoals(result.data.goals)
        setCurrentAssets(result.data.total_assets)
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

  const atLimit = goals.length >= MAX_GOALS && editingId === null
  const today = koreanToday()
  const editingGoal = editingId === null ? null : goals.find((goal) => goal.goal_id === editingId)
  const criteria = formBadgeCriteria(currentAssets, editingGoal, today)
  const badgeMessage = goalBadgeMessage({
    criteria, targetAmount: form.target_amount, targetDate: form.target_date,
    currentAssets, editing: editingId !== null, today,
  })

  const startCreate = () => {
    setEditingId(null)
    setForm(emptyForm)
    setFormError('')
  }

  const startEdit = (goal) => {
    setEditingId(goal.goal_id)
    setForm({
      goal_name: goal.goal_name,
      target_amount: String(goal.target_amount),
      target_date: shortDate(goal.target_date),
    })
    setFormError('')
  }

  const change = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setFormError('')

    const payload = {
      goal_name: form.goal_name.trim(),
      target_amount: Number(form.target_amount),
      target_date: form.target_date,
    }

    try {
      if (editingId === null) {
        await createGoal(payload)
        showToast('저축 목표를 만들었습니다.')
      } else {
        await updateGoal(editingId, payload)
        showToast('저축 목표를 수정했습니다.')
      }
      startCreate()
      await load()
    } catch (submitError) {
      setFormError(getApiError(submitError))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (goal) => {
    if (!await confirmAction(`'${goal.goal_name}' 목표를 삭제할까요?`)) return
    setError('')
    try {
      await deleteGoal(goal.goal_id)
      showToast('저축 목표를 삭제했습니다.')
      if (editingId === goal.goal_id) startCreate()
      await load()
    } catch (removeError) {
      setError(getApiError(removeError))
    }
  }

  return (
    <PageShell
      eyebrow="내 재테크"
      title="저축 목표"
      description="목표는 최대 5개까지 만들 수 있습니다. 달성률은 계좌·예적금·주식을 합한 전체 자산 기준입니다."
    >
      {MOCKS_ENABLED && (
        <div className="mock-banner">
          목(mock) 데이터 표시 중 · 백엔드 연결 시 <code>VITE_USE_MOCKS=false</code> 로 전환
        </div>
      )}

      <Notice type="error">{error}</Notice>

      {loading ? <Loading /> : (
        <>
          {goals.length === 0 ? <Empty>아직 만든 저축 목표가 없습니다.</Empty> : (
            <div className="goal-list">
              {goals.map((goal) => {
                const percent = goalPercent(goal)
                const done = goal.status === 'COMPLETED'
                return (
                  <div key={goal.goal_id} className={`goal-card${done ? ' is-done' : ''}`}>
                    <div className="goal-card-top">
                      <h3>{goal.goal_name}</h3>
                      <span className={`goal-state ${done ? 'done' : 'active'}`}>{done ? '달성' : '진행 중'}</span>
                    </div>

                    <div className="goal-progress-track">
                      <div
                        className={`goal-progress-fill${done ? ' is-done' : ''}`}
                        style={{ width: `${Math.min(percent, 100)}%` }}
                      />
                    </div>

                    <div className="goal-card-figures">
                      <span>달성률 <strong>{percent.toFixed(1)}%</strong></span>
                      <span>목표 <strong>{won(goal.target_amount)}</strong></span>
                    </div>
                    <div className="goal-card-figures">
                      <span>목표일 {shortDate(goal.target_date)}</span>
                      {goal.completed_at && <span>달성일 {shortDate(goal.completed_at)}</span>}
                    </div>

                    <Notice type="info">{goal.requires_target_update ? "초기 자산 설정 전에 만든 목표입니다. 현재 총자산보다 큰 금액으로 수정해 주세요." : ""}</Notice>
                    {done && goal.badge_criteria && (
                      <Notice type="info">{goal.badge_criteria.eligible
                        ? '목표 달성 뱃지 인정 조건을 충족한 실적입니다.'
                        : '목표는 완료되었지만 목표 달성 뱃지 인정 조건을 충족하지 않아 실적에 포함되지 않습니다. 이미 받은 뱃지는 유지됩니다.'}</Notice>
                    )}
                    <div className="goal-card-actions">
                      {!done && (
                        <button type="button" className="goal-edit-button" onClick={() => startEdit(goal)}>수정</button>
                      )}
                      <button type="button" className="goal-delete-button" onClick={() => remove(goal)}>삭제</button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          <section className="service-card">
            <span className="card-label">{editingId === null ? '새 목표' : '목표 수정'}</span>
            <h2>{editingId === null ? '저축 목표 만들기' : '저축 목표 수정'}</h2>
            <p>초기 자산을 설정한 뒤 목표를 만들 수 있습니다. 목표 금액은 1원 이상 10억 원 이하이며, 현재 총자산보다 커야 합니다. 목표일은 오늘 이후여야 합니다.</p>
            {currentAssets !== null && (
              <div className="notice notice-info">
                <p>현재 총자산: <strong>{won(currentAssets)}</strong></p>
                <p>{editingId !== null && criteria.baseline_known ? '이 목표의' : '새 목표의 현재 기준'} 뱃지 인정 최소 목표금액: <strong>{criteria.assets_at_creation === 0 ? '인정 대상 아님 (생성 당시 총자산 0원)' : won(criteria.minimum_target_amount)}</strong></p>
                <p>뱃지 인정 최소 목표기간: <strong>생성일부터 7일</strong> (목표일 {addCalendarDays(criteria.created_on, criteria.minimum_period_days)} 이후, 해당 날짜 포함)</p>
                <p>{GOAL_BADGE_WAIT_NOTICE}</p>
                <p>{editingId !== null && criteria.baseline_known
                  ? `생성 당시 총자산 ${won(criteria.assets_at_creation)} 및 생성일 ${criteria.created_on}을 기준으로 수정한 금액과 기간을 판단합니다.`
                  : '뱃지는 목표 생성 당시 총자산의 105% 이상인 목표금액을 기준으로 인정합니다.'}</p>
                <p>뱃지 조건을 만족하지 않아도 현재 총자산보다 큰 목표는 만들 수 있습니다. 총자산은 시장가격에 따라 달라질 수 있으며 저장할 때 다시 확인합니다.</p>
              </div>
            )}

            {atLimit ? (
              <Notice type="info">
                저축 목표는 최대 {MAX_GOALS}개까지만 만들 수 있습니다. 기존 목표를 삭제한 뒤 다시 시도하세요.
              </Notice>
            ) : (
              <form onSubmit={submit}>
                <label className="field-label" htmlFor="goal_name">목표명</label>
                <input
                  id="goal_name"
                  type="text"
                  maxLength={50}
                  required
                  value={form.goal_name}
                  onChange={change('goal_name')}
                  placeholder="예: 유럽 여행 자금"
                />

                <label className="field-label" htmlFor="target_amount">목표 금액</label>
                <div className="input-with-unit">
                  <input
                    id="target_amount"
                    type="number"
                    min={currentAssets === null ? 1 : Math.max(1, Number(currentAssets) + 1)}
                    max="1000000000"
                    required
                    value={form.target_amount}
                    onChange={change('target_amount')}
                  />
                  <span>원</span>
                </div>

                <label className="field-label" htmlFor="target_date">목표일</label>
                <input
                  id="target_date"
                  type="date"
                  min={addCalendarDays(today, 1)}
                  required
                  value={form.target_date}
                  onChange={change('target_date')}
                />

                <Notice type="error">{formError}</Notice>
                <div aria-live="polite"><Notice type="info">{currentAssets !== null ? badgeMessage : ''}</Notice></div>

                <div className="button-row goal-form-buttons">
                  <button type="submit" className="service-primary-button" disabled={busy || currentAssets === null}>
                    {editingId === null ? '목표 만들기' : '수정 저장'}
                  </button>
                  {editingId !== null && (
                    <button type="button" className="service-secondary-button" onClick={startCreate} disabled={busy}>
                      취소
                    </button>
                  )}
                </div>
              </form>
            )}
          </section>
        </>
      )}
    </PageShell>
  )
}

export default GoalsPage
