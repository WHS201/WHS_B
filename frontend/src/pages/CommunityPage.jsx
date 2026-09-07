import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageShell from '../components/PageShell'
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
  return <Link to={`/profile/${item.user_id}`} className="author-link">{name}</Link>
}

function PostDetail({ postId, myId, onClose }) {
  const [post, setPost] = useState(null)
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState(emptyPost)
  const [commentText, setCommentText] = useState('')
  const [editingCommentId, setEditingCommentId] = useState(null)
  const [editCommentText, setEditCommentText] = useState('')
  const [showReport, setShowReport] = useState(false)
  const [reportReason, setReportReason] = useState('')
  // post_data() 에 조회자 본인 반응이 없어(백엔드 갭) 세션 동안 로컬로 추적한다.
  const [myReaction, setMyReaction] = useState(null)
  const [nameMap, setNameMap] = useState({})

  const learnNames = (rows) => {
    resolveNicknames(rows.map((row) => row.user_id)).then((map) => setNameMap((prev) => ({ ...prev, ...map })))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    Promise.all([getPost(postId), getComments(postId, { page: 1, size: 100 })])
      .then(([postRes, commentRes]) => {
        if (!active) return
        setPost(postRes.data)
        setMyReaction(postRes.data.my_reaction || null)
        setComments(commentRes.data.items)
        learnNames([postRes.data, ...commentRes.data.items])
        setLoading(false)
      })
      .catch((loadError) => {
        if (!active) return
        setError(getApiError(loadError))
        setLoading(false)
      })

    return () => { active = false }
  }, [postId])

  const refreshPost = async () => {
    const res = await getPost(postId)
    setPost(res.data)
  }

  const refreshComments = async () => {
    const res = await getComments(postId, { page: 1, size: 100 })
    setComments(res.data.items)
    learnNames(res.data.items)
  }

  const react = async (kind) => {
    const next = myReaction === kind ? 'NONE' : kind
    setBusy(true)
    setError('')
    try {
      await reactToPost(postId, next)
      setMyReaction(next === 'NONE' ? null : next)
      await refreshPost()
    } catch (reactError) {
      setError(getApiError(reactError))
    } finally {
      setBusy(false)
    }
  }

  const startEdit = () => {
    setEditForm({ board_type: post.board_type, title: post.title, content: post.content })
    setEditing(true)
  }

  const saveEdit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await updatePost(postId, {
        board_type: editForm.board_type,
        title: editForm.title.trim(),
        content: editForm.content.trim(),
      })
      setEditing(false)
      await refreshPost()
      showToast('게시글을 수정했습니다.')
    } catch (saveError) {
      setError(getApiError(saveError))
    } finally {
      setBusy(false)
    }
  }

  const uploadImages = async (files) => {
    if (!files || files.length === 0) return
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
    if (!await confirmAction('첨부 이미지를 삭제할까요?')) return
    try {
      await deleteAttachment(attachmentId)
      await refreshPost()
    } catch (removeError) {
      setError(getApiError(removeError))
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
    if (!commentText.trim()) return
    setBusy(true)
    try {
      await createComment(postId, { content: commentText.trim() })
      setCommentText('')
      await refreshComments()
      showToast('댓글을 등록했습니다.')
    } catch (commentError) {
      setError(getApiError(commentError))
    } finally {
      setBusy(false)
    }
  }

  const saveComment = async (commentId) => {
    if (!editCommentText.trim()) return
    setBusy(true)
    try {
      await updateComment(commentId, { content: editCommentText.trim() })
      setEditingCommentId(null)
      setEditCommentText('')
      await refreshComments()
    } catch (editError) {
      setError(getApiError(editError))
    } finally {
      setBusy(false)
    }
  }

  const removeComment = async (commentId) => {
    if (!await confirmAction('댓글을 삭제할까요?')) return
    try {
      await deleteComment(commentId)
      await refreshComments()
    } catch (removeError) {
      setError(getApiError(removeError))
    }
  }

  const submitReport = async (event) => {
    event.preventDefault()
    if (!reportReason.trim()) return
    setBusy(true)
    try {
      await reportContent({ target_type: 'POST', target_id: postId, reason: reportReason.trim() })
      setShowReport(false)
      setReportReason('')
      showToast('신고가 접수되었습니다.')
    } catch (reportError) {
      setError(getApiError(reportError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <button type="button" className="btn-neutral" onClick={onClose} style={{ minHeight: 36, marginBottom: 16, padding: '0 14px', borderRadius: 7, fontWeight: 800, cursor: 'pointer', background: '#fff' }}>← 목록</button>

      <Notice type="error">{error}</Notice>

      {loading || !post ? <Loading /> : editing ? (
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
                onChange={(event) => uploadImages(event.target.files)}
              />
            </label>
          )}

          <div className="reaction-row">
            <button
              type="button"
              className={`reaction-btn${myReaction === 'LIKE' ? ' active' : ''}`}
              disabled={busy}
              onClick={() => react('LIKE')}
            >
              ▲ 추천 {post.reactions?.LIKE ?? 0}
            </button>
            <button
              type="button"
              className={`reaction-btn down${myReaction === 'DISLIKE' ? ' active' : ''}`}
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
            {post.user_id !== myId && (
              <button type="button" className="btn-neutral" onClick={() => setShowReport((value) => !value)}>신고</button>
            )}
          </div>

          {showReport && (
            <form className="report-form" onSubmit={submitReport}>
              <label className="field-label" htmlFor="report_reason">신고 사유</label>
              <textarea id="report_reason" maxLength={1000} required value={reportReason} onChange={(event) => setReportReason(event.target.value)} placeholder="신고 사유를 입력해 주세요." />
              <div className="button-row goal-form-buttons">
                <button type="submit" className="service-primary-button" disabled={busy}>신고 접수</button>
                <button type="button" className="service-secondary-button" onClick={() => setShowReport(false)}>취소</button>
              </div>
            </form>
          )}

          <div className="comment-section">
            <h3>댓글 {comments.length}</h3>

            {comments.length === 0 ? <Empty>첫 댓글을 남겨보세요.</Empty> : (
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
                            <button type="button" onClick={() => { setEditingCommentId(comment.comment_id); setEditCommentText(comment.content) }}>수정</button>
                            <button type="button" onClick={() => removeComment(comment.comment_id)}>삭제</button>
                          </div>
                        )}
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}

            <form className="comment-form" onSubmit={submitComment}>
              <textarea
                maxLength={1000}
                required
                value={commentText}
                onChange={(event) => setCommentText(event.target.value)}
                placeholder="댓글을 입력하세요."
              />
              <button type="submit" disabled={busy}>댓글 등록</button>
            </form>
          </div>
        </>
      )}
    </div>
  )
}

function CommunityPage() {
  const [myId, setMyId] = useState(null)
  const [board, setBoard] = useState('')
  const [sort, setSort] = useState('latest')
  const [queryInput, setQueryInput] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [reloadKey, setReloadKey] = useState(0)

  const [list, setList] = useState(null)
  const [listLoading, setListLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [nameMap, setNameMap] = useState({})

  const [selectedId, setSelectedId] = useState(null)

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyPost)
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
    setPage(1)
  }

  const submitPost = async (event) => {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      await createPost({
        board_type: form.board_type,
        title: form.title.trim(),
        content: form.content.trim(),
      })
      setShowForm(false)
      setForm(emptyPost)
      setBoard('')
      setSort('latest')
      setPage(1)
      setReloadKey((value) => value + 1)
      showToast('게시글을 등록했습니다.')
    } catch (postError) {
      setFormError(getApiError(postError))
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
        <button type="button" className="service-primary-button" onClick={() => { setShowForm((v) => !v); setFormError('') }}>
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
        <PostDetail postId={selectedId} myId={myId} onClose={() => setSelectedId(null)} />
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
              <Notice type="error">{formError}</Notice>
              <div className="button-row goal-form-buttons">
                <button type="submit" className="service-primary-button" disabled={busy}>등록</button>
                <button type="button" className="service-secondary-button" onClick={() => setShowForm(false)} disabled={busy}>취소</button>
              </div>
            </form>
          )}

          <div className="tab-bar">
            {BOARDS.map(([value, label]) => (
              <button key={value || 'all'} className={board === value ? 'active' : ''} onClick={() => { setBoard(value); setPage(1) }}>
                {label}
              </button>
            ))}
          </div>

          <div className="community-toolbar">
            <select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1) }}>
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
                    <button type="button" className="post-card" onClick={() => setSelectedId(post.post_id)}>
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
