import {
  useEffect,
  useState,
} from 'react'

import PageShell from '../components/PageShell'
import { Notice } from '../components/Ui'

import {
  won,
} from '../utils/format'

import {
  createInvestmentOrder,
  getApiError,
  getInvestmentAssets,
  getInvestmentPrice,
} from '../api/finance'


function InvestmentsPage() {
  const [
    market,
    setMarket,
  ] = useState('KR')

  const [
    searchKeyword,
    setSearchKeyword,
  ] = useState('')

  const [
    assets,
    setAssets,
  ] = useState([])

  const [
    selectedAsset,
    setSelectedAsset,
  ] = useState(null)

  const [
    quote,
    setQuote,
  ] = useState(null)

  const [
    side,
    setSide,
  ] = useState('BUY')

  const [
    quantity,
    setQuantity,
  ] = useState('1')

  const [
    order,
    setOrder,
  ] = useState(null)

  const [
    error,
    setError,
  ] = useState('')

  const [
    loadingAssets,
    setLoadingAssets,
  ] = useState(false)

  const [
    loadingQuote,
    setLoadingQuote,
  ] = useState(false)

  const [
    busy,
    setBusy,
  ] = useState(false)


  // --------------------------------------------------------------
  // 종목 목록 불러오기

  const loadAssets = async (
    selectedMarket = market,
    keyword = searchKeyword,
  ) => {
    setLoadingAssets(true)
    setError('')

    try {
      const result = await getInvestmentAssets({
        market: selectedMarket,
        q: keyword.trim(),
      })

      setAssets(
        result.data || [],
      )

    } catch (assetError) {
      setAssets([])

      setError(
        getApiError(
          assetError,
          '종목 목록을 불러오지 못했습니다.',
        ),
      )

    } finally {
      setLoadingAssets(false)
    }
  }


  // --------------------------------------------------------------
  // 최초 접속 / 시장 변경

  useEffect(() => {
    loadAssets(
      market,
      '',
    )

    setSearchKeyword('')
    setSelectedAsset(null)
    setQuote(null)
    setOrder(null)
  }, [market])


  // --------------------------------------------------------------
  // 종목 검색

  const submitSearch = async (event) => {
    event.preventDefault()

    setSelectedAsset(null)
    setQuote(null)
    setOrder(null)

    await loadAssets(
      market,
      searchKeyword,
    )
  }


  // --------------------------------------------------------------
  // 검색 초기화

  const resetSearch = async () => {
    setSearchKeyword('')
    setSelectedAsset(null)
    setQuote(null)
    setOrder(null)

    await loadAssets(
      market,
      '',
    )
  }


  // --------------------------------------------------------------
  // 종목 선택

  const selectAsset = async (asset) => {
    setSelectedAsset(asset)
    setQuote(null)
    setOrder(null)
    setQuantity('1')
    setSide('BUY')
    setError('')
    setLoadingQuote(true)

    try {
      const result = await getInvestmentPrice(
        asset.symbol,
        asset.market,
      )

      setQuote(
        result.data,
      )

    } catch (quoteError) {
      setQuote(null)

      setError(
        getApiError(
          quoteError,
          '현재가를 불러오지 못했습니다.',
        ),
      )

    } finally {
      setLoadingQuote(false)
    }
  }


  // --------------------------------------------------------------
  // 주문

  const submitOrder = async (event) => {
    event.preventDefault()

    if (!selectedAsset || !quote) {
      return
    }

    setBusy(true)
    setError('')
    setOrder(null)

    try {
      const result = await createInvestmentOrder({
        symbol: selectedAsset.symbol,
        market: selectedAsset.market,
        side,
        quantity: Number(quantity),
      })

      setOrder(
        result.data,
      )

    } catch (orderError) {
      setError(
        getApiError(
          orderError,
          '주문 처리에 실패했습니다.',
        ),
      )

    } finally {
      setBusy(false)
    }
  }


  // --------------------------------------------------------------
  // 가격 표시

  const formatPrice = (data) => {
    if (!data) {
      return '-'
    }

    if (data.currency === 'KRW') {
      return won(data.price)
    }

    return `$${Number(
      data.price,
    ).toLocaleString()}`
  }


  return (
    <PageShell
      eyebrow="가상 주식 투자"
      title="투자 체험"
      description="국내·미국 주식과 ETF를 살펴보고 원하는 종목을 선택해 가상 투자를 체험하세요."
    >

      <Notice type="error">
        {error}
      </Notice>


      {/* 시장 선택 */}

      <div className="investment-market-tabs">

        <button
          type="button"
          className={
            market === 'KR'
              ? 'active'
              : ''
          }
          onClick={() =>
            setMarket('KR')
          }
        >
          국내
        </button>

        <button
          type="button"
          className={
            market === 'US'
              ? 'active'
              : ''
          }
          onClick={() =>
            setMarket('US')
          }
        >
          미국
        </button>

      </div>


      {/* 검색 */}

      <form
        className="investment-asset-search"
        onSubmit={submitSearch}
      >

        <input
          type="text"
          value={searchKeyword}
          onChange={(event) =>
            setSearchKeyword(
              event.target.value,
            )
          }
          placeholder={
            market === 'KR'
              ? '종목명 또는 종목코드 검색'
              : '회사명 또는 티커 검색'
          }
        />

        <button
          type="submit"
          disabled={loadingAssets}
        >
          검색
        </button>

        {searchKeyword && (
          <button
            type="button"
            className="investment-search-reset"
            onClick={resetSearch}
          >
            초기화
          </button>
        )}

      </form>


      <div className="investment-browser">

        {/* 왼쪽 종목 목록 */}

        <section className="investment-asset-panel">

          <div className="investment-section-title">

            <div>
              <span className="card-label">
                종목 목록
              </span>

              <h2>
                {market === 'KR'
                  ? '국내 주식 · ETF'
                  : '미국 주식 · ETF'}
              </h2>
            </div>

            <span className="investment-asset-count">
              {assets.length}개
            </span>

          </div>


          {loadingAssets ? (

            <div className="investment-empty">
              종목을 불러오는 중입니다.
            </div>

          ) : assets.length === 0 ? (

            <div className="investment-empty">
              표시할 종목이 없습니다.
            </div>

          ) : (

            <div className="investment-asset-list">

              {assets.map((asset) => {

                const selected =
                  selectedAsset?.symbol === asset.symbol
                  && selectedAsset?.market === asset.market

                return (
                  <button
                    key={`${asset.market}-${asset.symbol}`}
                    type="button"
                    className={
                      selected
                        ? 'investment-asset-row selected'
                        : 'investment-asset-row'
                    }
                    onClick={() =>
                      selectAsset(asset)
                    }
                  >

                    <div className="investment-asset-main">

                      <strong>
                        {asset.name}
                      </strong>

                      <span>
                        {asset.symbol}
                      </span>

                    </div>

                    <div className="investment-asset-meta">

                      <span>
                        {asset.asset_type === 'ETF'
                          ? 'ETF'
                          : '주식'}
                      </span>

                      <span>
                        {asset.market === 'KR'
                          ? '국내'
                          : '미국'}
                      </span>

                    </div>

                  </button>
                )
              })}

            </div>

          )}

        </section>


        {/* 오른쪽 종목 상세 / 주문 */}

        <section className="investment-detail-panel">

          {!selectedAsset ? (

            <div className="investment-select-guide">

              <strong>
                투자할 종목을 선택하세요
              </strong>

              <p>
                왼쪽 종목 목록에서 원하는 종목을
                클릭하면 현재가와 주문 화면이 표시됩니다.
              </p>

            </div>

          ) : loadingQuote ? (

            <div className="investment-select-guide">
              현재가를 불러오는 중입니다.
            </div>

          ) : quote ? (

            <>

              <div className="investment-detail-header">

                <div>

                  <span className="card-label">
                    {quote.market === 'KR'
                      ? '국내'
                      : '미국'}
                    {' · '}
                    {quote.asset_type}
                  </span>

                  <h2>
                    {quote.name}
                  </h2>

                  <p>
                    {quote.symbol}
                  </p>

                </div>


                <div className="investment-current-price">

                  <strong>
                    {formatPrice(quote)}
                  </strong>

                  {quote.price_krw && (
                    <span>
                      약 {won(quote.price_krw)}
                    </span>
                  )}

                  <em
                    className={
                      quote.is_tradable
                        ? 'tradable'
                        : ''
                    }
                  >
                    {quote.is_tradable
                      ? '거래 가능'
                      : quote.market_session}
                  </em>

                </div>

              </div>


              {quote.exchange_rate && (

                <div className="investment-exchange-rate">
                  적용 환율 약{' '}
                  {Number(
                    quote.exchange_rate,
                  ).toLocaleString()}
                  원/USD
                </div>

              )}


              <form
                className="investment-order-form"
                onSubmit={submitOrder}
              >

                <span className="card-label">
                  시장가 주문
                </span>

                <div className="side-selector">

                  <button
                    type="button"
                    className={
                      side === 'BUY'
                        ? 'buy active'
                        : 'buy'
                    }
                    onClick={() =>
                      setSide('BUY')
                    }
                  >
                    매수
                  </button>

                  <button
                    type="button"
                    className={
                      side === 'SELL'
                        ? 'sell active'
                        : 'sell'
                    }
                    onClick={() =>
                      setSide('SELL')
                    }
                  >
                    매도
                  </button>

                </div>


                <label className="field-label">
                  주문 수량
                </label>

                <div className="input-with-unit">

                  <input
                    type="number"
                    min="1"
                    max="1000000"
                    value={quantity}
                    onChange={(event) =>
                      setQuantity(
                        event.target.value,
                      )
                    }
                  />

                  <span>
                    주
                  </span>

                </div>


                <div className="investment-estimate">

                  <span>
                    예상 주문 금액
                  </span>

                  <strong>
                    {quote.currency === 'KRW'
                      ? won(
                          Number(quote.price)
                          * Number(quantity || 0),
                        )
                      : `$${(
                          Number(quote.price)
                          * Number(quantity || 0)
                        ).toLocaleString()}`}
                  </strong>

                </div>


                <button
                  type="submit"
                  className={
                    `order-submit ${side.toLowerCase()}`
                  }
                  disabled={
                    busy
                    || !quote
                    || !quantity
                  }
                >
                  {busy
                    ? '처리 중...'
                    : side === 'BUY'
                      ? '매수 주문'
                      : '매도 주문'}
                </button>

              </form>

            </>

          ) : (

            <div className="investment-select-guide">
              현재가 정보를 불러오지 못했습니다.
            </div>

          )}

        </section>

      </div>


      {/* 주문 결과 */}

      {order && (

        <section className="order-result">

          <span>
            주문 체결 완료
          </span>

          <h2>
            {order.name}
            {' '}
            {order.quantity}주
          </h2>

          <div>

            <p>
              체결 금액
              {' '}
              <strong>
                {won(
                  order.settlement_amount_krw,
                )}
              </strong>
            </p>

            <p>
              수수료
              {' '}
              <strong>
                {won(order.fee)}
              </strong>
            </p>

            <p>
              거래 후 잔액
              {' '}
              <strong>
                {won(
                  order.balance_after,
                )}
              </strong>
            </p>

            <p>
              보유 수량
              {' '}
              <strong>
                {order.holding_quantity}주
              </strong>
            </p>

          </div>

        </section>

      )}

    </PageShell>
  )
}


export default InvestmentsPage