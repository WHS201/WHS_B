import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import PostImageEditor from '../components/PostImageEditor'
import { savePostWithImages, validatePostImages } from '../utils/postImages'
import PageShell from '../components/PageShell'
import Pagination from '../components/Pagination'
import usePagedList from '../hooks/usePagedList'
import { confirmAction, showToast } from '../components/Toast'
import { Empty, Loading, Notice } from '../components/Ui'
import {
  MOCKS_ENABLED, createComment, createPost, deleteAttachment, deleteComment, deletePost, getApiError,
  getComments, getMyProfile, getPost, getPosts, reactToPost, reportContent,
  updateComment, updatePost, uploadPostImages,
} from '../api/features'
import { resolveNicknames } from '../api/profileNames'

const BOARDS = [
  ['', '전체'],
  ['FREE', '자유'],
  ['KR_STOCK', '국내주식'],
  ['US_STOCK', '미국주식'],
  ['DEPOSIT_SAVING', '예·적금'],
]
const BOARD_LABEL = { FREE: '자유', KR_STOCK: '국내주식', US_STOCK: '미국주식', DEPOSIT_SAVING: '예·적금' }
const SORTS = [['latest', '최신순'], ['likes', '추천순'], ['dislikes', '비추천순']]
const PAGE_SIZE = 10
const COMMENT_PAGE_SIZE = 20
const emptyPost = { board_type: 'FREE', title: '', content: '' }

const dateTime = (value) => {
  if (!value) {
    return '-'
  }

  // 서버 시간이 UTC인데 Z가 없는 경우에도 UTC로 해석
  const normalizedValue =
    /Z$|[+-]\d{2}:\d{2}$/.test(value)
      ? value
      : `${value}Z`

  const date = new Date(normalizedValue)

  if (Number.isNaN(date.getTime())) {
    return '-'
  }

  const parts = new Intl.DateTimeFormat(
    'ko-KR',
    {
      timeZone: 'Asia/Seoul',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    },
  ).formatToParts(date)

  const get = (type) =>
    parts.find((part) => part.type === type)?.value || ''

  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}`
}

const authorName = (item, myId, nameMap = {}) => (
  item.user_id === myId
    ? '나'
    : nameMap[item.user_id] || item.author_nickname || `작성자 #${item.user_id}`
)

function Author({ item, myId, nameMap }) {
  const name = authorName(item, myId, nameMap)
  if (item.user_id === myId || item.user_id == null) return name
  return <Link to={`/profile/${item.user_id}`} className="author-link" onClick={(event) => event.stopPropagation()}>{name}</Link>
}

function ReportForm({ target, reason, error, busy, onChange, onSubmit, onCancel }) {
  const label = target.target_type === 'COMMENT' ? '댓글 신고' : '게시글 신고'
  const inputId = `report_reason_${target.target_type}_${target.target_id}`

  return (
    <form className="report-form" onSubmit={onSubmit} aria-label={label}>
      <label className="field-label" htmlFor={inputId}>{label} 사유</label>
      <textarea
        id={inputId}
        maxLength={1000}
        required
        disabled={busy}
        value={reason}
        onChange={(event) => onChange(event.target.value)}
        placeholder="신고 사유를 입력해 주세요."
      />
      <Notice type="error">{error}</Notice>
      <div className="button-row goal-form-buttons">
        <button type="submit" className="service-primary-button" disabled={busy || !reason.trim()}>신고 접수</button>
        <button type="button" className="service-secondary-button" onClick={onCancel} disabled={busy}>취소</button>
      </div>
    </form>
  )
}

function PostDetail({ postId, myId, onClose }) {
  const [post, setPost] = useState(null)
  const loadCommentPage = useCallback((params) => getComments(postId, params), [postId])
  const {
    items: comments, total: commentTotal, page: commentPage, totalPages: commentPages,
    loading: commentsLoading, error: commentsError,
    goToPage: goToCommentPage, reload: reloadComments, retry: retryComments,
  } = usePagedList(loadCommentPage, COMMENT_PAGE_SIZE)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState(emptyPost)
  const [editImages, setEditImages] = useState([])
  const [commentText, setCommentText] = useState('')
  const [editingCommentId, setEditingCommentId] = useState(null)
  const [editCommentText, setEditCommentText] = useState('')
  // 신고 대상의 종류와 번호를 함께 저장해 게시글과 댓글을 구분합니다.
  const [reportTarget, setReportTarget] = useState(null)
  const [reportReason, setReportReason] = useState('')
  const [reportError, setReportError] = useState('')
  const [nameMap, setNameMap] = useState({})
  // 서버가 반환한 게시글의 내 반응을 버튼 표시와 취소 판단에 사용합니다.
  const myReaction = post?.my_reaction ?? null

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    getPost(postId)
      .then((postRes) => {
        if (!active) return
        setPost(postRes.data)
        setLoading(false)
      })
      .catch((loadError) => {
        if (!active) return
        setError(getApiError(loadError))
        setLoading(false)
      })

    return () => { active = false }
  }, [postId])

  useEffect(() => {
    let active = true
    const rows = post ? [post, ...comments] : comments
    resolveNicknames(rows.map((row) => row.user_id))
      .then((map) => { if (active) setNameMap((prev) => ({ ...prev, ...map })) })
      .catch(() => {})
    return () => { active = false }
  }, [post, comments])

  const refreshPost = async () => {
    const res = await getPost(postId)
    setPost(res.data)
  }

  const changeCommentPage = (nextPage) => {
    if (busy || commentsLoading) return
    setEditingCommentId(null)
    setEditCommentText('')
    if (reportTarget?.target_type === 'COMMENT') {
      setReportTarget(null)
      setReportReason('')
      setReportError('')
    }
    goToCommentPage(nextPage)
  }

  const react = async (kind) => {
    if (busy) return
    const next = myReaction === kind ? 'NONE' : kind
    setBusy(true)
    setError('')
    try {
      const response = await reactToPost(postId, next)
      if (response.data?.post_id === postId) {
        // 저장된 선택 상태와 반응 개수를 같은 응답으로 갱신합니다.
        setPost(response.data)
      } else {
        // 기존 목(mock) 응답처럼 반응 종류만 반환하는 경우 다시 조회합니다.
        await refreshPost()
      }
    } catch (reactError) {
      setError(getApiError(reactError))
    } finally {
      setBusy(false)
    }
  }

  const startEdit = () => {
    setEditForm({ board_type: post.board_type, title: post.title, content: post.content })
    setEditImages([])
    setEditing(true)
  }

  const saveEdit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const problem = validatePostImages(editImages, post.attachments?.length || 0)
      if (problem) throw new Error(problem)
      await savePostWithImages({ postId, files: editImages, payload: {
        board_type: editForm.board_type,
        title: editForm.title.trim(),
        content: editForm.content.trim(),
      } }, { updatePost, uploadPostImages })
      setEditImages([])
      setEditing(false)
      await refreshPost()
      showToast('게시글을 수정했습니다.')
    } catch (saveError) {
      setError(`${saveError.postSaved ? '글은 저장되었지만 이미지 첨부에 실패했습니다. 이미지를 확인하고 다시 저장해 주세요. ' : ''}${getApiError(saveError)}`)
    } finally {
      setBusy(false)
    }
  }

  const uploadImages = async (files) => {
    if (busy || !files || files.length === 0) return
    const problem = validatePostImages(Array.from(files), post.attachments?.length || 0)
    if (problem) { setError(problem); return }
    setBusy(true)
    setError('')
    try {
      await uploadPostImages(postId, files)
      await refreshPost()
      showToast('이미지를 첨부했습니다.')
    } catch (uploadError) {
      setError(getApiError(uploadError))
    } finally {
      setBusy(false)
    }
  }

  const removeAttachment = async (attachmentId) => {
    if (busy || !await confirmAction('첨부 이미지를 삭제할까요? 삭제는 즉시 반영됩니다.')) return
    setBusy(true)
    try {
      await deleteAttachment(attachmentId)
      await refreshPost()
    } catch (removeError) {
      setError(getApiError(removeError))
    } finally {
      setBusy(false)
    }
  }

  const removePost = async () => {
    if (!await confirmAction('이 게시글을 삭제할까요?')) return
    try {
      await deletePost(postId)
      showToast('게시글을 삭제했습니다.')
      onClose()
    } catch (removeError) {
      setError(getApiError(removeError))
    }
  }

  const submitComment = async (event) => {
    event.preventDefault()
    if (busy || commentsLoading || !commentText.trim()) return
    setBusy(true)
    setError('')
    try {
      await createComment(postId, { content: commentText.trim() })
      setCommentText('')
      setEditingCommentId(null)
      setEditCommentText('')
      if (reportTarget?.target_type === 'COMMENT') {
        setReportTarget(null)
        setReportReason('')
        setReportError('')
      }
      reloadComments('last')
      showToast('댓글을 등록했습니다.')
    } catch (commentError) {
      setError(getApiError(commentError))
    } finally {
      setBusy(false)
    }
  }

  const saveComment = async (commentId) => {
    if (busy || commentsLoading || !editCommentText.trim()) return
    setBusy(true)
    setError('')
    try {
      await updateComment(commentId, { content: editCommentText.trim() })
      setEditingCommentId(null)
      setEditCommentText('')
      reloadComments()
    } catch (editError) {
      setError(getApiError(editError))
    } finally {
      setBusy(false)
    }
  }

  const removeComment = async (commentId) => {
    if (busy || commentsLoading) return
    if (!await confirmAction('댓글을 삭제할까요?')) return
    setBusy(true)
    setError('')
    try {
      await deleteComment(commentId)
      reloadComments()
    } catch (removeError) {
      setError(getApiError(removeError))
    } finally {
      setBusy(false)
    }
  }

  const toggleReport = (targetType, targetId) => {
    if (busy || myId == null) return
    const isSameTarget = reportTarget?.target_type === targetType
      && reportTarget.target_id === targetId
    setReportTarget(isSameTarget ? null : { target_type: targetType, target_id: targetId })
    setReportReason('')
    setReportError('')
  }

  const closeReport = () => {
    if (busy) return
    setReportTarget(null)
    setReportReason('')
    setReportError('')
  }

  const submitReport = async (event) => {
    event.preventDefault()
    if (busy || !reportTarget || !reportReason.trim()) return
    setBusy(true)
    setReportError('')
    try {
      await reportContent({
        target_type: reportTarget.target_type,
        target_id: reportTarget.target_id,
        reason: reportReason.trim(),
      })
      setReportTarget(null)
      setReportReason('')
      showToast('신고가 접수되었습니다.')
    } catch (reportError) {
      setReportError(getApiError(reportError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <button type="button" className="btn-neutral" onClick={onClose} style={{ minHeight: 36, marginBottom: 16, padding: '0 14px', borderRadius: 7, fontWeight: 800, cursor: 'pointer', background: '#fff' }}>← 목록</button>

      <Notice type="error">{error}</Notice>

      {loading ? <Loading /> : !post ? <Empty>게시글을 불러올 수 없습니다. 삭제된 글인지 확인해 주세요.</Empty> : editing ? (
        <form className="post-form service-card" onSubmit={saveEdit}>
          <span className="card-label">게시글 수정</span>
          <label className="field-label" htmlFor="edit_board">게시판</label>
          <select id="edit_board" value={editForm.board_type} onChange={(e) => setEditForm((f) => ({ ...f, board_type: e.target.value }))}>
            {Object.entries(BOARD_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
          <label className="field-label" htmlFor="edit_title">제목</label>
          <input id="edit_title" type="text" maxLength={100} required value={editForm.title} onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))} />
          <label className="field-label" htmlFor="edit_content">내용</label>
          <textarea id="edit_content" maxLength={10000} required value={editForm.content} onChange={(e) => setEditForm((f) => ({ ...f, content: e.target.value }))} />
          <PostImageEditor files={editImages} onChange={setEditImages} existing={post.attachments || []} onRemove={removeAttachment} busy={busy} />
          <div className="button-row goal-form-buttons">
            <button type="submit" className="service-primary-button" disabled={busy}>수정 저장</button>
            <button type="button" className="service-secondary-button" onClick={() => setEditing(false)} disabled={busy}>취소</button>
          </div>
        </form>
      ) : (
        <>
          <div className="post-detail-head">
            <span className="board-chip">{BOARD_LABEL[post.board_type] || post.board_type}</span>
            <h2>{post.title}</h2>
          </div>
          <div className="post-detail-sub">
            <Author item={post} myId={myId} nameMap={nameMap} /> · {dateTime(post.created_at)}
            {post.updated_at && post.updated_at !== post.created_at && ` · 수정됨 ${dateTime(post.updated_at)}`}
          </div>

          <div className="post-body">{post.content}</div>

          {post.attachments?.length > 0 && (
            <div className="post-attach">
              {post.attachments.map((attachment) => (
                <div key={attachment.attachment_id} className="post-attach-item">
                  <img
                    src={attachment.url}
                    alt="첨부 이미지"
                    onError={(event) => { event.currentTarget.style.display = 'none' }}
                  />
                  {post.user_id === myId && (
                    <button type="button" onClick={() => removeAttachment(attachment.attachment_id)} aria-label="첨부 삭제">×</button>
                  )}
                </div>
              ))}
            </div>
          )}

          {post.user_id === myId && !editing && (
            <label className="attach-upload">
              이미지 첨부 (최대 5장)
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                multiple
                disabled={busy}
                onChange={(event) => { uploadImages(event.target.files); event.target.value = "" }}
              />
            </label>
          )}

          <div className="reaction-row">
            <button
              type="button"
              className={`reaction-btn${myReaction === 'LIKE' ? ' active' : ''}`}
              aria-pressed={myReaction === 'LIKE'}
              disabled={busy}
              onClick={() => react('LIKE')}
            >
              ▲ 추천 {post.reactions?.LIKE ?? 0}
            </button>
            <button
              type="button"
              className={`reaction-btn down${myReaction === 'DISLIKE' ? ' active' : ''}`}
              aria-pressed={myReaction === 'DISLIKE'}
              disabled={busy}
              onClick={() => react('DISLIKE')}
            >
              ▼ 비추천 {post.reactions?.DISLIKE ?? 0}
            </button>
          </div>

          <div className="post-detail-actions">
            {post.user_id === myId && (
              <>
                <button type="button" className="btn-neutral" onClick={startEdit}>수정</button>
                <button type="button" className="btn-danger" onClick={removePost}>삭제</button>
              </>
            )}
            {myId != null && post.user_id !== myId && (
              <button
                type="button"
                className="btn-neutral"
                disabled={busy}
                aria-expanded={reportTarget?.target_type === 'POST' && reportTarget.target_id === postId}
                onClick={() => toggleReport('POST', postId)}
              >신고</button>
            )}
          </div>

          {reportTarget?.target_type === 'POST' && reportTarget.target_id === postId && (
            <ReportForm
              target={reportTarget}
              reason={reportReason}
              error={reportError}
              busy={busy}
              onChange={setReportReason}
              onSubmit={submitReport}
              onCancel={closeReport}
            />
          )}

          <div className="comment-section" aria-busy={commentsLoading}>
            <h3>댓글 {commentTotal}</h3>
            <Notice type="error">{commentsError}</Notice>

            {commentsLoading ? <Loading /> : commentsError ? (
              <button type="button" className="btn-neutral" onClick={retryComments} disabled={busy}>댓글 다시 불러오기</button>
            ) : comments.length === 0 ? <Empty>첫 댓글을 남겨보세요.</Empty> : (
              <ul className="comment-list">
                {comments.map((comment) => (
                  <li key={comment.comment_id} className="comment-item">
                    <div className="comment-meta">
                      <strong><Author item={comment} myId={myId} nameMap={nameMap} /></strong>
                      <span>{dateTime(comment.created_at)}</span>
                    </div>

                    {editingCommentId === comment.comment_id ? (
                      <div className="comment-form">
                        <textarea maxLength={1000} value={editCommentText} onChange={(event) => setEditCommentText(event.target.value)} />
                        <div>
                          <button type="button" onClick={() => saveComment(comment.comment_id)} disabled={busy}>저장</button>
                          {' '}
                          <button type="button" className="btn-neutral" onClick={() => setEditingCommentId(null)}>취소</button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="comment-body">{comment.content}</div>
                        {comment.user_id === myId && (
                          <div className="comment-actions">
                            <button type="button" disabled={busy} onClick={() => { setEditingCommentId(comment.comment_id); setEditCommentText(comment.content) }}>수정</button>
                            <button type="button" disabled={busy} onClick={() => removeComment(comment.comment_id)}>삭제</button>
                          </div>
                        )}
                        {myId != null && comment.user_id !== myId && (
                          <div className="comment-actions">
                            <button
                              type="button"
                              disabled={busy}
                              aria-expanded={reportTarget?.target_type === 'COMMENT' && reportTarget.target_id === comment.comment_id}
                              onClick={() => toggleReport('COMMENT', comment.comment_id)}
                            >신고</button>
                          </div>
                        )}
                        {reportTarget?.target_type === 'COMMENT' && reportTarget.target_id === comment.comment_id && (
                          <ReportForm
                            target={reportTarget}
                            reason={reportReason}
                            error={reportError}
                            busy={busy}
                            onChange={setReportReason}
                            onSubmit={submitReport}
                            onCancel={closeReport}
                          />
                        )}
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}

            <Pagination
              label="댓글"
              page={commentPage}
              totalPages={commentPages}
              disabled={busy || commentsLoading}
              onPageChange={changeCommentPage}
            />

            <form className="comment-form" onSubmit={submitComment}>
              <textarea
                maxLength={1000}
                required
                value={commentText}
                onChange={(event) => setCommentText(event.target.value)}
                placeholder="댓글을 입력하세요."
              />
              <button type="submit" disabled={busy || commentsLoading}>댓글 등록</button>
            </form>
          </div>
        </>
      )}
    </div>
  )
}

function CommunityPage() {
  const [myId, setMyId] = useState(null)
  const navigate = useNavigate()
  const location = useLocation()
  const { postId: routePostId } = useParams()
  const [params, setParams] = useSearchParams()
  const selectedId = routePostId === undefined ? null : Number(routePostId)
  const board = params.get('board') || ''
  const sort = params.get('sort') || 'latest'
  const search = params.get('q') || ''
  const page = Math.max(1, Math.min(10000, Number(params.get('page')) || 1))
  const [queryInput, setQueryInput] = useState(search)
  useEffect(() => setQueryInput(search), [search])
  const filters = (patch) => setParams((current) => {
    const next = new URLSearchParams(current)
    Object.entries(patch).forEach(([key, value]) => value ? next.set(key, String(value)) : next.delete(key))
    return next
  })
  const setBoard = (value) => filters({ board: value, page: 1 })
  const setSort = (value) => filters({ sort: value, page: 1 })
  const setSearch = (value) => filters({ q: value, page: 1 })
  const setPage = (value) => filters({ page: typeof value === 'function' ? value(page) : value })
  const openPost = (id) => navigate(`/community/posts/${id}${location.search}`)
  const closePost = () => navigate(`/community${location.search}`)
  const [reloadKey, setReloadKey] = useState(0)

  const [list, setList] = useState(null)
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [nameMap, setNameMap] = useState({})


  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyPost)
  const [images, setImages] = useState([])
  const [createdPostId, setCreatedPostId] = useState(null)
  useEffect(() => {
    // Opening the saved post ends a partially completed creation flow.
    if (selectedId !== null && selectedId === createdPostId) {
      setCreatedPostId(null)
      setImages([])
      setForm(emptyPost)
      setShowForm(false)
    }
  }, [selectedId, createdPostId])
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getMyProfile()
      .then((res) => setMyId(res.data.user_id))
      .catch(() => setMyId(null))
  }, [])

  useEffect(() => {
    if (selectedId !== null) return
    let active = true
    setListLoading(true)
    setListError('')

    const params = { page, size: PAGE_SIZE, sort }
    if (board) params.board_type = board
    if (search) params.q = search

    getPosts(params)
      .then((res) => {
        if (!active) return
        setList(res.data)
        setListLoading(false)
        resolveNicknames(res.data.items.map((post) => post.user_id))
          .then((map) => { if (active) setNameMap((prev) => ({ ...prev, ...map })) })
      })
      .catch((loadError) => {
        if (!active) return
        setListError(getApiError(loadError))
        setListLoading(false)
      })

    return () => { active = false }
  }, [board, sort, search, page, selectedId, reloadKey])

  const submitSearch = (event) => {
    event.preventDefault()
    setSearch(queryInput.trim())
  }

  const submitPost = async (event) => {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      const problem = validatePostImages(images)
      if (problem) throw new Error(problem)
      const savedId = await savePostWithImages({ postId: createdPostId, files: images, onSaved: setCreatedPostId, payload: {
        board_type: form.board_type,
        title: form.title.trim(),
        content: form.content.trim(),
      } }, { createPost, updatePost, uploadPostImages })
      setImages([])
      setCreatedPostId(null)
      setShowForm(false)
      setForm(emptyPost)
      openPost(savedId)
      setReloadKey((value) => value + 1)
      showToast('게시글을 등록했습니다.')
    } catch (postError) {
      setFormError(`${postError.postSaved ? '글은 저장되었지만 이미지 첨부에 실패했습니다. 다시 등록하면 같은 글에 첨부를 재시도합니다. ' : ''}${getApiError(postError)}`)
    } finally {
      setBusy(false)
    }
  }

  const totalPages = list ? Math.max(1, Math.ceil(list.total / PAGE_SIZE)) : 1
  const items = list?.items || []

  return (
    <PageShell
      eyebrow="커뮤니티"
      title="게시판"
      description="자유 · 국내주식 · 미국주식 · 예·적금 게시판에서 다른 사용자와 정보를 나눠보세요."
      actions={selectedId === null && (
        <button type="button" className="service-primary-button" disabled={busy} onClick={() => { if (createdPostId) { openPost(createdPostId); return } setShowForm((v) => !v); setFormError('') }}>
          {showForm ? '작성 닫기' : '글쓰기'}
        </button>
      )}
    >
      {MOCKS_ENABLED && (
        <div className="mock-banner">
          목(mock) 데이터 표시 중 · 백엔드 연결 시 <code>VITE_USE_MOCKS=false</code> 로 전환
        </div>
      )}

      {selectedId !== null ? (
        Number.isSafeInteger(selectedId) && selectedId > 0
          ? <PostDetail key={selectedId} postId={selectedId} myId={myId} onClose={closePost} />
          : <Notice type="error">올바르지 않은 게시글 주소입니다. <Link to="/community">목록으로</Link></Notice>
      ) : (
        <>
          {showForm && (
            <form className="post-form service-card" onSubmit={submitPost}>
              <span className="card-label">새 게시글</span>
              <label className="field-label" htmlFor="new_board">게시판</label>
              <select id="new_board" value={form.board_type} onChange={(event) => setForm((f) => ({ ...f, board_type: event.target.value }))}>
                {Object.entries(BOARD_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              <label className="field-label" htmlFor="new_title">제목</label>
              <input id="new_title" type="text" maxLength={100} required value={form.title} onChange={(event) => setForm((f) => ({ ...f, title: event.target.value }))} />
              <label className="field-label" htmlFor="new_content">내용</label>
              <textarea id="new_content" maxLength={10000} required value={form.content} onChange={(event) => setForm((f) => ({ ...f, content: event.target.value }))} />
              <PostImageEditor files={images} onChange={setImages} busy={busy} />
              {createdPostId && <p className="mini-sub">게시글은 저장되었습니다. <Link to={`/community/posts/${createdPostId}`}>저장된 글 확인</Link></p>}
              <Notice type="error">{formError}</Notice>
              <div className="button-row goal-form-buttons">
                <button type="submit" className="service-primary-button" disabled={busy}>등록</button>
                <button type="button" className="service-secondary-button" onClick={() => { if (createdPostId) openPost(createdPostId); else setShowForm(false) }} disabled={busy}>취소</button>
              </div>
            </form>
          )}

          <div className="tab-bar">
            {BOARDS.map(([value, label]) => (
              <button key={value || 'all'} className={board === value ? 'active' : ''} onClick={() => setBoard(value)}>
                {label}
              </button>
            ))}
          </div>

          <div className="community-toolbar">
            <select value={sort} onChange={(event) => setSort(event.target.value)}>
              {SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            {list && <span className="tx-count">전체 {list.total}건</span>}
            <form className="community-search" onSubmit={submitSearch}>
              <input type="text" maxLength={100} value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="제목·내용 검색" />
              <button type="submit">검색</button>
            </form>
          </div>

          <Notice type="error">{listError}</Notice>

          {listLoading ? <Loading /> : items.length === 0 ? <Empty>게시글이 없습니다.</Empty> : (
            <>
              <ul className="post-list">
                {items.map((post) => (
                  <li key={post.post_id} className="post-item">
                    <button type="button" className="post-card" onClick={() => openPost(post.post_id)}>
                      <h3>{post.title}</h3>
                      <div className="post-card-meta">
                        <span className="board-chip">{BOARD_LABEL[post.board_type] || post.board_type}</span>
                        <span><Author item={post} myId={myId} nameMap={nameMap} /></span>
                        <span>{dateTime(post.created_at)}</span>
                        <span className="react-mini">▲ {post.reactions?.LIKE ?? 0}</span>
                        <span className="react-mini down">▼ {post.reactions?.DISLIKE ?? 0}</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>

              <div className="pager">
                <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>이전</button>
                <span>{page} / {totalPages}</span>
                <button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>다음</button>
              </div>
            </>
          )}
        </>
      )}
    </PageShell>
  )
}

export default CommunityPage
