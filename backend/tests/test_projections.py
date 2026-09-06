from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.account import Account
from app.models.deposits_savings import (
    Deposit, FinancialProduct, FinancialProductOption, LedgerTransaction, Saving, SavingPayment,
)
from app.models.features import AuditLog, SavingGoal
from app.models.simulation_setting import SimulationSetting


def free_payload(**overrides):
    return {
        "initial_asset": 1000, "monthly_income": 300, "monthly_expense": 100,
        "months": 3, "initial_allocation": {"cash": 600, "kr_stock": 400},
        "monthly_allocation": {"cash": 100, "kr_stock": 100},
        "annual_returns": {"kr_stock": 0},
        "initial_exchange_rate": 1300, "future_exchange_rate": 1300,
        **overrides,
    }


def assert_data(response):
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def seed_product(kind, code):
    product = FinancialProduct(external_product_code=code, bank_name="시험 은행", product_name=code, product_type=kind)
    db.session.add(product)
    db.session.flush()
    option = FinancialProductOption(
        product_id=product.product_id, term_months=12,
        base_interest_rate=0, max_interest_rate=0, interest_method="SIMPLE",
        min_amount=1, max_amount=100000000,
    )
    db.session.add(option)
    db.session.flush()
    return product.product_id, option.option_id


def test_zero_return_free_projection_has_known_result_and_no_financial_writes(client, auth):
    before_audit = AuditLog.query.count()
    result = assert_data(client.post("/api/simulations/free", headers=auth(), json=free_payload()))
    assert result["is_hypothetical"] is True
    assert result["expected_total_assets"] == 1600
    assert result["future_contributions"] == 600
    assert result["amounts"]["cash"] == 900
    assert result["amounts"]["kr_stock"] == 700
    assert [item["total_assets"] for item in result["timeline"]] == [1200, 1400, 1600]
    assert result["expected_interest"] == result["expected_tax"] == result["expected_investment_profit"] == 0
    assert Account.query.filter_by(user_id=1).one().balance == 1000
    assert LedgerTransaction.query.count() == 0
    assert SavingGoal.query.count() == 0
    assert AuditLog.query.count() == before_audit


def test_free_projection_exposes_foreign_exchange_effect(client, auth):
    result = assert_data(client.post("/api/simulations/free", headers=auth(), json=free_payload(
        months=1, monthly_income=0, monthly_expense=0,
        initial_allocation={"us_stock": 1000}, monthly_allocation={},
        annual_returns={"us_stock": 0}, future_exchange_rate=1430,
    )))
    assert result["expected_total_assets"] == 1100
    assert result["exchange_rate_effect"] == 100
    assert result["expected_investment_profit"] == 100


def test_free_savings_projection_applies_tax_to_positive_interest(client, auth):
    result = assert_data(client.post("/api/simulations/free", headers=auth(), json=free_payload(
        initial_asset=10000, months=12, monthly_income=0, monthly_expense=0,
        initial_allocation={"saving": 10000}, monthly_allocation={},
        annual_returns={"saving": 10},
    )))
    # Annual effective growth, monthly intermediate Decimal conversion and won rounding.
    assert 999 <= result["expected_interest"] <= 1000
    assert 153 <= result["expected_tax"] <= 154
    assert 10845 <= result["expected_total_assets"] <= 10847
    assert result["expected_total_assets"] == result["timeline"][-1]["total_assets"]


@pytest.mark.parametrize("overrides,status", [
    ({"initial_allocation": {"cash": 999}}, 422),
    ({"monthly_allocation": {"cash": 199}}, 422),
    ({"monthly_expense": 301}, 422),
    ({"monthly_allocation": {"existing_saving": 200}}, 400),
    ({"months": 601}, 400),
    ({"initial_allocation": {"unknown": 1000}}, 400),
    ({"annual_returns": {"saving": -1}}, 400),
    ({"future_exchange_rate": 0}, 400),
])
def test_projection_rejects_invalid_planning_inputs(client, auth, overrides, status):
    response = client.post("/api/simulations/free", headers=auth(), json=free_payload(**overrides))
    assert response.status_code == status, response.get_json()
    assert response.get_json()["success"] is False
    assert Account.query.filter_by(user_id=1).one().balance == 1000


def test_goal_projection_uses_owned_server_values(client, auth, make_goal):
    goal = make_goal(target_date="2026-04-01")
    payload = {"monthly_allocation": {"cash": 100}, "annual_returns": {}, "future_exchange_rate": 1300}
    result = assert_data(client.post(f"/api/goals/{goal['goal_id']}/simulation", headers=auth(), json=payload))
    assert result["initial_assets"] == 1000
    assert result["expected_total_assets"] == 1300
    assert result["difference"] == -3700
    response = client.post(f"/api/goals/{goal['goal_id']}/simulation", headers=auth(2), json=payload)
    assert response.status_code == 404
    response = client.post(f"/api/goals/{goal['goal_id']}/simulation", headers=auth(), json={**payload, "initial_asset": 1000000})
    assert response.status_code == 400
    assert Account.query.filter_by(user_id=1).one().balance == 1000


def test_goal_projection_preserves_and_matures_actual_contracts_hypothetically(client, auth, make_goal):
    product_id, option_id = seed_product("DEPOSIT", "zero-deposit")
    deposit = Deposit(
        user_id=1, product_id=product_id, option_id=option_id, principal=2000,
        applied_interest_rate=0, interest_method="SIMPLE",
        start_date=date(2025, 2, 1), maturity_date=date(2026, 2, 1), status="ACTIVE",
    )
    saving_product_id, saving_option_id = seed_product("SAVING", "zero-saving")
    saving = Saving(
        user_id=1, product_id=saving_product_id, option_id=saving_option_id,
        monthly_amount=100, scheduled_payment_count=3, applied_interest_rate=0,
        interest_method="SIMPLE", payment_day=10, next_payment_date=date(2026, 1, 10),
        start_date=date(2025, 12, 10), maturity_date=date(2026, 3, 10),
        total_paid_principal=100, status="ACTIVE",
    )
    db.session.add_all([deposit, saving])
    db.session.flush()
    db.session.add(SavingPayment(
        saving_id=saving.saving_id, payment_sequence=1, payment_year_month="2025-12",
        scheduled_date=date(2025, 12, 10), amount=100, status="PAID",
    ))
    db.session.commit()
    goal = make_goal(target_date="2026-04-01")
    result = assert_data(client.post(f"/api/goals/{goal['goal_id']}/simulation", headers=auth(), json={
        "monthly_allocation": {"existing_saving": 100}, "annual_returns": {}, "future_exchange_rate": 1300,
    }))
    assert result["initial_assets"] == 3100
    assert result["future_contributions"] == 300
    assert result["expected_total_assets"] == 3400
    assert result["amounts"]["cash"] == 3400
    assert result["amounts"]["existing_saving"] == result["amounts"]["existing_deposit"] == 0
    assert result["missed_payments"] == 0
    assert result["expected_interest"] == result["expected_tax"] == 0
    assert deposit.status == saving.status == "ACTIVE"
    assert saving.total_paid_principal == 100
    assert SavingPayment.query.count() == 1
    assert Account.query.filter_by(user_id=1).one().balance == 1000
    assert LedgerTransaction.query.count() == 0


def test_goal_projection_uses_contract_interest_and_withholding(client, auth, make_goal):
    product_id, option_id = seed_product("DEPOSIT", "ten-percent-deposit")
    db.session.add(Deposit(
        user_id=1, product_id=product_id, option_id=option_id, principal=10000,
        applied_interest_rate=Decimal("10"), interest_method="SIMPLE",
        start_date=date(2025, 2, 1), maturity_date=date(2026, 2, 1), status="ACTIVE",
    ))
    db.session.commit()
    goal = make_goal(target_amount=20000, target_date="2026-02-01")
    result = assert_data(client.post(f"/api/goals/{goal['goal_id']}/simulation", headers=auth(), json={
        "monthly_allocation": {"cash": 100}, "annual_returns": {}, "future_exchange_rate": 1300,
    }))
    assert result["expected_interest"] == 1000
    assert result["expected_tax"] == 154
    assert result["expected_net_interest"] == 846
    assert result["expected_total_assets"] == 11946


def test_goal_projection_marks_unfunded_saving_installments_missed(client, auth, make_goal):
    product_id, option_id = seed_product("SAVING", "unfunded-saving")
    saving = Saving(
        user_id=1, product_id=product_id, option_id=option_id,
        monthly_amount=100, scheduled_payment_count=3, applied_interest_rate=0,
        interest_method="SIMPLE", payment_day=10, next_payment_date=date(2026, 1, 10),
        start_date=date(2025, 12, 10), maturity_date=date(2026, 3, 10),
        total_paid_principal=100, status="ACTIVE",
    )
    db.session.add(saving)
    db.session.flush()
    db.session.add(SavingPayment(
        saving_id=saving.saving_id, payment_sequence=1, payment_year_month="2025-12",
        scheduled_date=date(2025, 12, 10), amount=100, status="PAID",
    ))
    Account.query.filter_by(user_id=1).one().balance = 0
    SimulationSetting.query.filter_by(user_id=1).one().monthly_income = 0
    db.session.commit()
    goal = make_goal(target_date="2026-04-01")
    result = assert_data(client.post(f"/api/goals/{goal['goal_id']}/simulation", headers=auth(), json={
        "monthly_allocation": {}, "annual_returns": {}, "future_exchange_rate": 1300,
    }))
    assert result["missed_payments"] == 2
    assert result["expected_total_assets"] == 100
    assert SavingPayment.query.count() == 1
    assert saving.total_paid_principal == 100
