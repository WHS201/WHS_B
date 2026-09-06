from flask import Blueprint, request

from app.models.user import User
from app.models.features import Inquiry, Report, AuditLog, Post, Comment
from app.models.deposits_savings import LedgerTransaction, FinancialProduct
from app.models.market import MarketTransaction
from app.routes._helpers import success_response
from app.routes.features import body, ledger_data
from app.schemas import features as schemas
from app.services.feature_common import endpoint, user_id, get_row, page, fail, serialize
from app.services import admin_service as admin, community_service as community

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/users")
@endpoint(admin=True)
def users():
    query = User.query
    q = request.args.get("q", "").strip()
    if len(q) > 100:
        fail("INVALID_REQUEST", "검색어는 100자 이하입니다.")
    if q:
        query = query.filter(User.username.contains(q, autoescape=True))
    return success_response(page(query.order_by(User.user_id.desc()), admin.user_data))


@admin_bp.get("/users/<int:target_id>")
@endpoint(admin=True)
def user_detail(target_id):
    return success_response(admin.user_data(get_row(User, target_id)))


@admin_bp.patch("/users/<int:target_id>/status")
@endpoint(admin=True)
def status(target_id):
    data = body(schemas.UserStatusSchema)
    return success_response(admin.change_status(target_id, data["status"], data["reason"]))


@admin_bp.delete("/users/<int:target_id>")
@endpoint(admin=True)
def remove_user(target_id):
    admin.remove_user(target_id, body(schemas.ReasonSchema)["reason"])
    return success_response({})


@admin_bp.post("/users/<int:target_id>/adjustments")
@endpoint(admin=True)
def adjustments(target_id):
    data = body(schemas.AdjustmentSchema)
    return success_response(admin.adjust_account(target_id, data["amount"], data["reason"]), 201)


@admin_bp.get("/products")
@endpoint(admin=True)
def products():
    return success_response(page(FinancialProduct.query.order_by(FinancialProduct.product_id.desc())))


@admin_bp.patch("/products/<int:product_id>")
@endpoint(admin=True)
def update_product(product_id):
    return success_response(admin.patch_product(product_id, body(schemas.ProductPatchSchema)))


@admin_bp.get("/products/<int:product_id>")
@endpoint(admin=True)
def product_detail(product_id):
    row = get_row(FinancialProduct, product_id)
    return success_response({**serialize(row), "options": [serialize(option) for option in row.options]})


@admin_bp.patch("/products/<int:product_id>/options/<int:option_id>")
@endpoint(admin=True)
def update_option(product_id, option_id):
    return success_response(admin.patch_product(product_id, body(schemas.ProductOptionSchema), option_id))


@admin_bp.delete("/products/<int:product_id>")
@endpoint(admin=True)
def delete_product(product_id):
    return success_response(admin.patch_product(product_id, {**body(schemas.ReasonSchema), "is_active": False}))


@admin_bp.get("/transactions")
@endpoint(admin=True)
def transactions():
    query = LedgerTransaction.query
    uid = request.args.get("user_id")
    if uid:
        if not uid.isdecimal():
            fail("INVALID_REQUEST", "user_id는 정수여야 합니다.")
        query = query.filter_by(user_id=int(uid))
    return success_response(page(query.order_by(LedgerTransaction.ledger_transaction_id.desc()), ledger_data))


@admin_bp.get("/transactions/<int:transaction_id>")
@endpoint(admin=True)
def transaction_detail(transaction_id):
    return success_response(ledger_data(get_row(LedgerTransaction, transaction_id)))


@admin_bp.get("/market-transactions")
@endpoint(admin=True)
def market_transactions():
    return success_response(page(MarketTransaction.query.order_by(MarketTransaction.market_transaction_id.desc())))


@admin_bp.get("/posts")
@endpoint(admin=True)
def posts():
    return success_response(community.list_posts())


@admin_bp.get("/comments")
@endpoint(admin=True)
def comments():
    return success_response(page(Comment.query.filter_by(deleted_at=None).order_by(Comment.comment_id.desc())))


@admin_bp.delete("/posts/<int:post_id>")
@endpoint(admin=True)
def delete_post(post_id):
    community.delete_content("POST", post_id, reason=body(schemas.ReasonSchema)["reason"])
    return success_response({})


@admin_bp.delete("/comments/<int:comment_id>")
@endpoint(admin=True)
def delete_comment(comment_id):
    community.delete_content("COMMENT", comment_id, reason=body(schemas.ReasonSchema)["reason"])
    return success_response({})


@admin_bp.get("/reports")
@endpoint(admin=True)
def reports():
    return success_response(page(Report.query.order_by(Report.report_id.desc())))


@admin_bp.patch("/reports/<int:report_id>")
@endpoint(admin=True)
def resolve_report(report_id):
    return success_response(admin.resolve_report(report_id, body(schemas.ResolutionSchema), user_id()))


@admin_bp.get("/inquiries")
@endpoint(admin=True)
def inquiries():
    return success_response(page(Inquiry.query.order_by(Inquiry.inquiry_id.desc()), community.inquiry_data))


@admin_bp.get("/inquiries/<int:inquiry_id>")
@endpoint(admin=True)
def inquiry(inquiry_id):
    return success_response(community.inquiry_data(get_row(Inquiry, inquiry_id)))


@admin_bp.patch("/inquiries/<int:inquiry_id>/answer")
@endpoint(admin=True)
def answer(inquiry_id):
    return success_response(admin.answer_inquiry(inquiry_id, body(schemas.AnswerSchema), user_id()))


@admin_bp.get("/audit-logs")
@endpoint(admin=True)
def logs():
    query = AuditLog.query
    for key in ("action", "target_type"):
        value = request.args.get(key)
        if value:
            if len(value) > 80:
                fail("INVALID_REQUEST", "필터 값이 너무 깁니다.")
            query = query.filter(getattr(AuditLog, key) == value)
    return success_response(page(query.order_by(AuditLog.audit_log_id.desc())))
