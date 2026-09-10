import test from 'node:test'
import assert from 'node:assert/strict'
import { auditValue, goalPercent, label, ledgerLabel, ledgerNet, memberLabel } from '../src/utils/presentation.js'
import { savePostWithImages, validatePostImages } from '../src/utils/postImages.js'

test('goal display caps all values and retains completed progress after losses', () => {
  for (const [value, expected] of [[999988.7, 100], [1090025.4, 100], [-5, 0], [50.25, 50.25], [null, 0], ['bad', 0]]) {
    assert.equal(goalPercent({ progress_percent: value, status: 'ACTIVE' }), expected)
  }
  assert.equal(goalPercent({ progress_percent: 2, status: 'COMPLETED' }), 100)
})

test('ledger selection labels the actual ID, type, signed amount and time', () => {
  const row = { ledger_transaction_id: 327, transaction_type: 'SAVING_PAYMENT', created_at: '2026-09-01T00:05:00Z', entries: [{ entry_type: 'DEBIT', amount: 300000 }] }
  assert.equal(ledgerNet(row), -300000)
  assert.match(ledgerLabel(row), /거래 #327 · 적금 납입 · -300,000원/)
  assert.match(ledgerLabel(row), /2026-09-01 09:05/)
  assert.equal(label('ADMIN_ADJUSTMENT'), '관리자 잔액 조정')
})

test('admin labels keep zero and false values meaningful', () => {
  assert.equal(auditValue({ balance: 0, status: 'ACTIVE', is_initial_asset_set: false }), '잔액: 0\n상태: 이용 중\n초기 자산 설정 완료: 아니요')
  assert.equal(memberLabel({ user_id: 5, nickname: '회원이름', username: 'login5' }, 5), '회원이름 (login5) · #5')
  assert.notEqual(label('ADMIN_USER_STATUS'), label('UPDATE'))
  assert.equal(auditValue(null), '기록 없음')
})

const image = (overrides = {}) => ({ name: 'sample.png', type: 'image/png', size: 10, ...overrides })
test('image validation applies the combined existing and pending limit', () => {
  assert.equal(validatePostImages([image()], 4), '')
  assert.match(validatePostImages([image(), image()], 4), /최대 5장/)
  assert.match(validatePostImages([image({ size: 10 * 1024 * 1024 + 1 })]), /10MB/)
  assert.match(validatePostImages([image({ type: 'image/svg+xml' })]), /PNG, JPG, WEBP/)
})

test('retry after image upload failure updates the saved post without duplicating it', async () => {
  let savedId = null
  const calls = []
  let failed = false
  const api = {
    createPost: async () => { calls.push('create'); return { data: { post_id: 51 } } },
    updatePost: async (id) => { calls.push(`update:${id}`); return { data: { post_id: id } } },
    uploadPostImages: async (id) => { calls.push(`upload:${id}`); if (!failed) { failed = true; throw new Error('upload failed') } },
  }
  const options = { payload: { title: '글', content: '내용' }, files: [image()], onSaved: (id) => { savedId = id } }
  await assert.rejects(savePostWithImages(options, api), (error) => error.postSaved === true)
  assert.equal(savedId, 51)
  assert.equal(await savePostWithImages({ ...options, postId: savedId }, api), 51)
  assert.deepEqual(calls, ['create', 'upload:51', 'update:51', 'upload:51'])
})

test('a failed post save does not attempt uploading or mark the post as saved', async () => {
  let saved = false
  await assert.rejects(savePostWithImages({ payload: {}, files: [image()], onSaved: () => { saved = true } }, {
    createPost: async () => { throw new Error('save failed') },
    uploadPostImages: async () => assert.fail('upload must not run'),
  }), /save failed/)
  assert.equal(saved, false)
})
