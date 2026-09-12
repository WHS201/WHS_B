"""Opt-in InnoDB tests. ONLY an empty, disposable local test database is allowed.

Set WHS_RUN_MYSQL_TESTS=1 and WHS_TEST_MYSQL_URL to the loopback URL of a
new disposable MySQL container, database whs_stability_test. Never use .env.
Each test creates and removes its own tables in that explicitly opted-in DB.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
from threading import Barrier, Event, local

import pytest
from sqlalchemy import event
from sqlalchemy.engine import make_url

from app import create_app
from app.errors.exceptions import BusinessException
from app.extensions import db
from app.models.account import Account
from app.models.deposits_savings import LedgerTransaction, Saving, SavingPayment
from app.models.features import AuditLog
from app.models.monthly_cash_flow import MonthlyCashFlow
from app.models.simulation_setting import SimulationSetting
from app.models.user import User
from app.services import deposit_saving_batch_service as savings
from app.services import monthly_income_service as income
from test_saving_batch_stability import DUE, FUTURE, due_ids, make_saving


@pytest.fixture
def mysql_app():
    if os.environ.get("WHS_RUN_MYSQL_TESTS") != "1":
        pytest.skip("Opt-in disposable MySQL container is not configured")
    url = make_url(os.environ["WHS_TEST_MYSQL_URL"])
    if (url.drivername != "mysql+pymysql" or url.host != "127.0.0.1"
            or not url.port or url.port == 3306 or url.database != "whs_stability_test"):
        pytest.fail("Use only a disposable loopback MySQL test DB on an explicit non-default port")
    application = create_app({
        "TESTING": True, "APP_ENV": "test", "FEATURE_RATE_LIMIT_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": url,
        "SQLALCHEMY_ENGINE_OPTIONS": {"isolation_level": "REPEATABLE READ", "pool_size": 5},
    })
    with application.app_context():
        with db.engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT DATABASE()").scalar() == "whs_stability_test"
            assert connection.exec_driver_sql("SHOW TABLES").fetchall() == [], "Refuse a non-empty test DB"
            assert connection.exec_driver_sql("SELECT @@transaction_isolation").scalar() == "REPEATABLE-READ"
        db.create_all()
        db.session.add(User(user_id=1, username="mysqltest", nickname="Test", role="USER",
                            status="ACTIVE", token_version=0, password_hash="unused-test-hash"))
        db.session.flush()
        db.session.add(Account(user_id=1, account_number="100000000001", balance=1000))
        db.session.add(SimulationSetting(user_id=1, initial_asset=1000, is_initial_asset_set=True,
                                         monthly_income=100, monthly_expense=20))
        db.session.commit()
        for row in AuditLog.query.all():
            row.created_at = datetime(2020, 1, 1)
        db.session.commit()
        db.session.remove()
        try:
            yield application
        finally:
            db.session.remove()
            # Tables were created above in a verified empty disposable DB.
            # The existing user/badge FK cycle needs FK checks disabled for teardown.
            with db.engine.begin() as connection:
                connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
                for table in reversed(list(db.metadata.tables.values())):
                    table.drop(connection, checkfirst=True)
                connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
            db.engine.dispose()


def overlap_after_snapshots(application, table, prepare, act):
    """Both read first; A holds the row before B attempts the locking read."""
    snapshots_ready = Barrier(2)
    leader_locked, follower_attempted = Event(), Event()
    worker = local()
    with application.app_context():
        engine = db.engine

    def relevant(statement):
        return "FOR UPDATE" in statement.upper() and f"FROM {table} " in statement.replace("\n", " ")

    def before(connection, cursor, statement, parameters, context, executemany):
        if getattr(worker, "name", "") == "B" and relevant(statement):
            follower_attempted.set()

    def after(connection, cursor, statement, parameters, context, executemany):
        if getattr(worker, "name", "") == "A" and relevant(statement) and not leader_locked.is_set():
            leader_locked.set()
            assert follower_attempted.wait(15), "Second worker did not attempt the locked row"

    def run(name):
        worker.name = name
        with application.app_context():
            try:
                snapshot = prepare()
                snapshots_ready.wait(timeout=15)
                if name == "B":
                    assert leader_locked.wait(15)
                return act(snapshot)
            finally:
                db.session.remove()

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(run, "A"), pool.submit(run, "B")
            results = [first.result(timeout=45), second.result(timeout=45)]
        assert leader_locked.is_set() and follower_attempted.is_set()
        return results
    finally:
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "after_cursor_execute", after)


@pytest.mark.parametrize("balance,first_result", [(1000, "PAID"), (0, "MISSED")])
def test_mysql_overlapping_saving_candidates_skip_future_installment(mysql_app, balance, first_result):
    with mysql_app.app_context():
        saving_id = make_saving(balance)
        db.session.remove()

    def prepare():
        candidates = due_ids()
        assert candidates == [saving_id]
        item = db.session.get(Saving, saving_id)
        account = Account.query.filter_by(user_id=1).one()
        assert item.next_payment_date == DUE
        # Keep references alive so SQLAlchemy's identity map is truly stale.
        return candidates, item, account

    def act(snapshot):
        return savings._process_saving_payment(snapshot[0][0], DUE)

    assert overlap_after_snapshots(mysql_app, "savings", prepare, act) == [first_result, None]
    with mysql_app.app_context():
        item = db.session.get(Saving, saving_id)
        assert item.next_payment_date == FUTURE and item.status == "ACTIVE"
        assert item.total_paid_principal == (200 if balance else 100)
        assert Account.query.filter_by(user_id=1).one().balance == (900 if balance else 0)
        assert SavingPayment.query.count() == 2
        assert SavingPayment.query.filter_by(payment_year_month="2026-09", status=first_result).count() == 1
        assert SavingPayment.query.filter(SavingPayment.scheduled_date > DUE).count() == 0
        assert LedgerTransaction.query.count() == (1 if balance else 0)


def test_mysql_overlapping_monthly_recovery_pays_once(mysql_app):
    from zoneinfo import ZoneInfo
    year_month = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m")

    def prepare():
        assert MonthlyCashFlow.query.filter_by(user_id=1, year_month=year_month).count() == 0
        account = Account.query.filter_by(user_id=1).one()
        setting = SimulationSetting.query.filter_by(user_id=1).one()
        assert account.balance == 1000
        return account, setting

    def act(snapshot):
        try:
            income.pay_monthly_income(1, year_month, automatic=True)
            return "PAID"
        except BusinessException as error:
            return error.code

    assert overlap_after_snapshots(mysql_app, "accounts", prepare, act) == ["PAID", "MONTHLY_INCOME_ALREADY_PAID"]
    with mysql_app.app_context():
        assert MonthlyCashFlow.query.count() == 1
        assert Account.query.filter_by(user_id=1).one().balance == 1080
        rows = LedgerTransaction.query.order_by(LedgerTransaction.ledger_transaction_id).all()
        assert [row.transaction_type for row in rows] == ["MONTHLY_INCOME", "MONTHLY_EXPENSE"]
        assert [row.balance_after for row in rows] == [1100, 1080]
