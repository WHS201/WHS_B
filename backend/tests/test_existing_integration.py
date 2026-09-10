"""Regression checks at the boundary between existing and additional features."""
from decimal import Decimal

from app.extensions import db
from app.models.account import Account
from app.models.user import User
from app.models.features import AuditLog
from app.models.deposits_savings import FinancialProduct, FinancialProductOption, Deposit, LedgerTransaction
from app.services import fss_product_service


def test_cookie_login_initial_asset_goal_password_audit(client, app):
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    signup = client.post("/api/auth/signup", json={"username": "newmember", "password": "Testing123!", "nickname": "새사용자"})
    assert signup.status_code == 201, signup.json
    login = client.post("/api/auth/login", json={"username": "newmember", "password": "Testing123!"})
    assert login.status_code == 200, login.json
    csrf = client.get_cookie("csrf_access_token").value
    headers = {"X-CSRF-TOKEN": csrf}
    initial = client.post("/api/simulation/initial-asset", json={"initial_asset": 10000}, headers=headers)
    assert initial.status_code == 200, initial.json
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200, dashboard.json
    assert dashboard.json["data"]["total_assets"] == 10000
    assert dashboard.json["data"]["total_profit"] == 0
    goal = client.post("/api/goals", headers=headers, json={"goal_name": "다음 목표", "target_amount": 20000, "target_date": "2027-01-01"})
    assert goal.status_code == 201, goal.json
    changed = client.patch("/api/users/me/password", headers=headers, json={"current_password": "Testing123!", "new_password": "Changed123!"})
    assert changed.status_code == 200, changed.json
    assert client.get("/api/dashboard").status_code == 401
    uid = User.query.filter_by(username="newmember").one().user_id
    event = AuditLog.query.filter_by(action="PASSWORD_CHANGE", target_id=uid).one()
    assert event.actor_user_id == uid
    assert event.before_value is None and event.after_value is None


def make_product():
    product = FinancialProduct(external_product_code="001:deposit", bank_name="KB국민은행", product_name="기본 예금", product_type="DEPOSIT")
    db.session.add(product)
    db.session.flush()
    option = FinancialProductOption(product_id=product.product_id, term_months=12, base_interest_rate=Decimal("3"), max_interest_rate=Decimal("3"), interest_method="SIMPLE", min_amount=1, max_amount=1000000)
    db.session.add(option)
    db.session.commit()
    return product, option


def test_existing_deposit_connects_dashboard_and_audit(client, auth):
    _, option = make_product()
    response = client.post("/api/deposits", headers=auth(), json={"option_id": option.option_id, "principal": 400})
    assert response.status_code == 201, response.json
    dashboard = client.get("/api/dashboard", headers=auth()).json["data"]
    assert dashboard["amounts"]["cash"] == 600
    assert dashboard["amounts"]["deposit"] == 400
    assert dashboard["total_assets"] == 1000  # unearned interest excluded
    assert AuditLog.query.filter_by(target_type="deposits", action="CREATE").count() == 1
    assert AuditLog.query.filter_by(target_type="ledger_transactions", action="CREATE").count() == 1
    before = AuditLog.query.count()
    response = client.post("/api/deposits", headers=auth(), json={"option_id": option.option_id, "principal": 700})
    assert response.status_code == 422
    assert Deposit.query.count() == 1
    assert LedgerTransaction.query.filter_by(user_id=1).count() == 1
    assert Account.query.filter_by(user_id=1).one().balance == 600
    assert AuditLog.query.count() == before


def test_admin_product_edits_survive_scheduled_source_sync(client, auth, monkeypatch):
    product, option = make_product()
    response = client.patch(f"/api/admin/products/{product.product_id}", headers=auth(3), json={"product_name": "운영자 수정", "reason": "설명 정정"})
    assert response.status_code == 200
    response = client.patch(f"/api/admin/products/{product.product_id}/options/{option.option_id}", headers=auth(3), json={"base_interest_rate": "4.25", "max_interest_rate": "4.25", "reason": "금리 정정"})
    assert response.status_code == 200
    raw = {"kor_co_nm": "국민은행", "fin_co_no": "001", "fin_prdt_cd": "deposit", "fin_prdt_nm": "외부 상품명", "join_member": "개인"}
    rate = {"fin_co_no": "001", "fin_prdt_cd": "deposit", "save_trm": "12", "intr_rate_type": "S", "intr_rate": 2, "intr_rate2": 2}
    monkeypatch.setattr(fss_product_service, "ENDPOINTS", {"DEPOSIT": "fixture"})
    monkeypatch.setattr(fss_product_service, "_fetch_all", lambda endpoint: ([raw], [rate]))
    fss_product_service.sync_products()
    db.session.expire_all()
    assert db.session.get(FinancialProduct, product.product_id).product_name == "운영자 수정"
    assert db.session.get(FinancialProductOption, option.option_id).base_interest_rate == Decimal("4.25")
    response = client.get(f"/api/admin/products/{product.product_id}", headers=auth(3))
    assert response.json["data"]["options"][0]["sync_locked"] is True


def test_admin_option_rejects_unrepresentable_mysql_rate(client, auth):
    product, option = make_product()
    response = client.patch(f"/api/admin/products/{product.product_id}/options/{option.option_id}", headers=auth(3), json={"base_interest_rate": "100", "max_interest_rate": "100", "reason": "테스트"})
    assert response.status_code == 400
    assert option.base_interest_rate == Decimal("3")


def test_equal_asset_goal_is_rejected_before_badge_award(client, auth):
    response = client.post("/api/goals", headers=auth(), json={
        "goal_name": "현재 목표", "target_amount": 1000, "target_date": "2027-01-01",
    })
    assert response.status_code == 422, response.json
    assert response.json["error"]["code"] == "INVALID_TARGET_AMOUNT"
    assert client.get("/api/badges/me", headers=auth()).json["data"] == []


def test_krw_only_goal_projection_does_not_fetch_fx(client, auth, make_goal, monkeypatch):
    from app.services import market_data_service
    goal = make_goal()
    def unexpected_fx():
        raise AssertionError("KRW-only simulation must not depend on exchange data")
    monkeypatch.setattr(market_data_service, "fetch_exchange_rate", unexpected_fx)
    response = client.post(f"/api/goals/{goal['goal_id']}/simulation", headers=auth(), json={
        "monthly_allocation": {"cash": 100}, "annual_returns": {}, "future_exchange_rate": 1300,
    })
    assert response.status_code == 200, response.json
    assert response.json["data"]["expected_total_assets"] == 2200
