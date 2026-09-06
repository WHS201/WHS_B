from datetime import datetime

from app.extensions import db
from app.models.user import User
from app.models.features import Report, Inquiry
from app.models.deposits_savings import FinancialProduct, FinancialProductOption
from app.services.feature_common import fail, get_row, serialize
from app.services.audit_service import audit
from app.services.account_service import get_account_by_user_id, credit, debit
from app.services.ledger_service import create_ledger


def user_data(user):
    return serialize(user, exclude=("password_hash", "failed_login_count", "login_locked_until", "token_version"))


def change_status(target_id, status, reason):
    user = get_row(User, target_id, lock=True)
    if user.role == "ADMIN" or user.status == "WITHDRAWN":
        fail("INVALID_USER_STATE", "관리자 또는 탈퇴한 계정은 변경할 수 없습니다.", 409)
    before = user.status
    user.status = status
    if before != status:
        user.token_version += 1
    audit("ADMIN_USER_STATUS", "users", target_id, {"status": before}, {"status": status}, reason)
    db.session.commit()
    return user_data(user)


def remove_user(target_id, reason):
    from app.models.social_account import SocialAccount
    from app.services.financial_cleanup_service import delete_user_financial_data
    get_account_by_user_id(target_id)
    user = get_row(User, target_id, lock=True)
    if user.role == "ADMIN" or user.status == "WITHDRAWN":
        fail("INVALID_USER_STATE", "관리자 또는 이미 탈퇴한 계정입니다.", 409)
    delete_user_financial_data(target_id)
    SocialAccount.query.filter_by(user_id=target_id).delete(synchronize_session=False)
    user.status = "WITHDRAWN"
    user.token_version += 1
    audit("ADMIN_USER_WITHDRAW", "users", target_id, reason=reason)
    db.session.commit()


def adjust_account(target_id, amount, reason):
    account = get_account_by_user_id(target_id)
    user = get_row(User, target_id, lock=True)
    if user.status == "WITHDRAWN" or amount == 0:
        fail("INVALID_ADJUSTMENT", "탈퇴한 계정 또는 0원 조정은 허용하지 않습니다.", 422)
    before = account.balance
    (credit if amount > 0 else debit)(account, abs(amount))
    row = create_ledger(account, "ADMIN_ADJUSTMENT", abs(amount), "CREDIT" if amount > 0 else "DEBIT", "USER", target_id)
    db.session.flush()
    audit("ADMIN_ACCOUNT_ADJUSTMENT", "ledger_transactions", row.ledger_transaction_id,
          {"balance": before}, {"balance": account.balance, "amount": amount}, reason)
    db.session.commit()
    return {"ledger_transaction_id": row.ledger_transaction_id, "balance_after": account.balance}


def patch_product(product_id, payload, option_id=None):
    row = get_row(FinancialProductOption if option_id else FinancialProduct, option_id or product_id, lock=True)
    if option_id and row.product_id != product_id:
        fail("NOT_FOUND", "상품 옵션을 찾을 수 없습니다.", 404)
    before = serialize(row)
    row.sync_locked = payload.get("sync_locked", True)
    for key, value in payload.items():
        if key != "reason":
            setattr(row, key, value)
    if option_id:
        if row.max_amount < row.min_amount or row.max_interest_rate < row.base_interest_rate:
            fail("INVALID_PRODUCT_OPTION", "최대 금액·금리는 최소 금액·기본 금리 이상이어야 합니다.", 422)
    audit("ADMIN_PRODUCT_UPDATE", row.__tablename__, option_id or product_id, before, serialize(row), payload["reason"])
    db.session.commit()
    return serialize(row)


def resolve_report(report_id, payload, admin_id):
    row = get_row(Report, report_id, lock=True)
    if row.status != "PENDING":
        fail("ALREADY_RESOLVED", "이미 처리된 신고입니다.", 409)
    row.status, row.resolution_reason = payload["status"], payload["reason"]
    row.resolved_at, row.resolved_by = datetime.utcnow(), admin_id
    audit("REPORT_RESOLVE", "reports", report_id, after={"status": row.status}, reason=payload["reason"])
    db.session.commit()
    return serialize(row)


def answer_inquiry(inquiry_id, payload, admin_id):
    row = get_row(Inquiry, inquiry_id, lock=True)
    row.status, row.admin_answer = "ANSWERED", payload["answer"]
    row.answered_at, row.answered_by = datetime.utcnow(), admin_id
    audit("INQUIRY_ANSWER", "inquiries", inquiry_id, reason=payload["reason"])
    db.session.commit()
    return serialize(row)
