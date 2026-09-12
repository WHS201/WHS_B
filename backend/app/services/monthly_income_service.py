from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from app.extensions import db

from app.models.monthly_cash_flow import MonthlyCashFlow
from app.models.simulation_setting import SimulationSetting
from app.models.deposits_savings import LedgerTransaction
from app.models.features import AuditLog
from app.models.user import User

from app.services.account_service import (
    get_account_by_user_id,
    credit,
    debit
)

from app.services.ledger_service import create_ledger

from app.errors.exceptions import BusinessException

from app.constants import (
    MonthlyCashFlowStatus,
    TransactionType,
    EntryType
)


def automatic_income_eligible(setting, reference_date, lock=False):
    """Recover only users initialized by this month's original 00:05 KST run.

    Existing initialization/reset audits cover zero initial assets as well.
    The initial-funding ledger also supports older positive-asset setups.
    """
    if not setting.is_initial_asset_set:
        return False
    cutoff = datetime.combine(reference_date.replace(day=1), time(0, 5),
                              tzinfo=ZoneInfo("Asia/Seoul")).astimezone(timezone.utc).replace(tzinfo=None)

    def latest(query):
        return (query.populate_existing().with_for_update() if lock else query).first()

    initialized = latest(AuditLog.query.filter(
        AuditLog.target_type == "simulation_settings",
        AuditLog.target_id == setting.simulation_setting_id,
        AuditLog.action.in_(["CREATE", "UPDATE"]),
        AuditLog.after_value["is_initial_asset_set"].as_boolean().is_(True),
    ).order_by(AuditLog.audit_log_id.desc()))
    reset = latest(AuditLog.query.filter_by(
        target_type="users", target_id=setting.user_id, action="SIMULATION_RESET",
    ).order_by(AuditLog.audit_log_id.desc()))
    funding = latest(LedgerTransaction.query.filter_by(
        user_id=setting.user_id, transaction_type="INITIAL_ASSET",
    ).order_by(LedgerTransaction.ledger_transaction_id.desc()))
    evidence = []
    if initialized and (not reset or initialized.audit_log_id > reset.audit_log_id):
        evidence.append(initialized.created_at)
    if funding and (not reset or funding.created_at >= reset.created_at):
        evidence.append(funding.created_at)
    if not evidence:
        # An old, unchanged initialized setting proves it was ready before the
        # cutoff. After a reset, require evidence of the new initialization.
        return not reset and setting.updated_at <= cutoff
    return max(evidence) <= cutoff


def pay_monthly_income(user_id, year_month, automatic=False):
    # 1. YYYY-MM 형식 검사
    if (
        not isinstance(year_month, str)
        or len(year_month) != 7
        or year_month[4] != "-"
    ):
        raise BusinessException(
            code="INVALID_YEAR_MONTH",
            message="year_month 형식은 YYYY-MM이어야 합니다.",
            status_code=400
        )

    try:
        year = int(year_month[:4])
        month = int(year_month[5:7])
    except ValueError:
        raise BusinessException(
            code="INVALID_YEAR_MONTH",
            message="year_month 형식은 YYYY-MM이어야 합니다.",
            status_code=400
        )

    if year < 1 or month < 1 or month > 12:
        raise BusinessException(
            code="INVALID_YEAR_MONTH",
            message="유효하지 않은 연월입니다.",
            status_code=400
        )

    # 서버의 한국 시간을 기준으로 현재 지급 가능한 월 결정
    payable_year_month = datetime.now(
        ZoneInfo("Asia/Seoul")
    ).strftime("%Y-%m")

    # 과거 월 소급 지급과 미래 월 선지급 차단
    if year_month != payable_year_month:
        raise BusinessException(
            code="MONTHLY_INCOME_MONTH_NOT_PAYABLE",
            message=(
                f"월 정기 수입은 현재 월({payable_year_month})만 "
                "지급할 수 있습니다."
            ),
            status_code=400
        )

    # 이후 조회와 저장에는 서버가 결정한 지급월 사용
    year_month = payable_year_month

    try:
        # Serialize payment/reset on the account, then perform current locking
        # reads. A pre-lock lookup can be stale under InnoDB REPEATABLE READ.
        account = get_account_by_user_id(user_id)
        db.session.refresh(account, with_for_update=True)
        setting = SimulationSetting.query.filter_by(user_id=user_id).populate_existing().with_for_update().first()
        if setting is None:
            raise BusinessException(code="SIMULATION_SETTING_NOT_FOUND", status_code=404,
                                    message="시뮬레이션 설정을 찾을 수 없습니다.")
        existing_cash_flow = MonthlyCashFlow.query.filter_by(
            user_id=user_id, year_month=year_month,
        ).populate_existing().with_for_update().first()
        if existing_cash_flow is not None:
            raise BusinessException(code="MONTHLY_INCOME_ALREADY_PAID", status_code=409,
                                    message="해당 월의 정기 수입은 이미 지급되었습니다.")
        if automatic:
            user = User.query.filter_by(user_id=user_id).populate_existing().with_for_update().first()
            if (not user or user.status != "ACTIVE" or not automatic_income_eligible(
                setting, datetime.now(ZoneInfo("Asia/Seoul")).date(), lock=True,
            )):
                raise BusinessException(code="MONTHLY_INCOME_NOT_ELIGIBLE", status_code=422,
                                        message="이번 달 자동 월수입 지급 대상이 아닙니다.")
        monthly_income = setting.monthly_income
        monthly_expense = setting.monthly_expense
        # 5. 해당 월 지급 기록을 먼저 생성하여 원장 reference_id 확보
        cash_flow = MonthlyCashFlow(
            user_id=user_id,
            year_month=year_month,
            income_amount=monthly_income,
            status=MonthlyCashFlowStatus.PROCESSED.value
        )

        db.session.add(cash_flow)
        db.session.flush()

        # 6. 월 수입이 0원보다 클 경우 계좌 입금 + 원장 기록
        if monthly_income > 0:
            credit(
                account=account,
                amount=monthly_income
            )

            create_ledger(
                account=account,
                transaction_type=TransactionType.MONTHLY_INCOME.value,
                amount=monthly_income,
                entry_type=EntryType.CREDIT.value,
                reference_type="MONTHLY_CASH_FLOW",
                reference_id=cash_flow.monthly_cash_flow_id
            )
        # 7. 월 예상 지출이 0원보다 클 경우 계좌 차감 + 원장 기록
        if monthly_expense > 0:
            debit(
                account=account,
                amount=monthly_expense
            )

            create_ledger(
                account=account,
                transaction_type=TransactionType.MONTHLY_EXPENSE.value,
                amount=monthly_expense,
                entry_type=EntryType.DEBIT.value,
                reference_type="MONTHLY_CASH_FLOW",
                reference_id=cash_flow.monthly_cash_flow_id
            )

        # 8. 모든 작업 성공 시 한 번만 commit
        db.session.commit()

        return account, cash_flow

    except Exception:
        db.session.rollback()
        raise
