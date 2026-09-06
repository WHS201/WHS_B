from app.models.account import Account
from app.models.deposits_savings import (
    Deposit,
    DepositPreferenceCondition,
    Saving,
    SavingPreferenceCondition,
    SavingPayment,
    LedgerTransaction,
    LedgerEntry,
)
from app.models.market import MarketHolding, MarketTransaction
from app.models.monthly_cash_flow import MonthlyCashFlow
from app.models.simulation_setting import SimulationSetting
from app.models.features import SavingGoal, AssetSnapshot, UserBadge, ProfileVisibility, Inquiry, Attachment
from app.models.user import User
from app.extensions import db


def delete_simulation_activity(user_id):
    # Community/report/audit records survive a simulation reset. Inquiries and
    # their private images are reset with finance data, avoiding stale ledger IDs.
    for inquiry in Inquiry.query.filter_by(user_id=user_id).all():
        Attachment.query.filter_by(inquiry_id=inquiry.inquiry_id).delete(synchronize_session=False)
        db.session.delete(inquiry)
    for model in (SavingGoal, AssetSnapshot, UserBadge, ProfileVisibility):
        model.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    user = db.session.get(User, user_id)
    if user:
        user.representative_badge_id = None
    db.session.flush()

    # 예금에 연결된 우대조건 삭제
    deposit_ids = [
        deposit_id
        for (deposit_id,) in Deposit.query.with_entities(
            Deposit.deposit_id
        ).filter_by(user_id=user_id).all()
    ]

    if deposit_ids:
        DepositPreferenceCondition.query.filter(
            DepositPreferenceCondition.deposit_id.in_(deposit_ids)
        ).delete(synchronize_session=False)

    # 적금에 연결된 우대조건 / 납입내역 삭제
    saving_ids = [
        saving_id
        for (saving_id,) in Saving.query.with_entities(
            Saving.saving_id
        ).filter_by(user_id=user_id).all()
    ]

    if saving_ids:
        SavingPreferenceCondition.query.filter(
            SavingPreferenceCondition.saving_id.in_(saving_ids)
        ).delete(synchronize_session=False)

        SavingPayment.query.filter(
            SavingPayment.saving_id.in_(saving_ids)
        ).delete(synchronize_session=False)

    # 예금 / 적금 삭제
    Deposit.query.filter_by(
        user_id=user_id
    ).delete(synchronize_session=False)

    Saving.query.filter_by(
        user_id=user_id
    ).delete(synchronize_session=False)

    # 주식 / ETF 보유 및 거래내역 삭제
    MarketHolding.query.filter_by(
        user_id=user_id
    ).delete(synchronize_session=False)

    MarketTransaction.query.filter_by(
        user_id=user_id
    ).delete(synchronize_session=False)

    # 금융 원장 상세내역 삭제
    ledger_transaction_ids = [
        ledger_transaction_id
        for (ledger_transaction_id,) in LedgerTransaction.query.with_entities(
            LedgerTransaction.ledger_transaction_id
        ).filter_by(user_id=user_id).all()
    ]

    if ledger_transaction_ids:
        LedgerEntry.query.filter(
            LedgerEntry.ledger_transaction_id.in_(ledger_transaction_ids)
        ).delete(synchronize_session=False)

    # 금융 원장 거래내역 삭제
    LedgerTransaction.query.filter_by(
        user_id=user_id
    ).delete(synchronize_session=False)

    # 월별 현금흐름 삭제
    MonthlyCashFlow.query.filter_by(
        user_id=user_id
    ).delete(synchronize_session=False)


def delete_user_financial_data(user_id):
    delete_simulation_activity(user_id)

    # 시뮬레이션 설정 삭제
    SimulationSetting.query.filter_by(
        user_id=user_id
    ).delete(synchronize_session=False)

    # 가상계좌 삭제
    Account.query.filter_by(
        user_id=user_id
    ).delete(synchronize_session=False)
