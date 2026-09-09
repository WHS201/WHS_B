import { useEffect, useRef, useState } from 'react'
import { getApiError } from '../api/features'

// loadPage는 { page, size }를 받아 기존 목록 API를 호출하는 함수입니다.
// 컴포넌트 안에서 만드는 함수라면 useCallback으로 감싸서 전달합니다.
export default function usePagedList(loadPage, pageSize) {
  const [request, setRequest] = useState({ page: 1, last: false })
  const [data, setData] = useState({ items: [], total: 0, page: 1, totalPages: 1 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const requestVersion = useRef(0)

  useEffect(() => {
    let active = true
    const version = ++requestVersion.current
    const isCurrent = () => active && version === requestVersion.current
    setLoading(true)
    setError('')

    const load = async () => {
      try {
        let page = request.page
        // 마지막 페이지가 삭제된 경우, 남아 있는 마지막 페이지를 다시 조회합니다.
        // 댓글 작성 직후에는 최신 댓글이 있는 마지막 페이지로 이동합니다.
        for (let attempt = 0; attempt < 3; attempt += 1) {
          const response = await loadPage({ page, size: pageSize })
          if (!isCurrent()) return
          const result = response.data
          if (!Array.isArray(result?.items) || !Number.isInteger(result.total) || result.total < 0) {
            throw new Error('목록 정보를 읽을 수 없습니다. 다시 불러와 주세요.')
          }
          const size = result.size ?? pageSize
          if (!Number.isInteger(size) || size < 1) {
            throw new Error('목록 정보를 읽을 수 없습니다. 다시 불러와 주세요.')
          }
          const totalPages = Math.max(1, Math.ceil(result.total / size))
          if (page > totalPages || (request.last && page !== totalPages)) {
            page = totalPages
            continue
          }
          setData({ items: result.items, total: result.total, page, totalPages })
          return
        }
        throw new Error('목록이 계속 변경되고 있습니다. 다시 불러와 주세요.')
      } catch (loadError) {
        if (isCurrent()) setError(getApiError(loadError))
      } finally {
        if (isCurrent()) setLoading(false)
      }
    }

    load()
    return () => { active = false }
  }, [loadPage, pageSize, request])

  const requestPage = (page, last = false) => {
    // 새 요청 직전에 이전 요청을 무효화하여 늦게 온 응답이 화면을 덮지 않게 합니다.
    requestVersion.current += 1
    setLoading(true)
    setError('')
    setRequest({ page, last })
  }

  const goToPage = (page) => {
    if (!Number.isInteger(page) || page < 1 || page > data.totalPages) return
    requestPage(page)
  }

  // 기본값: 현재 페이지 / 1: 첫 페이지 / 'last': 마지막 페이지.
  const reload = (target = data.page) => {
    if (target === 'last') {
      requestPage(data.page, true)
    } else if (Number.isInteger(target) && target >= 1) {
      requestPage(target)
    }
  }

  // 실패한 요청의 페이지를 그대로 다시 시도합니다.
  const retry = () => requestPage(request.page, request.last)

  return { ...data, loading, error, goToPage, reload, retry }
}
