from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from app import create_app

from app.services.deposit_saving_batch_service import (
    run_daily_financial_batch,
)

from app.services.fss_product_service import (
    sync_products,
)

from app.services.monthly_income_batch_service import (
    process_monthly_incomes,
)

from app.services.portfolio_service import (
    record_daily_snapshots,
)

from app.services.feature_setup import (
    cleanup_request_buckets,
)


app = create_app()


def run_financial_batch():
    with app.app_context():
        # 월 수입과 예·적금 처리에 같은 한국 날짜 기준을 사용합니다.
        reference_date = datetime.now(ZoneInfo("Asia/Seoul")).date()

        # 매월 1일에는 월 수입·지출 처리가 끝난 후 예·적금을 처리합니다.
        # 월 수입 처리 중 예외가 발생하면 아래 예·적금 처리는 실행되지 않습니다.
        if reference_date.day == 1:
            income_result = process_monthly_incomes()
            app.logger.info(
                "Monthly income batch result: %s",
                income_result,
            )

        financial_result = run_daily_financial_batch(
            reference_date=reference_date,
        )
        app.logger.info(
            "daily financial batch result: %s",
            financial_result,
        )


def run_fss_sync():
    with app.app_context():
        app.logger.info(
            "FSS product sync result: %s",
            sync_products(),
        )


def run_asset_snapshots():
    with app.app_context():
        result = record_daily_snapshots()

        app.logger.info(
            "asset snapshots result: %s",
            result,
        )

        cleanup_request_buckets()


scheduler = BlockingScheduler(
    timezone="Asia/Seoul",
)


# 매일 23:50
scheduler.add_job(
    run_asset_snapshots,
    "cron",
    hour=23,
    minute=50,
)


# 매일 00:05 — 1일에는 월 수입·지출 처리 후 예·적금 처리
scheduler.add_job(
    run_financial_batch,
    "cron",
    hour=0,
    minute=5,
)


# 매일 02:00
scheduler.add_job(
    run_fss_sync,
    "cron",
    hour=2,
    minute=0,
)


if __name__ == "__main__":
    scheduler.start()
