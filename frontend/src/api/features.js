import api from './client'
import mockRequest, { MOCKS_ENABLED } from './mock/featuresMock'

export { MOCKS_ENABLED }
export { getApiError } from './finance'

// 신규 기능 API (backend.zip 의 routes/features.py 기준으로 경로 확정).
// 백엔드가 아직 Flask 에 등록되지 않아, VITE_USE_MOCKS=true 이면 목 응답을 돌려준다.
async function call(method, url, { params, data } = {}) {
  if (MOCKS_ENABLED) return mockRequest(method, url, { params, data })
  const response = await api.request({ method, url, params, data })
  return response.data
}

// multipart/form-data 업로드 (이미지). axios 인스턴스의 기본 JSON 헤더를 비운다.
async function upload(url, files) {
  if (MOCKS_ENABLED) return mockRequest('post', url, { data: { _files: files.length } })
  const form = new FormData()
  Array.from(files).forEach((file) => form.append('images', file))
  const response = await api.post(url, form, { headers: { 'Content-Type': undefined } })
  return response.data
}

// 대시보드
export const getDashboard = () => call('get', '/dashboard')
export const getDashboardHistory = (params = {}) => call('get', '/dashboard/history', { params })

// 미래 자산 시뮬레이션
export const runFreeProjection = (payload) => call('post', '/simulations/free', { data: payload })
export const runGoalProjection = (goalId, payload) => call('post', `/goals/${goalId}/simulation`, { data: payload })

// 저축 목표
export const getGoals = () => call('get', '/goals')
export const getGoal = (goalId) => call('get', `/goals/${goalId}`)
export const createGoal = (payload) => call('post', '/goals', { data: payload })
export const updateGoal = (goalId, payload) => call('patch', `/goals/${goalId}`, { data: payload })
export const deleteGoal = (goalId) => call('delete', `/goals/${goalId}`)

// 거래 내역
export const getLedgerTransactions = (params = {}) => call('get', '/transactions', { params })
export const getLedgerTransaction = (transactionId) => call('get', `/transactions/${transactionId}`)
export const getInvestmentTransactions = (params = {}) => call('get', '/investments/transactions', { params })

// 뱃지
export const getBadgeCatalog = () => call('get', '/badges')
export const getMyBadges = () => call('get', '/badges/me')

// 커뮤니티
export const getPosts = (params = {}) => call('get', '/posts', { params })
export const getPost = (postId) => call('get', `/posts/${postId}`)
export const createPost = (payload) => call('post', '/posts', { data: payload })
export const updatePost = (postId, payload) => call('patch', `/posts/${postId}`, { data: payload })
export const deletePost = (postId) => call('delete', `/posts/${postId}`)
export const getComments = (postId, params = {}) => call('get', `/posts/${postId}/comments`, { params })
export const createComment = (postId, payload) => call('post', `/posts/${postId}/comments`, { data: payload })
export const updateComment = (commentId, payload) => call('patch', `/comments/${commentId}`, { data: payload })
export const deleteComment = (commentId) => call('delete', `/comments/${commentId}`)
export const reactToPost = (postId, reactionType) => call('put', `/posts/${postId}/reaction`, { data: { reaction_type: reactionType } })
export const reportContent = (payload) => call('post', '/reports', { data: payload })
export const getMyReports = (params = {}) => call('get', '/reports/me', { params })
export const uploadPostImages = (postId, files) => upload(`/posts/${postId}/images`, files)
export const deleteAttachment = (attachmentId) => call('delete', `/attachments/${attachmentId}`)

// 거래 오류 문의
export const getInquiries = (params = {}) => call('get', '/inquiries', { params })
export const getInquiry = (inquiryId) => call('get', `/inquiries/${inquiryId}`)
export const createInquiry = (payload) => call('post', '/inquiries', { data: payload })
export const uploadInquiryImages = (inquiryId, files) => upload(`/inquiries/${inquiryId}/images`, files)

// 프로필
export const getMyProfile = () => call('get', '/profiles/me')
export const getProfile = (userId) => call('get', `/profiles/${userId}`)
export const updateMyProfile = (payload) => call('patch', '/profiles/me', { data: payload })
export const getMyVisibility = () => call('get', '/profiles/me/visibility')
export const updateMyVisibility = (payload) => call('patch', '/profiles/me/visibility', { data: payload })

// 관리자 (/api/admin/*, ADMIN 권한 필요; 비관리자는 403)
export const adminGetUsers = (params = {}) => call('get', '/admin/users', { params })
export const adminGetUser = (userId) => call('get', `/admin/users/${userId}`)
export const adminSetUserStatus = (userId, payload) => call('patch', `/admin/users/${userId}/status`, { data: payload })
export const adminDeleteUser = (userId, reason) => call('delete', `/admin/users/${userId}`, { data: { reason } })
export const adminAdjustAccount = (userId, payload) => call('post', `/admin/users/${userId}/adjustments`, { data: payload })
export const adminGetProducts = (params = {}) => call('get', '/admin/products', { params })
export const adminGetProduct = (productId) => call('get', `/admin/products/${productId}`)
export const adminPatchProduct = (productId, payload) => call('patch', `/admin/products/${productId}`, { data: payload })
export const adminPatchOption = (productId, optionId, payload) => call('patch', `/admin/products/${productId}/options/${optionId}`, { data: payload })
export const adminDeleteProduct = (productId, reason) => call('delete', `/admin/products/${productId}`, { data: { reason } })
export const adminGetLedger = (params = {}) => call('get', '/admin/transactions', { params })
export const adminGetMarketTransactions = (params = {}) => call('get', '/admin/market-transactions', { params })
export const adminGetPosts = (params = {}) => call('get', '/admin/posts', { params })
export const adminGetCommentsAll = (params = {}) => call('get', '/admin/comments', { params })
export const adminDeletePost = (postId, reason) => call('delete', `/admin/posts/${postId}`, { data: { reason } })
export const adminDeleteComment = (commentId, reason) => call('delete', `/admin/comments/${commentId}`, { data: { reason } })
export const adminGetReports = (params = {}) => call('get', '/admin/reports', { params })
export const adminResolveReport = (reportId, payload) => call('patch', `/admin/reports/${reportId}`, { data: payload })
export const adminGetInquiries = (params = {}) => call('get', '/admin/inquiries', { params })
export const adminGetInquiry = (inquiryId) => call('get', `/admin/inquiries/${inquiryId}`)
export const adminAnswerInquiry = (inquiryId, payload) => call('patch', `/admin/inquiries/${inquiryId}/answer`, { data: payload })
export const adminGetAuditLogs = (params = {}) => call('get', '/admin/audit-logs', { params })
