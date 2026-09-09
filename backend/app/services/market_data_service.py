"""
외부 시장 데이터(yfinance) 접근 계층.

- 현재가 조회
- 종목 검색
- USD/KRW 환율 조회
- 거래소 현지 시간 기준 시장 세션 판단

DB에 접근하지 않으며, 순수하게 외부 데이터만 다룬다.
"""

from datetime import date, datetime, time
from functools import lru_cache
from decimal import Decimal
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
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


# 평소 시간 참고값. 정규장 판정에는 아래 고정값 대신 당일 캘린더를 사용한다.
KR_REGULAR_OPEN = time(9, 0)
KR_REGULAR_CLOSE = time(15, 30)
US_PRE_OPEN = time(4, 0)
US_REGULAR_OPEN = time(9, 30)
US_REGULAR_CLOSE = time(16, 0)
US_AFTER_CLOSE = time(20, 0)
US_EARLY_AFTER_CLOSE = time(17, 0)

CALENDAR_NAMES = {
    Market.KR: "XKRX",
    Market.US: "XNYS",
}
MARKET_TIMEZONES = {
    Market.KR: KST,
    Market.US: ET,
}

# exchange-calendars 4.13.2에 빠진 확정 휴장일을 보완한다.
# 2026-06-03: 제9회 전국동시지방선거일.
# 제헌절은 아래 _get_regular_session_bounds에서 2026년부터 매년 반영한다.
EXTRA_CLOSED_DATES = {
    Market.KR: frozenset({date(2026, 6, 3)}),
    Market.US: frozenset(),
}

# 거래소 공지로 확인한 특별 개장/폐장 시간만 이 표에 추가한다.
# 형식: date(연도, 월, 일): (time(개장시, 분), time(폐장시, 분))
# 모두 한국 현지 시각이다. 휴장일을 거래일로 바꾸는 용도로 사용하지 않는다.
KR_SESSION_OVERRIDES = {}

# 2026-11-19 수능일은 확인됐지만, 이 수정 시점(2026-09-09)에
# 해당일 KRX 거래시간 공지는 확인하지 못했다. 기본 09:00~15:30을
# 적용하지 않는다. 공지 확인 후 위 표에 정확한 시간을 추가하면 해제된다.
# 수능 시행일 출처:
# https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=100526&lev=0&m=0204
KR_PENDING_SESSION_DATES = frozenset({date(2026, 11, 19)})


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


@lru_cache(maxsize=4)
def _get_exchange_calendar(calendar_name, year):
    """거래소별 연간 캘린더를 재사용한다. 조회 실패 결과는 캐시하지 않는다."""
    return xcals.get_calendar(
        calendar_name,
        start=f"{year:04d}-01-01",
        end=f"{year:04d}-12-31",
    )


def _get_regular_session_bounds(market, trading_date):
    """당일 정규장 (개장, 폐장)을 반환한다. 휴장일은 None, 실패는 503이다."""
    if trading_date in EXTRA_CLOSED_DATES[market]:
        return None

    # 2026년부터 공휴일로 복원된 제헌절. 이 공휴일에 대체일을 추정하지 않는다.
    # https://www.mpm.go.kr/mpm/comm/newsPress/newsPressRelease/?boardId=bbs_0000000000000029&cntId=4250&mode=view
    if (
        market == Market.KR
        and trading_date.year >= 2026
        and (trading_date.month, trading_date.day) == (7, 17)
    ):
        return None

    if (
        market == Market.KR
        and trading_date in KR_PENDING_SESSION_DATES
        and trading_date not in KR_SESSION_OVERRIDES
    ):
        raise BusinessException(
            code="MARKET_CALENDAR_UNAVAILABLE",
            message="오늘의 특별 거래시간 확인이 필요하여 주문할 수 없습니다.",
            status_code=503,
        )

    try:
        calendar = _get_exchange_calendar(CALENDAR_NAMES[market], trading_date.year)
        day = trading_date.isoformat()
        # 1월 1일·연말 휴장일도 정상적으로 빈 일정으로 조회한다.
        schedule = calendar.schedule.loc[day:day]
        if schedule.empty:
            return None

        session = schedule.iloc[0]
        opens_at = session["open"].to_pydatetime()
        closes_at = session["close"].to_pydatetime()

        if market == Market.KR and trading_date in KR_SESSION_OVERRIDES:
            open_time, close_time = KR_SESSION_OVERRIDES[trading_date]
            opens_at = datetime.combine(trading_date, open_time, tzinfo=KST)
            closes_at = datetime.combine(trading_date, close_time, tzinfo=KST)

        if (
            opens_at.tzinfo is None
            or closes_at.tzinfo is None
            or not opens_at < closes_at
        ):
            raise ValueError("Invalid exchange session bounds")

        return opens_at, closes_at

    except Exception as error:
        # 캘린더 오류·지원 범위 초과를 '거래 가능'이나 '휴장'으로 숨기지 않는다.
        raise BusinessException(
            code="MARKET_CALENDAR_UNAVAILABLE",
            message="거래소 일정을 확인할 수 없어 주문할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            status_code=503,
        ) from error


def get_market_session(market):
    """서버 현재 시각과 거래소의 당일 개장·폐장 시각으로 세션을 판단한다."""
    try:
        market = Market(market)
    except (TypeError, ValueError) as error:
        raise BusinessException(
            code=InvestmentErrorCode.INVALID_REQUEST,
            message="지원하지 않는 시장입니다.",
            status_code=400,
        ) from error

    now = datetime.now(MARKET_TIMEZONES[market])
    bounds = _get_regular_session_bounds(market, now.date())
    if bounds is None:
        return MarketSession.HOLIDAY

    opens_at, closes_at = bounds
    # 개장 시각부터 허용하고, 폐장 시각부터는 정규장 주문을 막는다.
    if opens_at <= now < closes_at:
        return MarketSession.REGULAR

    if market == Market.KR:
        return MarketSession.CLOSED

    # 미국 프리/애프터는 기존 화면의 세션 구분용이다.
    # 실제 주문은 기존 TRADABLE_SESSIONS 정책대로 정규장에서만 체결한다.
    pre_opens_at = datetime.combine(now.date(), US_PRE_OPEN, tzinfo=ET)
    if pre_opens_at <= now < opens_at:
        return MarketSession.PRE_MARKET

    # 미국 주식/ETF의 조기 폐장일에는 애프터 표시도 17:00에 끝낸다.
    # https://www.nyse.com/trade/hours-calendars
    after_close_time = (
        US_EARLY_AFTER_CLOSE
        if closes_at.astimezone(ET).time() < US_REGULAR_CLOSE
        else US_AFTER_CLOSE
    )
    after_closes_at = datetime.combine(now.date(), after_close_time, tzinfo=ET)
    if closes_at <= now < after_closes_at:
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