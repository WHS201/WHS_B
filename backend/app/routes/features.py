"""Additional user APIs, following the existing /api success/error contract."""
from io import BytesIO

from flask import Blueprint, request, send_file

from app.extensions import db
from app.models.features import SavingGoal, AssetSnapshot, Badge, Post, Comment, Inquiry, Report, Attachment
from app.models.deposits_savings import LedgerTransaction
from app.models.market import MarketTransaction
from app.routes._helpers import require_json_body, success_response
from app.schemas import features as schemas
from app.services.feature_common import endpoint, user_id, get_row, serialize, page, fail, current_user
from app.services import portfolio_service as portfolio, community_service as community, profile_service as profiles
from app.services.projection_service import project
from app.services.account_service import get_account_by_user_id
from app.services.audit_service import audit

features_bp = Blueprint("features", __name__, url_prefix="/api")


def body(schema, partial=False):
    payload = schema().load(require_json_body(), partial=partial)
    if not payload:
        fail("INVALID_REQUEST", "변경할 항목을 입력해 주세요.")
    return payload


@features_bp.get("/goals")
@endpoint()
def goals():
    result = portfolio.dashboard(user_id())
    return success_response(result["goals"])


@features_bp.post("/goals")
@endpoint()
def create_goal():
    return success_response(portfolio.save_goal(user_id(), body(schemas.GoalSchema)), 201)


@features_bp.get("/goals/<int:goal_id>")
@endpoint()
def get_goal(goal_id):
    row = get_row(SavingGoal, goal_id, owner=user_id())
    return success_response(portfolio.goal_data(row, portfolio.valuation(user_id())["total_assets"]))


@features_bp.patch("/goals/<int:goal_id>")
@endpoint()
def update_goal(goal_id):
    return success_response(portfolio.save_goal(user_id(), body(schemas.GoalSchema, partial=True), goal_id))


@features_bp.delete("/goals/<int:goal_id>")
@endpoint()
def delete_goal(goal_id):
    get_account_by_user_id(user_id())
    db.session.delete(get_row(SavingGoal, goal_id, owner=user_id(), lock=True))
    db.session.commit()
    return success_response({})


@features_bp.post("/simulations/free")
@endpoint()
def free_projection():
    return success_response(project(require_json_body()))


@features_bp.post("/goals/<int:goal_id>/simulation")
@endpoint()
def goal_projection(goal_id):
    return success_response(project(require_json_body(), user_id(), goal_id))


@features_bp.get("/dashboard")
@endpoint()
def dashboard():
    return success_response(portfolio.dashboard(user_id()))


@features_bp.get("/dashboard/history")
@endpoint()
def history():
    return success_response(page(AssetSnapshot.query.filter_by(user_id=user_id()).order_by(AssetSnapshot.snapshot_date.desc())))


def ledger_data(row):
    return {**serialize(row), "entries": [serialize(e) for e in row.entries]}


@features_bp.get("/transactions")
@endpoint()
def transactions():
    query = LedgerTransaction.query.filter_by(user_id=user_id())
    kind = request.args.get("transaction_type")
    if kind:
        if len(kind) > 50:
            fail("INVALID_REQUEST", "거래 구분이 너무 깁니다.")
        query = query.filter_by(transaction_type=kind)
    return success_response(page(query.order_by(LedgerTransaction.ledger_transaction_id.desc()), ledger_data))


@features_bp.get("/transactions/<int:transaction_id>")
@endpoint()
def transaction_detail(transaction_id):
    return success_response(ledger_data(get_row(LedgerTransaction, transaction_id, owner=user_id())))


@features_bp.get("/investments/transactions")
@endpoint()
def investment_transactions():
    return success_response(page(MarketTransaction.query.filter_by(user_id=user_id()).order_by(MarketTransaction.market_transaction_id.desc())))


@features_bp.get("/profiles/me")
@endpoint()
def my_profile():
    return success_response(profiles.profile(user_id(), user_id()))


@features_bp.get("/profiles/<int:target_id>")
@endpoint()
def public_profile(target_id):
    return success_response(profiles.profile(target_id, user_id()))


@features_bp.patch("/profiles/me")
@endpoint()
def update_profile():
    return success_response(profiles.update_profile(user_id(), body(schemas.ProfileSchema)))


@features_bp.get("/profiles/me/visibility")
@endpoint()
def visibility():
    return success_response(profiles.visibility(user_id()))


@features_bp.patch("/profiles/me/visibility")
@endpoint()
def update_visibility():
    return success_response(profiles.update_visibility(user_id(), body(schemas.VisibilitySchema)))


@features_bp.get("/badges")
@endpoint()
def badges():
    return success_response([serialize(b) for b in Badge.query.order_by(Badge.badge_id)])


@features_bp.get("/badges/me")
@endpoint()
def my_badges():
    return success_response(portfolio.dashboard(user_id())["badges"])


@features_bp.get("/posts")
@endpoint()
def posts():
    return success_response(community.list_posts(viewer_id=user_id()))


@features_bp.post("/posts")
@endpoint()
def create_post():
    return success_response(community.save_post(user_id(), body(schemas.PostSchema)), 201)


@features_bp.get("/posts/<int:post_id>")
@endpoint()
def post_detail(post_id):
    return success_response(community.post_data(
        community.live_post(post_id),
        viewer_id=user_id(),
    ))


@features_bp.patch("/posts/<int:post_id>")
@endpoint()
def update_post(post_id):
    return success_response(community.save_post(user_id(), body(schemas.PostSchema, partial=True), post_id))


@features_bp.delete("/posts/<int:post_id>")
@endpoint()
def delete_post(post_id):
    community.delete_content("POST", post_id, owner=user_id())
    return success_response({})


@features_bp.get("/posts/<int:post_id>/comments")
@endpoint()
def comments(post_id):
    community.live_post(post_id)
    return success_response(page(Comment.query.filter_by(post_id=post_id, deleted_at=None).order_by(Comment.comment_id), lambda c: serialize(c, exclude=("deleted_at",))))


@features_bp.post("/posts/<int:post_id>/comments")
@endpoint()
def create_comment(post_id):
    return success_response(community.save_comment(user_id(), body(schemas.CommentSchema), post_id=post_id), 201)


@features_bp.patch("/comments/<int:comment_id>")
@endpoint()
def update_comment(comment_id):
    return success_response(community.save_comment(user_id(), body(schemas.CommentSchema), comment_id=comment_id))


@features_bp.delete("/comments/<int:comment_id>")
@endpoint()
def delete_comment(comment_id):
    community.delete_content("COMMENT", comment_id, owner=user_id())
    return success_response({})


@features_bp.put("/posts/<int:post_id>/reaction")
@endpoint()
def reaction(post_id):
    return success_response(community.react(user_id(), post_id, body(schemas.ReactionSchema)["reaction_type"]))


@features_bp.post("/reports")
@endpoint()
def create_report():
    return success_response(community.create_report(user_id(), body(schemas.ReportSchema)), 201)


@features_bp.get("/reports/me")
@endpoint()
def my_reports():
    return success_response(page(Report.query.filter_by(reporter_user_id=user_id()).order_by(Report.report_id.desc())))


@features_bp.post("/inquiries")
@endpoint()
def create_inquiry():
    return success_response(community.create_inquiry(user_id(), body(schemas.InquirySchema)), 201)


@features_bp.get("/inquiries")
@endpoint()
def inquiries():
    return success_response(page(Inquiry.query.filter_by(user_id=user_id()).order_by(Inquiry.inquiry_id.desc()), community.inquiry_data))


@features_bp.get("/inquiries/<int:inquiry_id>")
@endpoint()
def inquiry_detail(inquiry_id):
    return success_response(community.inquiry_data(get_row(Inquiry, inquiry_id, owner=user_id())))


@features_bp.post("/posts/<int:post_id>/images")
@endpoint()
def post_images(post_id):
    return success_response(community.upload(user_id(), "POST", post_id, request.files.getlist("images")), 201)


@features_bp.post("/inquiries/<int:inquiry_id>/images")
@endpoint()
def inquiry_images(inquiry_id):
    return success_response(community.upload(user_id(), "INQUIRY", inquiry_id, request.files.getlist("images")), 201)


@features_bp.get("/attachments/<string:attachment_id>")
@endpoint()
def attachment(attachment_id):
    row = get_row(Attachment, attachment_id)
    if row.post_id:
        community.live_post(row.post_id)
    elif row.user_id != user_id() and current_user().role != "ADMIN":
        fail("NOT_FOUND", "첨부파일을 찾을 수 없습니다.", 404)
    response = send_file(BytesIO(row.data), mimetype=row.mime_type, download_name="image", max_age=0)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@features_bp.delete("/attachments/<string:attachment_id>")
@endpoint()
def delete_attachment(attachment_id):
    row = get_row(Attachment, attachment_id, owner=user_id(), lock=True)
    audit("IMAGE_DELETE", "posts" if row.post_id else "inquiries", row.post_id or row.inquiry_id)
    db.session.delete(row)
    db.session.commit()
    return success_response({})
