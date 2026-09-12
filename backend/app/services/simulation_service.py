from app.extensions import db

from app.models.simulation_setting import SimulationSetting
from app.services.account_service import (
    get_account_by_user_id,
    credit
)

from app.services.ledger_service import create_ledger
from app.services.financial_cleanup_service import delete_simulation_activity

from app.errors.exceptions import BusinessException

from app.constants import (
    TransactionType,
    EntryType
)


def set_initial_asset(user_id, initial_asset):
    account = get_account_by_user_id(user_id)

    setting = (
        SimulationSetting.query
        .filter_by(user_id=user_id)
        .populate_existing()
        .with_for_update()
        .first()
    )

    if setting is None:
        raise BusinessException(
            code="SIMULATION_SETTING_NOT_FOUND",
            message="시뮬레이션 설정을 찾을 수 없습니다.",
            status_code=404
        )

    if setting.is_initial_asset_set:
        raise BusinessException(
            code="INITIAL_ASSET_ALREADY_SET",
            message="초기 자산은 이미 설정되었습니다.",
            status_code=422
        )

    try:
        if initial_asset > 0:
            credit(
                account=account,
                amount=initial_asset
            )

            create_ledger(
                account=account,
                transaction_type=TransactionType.INITIAL_ASSET.value,
                amount=initial_asset,
                entry_type=EntryType.CREDIT.value,
                reference_type="SIMULATION_SETTING",
                reference_id=setting.simulation_setting_id
            )

        setting.initial_asset = initial_asset
        setting.is_initial_asset_set = True

        db.session.commit()

        return account, setting

    except Exception:
        db.session.rollback()
        raise


def update_simulation_settings(
    user_id,
    monthly_income,
    monthly_expense
):
    setting = SimulationSetting.query.filter_by(
        user_id=user_id
    ).first()

    if setting is None:
        raise BusinessException(
            code="SIMULATION_SETTING_NOT_FOUND",
            message="시뮬레이션 설정을 찾을 수 없습니다.",
            status_code=404
        )

    if monthly_expense > monthly_income:
        raise BusinessException(
            code="INVALID_MONTHLY_EXPENSE",
            message="월 예상 지출은 월 정기 수입을 초과할 수 없습니다.",
            status_code=422
        )

    try:
        setting.monthly_income = monthly_income
        setting.monthly_expense = monthly_expense

        db.session.commit()

        return setting

    except Exception:
        db.session.rollback()
        raise


def reset_simulation_data(user_id):
    account = get_account_by_user_id(user_id)

    setting = SimulationSetting.query.filter_by(
        user_id=user_id
    ).first()

    if setting is None:
        raise BusinessException(
            code="SIMULATION_SETTING_NOT_FOUND",
            message="시뮬레이션 설정을 찾을 수 없습니다.",
            status_code=404
        )

    try:
        from app.services.audit_service import audit
        audit("SIMULATION_RESET", "users", user_id, before={"balance": account.balance}, after={"balance": 0})
        delete_simulation_activity(user_id)

        account.balance = 0

        setting.initial_asset = 0
        setting.is_initial_asset_set = False
        setting.monthly_income = 0
        setting.monthly_expense = 0

        db.session.commit()

        return account, setting

    except Exception:
        db.session.rollback()
        raise
