from app import create_app
from app.services.deposit_saving_batch_service import run_daily_financial_batch
from app.services.monthly_income_batch_service import process_monthly_incomes
from datetime import datetime
from zoneinfo import ZoneInfo


app = create_app()

with app.app_context():
    reference_date = datetime.now(ZoneInfo("Asia/Seoul")).date()
    income_result = process_monthly_incomes(reference_date=reference_date)
    if income_result["failed_count"] or income_result.get("not_due"):
        raise RuntimeError("Financial batch deferred until monthly income recovery succeeds")
    print(run_daily_financial_batch(reference_date=reference_date))
