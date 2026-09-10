import usePagedList from '../hooks/usePagedList'
import { getLedgerTransactions } from '../api/features'
import { ledgerLabel } from '../utils/presentation'
import { Empty, Loading, Notice } from './Ui'
import Pagination from './Pagination'

export default function LedgerPicker({ selected, onChange, busy }) {
  const { items, page, totalPages, loading, error, goToPage, retry } = usePagedList(getLedgerTransactions, 10)
  return (
    <fieldset className="ledger-picker" disabled={busy}>
      <legend>관련 거래 선택 (선택 사항)</legend>
      <p className="mini-sub">본인의 금융 원장 거래만 표시됩니다. 거래와 무관한 문의는 선택하지 않아도 됩니다.</p>
      {selected && <p className="selected-ledger">선택: {ledgerLabel(selected)} <button type="button" onClick={() => onChange(null)}>선택 해제</button></p>}
      <Notice type="error">{error}</Notice>
      {loading ? <Loading /> : error ? <button type="button" onClick={retry}>거래 다시 불러오기</button>
        : items.length === 0 ? <Empty>연결할 거래가 없습니다. 거래 선택 없이 문의할 수 있습니다.</Empty>
          : items.map((row) => (
            <label className="ledger-choice" key={row.ledger_transaction_id}>
              <input type="radio" name="inquiry-ledger" checked={selected?.ledger_transaction_id === row.ledger_transaction_id} onChange={() => onChange(row)} />
              <span>{ledgerLabel(row)}</span>
            </label>
          ))}
      <Pagination label="연결할 거래" page={page} totalPages={totalPages} disabled={busy || loading} onPageChange={goToPage} />
    </fieldset>
  )
}
