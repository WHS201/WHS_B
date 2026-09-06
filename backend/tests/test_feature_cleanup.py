from datetime import date
from io import BytesIO

from PIL import Image

from app.extensions import db
from app.models.account import Account
from app.models.deposits_savings import LedgerTransaction
from app.models.features import (
    AssetSnapshot, Attachment, AuditLog, Badge, Comment, Inquiry, Post,
    ProfileVisibility, Report, SavingGoal, UserBadge,
)
from app.models.simulation_setting import SimulationSetting
from app.models.user import User
from app.services.ledger_service import create_ledger


def upload_image(client, auth, parent, identifier):
    output = BytesIO()
    Image.new("RGB", (2, 2), "green").save(output, format="PNG")
    output.seek(0)
    response = client.post(f"/api/{parent}/{identifier}/images", headers=auth(), data={
        "images": (output, "test.png", "image/png"),
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"][0]["attachment_id"]


def test_reset_removes_financial_features_and_keeps_community_and_audit(client, auth, make_goal, make_post, make_inquiry):
    make_goal()
    other_goal = make_goal(2)
    post = make_post()
    response = client.post(f"/api/posts/{post['post_id']}/comments", headers=auth(), json={"content": "기록 보존"})
    assert response.status_code == 201
    response = client.post("/api/reports", headers=auth(), json={
        "target_type": "POST", "target_id": post["post_id"], "reason": "기록 확인",
    })
    assert response.status_code == 201
    post_image_id = upload_image(client, auth, "posts", post["post_id"])
    account = Account.query.filter_by(user_id=1).one()
    original_number = account.account_number
    ledger = create_ledger(account, "INITIAL_ASSET", 1000, "CREDIT", "USER", 1)
    badge = Badge.query.filter_by(code="FIRST_GOAL").one()
    db.session.add_all([
        AssetSnapshot(user_id=1, snapshot_date=date(2026, 1, 1), amounts={"cash": 1000}, total_assets=1000),
        UserBadge(user_id=1, badge_id=badge.badge_id),
        ProfileVisibility(user_id=1, show_total_assets=True),
    ])
    db.session.get(User, 1).representative_badge_id = badge.badge_id
    db.session.commit()
    inquiry = make_inquiry(related_ledger_transaction_id=ledger.ledger_transaction_id)
    inquiry_image_id = upload_image(client, auth, "inquiries", inquiry["inquiry_id"])
    original_log_ids = {row.audit_log_id for row in AuditLog.query.all()}
    response = client.delete("/api/simulation/reset", headers=auth())
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"] == {
        "balance": 0, "initial_asset": 0, "is_initial_asset_set": False,
        "monthly_income": 0, "monthly_expense": 0,
    }
    db.session.expire_all()
    assert SavingGoal.query.filter_by(user_id=1).count() == 0
    assert db.session.get(SavingGoal, other_goal["goal_id"]) is not None
    assert AssetSnapshot.query.filter_by(user_id=1).count() == 0
    assert UserBadge.query.filter_by(user_id=1).count() == 0
    assert Inquiry.query.filter_by(user_id=1).count() == 0
    assert ProfileVisibility.query.filter_by(user_id=1).count() == 0
    assert LedgerTransaction.query.filter_by(user_id=1).count() == 0
    assert db.session.get(Attachment, inquiry_image_id) is None
    assert db.session.get(Attachment, post_image_id) is not None
    assert Post.query.filter_by(user_id=1).count() == 1
    assert Comment.query.filter_by(user_id=1).count() == 1
    assert Report.query.filter_by(reporter_user_id=1).count() == 1
    assert original_log_ids <= {row.audit_log_id for row in AuditLog.query.all()}
    user = db.session.get(User, 1)
    assert user.nickname == "사용자1" and user.role == "USER" and user.status == "ACTIVE"
    assert user.representative_badge_id is None
    assert Account.query.filter_by(user_id=1).one().account_number == original_number
    assert SimulationSetting.query.filter_by(user_id=1).one().is_initial_asset_set is False
    assert Account.query.filter_by(user_id=2).one().balance == 1000


def test_admin_withdrawal_keeps_operational_records_and_revokes_session(client, auth, make_post, make_goal, make_inquiry):
    old_headers = auth()
    make_post()
    make_goal()
    make_inquiry()
    response = client.delete("/api/admin/users/1", headers=auth(3), json={"reason": "회원 탈퇴 요청 처리"})
    assert response.status_code == 200, response.get_json()
    user = db.session.get(User, 1)
    assert user.status == "WITHDRAWN" and user.token_version == 1
    assert Account.query.filter_by(user_id=1).count() == 0
    assert SimulationSetting.query.filter_by(user_id=1).count() == 0
    assert SavingGoal.query.filter_by(user_id=1).count() == 0
    assert Inquiry.query.filter_by(user_id=1).count() == 0
    assert Post.query.filter_by(user_id=1).count() == 1
    assert AuditLog.query.filter_by(action="ADMIN_USER_WITHDRAW", target_id=1).count() == 1
    response = client.get("/api/goals", headers=old_headers)
    assert response.status_code == 401
