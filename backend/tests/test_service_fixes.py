"""Regression tests for the September service feedback; isolated SQLite only."""
from datetime import date, datetime

import pytest

from app.extensions import db
from app.models.account import Account
from app.models.deposits_savings import LedgerTransaction
from app.models.features import AuditLog, Inquiry, SavingGoal, UserBadge
from app.models.simulation_setting import SimulationSetting
from app.models.user import User
from app.services.ledger_service import create_ledger
from app.services import portfolio_service


def data(response, status=200):
    assert response.status_code == status, response.get_json()
    return response.get_json()["data"]


def test_goal_progress_is_capped_everywhere_and_completed_stays_100(client, auth, make_goal):
    goal = make_goal(target_amount=1500)
    Account.query.filter_by(user_id=1).one().balance = 100000000
    db.session.commit()
    data(client.patch("/api/profiles/me/visibility", headers=auth(), json={
        "show_completed_goals": True, "show_goal_progress": True,
    }))
    dashboard = data(client.get("/api/dashboard", headers=auth()))
    assert dashboard["goals"][0]["progress_percent"] == 100
    assert dashboard["goals"][0]["status"] == "COMPLETED"
    # Completion is retained even when the portfolio subsequently falls.
    Account.query.filter_by(user_id=1).one().balance = 10
    db.session.commit()
    assert data(client.get(f"/api/goals/{goal['goal_id']}", headers=auth()))["progress_percent"] == 100
    assert data(client.get("/api/goals", headers=auth()))[0]["progress_percent"] == 100
    for path, viewer in (("/api/profiles/me", 1), ("/api/profiles/1", 2)):
        result = data(client.get(path, headers=auth(viewer)))["completed_goals"][0]
        assert result["progress_percent"] == 100
        if viewer == 2:
            assert "target_amount" not in result


@pytest.mark.parametrize("target", [999, 1000])
def test_goal_must_exceed_current_assets(client, auth, target):
    response = client.post("/api/goals", headers=auth(), json={
        "goal_name": "새 목표", "target_amount": target, "target_date": "2027-01-01",
    })
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "INVALID_TARGET_AMOUNT"


def test_initial_setup_is_required_before_goal_creation(client, auth):
    setting = SimulationSetting.query.filter_by(user_id=1).one()
    setting.is_initial_asset_set = False
    Account.query.filter_by(user_id=1).one().balance = 0
    db.session.commit()
    payload = {"goal_name": "첫 목표", "target_amount": 10000, "target_date": "2027-01-01"}
    response = client.post("/api/goals", headers=auth(), json=payload)
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "INITIAL_ASSET_REQUIRED"
    data(client.post("/api/simulation/initial-asset", headers=auth(), json={"initial_asset": 0}))
    data(client.post("/api/goals", headers=auth(), json=payload), 201)
    assert UserBadge.query.filter_by(user_id=1).count() == 0


def test_legacy_goal_cannot_complete_from_initial_funding_but_can_be_revised(client, auth):
    account = Account.query.filter_by(user_id=1).one()
    account.balance = 0
    setting = SimulationSetting.query.filter_by(user_id=1).one()
    setting.is_initial_asset_set = False
    legacy = SavingGoal(user_id=1, goal_name="설정 전 목표", target_amount=10000,
                        target_date=date(2027, 1, 1), created_at=datetime(2020, 1, 1),
                        updated_at=datetime(2020, 1, 1))
    db.session.add(legacy)
    db.session.commit()
    legacy_id = legacy.goal_id
    data(client.post("/api/simulation/initial-asset", headers=auth(), json={"initial_asset": 100000000}))
    for _ in range(2):
        result = data(client.get("/api/dashboard", headers=auth()))
        assert result["goals"][0]["status"] == "ACTIVE"
        assert result["goals"][0]["requires_target_update"] is True
        assert result["goals"][0]["progress_percent"] == 100
        assert result["badges"] == []
    assert portfolio_service.record_daily_snapshots()["failed"] == 0
    assert UserBadge.query.filter_by(user_id=1).count() == 0
    revised = data(client.patch(f"/api/goals/{legacy_id}", headers=auth(), json={"target_amount": 100001000}))
    assert revised["requires_target_update"] is False
    Account.query.filter_by(user_id=1).one().balance = 100001000
    db.session.commit()
    result = data(client.get("/api/dashboard", headers=auth()))
    assert result["goals"][0]["status"] == "COMPLETED"
    # No creation-time asset snapshot exists for this legacy goal. Completion
    # remains available, but it cannot prove the new badge criteria.
    assert result["goals"][0]["badge_criteria"]["baseline_known"] is False
    assert result["badges"] == []


def test_recovery_goal_below_original_funding_is_still_eligible(client, auth, make_goal):
    account = Account.query.filter_by(user_id=1).one()
    funding = create_ledger(account, "INITIAL_ASSET", 1000, "CREDIT", "USER", 1)
    funding.created_at = datetime(2020, 1, 1)
    account.balance = 500
    db.session.commit()
    make_goal(target_amount=800)
    account.balance = 800
    db.session.commit()
    assert data(client.get("/api/dashboard", headers=auth()))["goals"][0]["status"] == "COMPLETED"


def test_selected_ledger_links_inquiry_and_admin_can_identify_it(client, auth):
    account = Account.query.filter_by(user_id=1).one()
    ledger = create_ledger(account, "SAVING_PAYMENT", 100, "DEBIT", "SAVING", 25)
    db.session.commit()
    ledger_id = ledger.ledger_transaction_id
    own = data(client.get("/api/transactions", headers=auth()))["items"][0]
    assert own["ledger_transaction_id"] == ledger_id
    inquiry = data(client.post("/api/inquiries", headers=auth(), json={
        "title": "납입 확인", "content": "선택한 거래를 확인해 주세요.",
        "related_ledger_transaction_id": own["ledger_transaction_id"],
    }), 201)
    detail = data(client.get(f"/api/admin/inquiries/{inquiry['inquiry_id']}", headers=auth(3)))
    assert detail["related_transaction"]["ledger_transaction_id"] == ledger_id
    assert detail["related_transaction"]["entries"][0]["entry_type"] == "DEBIT"
    assert detail["member"] == {"user_id": 1, "username": "testuser1", "nickname": "사용자1"}
    assert client.post("/api/inquiries", headers=auth(2), json={
        "title": "확인", "content": "다른 사람 거래", "related_ledger_transaction_id": ledger_id,
    }).status_code == 404
    assert data(client.get("/api/transactions", headers=auth(2)))["total"] == 0


def test_inquiry_read_does_not_expose_reused_or_missing_ledger(client, auth, make_inquiry):
    inquiry = make_inquiry()
    other = create_ledger(Account.query.filter_by(user_id=2).one(), "INITIAL_ASSET", 1000, "CREDIT", "USER", 2)
    db.session.flush()
    row = db.session.get(Inquiry, inquiry["inquiry_id"])
    row.related_ledger_transaction_id = other.ledger_transaction_id
    db.session.commit()
    path = f"/api/inquiries/{row.inquiry_id}"
    assert data(client.get(path, headers=auth()))["related_transaction"] is None
    row.related_ledger_transaction_id = 999999
    db.session.commit()
    assert data(client.get(path, headers=auth()))["related_transaction"] is None


@pytest.mark.parametrize("kind", ["POST", "COMMENT"])
def test_admin_report_details_preserve_full_reason_and_deleted_state(client, auth, make_post, kind):
    post = make_post(content="확인할 원문 " * 200)
    target_id = post["post_id"]
    if kind == "COMMENT":
        target_id = data(client.post(f"/api/posts/{post['post_id']}/comments", headers=auth(),
                                    json={"content": "확인할 댓글"}), 201)["comment_id"]
    reason = "긴 신고 사유 " * 90
    report = data(client.post("/api/reports", headers=auth(2), json={
        "target_type": kind, "target_id": target_id, "reason": reason,
    }), 201)
    path = f"/api/admin/reports/{report['report_id']}"
    assert client.get(path, headers=auth()).status_code == 403
    detail = data(client.get(path, headers=auth(3)))
    assert detail["reason"] == reason
    assert detail["target"]["content"]
    assert detail["member"]["username"] == "testuser2"
    data(client.delete(f"/api/posts/{post['post_id']}", headers=auth()))
    detail = data(client.get(path, headers=auth(3)))
    assert detail["target"]["deleted"] is True
    assert detail["target"]["content"] is None
    assert detail["reason"] == reason
    data(client.patch(path, headers=auth(3), json={"status": "RESOLVED", "reason": "검토 완료"}))
    assert data(client.get(path, headers=auth(3)))["status"] == "RESOLVED"


def test_admin_member_enrichment_stays_private(client, auth, make_post, make_inquiry):
    post = make_post()
    make_inquiry()
    data(client.post(f"/api/posts/{post['post_id']}/comments", headers=auth(), json={"content": "댓글"}), 201)
    for endpoint in ("posts", "comments", "inquiries"):
        result = data(client.get(f"/api/admin/{endpoint}", headers=auth(3)))["items"][0]
        assert set(result["member"]) == {"user_id", "username", "nickname"}
        assert client.get(f"/api/admin/{endpoint}", headers=auth()).status_code == 403
    public_post = data(client.get(f"/api/posts/{post['post_id']}", headers=auth(2)))
    assert "member" not in public_post


def test_revoked_sessions_use_plain_language_without_changing_validation(client, auth):
    original = auth()
    data(client.patch("/api/admin/users/1/status", headers=auth(3), json={"status": "SUSPENDED", "reason": "검토"}))
    response = client.get("/api/goals", headers=original)
    assert response.status_code == 401
    assert response.get_json()["error"] == {"code": "TOKEN_REVOKED", "message": "정지된 계정입니다."}
    data(client.patch("/api/admin/users/1/status", headers=auth(3), json={"status": "ACTIVE", "reason": "완료"}))
    response = client.get("/api/goals", headers=original)
    assert response.status_code == 401
    assert response.get_json()["error"]["message"] == "계정 상태가 변경되어 다시 로그인해야 합니다."
    data(client.get("/api/goals", headers=auth(1, token_version=2)))


def test_unloaded_audit_field_records_persisted_previous_value(app):
    user = db.session.get(User, 1)
    db.session.expire(user, ["status"])
    user.status = "SUSPENDED"
    db.session.commit()
    log = AuditLog.query.filter_by(action="UPDATE", target_type="users", target_id=1).one()
    assert log.before_value == {"status": "ACTIVE"}
    assert log.after_value == {"status": "SUSPENDED"}
    before_count = AuditLog.query.count()
    user.status = "ACTIVE"
    db.session.flush()
    db.session.rollback()
    assert AuditLog.query.count() == before_count
    assert db.session.get(User, 1).status == "SUSPENDED"


def test_admin_action_and_automatic_audit_are_retained_and_distinguished(client, auth):
    data(client.patch("/api/admin/users/1/status", headers=auth(3), json={"status": "SUSPENDED", "reason": "검토 필요"}))
    logs = data(client.get("/api/admin/audit-logs?target_type=users", headers=auth(3)))["items"]
    changes = {row["action"]: row for row in logs if row["target_id"] == 1 and row["action"] in {"UPDATE", "ADMIN_USER_STATUS"}}
    assert set(changes) == {"UPDATE", "ADMIN_USER_STATUS"}
    assert changes["UPDATE"]["record_kind"] == "AUTOMATIC"
    assert changes["ADMIN_USER_STATUS"]["record_kind"] == "OPERATION"
    for row in changes.values():
        assert row["before_value"] == {"status": "ACTIVE"}
        assert row["after_value"] == {"status": "SUSPENDED"}
        assert row["member"]["username"] == "testuser3"
