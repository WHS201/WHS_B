export const MAX_POST_IMAGES = 5
export function validatePostImages(files, existingCount = 0) {
  if (files.length + existingCount > MAX_POST_IMAGES) return '이미지는 기존 첨부를 포함해 최대 5장입니다.'
  if (files.some((file) => !['image/png', 'image/jpeg', 'image/webp'].includes(file.type))) {
    return 'PNG, JPG, WEBP 이미지만 첨부할 수 있습니다.'
  }
  if (files.some((file) => file.size > 10 * 1024 * 1024)) return '이미지 한 장은 10MB 이하이어야 합니다.'
  return ''
}

// Keep the created ID before uploading so retrying a failed attachment never
// creates the same post twice. Existing upload/ownership endpoints are reused.
export async function savePostWithImages({ postId, payload, files, onSaved = () => {} }, api) {
  const response = postId ? await api.updatePost(postId, payload) : await api.createPost(payload)
  const savedId = postId || response.data.post_id
  onSaved(savedId)
  if (files.length) {
    try {
      await api.uploadPostImages(savedId, files)
    } catch (error) {
      error.postSaved = true
      throw error
    }
  }
  return savedId
}
