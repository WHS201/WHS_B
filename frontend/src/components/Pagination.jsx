export default function Pagination({ label, page, totalPages, disabled = false, onPageChange }) {
  if (totalPages <= 1) return null

  return (
    <nav className="pager" aria-label={`${label} 페이지 이동`}>
      <button
        type="button"
        disabled={disabled || page <= 1}
        onClick={() => onPageChange(page - 1)}
      >이전</button>
      <span aria-live="polite">{page} / {totalPages}</span>
      <button
        type="button"
        disabled={disabled || page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >다음</button>
    </nav>
  )
}
