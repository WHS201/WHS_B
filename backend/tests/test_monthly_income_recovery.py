"""Current-month recovery, eligibility evidence, retries and scheduler ordering."""
from datetime import date, datetime, timezone
from pathlib import Path
import runpy

import pytest

import app as app_module
from app.extensions import db
from app.models.account import Account
from app.models.deposits_savings import LedgerTransaction, SavingPayment
from app.models.features import AuditLog
from app.models.monthly_cash_flow import MonthlyCashFlow
from app.models.simulation_setting import SimulationSetting
from app.models.user import User
from app.services import deposit_saving_batch_service as savings
from app.services import monthly_income_batch_service as batch
from app.services import monthly_income_service as income
from app.services import simulation_service
from test_saving_batch_stability import make_saving


@pytest.fixture
def income_clock(app, monkeypatch):
    # Alembic's fileConfig in earlier migration tests disables existing
    # loggers. Keep these log assertions independent of test execution order.
    monkeypatch.setattr(app.logger, "disabled", False)
    class Clock(datetime):
        current = datetime(2026, 9, 1, 15, 5)  # September 2, 00:05 KST.

        @classmethod
        def now(cls, tz=None):
            return cls.current.replace(tzinfo=timezone.utc).astimezone(tz) if tz else cls.current

    monkeypatch.setattr(income, "datetime", Clock)
    monkeypatch.setattr(batch, "datetime", Clock)
    for setting in SimulationSetting.query.all():
        setting.monthly_expense = 20
        setting.is_initial_asset_set = setting.user_id != 3
        setting.created_at = setting.updated_at = datetime(2026, 8, 20)
    db.session.commit()
    for audit in AuditLog.query.all():
        audit.created_at = datetime(2026, 8, 20)
    db.session.commit()
    return Clock


@pytest.mark.parametrize("day", [1, 2, 28])
def test_normal_first_day_or_missed_day_recovers_current_month_once(income_clock, day, monkeypatch, caplog):
    income_clock.current = datetime(2026, 9, day, 3)
    paid_users = []
    real_pay = batch.pay_monthly_income
    def tracked(**kwargs):
        paid_users.append(kwargs["user_id"])
        return real_pay(**kwargs)
    monkeypatch.setattr(batch, "pay_monthly_income", tracked)
    with caplog.at_level("INFO"):
        first = batch.process_monthly_incomes()
        repeated = batch.process_monthly_incomes()
    assert first["processed_count"] == 2 and first["failed_count"] == 0
    assert repeated["processed_count"] == 0 and repeated["failed_count"] == 0
    assert paid_users == [1, 2]  # Paid users are excluded before payment calls.
    assert MonthlyCashFlow.query.count() == 2
    assert {row.year_month for row in MonthlyCashFlow.query} == {"2026-09"}
    assert Account.query.filter_by(user_id=1).one().balance == 1080
    assert LedgerTransaction.query.filter_by(transaction_type="MONTHLY_INCOME").count() == 2
    assert LedgerTransaction.query.filter_by(transaction_type="MONTHLY_EXPENSE").count() == 2
    assert "Monthly income recovery result" in caplog.text


def test_partial_failure_rolls_back_and_only_failed_user_retries(income_clock, monkeypatch, caplog):
    real_ledger = income.create_ledger
    real_pay = batch.pay_monthly_income
    attempts = []
    should_fail = [True]
    def ledger(**kwargs):
        if kwargs["account"].user_id == 2 and should_fail[0]:
            raise RuntimeError("synthetic recoverable ledger failure")
        return real_ledger(**kwargs)
    def pay(**kwargs):
        attempts.append(kwargs["user_id"])
        return real_pay(**kwargs)
    monkeypatch.setattr(income, "create_ledger", ledger)
    monkeypatch.setattr(batch, "pay_monthly_income", pay)
    first = batch.process_monthly_incomes()
    assert (first["processed_count"], first["failed_count"]) == (1, 1)
    assert Account.query.filter_by(user_id=1).one().balance == 1080
    assert Account.query.filter_by(user_id=2).one().balance == 1000
    assert MonthlyCashFlow.query.filter_by(user_id=2).count() == 0
    assert LedgerTransaction.query.filter_by(user_id=2).count() == 0
    should_fail[0] = False
    second = batch.process_monthly_incomes()
    assert (second["processed_count"], second["failed_count"]) == (1, 0)
    assert attempts == [1, 2, 2]
    assert Account.query.filter_by(user_id=1).one().balance == 1080
    assert Account.query.filter_by(user_id=2).one().balance == 1080
    assert MonthlyCashFlow.query.count() == 2
    assert LedgerTransaction.query.count() == 4
    assert "user_id=2 year_month=2026-09" in caplog.text


@pytest.mark.parametrize("initial_asset", [0, 1000])
def test_new_initialization_after_cutoff_waits_until_next_month(income_clock, initial_asset):
    setting = SimulationSetting.query.filter_by(user_id=1).one()
    setting.is_initial_asset_set = False
    db.session.commit()
    simulation_service.set_initial_asset(1, initial_asset)
    # Both initial-setting audit and positive funding ledger are later than
    # this month's cutoff, so neither may establish retroactive eligibility.
    assert batch.process_monthly_incomes()["processed_count"] == 1
    assert MonthlyCashFlow.query.filter_by(user_id=1).count() == 0
    for audit in AuditLog.query.filter_by(target_type="simulation_settings", target_id=setting.simulation_setting_id):
        if audit.after_value and audit.after_value.get("is_initial_asset_set") is True:
            audit.created_at = datetime(2026, 9, 2)
    for row in LedgerTransaction.query.filter_by(user_id=1, transaction_type="INITIAL_ASSET"):
        row.created_at = datetime(2026, 9, 2)
    db.session.commit()
    income_clock.current = datetime(2026, 10, 1, 3)
    assert batch.process_monthly_incomes()["processed_count"] == 2
    assert MonthlyCashFlow.query.filter_by(user_id=1, year_month="2026-10").count() == 1


def test_new_signup_without_initial_setting_never_gets_recovery(client, income_clock):
    response = client.post("/api/auth/signup", json={"username": "newincome", "password": "Testing123!", "nickname": "새회원"})
    assert response.status_code == 201
    uid = User.query.filter_by(username="newincome").one().user_id
    assert batch.process_monthly_incomes()["processed_count"] == 2
    assert MonthlyCashFlow.query.filter_by(user_id=uid).count() == 0


@pytest.mark.parametrize("reinitialize", [False, True])
def test_reset_removes_payment_but_does_not_allow_same_month_recovery(income_clock, reinitialize):
    batch.process_monthly_incomes()
    simulation_service.reset_simulation_data(1)
    if reinitialize:
        simulation_service.set_initial_asset(1, 0)
    assert batch.process_monthly_incomes()["processed_count"] == 0
    assert MonthlyCashFlow.query.filter_by(user_id=1).count() == 0
    assert Account.query.filter_by(user_id=1).one().balance == 0
    assert AuditLog.query.filter_by(action="SIMULATION_RESET", target_id=1).count() == 1


def test_zero_initial_assets_before_cutoff_are_eligible_from_audit(income_clock):
    setting = SimulationSetting.query.filter_by(user_id=1).one()
    setting.initial_asset = 0
    Account.query.filter_by(user_id=1).one().balance = 0
    db.session.commit()
    assert LedgerTransaction.query.filter_by(transaction_type="INITIAL_ASSET").count() == 0
    assert batch.process_monthly_incomes()["processed_count"] == 2
    assert Account.query.filter_by(user_id=1).one().balance == 80


def test_income_setting_change_does_not_erase_old_initialization_evidence(income_clock):
    setting = SimulationSetting.query.filter_by(user_id=1).one()
    setting.monthly_income = 250
    db.session.commit()
    assert batch.process_monthly_incomes()["processed_count"] == 2
    assert Account.query.filter_by(user_id=1).one().balance == 1230


def test_legacy_positive_initialization_can_use_existing_ledger(income_clock):
    AuditLog.query.filter_by(target_type="simulation_settings").delete(synchronize_session=False)
    setting = SimulationSetting.query.filter_by(user_id=1).one()
    setting.updated_at = datetime(2026, 9, 2)
    db.session.add(LedgerTransaction(account_id=Account.query.filter_by(user_id=1).one().account_id,
                                    user_id=1, transaction_type="INITIAL_ASSET", amount=1000,
                                    balance_after=1000, reference_type="SIMULATION_SETTING",
                                    reference_id=setting.simulation_setting_id, created_at=datetime(2026, 8, 20)))
    db.session.commit()
    assert income.automatic_income_eligible(setting, date(2026, 9, 2))


def test_legacy_unchanged_setting_eligible_but_uncertain_recent_setting_excluded(income_clock):
    AuditLog.query.filter_by(target_type="simulation_settings").delete(synchronize_session=False)
    setting = SimulationSetting.query.filter_by(user_id=1).one()
    assert income.automatic_income_eligible(setting, date(2026, 9, 2))
    setting.updated_at = datetime(2026, 9, 2)
    db.session.commit()
    assert not income.automatic_income_eligible(setting, date(2026, 9, 2))


@pytest.mark.parametrize("year_month", ["2026-08", "2026-10"])
def test_batch_cannot_recover_past_or_future_month(income_clock, year_month):
    with pytest.raises(ValueError, match="current month"):
        batch.process_monthly_incomes(date.fromisoformat(year_month + "-01"))
    assert MonthlyCashFlow.query.count() == 0


def load_scheduler(app, monkeypatch):
    monkeypatch.setattr(app_module, "create_app", lambda: app)
    path = Path(__file__).resolve().parents[1] / "run_batch_scheduler.py"
    return runpy.run_path(str(path))


def test_recovery_income_and_expenses_finish_before_saving_payment(app, income_clock, monkeypatch):
    income_clock.current = datetime(2026, 8, 31, 15, 5)
    make_saving(balance=50)  # Without income: MISSED. After net income: PAID.
    scheduler = load_scheduler(app, monkeypatch)
    scheduler["run_financial_batch"].__globals__["datetime"] = income_clock
    scheduler["run_financial_batch"]()
    assert SavingPayment.query.filter_by(payment_year_month="2026-09", status="PAID").count() == 1
    assert Account.query.filter_by(user_id=1).one().balance == 30
    rows = LedgerTransaction.query.filter_by(user_id=1).order_by(LedgerTransaction.ledger_transaction_id).all()
    assert [row.transaction_type for row in rows] == ["MONTHLY_INCOME", "MONTHLY_EXPENSE", "SAVING_PAYMENT"]


@pytest.mark.parametrize("result", [{"failed_count": 1}, {"failed_count": 0, "not_due": True}])
def test_failed_or_not_yet_due_income_defers_savings(app, monkeypatch, result):
    calls = []
    monkeypatch.setattr(batch, "process_monthly_incomes", lambda **kwargs: calls.append("income") or result)
    monkeypatch.setattr(savings, "run_daily_financial_batch", lambda **kwargs: calls.append("savings"))
    scheduler = load_scheduler(app, monkeypatch)
    scheduler["run_financial_batch"]()
    assert calls == ["income"]


def test_restart_recovers_before_scheduler_starts(app, monkeypatch):
    from apscheduler.schedulers import blocking
    calls = []
    jobs = []
    class Scheduler:
        def __init__(self, **kwargs):
            assert kwargs["timezone"] == "Asia/Seoul"
        def add_job(self, func, trigger, **kwargs):
            jobs.append((func.__name__, trigger, kwargs))
        def start(self):
            calls.append("start")
    monkeypatch.setattr(blocking, "BlockingScheduler", Scheduler)
    monkeypatch.setattr(app_module, "create_app", lambda: app)
    monkeypatch.setattr(batch, "process_monthly_incomes", lambda **kwargs: calls.append("income") or {"failed_count": 0})
    monkeypatch.setattr(savings, "run_daily_financial_batch", lambda **kwargs: calls.append("savings"))
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "run_batch_scheduler.py"), run_name="__main__")
    assert calls == ["income", "savings", "start"]
    assert ("run_financial_batch", "cron", {"hour": 0, "minute": 5}) in jobs


def test_restart_before_monthly_payment_time_never_pays_early(income_clock):
    income_clock.current = datetime(2026, 8, 31, 15, 4, 59)
    assert batch.process_monthly_incomes()["not_due"] is True
    assert MonthlyCashFlow.query.count() == 0
    income_clock.current = datetime(2026, 8, 31, 15, 5)
    assert batch.process_monthly_incomes()["processed_count"] == 2


def test_manual_financial_batch_uses_same_income_first_order(app, monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "create_app", lambda: app)
    monkeypatch.setattr(batch, "process_monthly_incomes", lambda **kwargs: calls.append("income") or {"failed_count": 0})
    monkeypatch.setattr(savings, "run_daily_financial_batch", lambda **kwargs: calls.append("savings"))
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "run_daily_financial_batch.py"))
    assert calls == ["income", "savings"]
