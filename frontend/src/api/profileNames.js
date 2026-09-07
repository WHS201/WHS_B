import { getProfile } from './features'

// 백엔드 post_data() / 댓글 응답에는 작성자 닉네임이 없고 user_id 만 온다.
// GET /profiles/{id} 로 닉네임을 채우고 모듈 단위로 캐시한다.
const cache = new Map()

export async function resolveNicknames(userIds) {
  const pending = [...new Set(userIds.filter((id) => id != null && !cache.has(id)))]

  await Promise.all(pending.map(async (id) => {
    try {
      const res = await getProfile(id)
      cache.set(id, res.data?.nickname || `사용자 #${id}`)
    } catch {
      cache.set(id, `사용자 #${id}`)
    }
  }))

  const map = {}
  userIds.forEach((id) => {
    if (id != null && cache.has(id)) map[id] = cache.get(id)
  })
  return map
}
