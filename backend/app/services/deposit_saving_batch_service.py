from datetime import date, datetime

from flask import current_app

from app.constants import EntryType, TransactionType
from app.errors.exceptions import BusinessException
from app.extensions import db
from app.models.deposits_savings import Deposit, Saving, SavingPayment
from app.services.account_service import credit, debit, get_account_by_user_id
from app.services.deposit_saving_calculations import (
    GENERAL_TAX_RATE,
    add_months,
    calculate_deposit_result,
    calculate_saving_maturity,
)
from app.services.ledger_service import create_ledger


def _next_payment_date(item, sequence):
    if sequence >= item.scheduled_payment_count:
        return None
    return add_months(item.start_date.replace(day=1), sequence).replace(
        day=item.payment_day
    )


def _process_saving_payment(saving_id, reference_date):
    item = Saving.query.filter_by(
        saving_id=saving_id,
        status="ACTIVE",
    ).populate_existing().with_for_update().first()
    # A competing run may have advanced the contract after both selected its ID.
    # Locking reads + populate_existing refresh both InnoDB and ORM state.
    if item is None or item.next_payment_date is None or item.next_payment_date > reference_date:
        db.session.commit()
        return None

    scheduled_date = item.next_payment_date
    payments = SavingPayment.query.filter_by(saving_id=item.saving_id).populate_existing().with_for_update().all()
    if any(payment.scheduled_date == scheduled_date
           or payment.payment_year_month == scheduled_date.strftime("%Y-%m") for payment in payments):
        db.session.commit()
        return None
    sequence = len(payments) + 1
    if sequence > item.scheduled_payment_count:
        item.next_payment_date = None
        db.session.commit()
        return None

    payment = SavingPayment(
        saving_id=item.saving_id,
        payment_sequence=sequence,
        payment_year_month=scheduled_date.strftime("%Y-%m"),
        scheduled_date=scheduled_date,
        amount=item.monthly_amount,
        processed_at=datetime.utcnow(),
    )
    if scheduled_date < reference_date:
        payment.status = "MISSED"
        result = "MISSED"
    else:
        account = get_account_by_user_id(item.user_id)
        db.session.refresh(account, with_for_update=True)
        try:
            debit(account, item.monthly_amount)
        except BusinessException as error:
            if error.code != "INSUFFICIENT_BALANCE":
                raise
            payment.status = "MISSED"
            result = "MISSED"
        else:
            payment.status = "PAID"
            item.total_paid_principal += item.monthly_amount
            create_ledger(
                account=account,
                transaction_type=TransactionType.SAVING_PAYMENT.value,
                amount=item.monthly_amount,
                entry_type=EntryType.DEBIT.value,
                reference_type="SAVING",
                reference_id=item.saving_id,
            )
            result = "PAID"

    db.session.add(payment)
    item.next_payment_date = _next_payment_date(item, sequence)
    db.session.commit()
    return result


def process_due_saving_payments(reference_date=None):
    reference_date = reference_date or date.today()
    paid_count = missed_count = failed_count = 0

    while True:
        saving_ids = [row[0] for row in db.session.query(Saving.saving_id).filter(
            Saving.status == "ACTIVE",
            Saving.next_payment_date.isnot(None),
            Saving.next_payment_date <= reference_date,
        ).all()]
        if not saving_ids:
            break

        progressed = False
        for saving_id in saving_ids:
            try:
                result = _process_saving_payment(saving_id, reference_date)
                progressed = progressed or result is not None
                if result == "PAID":
                    paid_count += 1
                elif result == "MISSED":
                    missed_count += 1
            except Exception:
                db.session.rollback()
                failed_count += 1
                current_app.logger.exception(
                    "saving payment batch failed: saving_id=%s", saving_id
                )
        if not progressed:
            break

    return {"paid_count": paid_count, "missed_count": missed_count,
            "failed_count": failed_count}


def _mature_deposit(deposit_id, reference_date):
    item = Deposit.query.filter_by(
        deposit_id=deposit_id,
        status="ACTIVE",
    ).with_for_update().first()
    if item is None or item.maturity_date > reference_date:
        return False

    account = get_account_by_user_id(item.user_id)
    result = calculate_deposit_result(
        item.principal,
        item.applied_interest_rate,
        item.start_date,
        item.maturity_date,
        item.interest_method,
    )
    item.status = "MATURED"
    item.gross_interest = result["expected_interest"]
    item.tax_rate = GENERAL_TAX_RATE
    item.tax_amount = result["expected_tax"]
    item.net_interest = result["expected_interest_after_tax"]
    item.payout_amount = result["expected_maturity_amount"]
    item.matured_at = datetime.utcnow()
    credit(account, item.payout_amount)
    create_ledger(
        account=account,
        transaction_type=TransactionType.DEPOSIT_MATURITY.value,
        amount=item.payout_amount,
        entry_type=EntryType.CREDIT.value,
        reference_type="DEPOSIT",
        reference_id=item.deposit_id,
    )
    db.session.commit()
    return True


def mature_due_deposits(reference_date=None):
    reference_date = reference_date or date.today()
    ids = [row[0] for row in db.session.query(Deposit.deposit_id).filter(
        Deposit.status == "ACTIVE",
        Deposit.maturity_date <= reference_date,
    ).all()]
    matured_count = failed_count = 0
    for deposit_id in ids:
        try:
            if _mature_deposit(deposit_id, reference_date):
                matured_count += 1
        except Exception:
            db.session.rollback()
            failed_count += 1
            current_app.logger.exception(
                "deposit maturity batch failed: deposit_id=%s", deposit_id
            )
    return {"matured_count": matured_count, "failed_count": failed_count}


def _mature_saving(saving_id, reference_date):
    item = Saving.query.filter_by(
        saving_id=saving_id,
        status="ACTIVE",
    ).with_for_update().first()
    if item is None or item.maturity_date > reference_date:
        return False

    paid = (
        SavingPayment.query
        .filter_by(
            saving_id=item.saving_id,
            status="PAID",
        )
        .populate_existing()
        .with_for_update()
        .all()
    )

    result = calculate_saving_maturity(
        paid,
        item.applied_interest_rate,
        item.maturity_date,
        item.interest_method,
    )
    account = get_account_by_user_id(item.user_id)
    item.status = "MATURED"
    item.total_paid_principal = sum(payment.amount for payment in paid)
    item.gross_interest = result["gross_interest"]
    item.tax_rate = GENERAL_TAX_RATE
    item.tax_amount = result["tax_amount"]
    item.net_interest = result["net_interest"]
    item.payout_amount = result["payout_amount"]
    item.matured_at = datetime.utcnow()
    item.next_payment_date = None
    credit(account, item.payout_amount)
    create_ledger(
        account=account,
        transaction_type=TransactionType.SAVING_MATURITY.value,
        amount=item.payout_amount,
        entry_type=EntryType.CREDIT.value,
        reference_type="SAVING",
        reference_id=item.saving_id,
    )
    db.session.commit()
    return True


def mature_due_savings(reference_date=None):
    reference_date = reference_date or date.today()
    ids = [row[0] for row in db.session.query(Saving.saving_id).filter(
        Saving.status == "ACTIVE",
        Saving.maturity_date <= reference_date,
    ).all()]
    matured_count = failed_count = 0
    for saving_id in ids:
        try:
            if _mature_saving(saving_id, reference_date):
                matured_count += 1
        except Exception:
            db.session.rollback()
            failed_count += 1
            current_app.logger.exception(
                "saving maturity batch failed: saving_id=%s", saving_id
            )
    return {"matured_count": matured_count, "failed_count": failed_count}


def run_daily_financial_batch(reference_date=None):
    reference_date = reference_date or date.today()
    return {
        "reference_date": reference_date.isoformat(),
        "saving_payments": process_due_saving_payments(reference_date),
        "deposit_maturities": mature_due_deposits(reference_date),
        "saving_maturities": mature_due_savings(reference_date),
    }
