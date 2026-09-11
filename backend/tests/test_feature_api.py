from datetime import date
from io import BytesIO

import pytest
from PIL import Image

from app.extensions import db
from app.models.account import Account
from app.models.deposits_savings import LedgerTransaction, LedgerEntry
from app.models.features import (
    Attachment, AuditLog, AssetSnapshot, Badge, Comment, Inquiry,
    PostReaction, Report, SavingGoal, UserBadge,
)
from app.models.user import User
from app.services import admin_service, portfolio_service
from app.services.ledger_service import create_ledger


def data(response, status=200):
    assert response.status_code == status, response.get_json()
    assert response.get_json()["success"] is True
    return response.get_json()["data"]


def error(response, status, code=None):
    assert response.status_code == status, response.get_json()
    assert response.get_json()["success"] is False
    if code:
        assert response.get_json()["error"]["code"] == code


def png_file():
    output = BytesIO()
    Image.new("RGB", (3, 2), "blue").save(output, format="PNG")
    output.seek(0)
    return output


@pytest.mark.parametrize("path", ["/api/goals", "/api/dashboard", "/api/posts", "/api/profiles/me", "/api/inquiries", "/api/admin/users"])
def test_new_routes_require_authentication(client, path):
    error(client.get(path), 401, "AUTH_REQUIRED")


def test_user_cannot_access_admin_data(client, auth):
    for path in ("/api/admin/users", "/api/admin/audit-logs", "/api/admin/inquiries"):
        error(client.get(path, headers=auth()), 403, "FORBIDDEN")
    users = data(client.get("/api/admin/users", headers=auth(3)))["items"]
    assert len(users) == 3
    assert all("password_hash" not in item and "token_version" not in item for item in users)


def test_goals_enforce_ownership_and_maximum_five(client, auth, make_goal):
    goal = make_goal()
    for method in ("get", "patch", "delete"):
        arguments = {"headers": auth(2)}
        if method == "patch":
            arguments["json"] = {"goal_name": "변경"}
        error(getattr(client, method)(f"/api/goals/{goal['goal_id']}", **arguments), 404)
    for index in range(4):
        make_goal(goal_name=f"목표{index}")
    response = client.post("/api/goals", headers=auth(), json={
        "goal_name": "여섯 번째", "target_amount": 9000, "target_date": "2027-01-01",
    })
    error(response, 422, "GOAL_LIMIT")
    assert SavingGoal.query.filter_by(user_id=1).count() == 5
    make_goal(2)


@pytest.mark.parametrize("overrides,status,code", [
    ({"target_date": "2026-01-01"}, 422, "INVALID_TARGET_DATE"),
    ({"target_amount": 999}, 422, "INVALID_TARGET_AMOUNT"),
    ({"target_amount": 0}, 400, "INVALID_REQUEST"),
    ({"target_amount": 1000000001}, 400, "INVALID_REQUEST"),
    ({"target_amount": 1.5}, 400, "INVALID_REQUEST"),
    ({"goal_name": "   "}, 400, "INVALID_REQUEST"),
    ({"user_id": 2}, 400, "INVALID_REQUEST"),
])
def test_goal_validation(client, auth, overrides, status, code):
    error(client.post("/api/goals", headers=auth(), json={
        "goal_name": "여행 자금", "target_amount": 5000, "target_date": "2027-01-01", **overrides,
    }), status, code)
    assert SavingGoal.query.count() == 0


def test_completed_goal_and_badge_are_recorded_once(client, auth, make_goal, goal_clock):
    goal = make_goal(target_amount=1500)
    goal_clock.advance(days=7)
    Account.query.filter_by(user_id=1).one().balance = 1500
    db.session.commit()
    for _ in range(2):
        dashboard = data(client.get("/api/dashboard", headers=auth()))
        assert dashboard["goals"][0]["status"] == "COMPLETED"
        assert [badge["code"] for badge in dashboard["badges"]] == ["FIRST_GOAL"]
    assert UserBadge.query.filter_by(user_id=1).count() == 1
    error(client.patch(f"/api/goals/{goal['goal_id']}", headers=auth(), json={"goal_name": "새 이름"}), 409, "GOAL_COMPLETED")


def test_profile_defaults_private_and_shares_only_selected_fields(client, auth, make_goal):
    make_goal()
    private = data(client.get("/api/profiles/1", headers=auth(2)))
    assert set(private) == {"user_id", "nickname"}
    data(client.patch("/api/profiles/me/visibility", headers=auth(), json={
        "show_active_goals": True, "show_goal_progress": True,
    }))
    public = data(client.get("/api/profiles/1", headers=auth(2)))
    assert "total_assets" not in public
    assert "target_amount" not in public["active_goals"][0]
    assert public["active_goals"][0]["progress_percent"] == 20
    own = data(client.get("/api/profiles/me", headers=auth()))
    assert own["total_assets"] == 1000
    assert own["active_goals"][0]["target_amount"] == 5000
    error(client.patch("/api/profiles/me/visibility", headers=auth(), json={"show_total_assets": "true"}), 400)


def test_representative_badge_must_be_owned(client, auth):
    badge = Badge.query.filter_by(code="FIRST_GOAL").one()
    error(client.patch("/api/profiles/me", headers=auth(), json={"representative_badge_id": badge.badge_id}), 422, "BADGE_NOT_OWNED")
    db.session.add(UserBadge(user_id=1, badge_id=badge.badge_id))
    db.session.commit()
    profile = data(client.patch("/api/profiles/me", headers=auth(), json={"representative_badge_id": badge.badge_id}))
    assert profile["representative_badge_id"] == badge.badge_id
    profile = data(client.patch("/api/profiles/me", headers=auth(), json={"representative_badge_id": None}))
    assert profile["representative_badge_id"] is None


def test_reactions_replace_and_remove_existing_choice(client, auth, make_post):
    post = make_post()
    endpoint = f"/api/posts/{post['post_id']}/reaction"
    for kind in ("LIKE", "LIKE", "DISLIKE"):
        data(client.put(endpoint, headers=auth(2), json={"reaction_type": kind}))
        assert PostReaction.query.count() == 1
    detail = data(client.get(f"/api/posts/{post['post_id']}", headers=auth()))
    assert detail["reactions"] == {"LIKE": 0, "DISLIKE": 1}
    for _ in range(2):
        data(client.put(endpoint, headers=auth(2), json={"reaction_type": "NONE"}))
    assert PostReaction.query.count() == 0


def test_community_edit_ownership_and_deleted_parent_visibility(client, auth, make_post):
    post = make_post()
    path = f"/api/posts/{post['post_id']}"
    error(client.patch(path, headers=auth(2), json={"title": "다른 제목"}), 404)
    comment = data(client.post(f"{path}/comments", headers=auth(2), json={"content": "도움이 됩니다."}), 201)
    error(client.patch(f"/api/comments/{comment['comment_id']}", headers=auth(), json={"content": "수정"}), 404)
    data(client.delete(path, headers=auth()))
    error(client.get(path, headers=auth()), 404)
    error(client.get(f"{path}/comments", headers=auth(2)), 404)
    error(client.post(f"{path}/comments", headers=auth(2), json={"content": "추가"}), 404)
    assert Comment.query.count() == 1


def test_reports_cannot_duplicate_and_admin_resolves_once(client, auth, make_post):
    post = make_post()
    payload = {"target_type": "POST", "target_id": post["post_id"], "reason": "게시판 확인 요청"}
    report = data(client.post("/api/reports", headers=auth(2), json=payload), 201)
    error(client.post("/api/reports", headers=auth(2), json=payload), 409)
    assert Report.query.count() == 1
    path = f"/api/admin/reports/{report['report_id']}"
    error(client.patch(path, headers=auth(), json={"status": "REJECTED", "reason": "검토 완료"}), 403)
    resolved = data(client.patch(path, headers=auth(3), json={"status": "REJECTED", "reason": "검토 완료"}))
    assert resolved["resolved_by"] == 3
    error(client.patch(path, headers=auth(3), json={"status": "RESOLVED", "reason": "재검토"}), 409, "ALREADY_RESOLVED")


def test_inquiries_and_linked_ledger_are_owner_scoped(client, auth, make_inquiry):
    account = Account.query.filter_by(user_id=1).one()
    ledger = create_ledger(account, "INITIAL_ASSET", 1000, "CREDIT", "USER", 1)
    db.session.commit()
    inquiry = make_inquiry(related_ledger_transaction_id=ledger.ledger_transaction_id)
    path = f"/api/inquiries/{inquiry['inquiry_id']}"
    error(client.get(path, headers=auth(2)), 404)
    assert data(client.get("/api/inquiries", headers=auth(2)))["total"] == 0
    error(client.post("/api/inquiries", headers=auth(2), json={
        "title": "확인", "content": "거래 확인", "related_ledger_transaction_id": ledger.ledger_transaction_id,
    }), 404)
    error(client.get(f"/api/transactions/{ledger.ledger_transaction_id}", headers=auth(2)), 404)
    own_ledger = data(client.get(f"/api/transactions/{ledger.ledger_transaction_id}", headers=auth()))
    assert own_ledger["entries"][0]["amount"] == 1000
    answer = data(client.patch(f"/api/admin/inquiries/{inquiry['inquiry_id']}/answer", headers=auth(3), json={
        "answer": "거래 내역 확인이 완료되었습니다.", "reason": "거래 원장 검토",
    }))
    assert answer["status"] == "ANSWERED"
    assert data(client.get(path, headers=auth()))["answered_by"] == 3


def test_private_image_access_and_public_post_images(client, auth, make_inquiry, make_post):
    inquiry = make_inquiry()
    uploaded = data(client.post(f"/api/inquiries/{inquiry['inquiry_id']}/images", headers=auth(), data={
        "images": (png_file(), "receipt.png", "image/png"),
    }), 201)
    path = uploaded[0]["url"]
    error(client.get(path, headers=auth(2)), 404)
    for user_id in (1, 3):
        response = client.get(path, headers=auth(user_id))
        assert response.status_code == 200
        assert response.mimetype == "image/png"
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        Image.open(BytesIO(response.data)).verify()
    post = make_post()
    public = data(client.post(f"/api/posts/{post['post_id']}/images", headers=auth(), data={
        "images": (png_file(), "plan.png", "image/png"),
    }), 201)[0]
    assert client.get(public["url"], headers=auth(2)).status_code == 200
    error(client.delete(public["url"], headers=auth(2)), 404)
    data(client.delete(f"/api/posts/{post['post_id']}", headers=auth()))
    error(client.get(public["url"], headers=auth()), 404)
    assert Attachment.query.count() == 1


def test_image_validation_batch_rollback_and_limit(client, auth, make_post):
    post = make_post()
    path = f"/api/posts/{post['post_id']}/images"
    error(client.post(path, headers=auth(2), data={"images": (png_file(), "a.png", "image/png")}), 404)
    error(client.post(path, headers=auth(), data={"images": [
        (png_file(), "valid.png", "image/png"),
        (BytesIO(b"not an image"), "invalid.png", "image/png"),
    ]}), 422, "INVALID_IMAGE")
    assert Attachment.query.count() == 0
    error(client.post(path, headers=auth(), data={"images": (png_file(), "wrong.jpg", "image/jpeg")}), 422, "INVALID_IMAGE")
    assert len(data(client.post(path, headers=auth(), data={
        "images": [(png_file(), f"{index}.png", "image/png") for index in range(5)],
    }), 201)) == 5
    error(client.post(path, headers=auth(), data={"images": (png_file(), "sixth.png", "image/png")}), 422, "IMAGE_LIMIT")
    assert Attachment.query.count() == 5


def test_admin_adjustment_records_balanced_ledger_and_audit(client, auth):
    path = "/api/admin/users/1/adjustments"
    error(client.post(path, headers=auth(), json={"amount": 100, "reason": "오류 정정"}), 403)
    adjustment = data(client.post(path, headers=auth(3), json={"amount": 200, "reason": "가상 거래 오류 정정"}), 201)
    assert adjustment["balance_after"] == 1200
    ledger = db.session.get(LedgerTransaction, adjustment["ledger_transaction_id"])
    assert ledger.transaction_type == "ADMIN_ADJUSTMENT"
    assert [(entry.entry_type, entry.amount) for entry in ledger.entries] == [("CREDIT", 200)]
    log = AuditLog.query.filter_by(action="ADMIN_ACCOUNT_ADJUSTMENT").one()
    assert log.actor_user_id == 3
    assert log.before_value == {"balance": 1000}
    assert log.after_value == {"balance": 1200, "amount": 200}
    assert log.reason == "가상 거래 오류 정정"
    data(client.post(path, headers=auth(3), json={"amount": -100, "reason": "추가 정정"}), 201)
    assert Account.query.filter_by(user_id=1).one().balance == 1100
    dashboard = data(client.get("/api/dashboard", headers=auth()))
    assert dashboard["net_funding"] == 100


def test_admin_adjustment_failure_rolls_back_financial_data(client, auth, monkeypatch):
    def unavailable_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit persistence failure")
    before_logs = AuditLog.query.count()
    monkeypatch.setattr(admin_service, "audit", unavailable_audit)
    error(client.post("/api/admin/users/1/adjustments", headers=auth(3), json={
        "amount": 200, "reason": "정정 처리", 
    }), 500, "INTERNAL_SERVER_ERROR")
    assert Account.query.filter_by(user_id=1).one().balance == 1000
    assert LedgerTransaction.query.count() == 0
    assert LedgerEntry.query.count() == 0
    assert AuditLog.query.count() == before_logs


@pytest.mark.parametrize("amount,code", [(0, "INVALID_ADJUSTMENT"), (-1001, "INSUFFICIENT_BALANCE")])
def test_invalid_adjustment_leaves_balance_unchanged(client, auth, amount, code):
    error(client.post("/api/admin/users/1/adjustments", headers=auth(3), json={"amount": amount, "reason": "정정"}), 422, code)
    assert Account.query.filter_by(user_id=1).one().balance == 1000
    assert LedgerTransaction.query.count() == 0


def test_suspension_and_reactivation_invalidate_previously_issued_tokens(client, auth):
    original = auth()
    data(client.patch("/api/admin/users/1/status", headers=auth(3), json={"status": "SUSPENDED", "reason": "문의 조사"}))
    error(client.get("/api/goals", headers=original), 401, "TOKEN_REVOKED")
    assert db.session.get(User, 1).token_version == 1
    data(client.patch("/api/admin/users/1/status", headers=auth(3), json={"status": "ACTIVE", "reason": "조사 완료"}))
    error(client.get("/api/goals", headers=original), 401, "TOKEN_REVOKED")
    assert db.session.get(User, 1).token_version == 2
    data(client.get("/api/goals", headers=auth(1, token_version=2)))
    error(client.patch("/api/admin/users/3/status", headers=auth(3), json={"status": "SUSPENDED", "reason": "변경 요청"}), 409)


def test_daily_snapshot_is_upserted_per_user_and_date(client, auth):
    assert portfolio_service.record_daily_snapshots() == {"recorded": 3, "failed": 0}
    Account.query.filter_by(user_id=1).one().balance = 1500
    db.session.commit()
    assert portfolio_service.record_daily_snapshots() == {"recorded": 3, "failed": 0}
    assert AssetSnapshot.query.count() == 3
    own = data(client.get("/api/dashboard/history", headers=auth()))
    assert own["total"] == 1
    assert own["items"][0]["total_assets"] == 1500
    assert own["items"][0]["snapshot_date"] == date(2026, 1, 1).isoformat()


def test_feature_rate_limit_has_a_bounded_window(client, auth, app, monkeypatch):
    from app.services import feature_common
    app.config.update(FEATURE_RATE_LIMIT_ENABLED=True, FEATURE_WRITE_REQUESTS_PER_MINUTE=1)
    monkeypatch.setattr(feature_common.time, "time", lambda: 6000)
    payload = {"board_type": "FREE", "title": "계획", "content": "내용"}
    data(client.post("/api/posts", headers=auth(), json=payload), 201)
    error(client.post("/api/posts", headers=auth(), json=payload), 429, "RATE_LIMITED")
    monkeypatch.setattr(feature_common.time, "time", lambda: 6060)
    data(client.post("/api/posts", headers=auth(), json=payload), 201)
