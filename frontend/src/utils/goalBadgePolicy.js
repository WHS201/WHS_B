const DAY_MS = 24 * 60 * 60 * 1000
export const MINIMUM_GOAL_DAYS = 7

export const koreanToday = (now = new Date()) => new Date(now.getTime() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10)
export const addCalendarDays = (day, days) => new Date(Date.parse(`${day}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10)
export const minimumBadgeTarget = (assets) => Math.ceil(Number(assets) * 105 / 100)
export const GOAL_BADGE_WAIT_NOTICE = '목표 생성 후 최소 7일(168시간)이 지난 뒤 실제 목표금액에 도달해야 뱃지 실적으로 인정됩니다. 그 전에 달성한 목표는 완료로 유지되지만, 나중에 7일이 지나도 뱃지 실적에는 포함되지 않습니다.'

export function completedAfterBadgeWait(goal) {
  if (!goal.created_at || !goal.completed_at) return false
  const utcTime = (value) => Date.parse(/Z$|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`)
  return utcTime(goal.completed_at) - utcTime(goal.created_at) >= MINIMUM_GOAL_DAYS * DAY_MS
}

export function formBadgeCriteria(currentAssets, goal = null, today = koreanToday()) {
  if (goal?.badge_criteria?.baseline_known) return goal.badge_criteria
  return {
    baseline_known: goal === null,
    assets_at_creation: Number(currentAssets),
    created_on: today,
    minimum_target_amount: minimumBadgeTarget(currentAssets),
    minimum_period_days: MINIMUM_GOAL_DAYS,
  }
}

export function goalBadgeMessage({ criteria, targetAmount, targetDate, currentAssets, editing = false, today = koreanToday() }) {
  if (!criteria.baseline_known) {
    return '이 목표는 생성 당시 총자산 기록이 없어 목표 달성 뱃지 대상에서 제외됩니다. 목표 수정과 달성은 가능하며, 뱃지를 받으려면 새 목표를 만들어 주세요.'
  }
  if (Number(criteria.assets_at_creation) === 0) {
    return editing
      ? '생성 당시 총자산이 0원이므로 이 목표는 수정하거나 달성할 수 있지만 목표 달성 뱃지 실적에는 포함되지 않습니다.'
      : '현재 총자산이 0원이므로 이 목표는 생성할 수 있지만 목표 달성 뱃지 실적에는 포함되지 않습니다.'
  }
  if (targetAmount === '' || !targetDate) return ''
  const amount = Number(targetAmount)
  if (!Number.isFinite(amount) || !Number.isInteger(amount) || amount < 1 || amount > 1000000000) return ''
  if (amount <= Number(currentAssets)) return '목표 금액은 현재 총자산보다 커야 합니다.'
  const end = Date.parse(`${targetDate}T00:00:00Z`)
  if (!Number.isFinite(end) || new Date(end).toISOString().slice(0, 10) !== targetDate) return ''
  if (targetDate <= today) return '목표일은 오늘 이후로 설정해 주세요.'
  const period = (end - Date.parse(`${criteria.created_on}T00:00:00Z`)) / DAY_MS
  const missing = []
  if (amount < criteria.minimum_target_amount) {
    missing.push(`목표금액을 최소 ${criteria.minimum_target_amount.toLocaleString('ko-KR')}원 이상`)
  }
  if (period < criteria.minimum_period_days) missing.push(`목표기간을 ${criteria.minimum_period_days}일 이상`)
  if (!missing.length) return '뱃지 금액·목표기간 조건을 만족합니다. 목표 생성 후 최소 7일(168시간)이 지난 뒤 실제 총자산이 목표금액 이상에 도달해야 뱃지 실적에 반영됩니다.'
  return `목표는 ${editing ? '수정' : '생성'}할 수 있지만, 목표 달성 뱃지를 받으려면 ${missing.join(', ')}으로 설정해야 합니다.`
}
