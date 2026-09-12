from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app
from app.extensions import db
from app.errors.exceptions import BusinessException
from app.models.simulation_setting import SimulationSetting
from app.models.monthly_cash_flow import MonthlyCashFlow
from app.models.user import User

from app.services.monthly_income_service import automatic_income_eligible, pay_monthly_income


def process_monthly_incomes(reference_date=None):
    # 현재 한국 시간 기준 연-월
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    year_month = now.strftime("%Y-%m")
    reference_date = reference_date or now.date()
    if reference_date.strftime("%Y-%m") != year_month:
        raise ValueError("Automatic monthly income recovery is limited to the current month")
    if now < now.replace(day=1, hour=0, minute=5, second=0, microsecond=0):
        # A restart just before the original payment time must not pay early
        # or let savings run before this month's income becomes due.
        return {"year_month": year_month, "processed_count": 0,
                "skipped_count": 0, "failed_count": 0, "not_due": True}

    # Select only unpaid, initialized, active users. Do not call the payment
    # function for every user on each daily run.
    paid = db.session.query(MonthlyCashFlow.monthly_cash_flow_id).filter(
        MonthlyCashFlow.user_id == SimulationSetting.user_id,
        MonthlyCashFlow.year_month == year_month,
    ).exists()
    user_ids = [uid for uid, in db.session.query(SimulationSetting.user_id).join(
        User, User.user_id == SimulationSetting.user_id,
    ).filter(SimulationSetting.is_initial_asset_set.is_(True), User.status == "ACTIVE", ~paid
             ).order_by(SimulationSetting.user_id).all()]

    processed_count = failed_count = 0
    skipped_count = MonthlyCashFlow.query.filter_by(year_month=year_month).count()
    db.session.rollback()  # End the candidate snapshot before taking per-user locks.

    for user_id in user_ids:
        try:
            setting = SimulationSetting.query.filter_by(user_id=user_id).first()
            eligible = setting is not None and automatic_income_eligible(setting, reference_date)
            db.session.rollback()
            if not eligible:
                skipped_count += 1
                continue
            # Eligibility and the month's payment are rechecked after the lock.
            pay_monthly_income(user_id=user_id, year_month=year_month, automatic=True)
            processed_count += 1
            current_app.logger.info("Monthly income recovered: user_id=%s year_month=%s", user_id, year_month)
        except BusinessException as error:
            db.session.rollback()
            if error.code in {"MONTHLY_INCOME_ALREADY_PAID", "MONTHLY_INCOME_NOT_ELIGIBLE"}:
                skipped_count += 1
            else:
                failed_count += 1
                current_app.logger.exception("Monthly income recovery failed: user_id=%s year_month=%s", user_id, year_month)
        except Exception:
            db.session.rollback()
            failed_count += 1
            current_app.logger.exception("Monthly income recovery failed: user_id=%s year_month=%s", user_id, year_month)

    result = {
        "year_month": year_month,
        "processed_count": processed_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
    }
    current_app.logger.info("Monthly income recovery result: %s", result)
    return result
