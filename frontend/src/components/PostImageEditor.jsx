import { useEffect, useState } from 'react'
import { Notice } from './Ui'
import { validatePostImages } from '../utils/postImages'

export default function PostImageEditor({ files, onChange, existing = [], onRemove, busy = false }) {
  const [previews, setPreviews] = useState([])
  const [error, setError] = useState('')
  useEffect(() => {
    const urls = files.map((file) => URL.createObjectURL(file))
    setPreviews(urls)
    return () => urls.forEach((url) => URL.revokeObjectURL(url))
  }, [files])

  const select = (event) => {
    const next = [...files, ...Array.from(event.target.files || [])]
    event.target.value = ''
    const problem = validatePostImages(next, existing.length)
    setError(problem)
    if (!problem) onChange(next)
  }

  return (
    <section className="image-editor" aria-label="게시글 이미지 관리">
      <strong>이미지 {existing.length + files.length} / 5장</strong>
      <p className="mini-sub">PNG·JPG·WEBP, 한 장당 10MB 이하. 새 이미지는 글을 저장할 때 첨부됩니다.</p>
      {existing.length > 0 && <p className="mini-sub">기존 이미지 삭제는 즉시 반영됩니다.</p>}
      <div className="post-attach">
        {existing.map((item) => (
          <div className="post-attach-item" key={item.attachment_id}>
            <img src={item.url} alt="기존 첨부 이미지" />
            <button type="button" disabled={busy} onClick={() => onRemove(item.attachment_id)} aria-label="기존 이미지 삭제">×</button>
          </div>
        ))}
        {files.map((file, index) => (
          <div className="post-attach-item" key={`${index}-${file.name}`}>
            <img src={previews[index]} alt={`첨부 예정: ${file.name}`} />
            <span className="mini-sub">{file.name}</span>
            <button type="button" disabled={busy} onClick={() => { onChange(files.filter((_, i) => i !== index)); setError('') }} aria-label={`${file.name} 선택 취소`}>×</button>
          </div>
        ))}
      </div>
      <label className="attach-upload">이미지 선택
        <input type="file" accept="image/png,image/jpeg,image/webp" multiple disabled={busy || existing.length + files.length >= 5} onChange={select} />
      </label>
      <Notice type="error">{error}</Notice>
    </section>
  )
}
