from datetime import datetime
from zoneinfo import ZoneInfo

from app.extensions import db

from app.models.monthly_cash_flow import MonthlyCashFlow
from app.models.simulation_setting import SimulationSetting

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


def pay_monthly_income(user_id, year_month):
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

    # 2. 시뮬레이션 설정 조회
    setting = SimulationSetting.query.filter_by(
        user_id=user_id
    ).first()

    if setting is None:
        raise BusinessException(
            code="SIMULATION_SETTING_NOT_FOUND",
            message="시뮬레이션 설정을 찾을 수 없습니다.",
            status_code=404
        )

    # 3. 같은 달에 이미 지급했는지 확인
    existing_cash_flow = MonthlyCashFlow.query.filter_by(
        user_id=user_id,
        year_month=year_month
    ).first()

    if existing_cash_flow is not None:
        raise BusinessException(
            code="MONTHLY_INCOME_ALREADY_PAID",
            message="해당 월의 정기 수입은 이미 지급되었습니다.",
            status_code=409
        )

    # 4. 계좌 조회
    account = get_account_by_user_id(user_id)

    monthly_income = setting.monthly_income
    monthly_expense = setting.monthly_expense

    try:
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
