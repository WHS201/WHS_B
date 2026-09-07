"""
주식 / ETF 도메인 서비스.

트랜잭션 경계는 이 계층이 단독으로 소유한다.
하위 함수(debit/credit/create_ledger)는 commit하지 않으며,
주문 서비스가 마지막에 한 번만 commit한다.
"""

from decimal import Decimal

from app.constants import (
    LEDGER_REFERENCE_TYPE_MARKET,
    TRADABLE_SESSIONS,
    AssetType,
    InvestmentErrorCode,
    Market,
    OrderSide,
    EntryType,
    TransactionType,
)
from app.errors.exceptions import BusinessException
from app.extensions import db
from app.models.market import (
    MarketAsset,
    MarketHolding,
    MarketTransaction,
)
from app.services import market_data_service
from app.services.account_service import (
    credit,
    debit,
    get_account_by_user_id,
)
from app.services.investment_calculations import (
    calculate_fee,
    calculate_settlement,
    calculate_tax,
    serialize_price,
    to_krw,
)
from app.services.ledger_service import create_ledger


# ----------------------------------------------------------------
# 종목 목록 조회

def get_assets(
    market=None,
    search="",
):
    """
    투자 화면에 표시할 종목 목록을 반환한다.

    검색어가 없을 때:
        DB에서 최대 20개만 반환

    검색어가 있을 때:
        DB 전체 종목에서 이름/코드 검색
        최대 50개 반환

    미국 종목은 DB 검색 결과가 부족하면
        Yahoo Finance 검색 결과도 추가한다.
    """

    if market:
        market = (
            market
            .strip()
            .upper()
        )

        if market not in {
            "KR",
            "US",
        }:
            raise BusinessException(
                code="INVALID_MARKET",
                message="지원하지 않는 시장입니다.",
                status_code=422,
            )

    search = (
        search
        or ""
    ).strip()


    query = MarketAsset.query.filter_by(
        is_active=True,
    )


    if market:
        query = query.filter_by(
            market=market,
        )


    # ------------------------------------------------------------
    # 검색어가 있는 경우
    #
    # DB 전체 종목을 대상으로 부분 검색한다.

    if search:
        keyword = f"%{search}%"

        query = query.filter(
            db.or_(
                MarketAsset.symbol.ilike(
                    keyword,
                ),
                MarketAsset.name.ilike(
                    keyword,
                ),
            )
        )

        db_assets = (
            query
            .order_by(
                MarketAsset.name.asc(),
            )
            .limit(50)
            .all()
        )


    # ------------------------------------------------------------
    # 검색어가 없는 경우
    #
    # 수천 종목을 화면에 모두 보내지 않고 20개만 보여준다.

    else:
        db_assets = (
            query
            .order_by(
                MarketAsset.asset_id.asc(),
            )
            .limit(20)
            .all()
        )


    results = [
        {
            "asset_id":
                asset.asset_id,

            "symbol":
                asset.symbol,

            "name":
                asset.name,

            "asset_type":
                asset.asset_type,

            "market":
                asset.market,

            "is_active":
                asset.is_active,

            "source":
                "DB",
        }
        for asset in db_assets
    ]


    # ------------------------------------------------------------
    # 검색어가 없으면 DB 기본 목록만 반환

    if not search:
        return results


    # ------------------------------------------------------------
    # 국내 종목
    #
    # 국내는 전체 종목 마스터가 DB에 있으므로
    # Yahoo 검색을 사용하지 않는다.

    if market == "KR":
        return results


    # ------------------------------------------------------------
    # 미국 종목
    #
    # 기존 방식처럼 Yahoo Finance 검색 결과도 합친다.

    external_assets = (
        market_data_service
        .search_assets(
            query=search,
            market=market,
            max_results=20,
        )
    )


    existing_keys = {
        (
            item["symbol"],
            item["market"],
        )
        for item in results
    }


    for asset in external_assets:

        key = (
            asset["symbol"],
            asset["market"],
        )

        if key in existing_keys:
            continue

        results.append({
            "asset_id": None,
            "symbol": asset["symbol"],
            "name": asset["name"],
            "asset_type": asset["asset_type"],
            "market": asset["market"],
            "is_active": True,
            "source": "YFINANCE",
        })

        existing_keys.add(
            key,
        )

        # 검색 결과가 지나치게 많아지지 않게 제한
        if len(results) >= 50:
            break


    return results

# ----------------------------------------------------------------
# 현재가 조회

def get_price(symbol, market):
    """
    종목의 현재가를 조회한다.

    미국 종목은 환율과 원화 환산 가격을 함께 반환한다.
    """

    market = Market(market)
    symbol = symbol.strip().upper()

    quote = market_data_service.fetch_quote(
        symbol,
        market,
    )

    session = market_data_service.get_market_session(
        market,
    )

    result = {
        "symbol": symbol,
        "market": market.value,
        "name": quote["name"],
        "asset_type": _resolve_asset_type(
            symbol,
            market,
        ).value,
        "price": serialize_price(
            quote["price"],
            market,
        ),
        "currency": quote["currency"],
        "market_session": session.value,
        "is_tradable": (
            session
            in TRADABLE_SESSIONS[market]
        ),
    }

    # 미국 종목만 환율 정보를 포함한다
    if market == Market.US:
        exchange_rate = (
            market_data_service
            .fetch_exchange_rate()
        )

        result["exchange_rate"] = float(
            exchange_rate
        )

        result["price_krw"] = to_krw(
            quote["price"],
            exchange_rate,
        )

    return result


# ----------------------------------------------------------------
# 주문

def create_order(
    user_id,
    symbol,
    market,
    side,
    quantity,
):
    """
    시장가 주문을 체결한다.

    처리 순서:
        시장 상태 확인
        → 현재가 확인
        → 환율 확인
        → 원화 금액 계산
        → 계좌 잔액 변경
        → 거래 기록 생성
        → 원장 기록
        → 보유자산 반영
        → commit
    """

    market = Market(market)
    side = OrderSide(side)
    quantity = Decimal(quantity)

    try:
        account = get_account_by_user_id(
            user_id
        )

        # 매도는 주문 전에 보유 수량을 먼저 확인한다
        if side == OrderSide.SELL:
            asset = _find_asset(
                symbol,
                market,
            )

            holding = _find_holding(
                user_id,
                asset.asset_id,
            )

            if holding.quantity < quantity:
                raise BusinessException(
                    code=(
                        InvestmentErrorCode
                        .INSUFFICIENT_HOLDINGS
                    ),
                    message="보유 수량이 부족합니다.",
                    status_code=422,
                )

        session = _require_tradable_session(
            market
        )

        quote = (
            market_data_service
            .fetch_quote(
                symbol,
                market,
            )
        )

        exchange_rate = (
            _resolve_exchange_rate(
                market
            )
        )

        if side == OrderSide.BUY:
            asset = _get_or_create_asset(
                symbol,
                market,
                quote["name"],
            )

        amount = (
            quote["price"]
            * quantity
        )

        amount_krw = to_krw(
            amount,
            exchange_rate,
        )

        fee = calculate_fee(
            amount_krw,
            market,
        )

        tax = calculate_tax(
            amount_krw,
            market,
            side,
        )

        settlement_amount_krw = (
            calculate_settlement(
                amount_krw,
                fee,
                tax,
                side,
            )
        )

        # 1. 계좌 잔액 변경
        if side == OrderSide.BUY:
            debit(
                account,
                settlement_amount_krw,
            )

        else:
            credit(
                account,
                settlement_amount_krw,
            )

        # 2. 거래 기록 생성
        transaction = MarketTransaction(
            user_id=user_id,
            asset_id=asset.asset_id,
            side=side.value,
            quantity=quantity,
            price=quote["price"],
            exchange_rate=exchange_rate,
            amount=amount,
            amount_krw=amount_krw,
            market_session=session.value,
            fee=fee,
            tax=tax,
        )

        db.session.add(
            transaction
        )

        db.session.flush()

        # 3. 원장 기록
        create_ledger(
            account=account,
            transaction_type=(
                TransactionType
                .STOCK_BUY
                .value
                if side == OrderSide.BUY
                else TransactionType
                .STOCK_SELL
                .value
            ),
            amount=settlement_amount_krw,
            entry_type=(
                EntryType
                .DEBIT
                .value
                if side == OrderSide.BUY
                else EntryType
                .CREDIT
                .value
            ),
            reference_type=(
                LEDGER_REFERENCE_TYPE_MARKET
            ),
            reference_id=(
                transaction
                .market_transaction_id
            ),
        )

        # 4. 보유자산 반영
        if side == OrderSide.BUY:
            holding = (
                _get_or_create_holding(
                    user_id,
                    asset.asset_id,
                )
            )

            _increase_holding(
                holding,
                quantity,
                amount,
                settlement_amount_krw,
            )

        else:
            _reduce_holding(
                holding,
                quantity,
            )

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    return _build_order_result(
        transaction=transaction,
        asset=asset,
        market=market,
        settlement_amount_krw=(
            settlement_amount_krw
        ),
        balance_after=account.balance,
        holding_quantity=(
            holding.quantity
        ),
    )


# ----------------------------------------------------------------
# 초기화

def reset_investment_data(user_id):
    """
    사용자의 주식/ETF 데이터를 삭제한다.

    시뮬레이션 초기화에서 호출하는 내부 함수이며,
    commit / rollback은 호출하는 상위 Service가 책임진다.

    market_holdings와 market_transactions는
    서로 참조하지 않고 각각
    users / market_assets만 참조하므로
    삭제 순서에 제약은 없다.

    market_assets는 사용자 데이터가 아닌
    공용 종목 정보이므로 삭제하지 않는다.
    """

    deleted_holdings = (
        MarketHolding.query
        .filter_by(
            user_id=user_id,
        )
        .delete(
            synchronize_session=False
        )
    )

    deleted_transactions = (
        MarketTransaction.query
        .filter_by(
            user_id=user_id,
        )
        .delete(
            synchronize_session=False
        )
    )

    return {
        "deleted_holdings":
            deleted_holdings,
        "deleted_transactions":
            deleted_transactions,
    }


# ----------------------------------------------------------------
# 시장 상태

def _require_tradable_session(
    market,
):
    """
    거래 가능한 세션인지 확인한다.
    """

    session = (
        market_data_service
        .get_market_session(
            market
        )
    )

    if (
        session
        not in TRADABLE_SESSIONS[market]
    ):
        raise BusinessException(
            code=(
                InvestmentErrorCode
                .MARKET_CLOSED
            ),
            message=(
                "현재 거래 가능한 시간이 아닙니다."
            ),
            status_code=422,
        )

    return session


def _resolve_exchange_rate(
    market,
):
    """
    미국 종목이면 환율을 조회하고,
    국내 종목이면 None을 반환한다.
    """

    if market == Market.US:
        return (
            market_data_service
            .fetch_exchange_rate()
        )

    return None


# ----------------------------------------------------------------
# 종목

def _resolve_asset_type(
    symbol,
    market,
):
    """
    자산 유형을 판단한다.

    DB에 등록된 종목이면 저장된 값을 사용하고,
    없으면 외부 시장 데이터로 판단한다.
    """

    asset = (
        MarketAsset.query
        .filter_by(
            symbol=symbol
        )
        .first()
    )

    if asset is not None:
        return AssetType(
            asset.asset_type
        )

    return (
        market_data_service
        .resolve_asset_type(
            symbol,
            market,
        )
    )


def _get_or_create_asset(
    symbol,
    market,
    name,
):
    """
    DB에 종목이 없으면 자동 등록한다.

    PRD:
    주요 종목은 DB에 저장하고,
    그 외 종목은 사용자가 조회할 때
    외부 데이터로 가져온다.
    """

    symbol = (
        symbol
        .strip()
        .upper()
    )

    asset = (
        MarketAsset.query
        .filter_by(
            symbol=symbol
        )
        .first()
    )

    if asset is not None:
        return asset

    asset = MarketAsset(
        symbol=symbol,
        name=name,
        asset_type=(
            market_data_service
            .resolve_asset_type(
                symbol,
                market,
            )
            .value
        ),
        market=market.value,
        is_active=True,
    )

    db.session.add(
        asset
    )

    db.session.flush()

    return asset


def _find_asset(
    symbol,
    market,
):
    """
    등록된 종목을 조회한다.

    매도는 보유 이력이 있어야 하므로
    자동 등록하지 않는다.
    """

    asset = (
        MarketAsset.query
        .filter_by(
            symbol=(
                symbol
                .strip()
                .upper()
            )
        )
        .first()
    )

    if asset is None:
        raise BusinessException(
            code=(
                InvestmentErrorCode
                .ASSET_NOT_FOUND
            ),
            message="등록되지 않은 종목입니다.",
            status_code=404,
        )

    return asset


# ----------------------------------------------------------------
# 보유자산

def _get_or_create_holding(
    user_id,
    asset_id,
):
    """
    보유 기록을 가져오거나 새로 만든다.
    """

    holding = (
        MarketHolding.query
        .filter_by(
            user_id=user_id,
            asset_id=asset_id,
        )
        .first()
    )

    if holding is not None:
        return holding

    holding = MarketHolding(
        user_id=user_id,
        asset_id=asset_id,
        quantity=Decimal("0"),
        total_acquisition_cost=(
            Decimal("0")
        ),
        total_acquisition_cost_krw=0,
    )

    db.session.add(
        holding
    )

    db.session.flush()

    return holding


def _find_holding(
    user_id,
    asset_id,
):
    """
    보유 기록을 조회한다.
    없으면 매도할 수 없다.
    """

    holding = (
        MarketHolding.query
        .filter_by(
            user_id=user_id,
            asset_id=asset_id,
        )
        .first()
    )

    if (
        holding is None
        or holding.quantity <= 0
    ):
        raise BusinessException(
            code=(
                InvestmentErrorCode
                .INSUFFICIENT_HOLDINGS
            ),
            message="보유하지 않은 종목입니다.",
            status_code=422,
        )

    return holding


def _increase_holding(
    holding,
    quantity,
    amount,
    settlement_amount_krw,
):
    """
    매수 수량과 취득원가를 누적한다.

    원화 원가에는 수수료를 포함한다.
    """

    holding.quantity = (
        holding.quantity
        + quantity
    )

    holding.total_acquisition_cost = (
        holding.total_acquisition_cost
        + amount
    )

    holding.total_acquisition_cost_krw = (
        holding.total_acquisition_cost_krw
        + settlement_amount_krw
    )


def _reduce_holding(
    holding,
    quantity,
):
    """
    매도 수량만큼 보유 정보를 줄인다.

    취득원가는 평균 단가 기준으로 비례 차감하여
    남은 수량의 평균 단가가 유지되도록 한다.
    """

    ratio = (
        quantity
        / holding.quantity
    )

    holding.quantity = (
        holding.quantity
        - quantity
    )

    holding.total_acquisition_cost = (
        holding.total_acquisition_cost
        - (
            holding.total_acquisition_cost
            * ratio
        )
    )

    holding.total_acquisition_cost_krw = int(
        Decimal(
            holding.total_acquisition_cost_krw
        )
        - (
            Decimal(
                holding.total_acquisition_cost_krw
            )
            * ratio
        )
    )

    # 전량 매도 시 잔여 원가를 0으로 정리한다
    if holding.quantity <= 0:
        holding.quantity = Decimal("0")
        holding.total_acquisition_cost = (
            Decimal("0")
        )
        holding.total_acquisition_cost_krw = 0


# ----------------------------------------------------------------
# 응답

def _build_order_result(
    transaction,
    asset,
    market,
    settlement_amount_krw,
    balance_after,
    holding_quantity,
):
    """
    주문 응답 데이터를 구성한다.
    """

    return {
        "market_transaction_id":
            transaction.market_transaction_id,

        "symbol":
            asset.symbol,

        "market":
            asset.market,

        "name":
            asset.name,

        "asset_type":
            asset.asset_type,

        "side":
            transaction.side,

        "quantity":
            int(transaction.quantity),

        "price":
            serialize_price(
                transaction.price,
                market,
            ),

        "currency":
            (
                "KRW"
                if market == Market.KR
                else "USD"
            ),

        "exchange_rate":
            (
                float(
                    transaction.exchange_rate
                )
                if (
                    transaction.exchange_rate
                    is not None
                )
                else None
            ),

        "amount":
            serialize_price(
                transaction.amount,
                market,
            ),

        "amount_krw":
            transaction.amount_krw,

        "fee":
            transaction.fee,

        "tax":
            transaction.tax,

        "settlement_amount_krw":
            settlement_amount_krw,

        "balance_after":
            balance_after,

        "holding_quantity":
            int(
                holding_quantity
            ),

        "market_session":
            transaction.market_session,

        "executed_at":
            (
                transaction.executed_at
                .isoformat()
                + "Z"
            ),
    }