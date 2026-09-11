import test from 'node:test'
import assert from 'node:assert/strict'
import { addCalendarDays, completedAfterBadgeWait, formBadgeCriteria, goalBadgeMessage, GOAL_BADGE_WAIT_NOTICE, koreanToday, minimumBadgeTarget } from '../src/utils/goalBadgePolicy.js'
import { goalPercent } from '../src/utils/presentation.js'
import mockRequest from '../src/api/mock/featuresMock.js'

const today = '2026-01-01'
const criteria = formBadgeCriteria(10000, null, today)
const message = (targetAmount, targetDate, overrides = {}) => goalBadgeMessage({
  criteria, currentAssets: 10000, targetAmount, targetDate, today, ...overrides,
})

test('badge minimum is an integer ceiling of 105%, including the requested examples', () => {
  for (const [assets, minimum] of [[0, 0], [10000, 10500], [10001, 10502], [14000000, 14700000], [999999999, 1049999999]]) {
    assert.equal(minimumBadgeTarget(assets), minimum)
  }
})

test('a small valid goal warns only about the insufficient amount', () => {
  assert.equal(message('10001', '2026-01-08'), '목표는 생성할 수 있지만, 목표 달성 뱃지를 받으려면 목표금액을 최소 10,500원 이상으로 설정해야 합니다.')
  assert.doesNotMatch(message('10499', '2026-01-08'), /목표기간/)
})

test('six days warns only about duration when the amount is sufficient', () => {
  assert.equal(message('10500', '2026-01-07'), '목표는 생성할 수 있지만, 목표 달성 뱃지를 받으려면 목표기간을 7일 이상으로 설정해야 합니다.')
  assert.doesNotMatch(message('10500', '2026-01-07'), /목표금액/)
})

test('both missing conditions are explained together without rejecting a valid goal', () => {
  assert.equal(message('10001', '2026-01-02'), '목표는 생성할 수 있지만, 목표 달성 뱃지를 받으려면 목표금액을 최소 10,500원 이상, 목표기간을 7일 이상으로 설정해야 합니다.')
})

test('exactly 105% and a seven-day plan still require actual completion after the wait', () => {
  const text = message('10500', '2026-01-08')
  assert.match(text, /금액·목표기간 조건을 만족/)
  assert.match(text, /최소 7일\(168시간\)이 지난 뒤 실제 총자산이 목표금액 이상에 도달해야/)
  assert.doesNotMatch(text, /생성할 수 있지만/)
})

test('the large asset example displays the correct personalized minimum', () => {
  assert.match(message('14000001', '2026-01-08', {
    currentAssets: 14000000, criteria: formBadgeCriteria(14000000, null, today),
  }), /최소 14,700,000원 이상/)
})

test('invalid goals never promise that they can be created', () => {
  for (const amount of ['9999', '10000']) {
    assert.equal(message(amount, '2026-01-08'), '목표 금액은 현재 총자산보다 커야 합니다.')
  }
  assert.equal(message('10500', '2026-01-01'), '목표일은 오늘 이후로 설정해 주세요.')
  for (const amount of ['', 'bad', 'Infinity', '-1', '1.5', '1000000001']) assert.equal(message(amount, '2026-01-08'), '')
  for (const day of ['', 'invalid', '2026-02-31']) assert.equal(message('10500', day), '')
})

test('editing retains the server creation baseline and rechecks the edited terms', () => {
  const goal = { badge_criteria: { ...criteria, eligible: false } }
  const editingCriteria = formBadgeCriteria(5000, goal, '2026-01-03')
  assert.equal(editingCriteria.minimum_target_amount, 10500)
  assert.equal(editingCriteria.created_on, '2026-01-01')
  assert.match(message('10500', '2026-01-08', { criteria: editingCriteria, currentAssets: 5000, editing: true, today: '2026-01-03' }), /금액·목표기간 조건을 만족/)
  assert.match(message('10499', '2026-01-08', { criteria: editingCriteria, currentAssets: 5000, editing: true }), /목표는 수정할 수 있지만/)
  assert.doesNotMatch(message('10499', '2026-01-08', { criteria: editingCriteria, currentAssets: 5000, editing: true }), /목표기간/)
  assert.match(message('10500', '2026-01-07', { criteria: editingCriteria, currentAssets: 5000, editing: true }), /목표기간을 7일 이상/)
})

test('an existing goal without a baseline explains the legacy exception', () => {
  const legacy = formBadgeCriteria(10000, { goal_id: 1 }, today)
  assert.equal(legacy.baseline_known, false)
  assert.equal(legacy.minimum_target_amount, 10500)
  const text = message('10500', '2026-01-08', { criteria: legacy, editing: true })
  assert.match(text, /생성 당시 총자산 기록이 없어/)
  assert.match(text, /목표 수정과 달성은 가능/)
  assert.match(text, /새 목표/)
})

test('Korean midnight and calendar boundaries agree with the backend period', () => {
  assert.equal(koreanToday(new Date('2026-01-01T14:59:59Z')), '2026-01-01')
  assert.equal(koreanToday(new Date('2026-01-01T15:00:00Z')), '2026-01-02')
  for (const [start, end] of [['2026-01-28', '2026-02-04'], ['2026-12-28', '2027-01-04'], ['2028-02-25', '2028-03-03']]) {
    assert.equal(addCalendarDays(start, 7), end)
    assert.match(message('10500', end, { criteria: formBadgeCriteria(10000, null, start), today: start }), /금액·목표기간 조건을 만족/)
  }
})

test('rounded 100% display retains the server ACTIVE state, and completed progress stays capped', () => {
  const goal = { status: 'ACTIVE', progress_percent: 100, completed_at: null }
  assert.equal(goalPercent(goal), 100)
  assert.equal(goal.status, 'ACTIVE')
  assert.equal(goalPercent({ status: 'COMPLETED', progress_percent: 2 }), 100)
  assert.equal(goalPercent({ status: 'ACTIVE', progress_percent: 1000 }), 100)
})

test('mock goal CRUD returns the same policy context used by the real goal form', async () => {
  const dashboard = (await mockRequest('get', '/dashboard')).data
  const assets = dashboard.total_assets
  const deadline = addCalendarDays(koreanToday(), 7)
  const created = (await mockRequest('post', '/goals', { data: {
    goal_name: '작은 목표', target_amount: assets + 1, target_date: deadline,
  } })).data
  assert.equal(created.status, 'ACTIVE')
  assert.equal(created.badge_criteria.eligible, false)
  assert.equal(created.badge_criteria.assets_at_creation, assets)
  const url = `/goals/${created.goal_id}`
  const edited = (await mockRequest('patch', url, { data: { target_amount: minimumBadgeTarget(assets) } })).data
  assert.equal(edited.badge_criteria.eligible, true)
  assert.equal(edited.badge_criteria.created_on, created.badge_criteria.created_on)
  assert.equal(edited.badge_criteria.assets_at_creation, assets)
  await assert.rejects(mockRequest('patch', url, { data: { target_amount: assets } }), (error) => error.response.status === 422)
  const loaded = (await mockRequest('get', '/dashboard')).data.goals.find((goal) => goal.goal_id === created.goal_id)
  assert.deepEqual(loaded.badge_criteria, edited.badge_criteria)
  await mockRequest('delete', url)
})

test('zero assets explain exclusion while allowing creation of a one-won goal', () => {
  const zeroCriteria = formBadgeCriteria(0, null, today)
  assert.equal(message('1', '2026-01-08', { criteria: zeroCriteria, currentAssets: 0 }),
    '현재 총자산이 0원이므로 이 목표는 생성할 수 있지만 목표 달성 뱃지 실적에는 포함되지 않습니다.')
  assert.match(message('', '', { criteria: zeroCriteria, currentAssets: 0 }), /총자산이 0원/)
  assert.doesNotMatch(message('1000000', '2026-01-30', { criteria: zeroCriteria, currentAssets: 0 }), /조건을 만족/)
})

test('editing a zero-baseline goal keeps the exclusion after assets have increased', () => {
  const zeroCriteria = formBadgeCriteria(0, null, today)
  const editingCriteria = formBadgeCriteria(10000, { badge_criteria: { ...zeroCriteria, eligible: false } }, '2026-01-03')
  assert.equal(editingCriteria.assets_at_creation, 0)
  const text = message('20000', '2026-01-30', { criteria: editingCriteria, editing: true })
  assert.match(text, /생성 당시 총자산이 0원/)
  assert.match(text, /수정하거나 달성할 수 있지만/)
  assert.match(text, /실적에는 포함되지 않습니다/)
})

test('a later zero balance does not mislabel a positive creation baseline', () => {
  const editingCriteria = formBadgeCriteria(0, { badge_criteria: criteria }, '2026-01-03')
  const text = message('10500', '2026-01-08', { criteria: editingCriteria, currentAssets: 0, editing: true })
  assert.doesNotMatch(text, /총자산이 0원/)
  assert.match(text, /최소 7일\(168시간\)이 지난 뒤/)
})

test('completion wait uses the saved timestamps at the day-six and exact day-seven boundaries', () => {
  const created_at = '2026-09-11T03:00:00Z'
  for (const [completed_at, expected] of [
    ['2026-09-11T03:00:00Z', false],
    ['2026-09-17T03:00:00Z', false],
    ['2026-09-18T02:59:59Z', false],
    ['2026-09-18T03:00:00Z', true],
    ['2026-09-19T03:00:00Z', true],
    [null, false], ['invalid', false],
  ]) {
    const goal = { created_at, completed_at, status: 'COMPLETED' }
    assert.equal(completedAfterBadgeWait(goal), expected)
    assert.equal(goal.status, 'COMPLETED')
    assert.equal(goalPercent(goal), 100)
  }
})

test('completion wait normalizes KST, UTC, and the database UTC representation', () => {
  const created_at = '2026-09-11T23:59:00+09:00'
  assert.equal(completedAfterBadgeWait({ created_at, completed_at: '2026-09-18T00:00:00+09:00' }), false)
  assert.equal(completedAfterBadgeWait({ created_at, completed_at: '2026-09-18T14:59:00Z' }), true)
  assert.equal(completedAfterBadgeWait({ created_at, completed_at: '2026-09-18T14:59:00' }), true)
})

test('shared screen guidance explains that early completion never becomes credit later', () => {
  assert.match(GOAL_BADGE_WAIT_NOTICE, /최소 7일\(168시간\)이 지난 뒤 실제 목표금액에 도달/)
  assert.match(GOAL_BADGE_WAIT_NOTICE, /완료로 유지/)
  assert.match(GOAL_BADGE_WAIT_NOTICE, /나중에 7일이 지나도 뱃지 실적에는 포함되지 않습니다/)
})
