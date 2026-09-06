"""Hypothetical projections only: no ORM writes, orders or ledger entries."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from marshmallow import Schema, fields, validate, validates_schema, ValidationError

from app.models.deposits_savings import Deposit, Saving, SavingPayment
from app.models.features import SavingGoal
from app.models.simulation_setting import SimulationSetting
from app.services.deposit_saving_calculations import add_months, calculate_deposit_result, calculate_saving_maturity
from app.services.feature_common import fail, get_row
from app.services.portfolio_service import today, valuation

ASSETS = ("cash", "saving", "kr_stock", "us_stock", "kr_etf", "us_etf")


class ProjectionSchema(Schema):
    initial_asset = fields.Integer(strict=True, validate=validate.Range(min=0, max=100000000))
    monthly_income = fields.Integer(strict=True, validate=validate.Range(min=0, max=10000000))
    monthly_expense = fields.Integer(strict=True, validate=validate.Range(min=0, max=10000000))
    months = fields.Integer(strict=True, validate=validate.Range(min=1, max=600))
    initial_allocation = fields.Dict(keys=fields.String(), values=fields.Integer(strict=True, validate=validate.Range(min=0, max=1000000000)))
    monthly_allocation = fields.Dict(required=True, keys=fields.String(), values=fields.Integer(strict=True, validate=validate.Range(min=0, max=10000000)))
    annual_returns = fields.Dict(required=True, keys=fields.String(), values=fields.Float(allow_nan=False, validate=validate.Range(min=-100, max=100)))
    initial_exchange_rate = fields.Float(allow_nan=False, validate=validate.Range(min=1, max=10000))
    future_exchange_rate = fields.Float(required=True, allow_nan=False, validate=validate.Range(min=1, max=10000))

    @validates_schema
    def validate_keys(self, data, **kwargs):
        for name, allowed in (("initial_allocation", ASSETS), ("monthly_allocation", (*ASSETS, "existing_saving")), ("annual_returns", ASSETS[1:])):
            if set(data.get(name, {})) - set(allowed):
                raise ValidationError({name: ["지원하지 않는 자산 분류입니다."]})
        if data["annual_returns"].get("saving", 0) < 0:
            raise ValidationError({"annual_returns": ["적금 가정 금리는 0 이상이어야 합니다."]})


def project(payload, user_id=None, goal_id=None):
    data = ProjectionSchema().load(payload)
    start = today()
    contracts, events, current = [], {}, None
    if goal_id is None:
        required = ("initial_asset", "monthly_income", "monthly_expense", "months", "initial_allocation", "initial_exchange_rate")
        if any(key not in data for key in required):
            fail("INVALID_REQUEST", "자유 시뮬레이션의 초기 자산·수입·지출·기간·배분·현재 환율이 필요합니다.")
        if data["monthly_allocation"].get("existing_saving", 0):
            fail("INVALID_REQUEST", "자유 시뮬레이션에는 기존 적금이 없습니다.")
        initial, income, expense = data["initial_asset"], data["monthly_income"], data["monthly_expense"]
        end = add_months(start, data["months"])
        balances = {k: Decimal(data["initial_allocation"].get(k, 0)) for k in ASSETS}
        if sum(balances.values()) != initial:
            fail("ALLOCATION_MISMATCH", "초기 배분 합계가 초기 자산과 일치해야 합니다.", 422)
        initial_fx = Decimal(str(data["initial_exchange_rate"]))
    else:
        if set(data) & {"initial_asset", "monthly_income", "monthly_expense", "months", "initial_allocation", "initial_exchange_rate"}:
            fail("INVALID_REQUEST", "목표 시뮬레이션의 현재 자산·수입·기간은 서버에서 가져옵니다.")
        goal = get_row(SavingGoal, goal_id, owner=user_id)
        end = goal.target_date
        if end <= start or end > add_months(start, 600):
            fail("INVALID_PERIOD", "미래 600개월 이내의 목표가 필요합니다.", 422)
        current = valuation(user_id)
        setting = SimulationSetting.query.filter_by(user_id=user_id).first()
        income, expense = (setting.monthly_income, setting.monthly_expense) if setting else (0, 0)
        initial = current["total_assets"]
        balances = {k: Decimal(current["amounts"].get(k, 0)) for k in ASSETS}
        balances["saving"] = Decimal(0)  # existing contracts are tracked separately
        initial_fx = Decimal(current["exchange_rate"] or "0")
        needs_fx = any(data["monthly_allocation"].get(k, 0) for k in ("us_stock", "us_etf"))
        if not initial_fx and needs_fx:
            from app.services.market_data_service import fetch_exchange_rate
            initial_fx = fetch_exchange_rate()
        elif not initial_fx:
            initial_fx = Decimal(str(data["future_exchange_rate"]))
        for row in Deposit.query.filter_by(user_id=user_id, status="ACTIVE"):
            contract = {"kind": "deposit", "principal": row.principal, "row": row, "active": True}
            contracts.append(contract)
        for row in Saving.query.filter_by(user_id=user_id, status="ACTIVE"):
            paid = [SimpleNamespace(amount=p.amount, scheduled_date=p.scheduled_date) for p in SavingPayment.query.filter_by(saving_id=row.saving_id, status="PAID")]
            contract = {"kind": "saving", "principal": row.total_paid_principal, "row": row, "active": True, "payments": paid}
            contracts.append(contract)
            processed = {p.payment_sequence for p in SavingPayment.query.filter_by(saving_id=row.saving_id)}
            for index in range(row.scheduled_payment_count):
                when = row.start_date if index == 0 else add_months(row.start_date.replace(day=1), index).replace(day=row.payment_day)
                if index + 1 not in processed and start < when <= end and when < row.maturity_date:
                    events.setdefault(when, []).append(("payment", contract))
        for contract in contracts:
            when = contract["row"].maturity_date
            # Overdue active contracts are settled hypothetically on the first
            # projected day; their original contractual maturity determines interest.
            if when <= end:
                events.setdefault(max(start + timedelta(days=1), when), []).append(("maturity", contract))
    allocation = data["monthly_allocation"]
    if expense > income or sum(allocation.values()) != income - expense:
        fail("ALLOCATION_MISMATCH", "월 배분 합계가 수입에서 지출을 뺀 금액과 일치해야 합니다.", 422)
    returns = {k: Decimal(str(data["annual_returns"].get(k, 0))) for k in ASSETS[1:]}
    future_fx = Decimal(str(data["future_exchange_rate"]))
    if not initial_fx.is_finite() or initial_fx <= 0:
        fail("MARKET_DATA_UNAVAILABLE", "유효한 현재 환율이 필요합니다.", 503)
    total_days = (end - start).days
    # Contributions occur at monthly anniversaries, after returns. Existing
    # contract payments follow their actual calendar dates.
    monthly_dates = set()
    for month in range(1, 601):
        when = add_months(start, month)
        if when > end:
            break
        monthly_dates.add(when)
    milestones = sorted(monthly_dates | set(events) | {end})
    previous, previous_fx = start, initial_fx
    contributions = gross_interest = tax = fx_effect = Decimal(0)
    missed = 0
    timeline = []
    for when in milestones:
        days = (when - previous).days
        next_fx = initial_fx + (future_fx - initial_fx) * Decimal((when - start).days) / total_days
        for key in ASSETS[1:]:
            # Annual effective return assumption; -100% becomes zero after a
            # positive interval. Additional savings use the same assumed curve.
            growth = Decimal(str(float(1 + returns[key] / 100) ** (days / 365))) if days else Decimal(1)
            old = balances[key]
            balances[key] *= growth
            if key == "saving":
                gross_interest += balances[key] - old
            if key.startswith("us_"):
                before_fx = balances[key]
                balances[key] *= next_fx / previous_fx
                fx_effect += balances[key] - before_fx
        if when in monthly_dates:
            contributions += income - expense
            for key in ASSETS:
                balances[key] += allocation.get(key, 0)
            balances["cash"] += allocation.get("existing_saving", 0)
        for kind, contract in sorted(events.get(when, []), key=lambda event: event[0] != "maturity"):
            row = contract["row"]
            if kind == "payment" and contract["active"]:
                if balances["cash"] >= row.monthly_amount:
                    balances["cash"] -= row.monthly_amount
                    contract["principal"] += row.monthly_amount
                    contract["payments"].append(SimpleNamespace(amount=row.monthly_amount, scheduled_date=when))
                else:
                    missed += 1
            elif kind == "maturity" and contract["active"]:
                if contract["kind"] == "deposit":
                    result = calculate_deposit_result(row.principal, row.applied_interest_rate, row.start_date, row.maturity_date, row.interest_method)
                    interest, taxes = result["expected_interest"], result["expected_tax"]
                else:
                    result = calculate_saving_maturity(contract["payments"], row.applied_interest_rate, row.maturity_date, row.interest_method)
                    interest, taxes = result["gross_interest"], result["tax_amount"]
                balances["cash"] += contract["principal"] + interest - taxes
                gross_interest += interest
                tax += taxes
                contract["active"] = False
        total = sum(balances.values()) + sum(c["principal"] for c in contracts if c["active"])
        if when in monthly_dates or when == end:
            timeline.append({"date": when.isoformat(), "total_assets": int(total)})
        previous, previous_fx = when, next_fx
    # Hypothetical additional saving interest is taxed at the horizon.
    saving_principal = (data.get("initial_allocation", {}).get("saving", 0) if goal_id is None else 0) + allocation.get("saving", 0) * len(monthly_dates)
    saving_tax = int(max(Decimal(0), balances["saving"] - saving_principal) * Decimal("0.154"))
    balances["saving"] -= saving_tax
    tax += saving_tax
    amounts = {k: int(v) for k, v in balances.items()}
    amounts["existing_deposit"] = sum(c["principal"] for c in contracts if c["active"] and c["kind"] == "deposit")
    amounts["existing_saving"] = sum(c["principal"] for c in contracts if c["active"] and c["kind"] == "saving")
    total = sum(amounts.values())
    timeline[-1]["total_assets"] = total
    result = {"is_hypothetical": True, "start_date": start.isoformat(), "end_date": end.isoformat(),
              "initial_assets": initial, "future_contributions": int(contributions),
              "amounts": amounts, "expected_total_assets": total, "expected_interest": int(gross_interest),
              "expected_tax": int(tax), "expected_net_interest": int(gross_interest - tax),
              "expected_investment_profit": total - initial - int(contributions) - int(gross_interest - tax),
              "exchange_rate_effect": int(fx_effect), "missed_payments": missed, "timeline": timeline,
              "assumptions": {"annual_returns": data["annual_returns"], "initial_exchange_rate": str(initial_fx),
                              "future_exchange_rate": str(future_fx), "contribution_timing": "monthly anniversary, after growth",
                              "fx_path": "linear", "new_savings": "assumed effective annual growth; tax at horizon",
                              "trading_fees": "not included", "future_returns_are_predictions": False}}
    if goal_id is not None:
        result.update(goal_id=goal_id, target_amount=goal.target_amount,
                      difference=total - goal.target_amount, progress_percent=round(total / goal.target_amount * 100, 4))
    return result
