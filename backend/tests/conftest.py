"""Feature tests use isolated SQLite data and deterministic market information."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import sys
from pathlib import Path

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import event

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.extensions import db
from app.models.account import Account
from app.models.features import Badge, SavingGoal
from app.models.simulation_setting import SimulationSetting
from app.models.user import User
from app.services import market_data_service, portfolio_service, projection_service


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setattr(portfolio_service, "today", lambda: date(2026, 1, 1))
    monkeypatch.setattr(projection_service, "today", lambda: date(2026, 1, 1))
    monkeypatch.setattr(market_data_service, "fetch_exchange_rate", lambda: Decimal("1300"))
    monkeypatch.setattr(
        market_data_service, "fetch_quote",
        lambda symbol, market: {"price": Decimal("100")},
    )
    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "isolated-feature-tests-secret-at-least-32-characters",
        "JWT_TOKEN_LOCATION": ["headers"],
        "FEATURE_RATE_LIMIT_ENABLED": False,
    })
    with application.app_context():
        with db.engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        db.create_all()
        for user_id, role in ((1, "USER"), (2, "USER"), (3, "ADMIN")):
            db.session.add(User(
                user_id=user_id, username=f"testuser{user_id}",
                nickname=f"사용자{user_id}", role=role, status="ACTIVE",
                token_version=0, password_hash="unused-test-hash",
            ))
        db.session.flush()
        for user_id in (1, 2, 3):
            db.session.add(Account(
                user_id=user_id, account_number=f"10000000000{user_id}", balance=1000,
            ))
            db.session.add(SimulationSetting(
                user_id=user_id, initial_asset=1000, is_initial_asset_set=True,
                monthly_income=100, monthly_expense=0,
            ))
        db.session.add_all([
            Badge(code="FIRST_GOAL", name="첫 목표", description="첫 목표 달성", badge_type="GOAL"),
            Badge(code="THREE_GOALS", name="세 목표", description="세 목표 달성", badge_type="GOAL"),
            Badge(code="SAVING_SIX_PAYMENTS", name="꾸준한 저축", description="6회 납입", badge_type="SAVING"),
            Badge(code="INVESTMENT_TEN_PERCENT", name="투자 수익", description="수익률 10%", badge_type="INVESTMENT"),
        ])
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def goal_clock(app, monkeypatch):
    """Opt-in clock for goal creation and completion; no production time changes."""
    class Clock(datetime):
        current = datetime(2026, 1, 1, 3)  # Noon in Korea.

        @classmethod
        def utcnow(cls):
            return cls.current

        @classmethod
        def now(cls, tz=None):
            return cls.current.replace(tzinfo=timezone.utc).astimezone(tz) if tz else cls.current

        @classmethod
        def advance(cls, **delta):
            cls.current += timedelta(**delta)

    def stamp_goal(mapper, connection, goal):
        if goal.created_at is None:
            goal.created_at = Clock.utcnow()
        if goal.updated_at is None:
            goal.updated_at = Clock.utcnow()

    monkeypatch.setattr(portfolio_service, "datetime", Clock)
    monkeypatch.setattr(portfolio_service, "today", lambda: Clock.now(timezone(timedelta(hours=9))).date())
    event.listen(SavingGoal, "before_insert", stamp_goal)
    try:
        yield Clock
    finally:
        event.remove(SavingGoal, "before_insert", stamp_goal)


@pytest.fixture
def auth(app):
    def headers(user_id=1, token_version=0):
        token = create_access_token(
            identity=str(user_id), additional_claims={"token_version": token_version},
        )
        return {"Authorization": f"Bearer {token}"}
    return headers


@pytest.fixture
def make_post(client, auth):
    def create(user_id=1, **overrides):
        response = client.post("/api/posts", headers=auth(user_id), json={
            "board_type": "FREE", "title": "재테크 계획", "content": "월 저축 계획 공유",
            **overrides,
        })
        assert response.status_code == 201, response.get_json()
        return response.get_json()["data"]
    return create


@pytest.fixture
def make_inquiry(client, auth):
    def create(user_id=1, **overrides):
        response = client.post("/api/inquiries", headers=auth(user_id), json={
            "title": "거래 확인 요청", "content": "가상 거래 내역 확인 부탁드립니다.",
            **overrides,
        })
        assert response.status_code == 201, response.get_json()
        return response.get_json()["data"]
    return create


@pytest.fixture
def make_goal(client, auth):
    def create(user_id=1, **overrides):
        response = client.post("/api/goals", headers=auth(user_id), json={
            "goal_name": "여행 자금", "target_amount": 5000, "target_date": "2027-01-01",
            **overrides,
        })
        assert response.status_code == 201, response.get_json()
        return response.get_json()["data"]
    return create
