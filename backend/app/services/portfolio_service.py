from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app.extensions import db
from app.models.account import Account
from app.models.user import User
from app.models.deposits_savings import Deposit, Saving, SavingPayment, LedgerTransaction, LedgerEntry
from app.models.market import MarketHolding, MarketTransaction
from app.models.simulation_setting import SimulationSetting
from app.models.features import SavingGoal, AssetSnapshot, Badge, UserBadge
from app.services import market_data_service
from app.services.feature_common import fail, get_row, serialize
from app.services.investment_calculations import to_krw
from app.services.goal_badge_policy import badge_criteria, record_creation_baseline


def today():
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def valuation(user_id):
    account = Account.query.filter_by(user_id=user_id).first()
    if account is None:
        fail("ACCOUNT_NOT_FOUND", "가상 계좌를 찾을 수 없습니다.", 404)
    amounts = {"cash": account.balance,
               "deposit": sum(x.principal for x in Deposit.query.filter_by(user_id=user_id, status="ACTIVE")),
               "saving": sum(x.total_paid_principal for x in Saving.query.filter_by(user_id=user_id, status="ACTIVE")),
               "kr_stock": 0, "us_stock": 0, "kr_etf": 0, "us_etf": 0}
    holdings = MarketHolding.query.filter(MarketHolding.user_id == user_id, MarketHolding.quantity > 0).all()
    rate = market_data_service.fetch_exchange_rate() if any(h.asset.market == "US" for h in holdings) else None
    if rate is not None and (not Decimal(rate).is_finite() or rate <= 0):
        fail("MARKET_DATA_UNAVAILABLE", "유효한 환율이 필요합니다.", 503)
    details, cost = [], 0
    for h in holdings:
        quote = market_data_service.fetch_quote(h.asset.symbol, h.asset.market)
        price = Decimal(quote["price"])
        if not price.is_finite() or price <= 0:
            fail("MARKET_DATA_UNAVAILABLE", "유효한 시장가격이 필요합니다.", 503)
        amount = to_krw(price * h.quantity, rate if h.asset.market == "US" else None)
        key = f"{h.asset.market.lower()}_{h.asset.asset_type.lower()}"
        amounts[key] += amount
        cost += h.total_acquisition_cost_krw
        details.append({"asset_id": h.asset_id, "symbol": h.asset.symbol, "name": h.asset.name,
                        "market": h.asset.market, "asset_type": h.asset.asset_type,
                        "quantity": str(h.quantity), "price": str(price), "value_krw": amount,
                        "acquisition_cost_krw": h.total_acquisition_cost_krw,
                        "unrealized_profit_krw": amount - h.total_acquisition_cost_krw})
    total = sum(amounts.values())
    # External virtual funding is not investment profit. Financial product
    # transfers cancel within total assets; only deposits' paid principal counts.
    funding = 0
    for ledger, entry in db.session.query(LedgerTransaction, LedgerEntry).join(LedgerEntry).filter(
        LedgerTransaction.user_id == user_id,
        LedgerTransaction.transaction_type.in_(["INITIAL_ASSET", "MONTHLY_INCOME", "MONTHLY_EXPENSE", "ADMIN_ADJUSTMENT"]),
    ):
        funding += entry.amount if entry.entry_type == "CREDIT" else -entry.amount
    market_value = sum(amounts[k] for k in ("kr_stock", "us_stock", "kr_etf", "us_etf"))
    bought = sold = 0
    for transaction in MarketTransaction.query.filter_by(user_id=user_id):
        if transaction.side == "BUY":
            bought += transaction.amount_krw + transaction.fee
        else:
            sold += transaction.amount_krw - transaction.fee - transaction.tax
    market_profit = market_value + sold - bought
    return {"amounts": amounts, "total_assets": total, "net_funding": funding,
            "total_profit": total - funding,
            "investment_profit": market_profit,
            "investment_return_percent": round(market_profit / bought * 100, 4) if bought else None,
            "unrealized_profit": market_value - cost, "holdings": details,
            "exchange_rate": str(rate) if rate is not None else None,
            "allocation_percent": {k: round(v / total * 100, 4) if total else 0 for k, v in amounts.items()},
            "valued_at": datetime.utcnow().isoformat() + "Z"}


def goal_progress(goal, total):
    if goal.status == "COMPLETED":
        return 100
    return min(100, max(0, round(total / goal.target_amount * 100, 4)))


def initial_funding(user_id):
    return LedgerTransaction.query.filter_by(
        user_id=user_id, transaction_type="INITIAL_ASSET",
    ).order_by(LedgerTransaction.ledger_transaction_id.desc()).first()


def needs_target_update(goal, funding):
    # Legacy goals created before setup must not complete from setup alone.
    # A later valid edit (target > current assets) makes the goal eligible again.
    return bool(funding and goal.status == "ACTIVE"
                and goal.target_amount <= funding.amount
                and goal.created_at <= funding.created_at
                and goal.updated_at <= funding.created_at)


def goal_data(goal, total=None):
    data = serialize(goal)
    if total is not None:
        data["progress_percent"] = goal_progress(goal, total)
    data["requires_target_update"] = needs_target_update(goal, initial_funding(goal.user_id))
    data["badge_criteria"] = badge_criteria(goal)
    return data


def refresh_achievements(user_id, portfolio):
    # Every caller locks the user's account before evaluating or resetting.
    setting = SimulationSetting.query.filter_by(user_id=user_id).first()
    initialized = bool(setting and setting.is_initial_asset_set)
    funding = initial_funding(user_id)
    for goal in SavingGoal.query.filter_by(user_id=user_id, status="ACTIVE").with_for_update():
        if initialized and not needs_target_update(goal, funding) and portfolio["total_assets"] >= goal.target_amount:
            goal.status, goal.completed_at = "COMPLETED", datetime.utcnow()
    db.session.flush()
    completed = sum(
        badge_criteria(goal)["eligible"]
        for goal in SavingGoal.query.filter_by(user_id=user_id, status="COMPLETED")
    )
    paid_counts = db.session.query(SavingPayment.saving_id, func.count()).join(Saving).filter(
        Saving.user_id == user_id, SavingPayment.status == "PAID").group_by(SavingPayment.saving_id).all()
    eligible = {"FIRST_GOAL": initialized and completed >= 1, "THREE_GOALS": initialized and completed >= 3,
                "SAVING_SIX_PAYMENTS": any(count >= 6 for _, count in paid_counts),
                "INVESTMENT_TEN_PERCENT": (portfolio["investment_return_percent"] or 0) >= 10}
    owned = {x.badge_id for x in UserBadge.query.filter_by(user_id=user_id)}
    for badge in Badge.query.all():
        if eligible.get(badge.code) and badge.badge_id not in owned:
            db.session.add(UserBadge(user_id=user_id, badge_id=badge.badge_id))


def badge_data(user_id):
    return [{**serialize(item.badge), "acquired_at": item.acquired_at.isoformat() + "Z"}
            for item in UserBadge.query.filter_by(user_id=user_id).order_by(UserBadge.acquired_at)]


def dashboard(user_id):
    from app.services.account_service import get_account_by_user_id

    get_account_by_user_id(user_id)
    result = valuation(user_id)
    refresh_achievements(user_id, result)
    db.session.commit()

    setting = SimulationSetting.query.filter_by(user_id=user_id).first()

    result.update({
        "goals": [
            goal_data(g, result["total_assets"])
            for g in SavingGoal.query.filter_by(user_id=user_id)
        ],
        "badges": badge_data(user_id),
        "monthly_income": setting.monthly_income if setting else 0,
        "monthly_expense": setting.monthly_expense if setting else 0,
        "monthly_surplus": (
            setting.monthly_income - setting.monthly_expense if setting else 0
        ),
        # 기존 예금 정보에 연결된 상품명과 은행명을 추가합니다.
        "active_deposits": [
            {
                **serialize(x),
                "product_name": x.product.product_name,
                "bank_name": x.product.bank_name,
            }
            for x in Deposit.query.filter_by(user_id=user_id, status="ACTIVE")
        ],
        # 기존 적금 정보에도 같은 방식으로 이름을 추가합니다.
        "active_savings": [
            {
                **serialize(x),
                "product_name": x.product.product_name,
                "bank_name": x.product.bank_name,
            }
            for x in Saving.query.filter_by(user_id=user_id, status="ACTIVE")
        ],
        "recent_trades": [
            serialize(x)
            for x in MarketTransaction.query.filter_by(user_id=user_id)
            .order_by(MarketTransaction.executed_at.desc())
            .limit(5)
        ],
    })

    return result


def save_goal(user_id, payload, goal_id=None):
    from app.services.account_service import get_account_by_user_id
    get_account_by_user_id(user_id)
    setting = SimulationSetting.query.filter_by(user_id=user_id).first()
    if not setting or not setting.is_initial_asset_set:
        fail("INITIAL_ASSET_REQUIRED", "가상 계좌에서 초기 자산을 먼저 설정한 뒤 목표를 만들어 주세요.", 422)
    goal = get_row(SavingGoal, goal_id, owner=user_id, lock=True) if goal_id else SavingGoal(user_id=user_id)
    if goal_id and goal.status != "ACTIVE":
        fail("GOAL_COMPLETED", "완료된 목표는 수정할 수 없습니다.", 409)
    if not goal_id and SavingGoal.query.filter_by(user_id=user_id).count() >= 5:
        fail("GOAL_LIMIT", "저축 목표는 최대 5개입니다.", 422)
    merged = {key: payload.get(key, getattr(goal, key, None)) for key in ("goal_name", "target_amount", "target_date")}
    created_on = today()
    if merged["target_date"] <= created_on:
        fail("INVALID_TARGET_DATE", "목표일은 오늘 이후여야 합니다.", 422)
    portfolio = valuation(user_id)
    current = portfolio["total_assets"]
    if merged["target_amount"] <= current:
        fail("INVALID_TARGET_AMOUNT", "목표 금액은 현재 총자산보다 커야 합니다.", 422)
    for key, value in merged.items():
        setattr(goal, key, value)
    db.session.add(goal)
    db.session.flush()
    if not goal_id:
        record_creation_baseline(goal, current, created_on)
    refresh_achievements(user_id, portfolio)
    db.session.commit()
    return goal_data(goal, current)


def record_daily_snapshots():
    from flask import current_app
    from app.services.account_service import get_account_by_user_id
    result = {"recorded": 0, "failed": 0}
    ids = [uid for uid, in db.session.query(User.user_id).filter_by(status="ACTIVE")]
    for uid in ids:
        try:
            get_account_by_user_id(uid)
            portfolio = valuation(uid)
            row = AssetSnapshot.query.filter_by(user_id=uid, snapshot_date=today()).first()
            if row is None:
                row = AssetSnapshot(user_id=uid, snapshot_date=today())
                db.session.add(row)
            row.amounts, row.total_assets = portfolio["amounts"], portfolio["total_assets"]
            row.recorded_at = datetime.utcnow()
            refresh_achievements(uid, portfolio)
            db.session.commit()
            result["recorded"] += 1
        except Exception:
            db.session.rollback()
            result["failed"] += 1
            current_app.logger.exception("Snapshot failed for user %s", uid)
    return result
