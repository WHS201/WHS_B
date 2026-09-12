"""Overlapping candidate lists, stale ORM state and payment atomicity."""
from datetime import date

import pytest

from app.extensions import db
from app.models.account import Account
from app.models.deposits_savings import (
    FinancialProduct, FinancialProductOption, LedgerTransaction, Saving, SavingPayment,
)
from app.services import deposit_saving_batch_service as batch


DUE = date(2026, 9, 1)
FUTURE = date(2026, 10, 1)


def make_saving(balance=1000):
    product = FinancialProduct(external_product_code="stability-saving", bank_name="Test bank",
                               product_name="Test saving", product_type="SAVING")
    db.session.add(product)
    db.session.flush()
    option = FinancialProductOption(product_id=product.product_id, term_months=3,
                                    base_interest_rate=0, max_interest_rate=0,
                                    interest_method="SIMPLE", min_amount=1, max_amount=1000000)
    db.session.add(option)
    db.session.flush()
    saving = Saving(user_id=1, product_id=product.product_id, option_id=option.option_id,
                    monthly_amount=100, scheduled_payment_count=3, applied_interest_rate=0,
                    interest_method="SIMPLE", payment_day=1, next_payment_date=DUE,
                    start_date=date(2026, 8, 1), maturity_date=date(2026, 11, 1),
                    total_paid_principal=100, status="ACTIVE")
    db.session.add(saving)
    db.session.flush()
    db.session.add(SavingPayment(saving_id=saving.saving_id, payment_sequence=1,
                                 payment_year_month="2026-08", scheduled_date=date(2026, 8, 1),
                                 amount=100, status="PAID"))
    Account.query.filter_by(user_id=1).one().balance = balance
    db.session.commit()
    saving_id = saving.saving_id
    db.session.rollback()
    return saving_id


def due_ids():
    return [row[0] for row in db.session.query(Saving.saving_id).filter(
        Saving.status == "ACTIVE", Saving.next_payment_date <= DUE,
    ).all()]


def payment_state(saving_id):
    db.session.expire_all()
    item = db.session.get(Saving, saving_id)
    return (Account.query.filter_by(user_id=1).one().balance, item.next_payment_date,
            item.total_paid_principal, item.status,
            [(p.payment_sequence, p.scheduled_date, p.status) for p in SavingPayment.query.order_by(SavingPayment.payment_id)],
            [(p.transaction_type, p.amount) for p in LedgerTransaction.query.order_by(LedgerTransaction.ledger_transaction_id)])


@pytest.mark.parametrize("balance,first_result", [(1000, "PAID"), (0, "MISSED")])
def test_two_runs_select_same_id_then_second_refreshes_and_skips(app, balance, first_result):
    saving_id = make_saving(balance)
    second_candidates = due_ids()
    stale_saving = db.session.get(Saving, saving_id)
    assert stale_saving.next_payment_date == DUE
    with app.app_context():  # First run has an independent ORM session.
        first_candidates = due_ids()
        assert first_candidates == second_candidates == [saving_id]
        assert batch._process_saving_payment(first_candidates[0], DUE) == first_result
        after_first = payment_state(saving_id)
        db.session.remove()
    assert stale_saving.next_payment_date == DUE  # Deliberately stale identity map.
    assert batch._process_saving_payment(second_candidates[0], DUE) is None
    assert payment_state(saving_id) == after_first
    assert after_first[0] == (900 if balance else 0)
    assert after_first[1] == FUTURE
    assert len(after_first[4]) == 2
    assert len(after_first[5]) == (1 if balance else 0)
    assert SavingPayment.query.filter(SavingPayment.scheduled_date > DUE).count() == 0


def test_existing_installment_is_skipped_without_advancing_cursor(app):
    saving_id = make_saving()
    db.session.add(SavingPayment(saving_id=saving_id, payment_sequence=2,
                                 payment_year_month="2026-09", scheduled_date=DUE,
                                 amount=100, status="PAID"))
    db.session.commit()
    before = payment_state(saving_id)
    assert batch._process_saving_payment(saving_id, DUE) is None
    assert payment_state(saving_id) == before


def test_same_month_record_blocks_duplicate_even_if_date_differs(app):
    saving_id = make_saving()
    db.session.add(SavingPayment(saving_id=saving_id, payment_sequence=2,
                                 payment_year_month="2026-09", scheduled_date=date(2026, 9, 2),
                                 amount=100, status="MISSED"))
    db.session.commit()
    before = payment_state(saving_id)
    assert batch._process_saving_payment(saving_id, DUE) is None
    assert payment_state(saving_id) == before


def test_payment_ledger_failure_rolls_back_whole_installment(app, monkeypatch):
    saving_id = make_saving()
    before = payment_state(saving_id)
    def fail(**kwargs):
        raise RuntimeError("synthetic ledger failure")
    monkeypatch.setattr(batch, "create_ledger", fail)
    result = batch.process_due_saving_payments(DUE)
    assert result == {"paid_count": 0, "missed_count": 0, "failed_count": 1}
    assert payment_state(saving_id) == before


def test_past_due_installment_keeps_existing_missed_policy(app):
    saving_id = make_saving()
    assert batch._process_saving_payment(saving_id, date(2026, 9, 2)) == "MISSED"
    assert Account.query.filter_by(user_id=1).one().balance == 1000
    assert LedgerTransaction.query.count() == 0
    assert db.session.get(Saving, saving_id).next_payment_date == FUTURE
