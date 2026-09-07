"""
외부 시장 데이터(yfinance) 접근 계층.

- 현재가 조회
- 종목 검색
- USD/KRW 환율 조회
- 거래소 현지 시간 기준 시장 세션 판단

DB에 접근하지 않으며, 순수하게 외부 데이터만 다룬다.
"""

from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

import yfinance as yf

from app.constants import (
    EXCHANGE_RATE_TICKER,
    InvestmentErrorCode,
    Market,
    MarketSession,
)
from app.errors.exceptions import BusinessException


KST = ZoneInfo("Asia/Seoul")
ET = ZoneInfo("America/New_York")


# 국내 정규장 09:00 ~ 15:30 (KST)

KR_REGULAR_OPEN = time(9, 0)
KR_REGULAR_CLOSE = time(15, 30)


# 미국 프리 04:00 / 정규 09:30 ~ 16:00 / 애프터 ~ 20:00 (ET)

US_PRE_OPEN = time(4, 0)
US_REGULAR_OPEN = time(9, 30)
US_REGULAR_CLOSE = time(16, 0)
US_AFTER_CLOSE = time(20, 0)


def build_ticker_symbols(symbol, market):
    """
    yfinance 조회용 티커 목록을 만든다.

    국내는 코스피(.KS)와 코스닥(.KQ)을 구분할 수 없으므로
    두 개를 순서대로 시도한다.
    """

    symbol = symbol.strip().upper()

    if market == Market.KR:
        return [
            f"{symbol}.KS",
            f"{symbol}.KQ",
        ]

    return [symbol]


def get_market_session(market):
    """거래소 현지 시간 기준으로 현재 시장 세션을 판단한다."""

    if market == Market.KR:
        now = datetime.now(KST)

        # 주말은 휴장
        if now.weekday() >= 5:
            return MarketSession.HOLIDAY

        current = now.time()

        if KR_REGULAR_OPEN <= current < KR_REGULAR_CLOSE:
            return MarketSession.REGULAR

        return MarketSession.CLOSED

    now = datetime.now(ET)

    if now.weekday() >= 5:
        return MarketSession.HOLIDAY

    current = now.time()

    if US_PRE_OPEN <= current < US_REGULAR_OPEN:
        return MarketSession.PRE_MARKET

    if US_REGULAR_OPEN <= current < US_REGULAR_CLOSE:
        return MarketSession.REGULAR

    if US_REGULAR_CLOSE <= current < US_AFTER_CLOSE:
        return MarketSession.AFTER_MARKET

    return MarketSession.CLOSED


def search_assets(query, market=None, max_results=20):
    """
    Yahoo Finance에서 종목명 또는 종목코드로 검색한다.

    반환 예:
    [
        {
            "symbol": "AMD",
            "name": "Advanced Micro Devices, Inc.",
            "asset_type": "STOCK",
            "market": "US",
        }
    ]
    """

    query = (query or "").strip()

    if not query:
        return []

    try:
        search = yf.Search(
            query,
            max_results=max_results,
            news_count=0,
            lists_count=0,
            include_cb=False,
            include_nav_links=False,
            include_research=False,
            enable_fuzzy_query=True,
        )

        results = []

        for item in search.quotes:
            raw_symbol = (
                item.get("symbol")
                or ""
            ).strip().upper()

            if not raw_symbol:
                continue

            quote_type = (
                item.get("quoteType")
                or ""
            ).upper()

            # 주식과 ETF만 허용
            if quote_type not in {
                "EQUITY",
                "ETF",
            }:
                continue

            exchange = (
                item.get("exchange")
                or ""
            ).upper()

            # --------------------------------------------------
            # 국내 종목

            if raw_symbol.endswith(".KS") or raw_symbol.endswith(".KQ"):
                detected_market = "KR"
                symbol = raw_symbol.rsplit(".", 1)[0]

            # --------------------------------------------------
            # 미국 종목

            elif exchange in {
                "NMS",
                "NYQ",
                "NGM",
                "NCM",
                "ASE",
                "NASDAQ",
                "NYSE",
            }:
                detected_market = "US"
                symbol = raw_symbol

            else:
                continue

            # 사용자가 국내/미국을 선택했다면 해당 시장만 반환
            if market and detected_market != market:
                continue

            name = (
                item.get("shortname")
                or item.get("longname")
                or item.get("shortName")
                or item.get("longName")
                or symbol
            )

            results.append({
                "symbol": symbol,
                "name": name,
                "asset_type": (
                    "ETF"
                    if quote_type == "ETF"
                    else "STOCK"
                ),
                "market": detected_market,
            })

        return results[:max_results]

    except Exception:
        return []


def fetch_quote(symbol, market):
    """
    현재가와 종목명을 조회한다.

    반환:
        {
            "ticker": "005930.KS",
            "name": "Samsung Electronics",
            "price": Decimal("71000"),
            "currency": "KRW",
        }
    """

    last_error = None

    for ticker_symbol in build_ticker_symbols(
        symbol,
        market,
    ):
        try:
            ticker = yf.Ticker(
                ticker_symbol
            )

            info = ticker.fast_info

            price = (
                info.get("last_price")
                if hasattr(info, "get")
                else None
            )

            if price is None:
                price = getattr(
                    info,
                    "last_price",
                    None,
                )

            if price is None:
                continue

            price = Decimal(
                str(price)
            )

            if price <= 0:
                continue

            name = _resolve_name(
                ticker,
                ticker_symbol,
            )

            return {
                "ticker": ticker_symbol,
                "name": name,
                "price": price,
                "currency": (
                    "KRW"
                    if market == Market.KR
                    else "USD"
                ),
            }

        except Exception as error:
            last_error = error
            continue

    raise BusinessException(
        code=InvestmentErrorCode.ASSET_NOT_FOUND,
        message="종목 정보를 찾을 수 없습니다.",
        status_code=404,
    ) from last_error


def _resolve_name(
    ticker,
    fallback,
):
    """종목명을 조회한다. 실패하면 티커를 그대로 사용한다."""

    try:
        info = ticker.get_info()

        return (
            info.get("shortName")
            or info.get("longName")
            or fallback
        )

    except Exception:
        return fallback


def resolve_asset_type(
    symbol,
    market,
):
    """
    ETF 여부를 판단한다.

    yfinance의 quoteType이 ETF면 ETF,
    아니면 STOCK으로 본다.
    """

    from app.constants import AssetType

    for ticker_symbol in build_ticker_symbols(
        symbol,
        market,
    ):
        try:
            info = (
                yf.Ticker(
                    ticker_symbol
                )
                .get_info()
            )

            quote_type = (
                info.get("quoteType")
                or ""
            ).upper()

            if quote_type == "ETF":
                return AssetType.ETF

            if quote_type:
                return AssetType.STOCK

        except Exception:
            continue

    return AssetType.STOCK


def fetch_exchange_rate():
    """USD/KRW 환율을 조회한다."""

    try:
        info = (
            yf.Ticker(
                EXCHANGE_RATE_TICKER
            )
            .fast_info
        )

        rate = (
            info.get("last_price")
            if hasattr(info, "get")
            else None
        )

        if rate is None:
            rate = getattr(
                info,
                "last_price",
                None,
            )

        if (
            rate is not None
            and rate > 0
        ):
            return Decimal(
                str(rate)
            )

    except Exception:
        pass

    raise BusinessException(
        code=InvestmentErrorCode.EXCHANGE_RATE_UNAVAILABLE,
        message="환율 정보를 가져올 수 없습니다.",
        status_code=503,
    )