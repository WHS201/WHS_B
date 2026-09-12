from datetime import date, datetime
from decimal import Decimal

from app.constants import EntryType, TransactionType
from app.errors.exceptions import BusinessException
from app.extensions import db
from app.models.deposits_savings import (EarlyTerminationRateRule, Saving,
    SavingPayment, SavingPreferenceCondition)
from app.services import product_service
from app.services.account_service import credit, debit, get_account_by_user_id
from app.services.deposit_saving_calculations import (GENERAL_TAX_RATE, add_months,
    calculate_applied_rate, calculate_saving_result, calculate_saving_termination,
    next_month_payment_date)
from app.services.deposit_saving_serialization import condition, payment, rate, saving
from app.services.ledger_service import create_ledger


def simulate(payload):
    option = product_service.get_option(payload["option_id"], "SAVING")
    product_service.validate_amount(payload["monthly_amount"], option, "월 납입금")
    conditions = product_service.get_conditions(option.option_id, payload["selected_condition_ids"])
    applied = calculate_applied_rate(option, conditions)
    start, maturity = date.today(), add_months(date.today(), option.term_months)
    return {"option_id": option.option_id, "monthly_amount": payload["monthly_amount"],
            "term_months": option.term_months, "base_interest_rate": rate(option.base_interest_rate),
            "preference_interest_rate": rate(sum((x.additional_interest_rate for x in conditions), Decimal("0"))),
            "applied_interest_rate": rate(applied), "interest_method": option.interest_method,
            "selected_conditions": [condition(x) for x in conditions],
            **calculate_saving_result(payload["monthly_amount"], applied, start, maturity,
                                      payload["payment_day"], option.term_months,
                                      option.interest_method)}


def create(user_id, payload):
    option = product_service.get_option(payload["option_id"], "SAVING", True)
    product_service.validate_amount(payload["monthly_amount"], option, "월 납입금")
    conditions = product_service.get_conditions(option.option_id, payload["selected_condition_ids"])
    try:
        account = get_account_by_user_id(user_id)
        start = date.today()
        item = Saving(user_id=user_id, product_id=option.product_id, option_id=option.option_id,
                      monthly_amount=payload["monthly_amount"], scheduled_payment_count=option.term_months,
                      applied_interest_rate=calculate_applied_rate(option, conditions),
                      interest_method=option.interest_method, payment_day=payload["payment_day"],
                      next_payment_date=next_month_payment_date(start, payload["payment_day"]),
                      start_date=start, maturity_date=add_months(start, option.term_months),
                      status="ACTIVE", total_paid_principal=payload["monthly_amount"])
        db.session.add(item); db.session.flush()
        for x in conditions:
            db.session.add(SavingPreferenceCondition(saving_id=item.saving_id, condition_id=x.condition_id,
                           condition_name=x.condition_name, additional_interest_rate=x.additional_interest_rate))
        db.session.add(SavingPayment(saving_id=item.saving_id, payment_sequence=1,
                       payment_year_month=start.strftime("%Y-%m"), scheduled_date=start,
                       amount=item.monthly_amount, status="PAID", processed_at=datetime.utcnow()))
        debit(account, item.monthly_amount)
        create_ledger(
            account=account,
            transaction_type=TransactionType.SAVING_PAYMENT.value,
            amount=item.monthly_amount,
            entry_type=EntryType.DEBIT.value,
            reference_type="SAVING",
            reference_id=item.saving_id,
        )
        db.session.commit(); return saving(item, True)
    except Exception:
        db.session.rollback(); raise


def _find(user_id, saving_id):
    item = Saving.query.filter_by(user_id=user_id, saving_id=saving_id).first()
    if item is None: raise BusinessException(code="SAVING_NOT_FOUND", message="적금을 찾을 수 없습니다.", status_code=404)
    return item


def get_list(user_id, filters):
    query = Saving.query.filter_by(user_id=user_id)
    if filters.get("status"): query = query.filter_by(status=filters["status"])
    page = query.order_by(Saving.created_at.desc()).paginate(page=filters["page"], per_page=filters["size"], error_out=False)
    return {"items": [saving(x) for x in page.items], "page": filters["page"],
            "size": filters["size"], "total_count": page.total}


def get_detail(user_id, saving_id):
    return saving(_find(user_id, saving_id), True)


def get_payments(user_id, saving_id, filters):
    _find(user_id, saving_id)
    query = SavingPayment.query.filter_by(saving_id=saving_id)
    if filters.get("status"): query = query.filter_by(status=filters["status"])
    page = query.order_by(SavingPayment.payment_sequence).paginate(page=filters["page"], per_page=filters["size"], error_out=False)
    return {"items": [payment(x) for x in page.items], "page": filters["page"],
            "size": filters["size"], "total_count": page.total}


def terminate(user_id, saving_id):
    try:
        item = Saving.query.filter_by(user_id=user_id, saving_id=saving_id).with_for_update().first()
        if item is None: raise BusinessException(code="SAVING_NOT_FOUND", message="적금을 찾을 수 없습니다.", status_code=404)
        if item.status == "MATURED": raise BusinessException(code="SAVING_ALREADY_MATURED", message="이미 만기 처리된 적금입니다.", status_code=409)
        if item.status == "TERMINATED": raise BusinessException(code="SAVING_ALREADY_TERMINATED", message="이미 중도해지된 적금입니다.", status_code=409)
        account = get_account_by_user_id(user_id)
        days = max((date.today() - item.start_date).days, 0)
        rule = EarlyTerminationRateRule.query.filter(
            EarlyTerminationRateRule.option_id == item.option_id,
            EarlyTerminationRateRule.minimum_holding_days <= days,
            db.or_(EarlyTerminationRateRule.maximum_holding_days.is_(None), EarlyTerminationRateRule.maximum_holding_days >= days)
        ).order_by(EarlyTerminationRateRule.minimum_holding_days.desc()).first()
        if rule is None: raise BusinessException(code="EARLY_TERMINATION_RULE_NOT_FOUND", message="중도해지 이율 규칙을 찾을 수 없습니다.", status_code=422)
        paid = (
            SavingPayment.query
            .filter_by(
                saving_id=saving_id,
                status="PAID"
            )
            .populate_existing()
            .with_for_update()
            .all()
        )
        result = calculate_saving_termination(paid, item.option, rule, date.today())
        item.status="TERMINATED"; item.applied_early_termination_rate=result["applied_rate"]
        item.gross_interest=result["gross_interest"]; item.tax_rate=GENERAL_TAX_RATE
        item.tax_amount=result["tax_amount"]; item.net_interest=result["net_interest"]
        item.payout_amount=result["payout_amount"]; item.terminated_at=datetime.utcnow(); item.next_payment_date=None
        credit(account, result["payout_amount"])
        create_ledger(
            account=account,
            transaction_type=TransactionType.SAVING_CANCEL.value,
            amount=result["payout_amount"],
            entry_type=EntryType.CREDIT.value,
            reference_type="SAVING",
            reference_id=item.saving_id,
        )
        db.session.commit(); return saving(item, True)
    except Exception:
        db.session.rollback(); raise
