export const won = (value) =>
  `${Number(value || 0).toLocaleString('ko-KR')}원`

export const rate = (value) =>
  `${Number(value || 0).toFixed(2)}%`

const normalizeDateValue = (value) => {
  if (!value) {
    return null
  }

  return /Z$|[+-]\d{2}:\d{2}$/.test(value)
    ? value
    : `${value}Z`
}

export const dateTimeKST = (value) => {
  const normalizedValue = normalizeDateValue(value)

  if (!normalizedValue) {
    return '-'
  }

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

export const shortDate = (value) => {
  const normalizedValue = normalizeDateValue(value)

  if (!normalizedValue) {
    return '-'
  }

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
    },
  ).formatToParts(date)

  const get = (type) =>
    parts.find((part) => part.type === type)?.value || ''

  return `${get('year')}-${get('month')}-${get('day')}`
}