"""Final goal/badge policy boundaries, using only isolated test data."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.extensions import db
from app.models.account import Account
from app.models.features import AuditLog, Badge, SavingGoal, UserBadge
from app.models.market import MarketAsset, MarketHolding
from app.models.user import User
from app.services import portfolio_service
from app.services.goal_badge_policy import completed_after_wait, creation_record


@pytest.fixture(autouse=True)
def deterministic_goal_clock(goal_clock):
    return goal_clock


def data(response, status=200):
    assert response.status_code == status, response.get_json()
    return response.get_json()["data"]


def balance(amount, user_id=1):
    Account.query.filter_by(user_id=user_id).one().balance = amount
    db.session.commit()


@pytest.mark.parametrize("assets,target,target_date,minimum,eligible", [
    (10000, 10001, "2026-01-08", 10500, False),
    (10000, 10499, "2026-01-08", 10500, False),
    (10000, 10500, "2026-01-07", 10500, False),
    (10000, 10001, "2026-01-02", 10500, False),
    (10000, 10500, "2026-01-08", 10500, True),
    (10000, 10501, "2026-01-09", 10500, True),
    (14000000, 14000001, "2026-01-08", 14700000, False),
    (14000000, 14699999, "2026-01-08", 14700000, False),
    (14000000, 14700000, "2026-01-08", 14700000, True),
    (10001, 10501, "2026-01-08", 10502, False),
    (10001, 10502, "2026-01-08", 10502, True),
    (0, 1, "2026-01-08", 0, False),
])
def test_creation_and_badge_boundaries(client, auth, make_goal, goal_clock, assets, target, target_date, minimum, eligible):
    balance(assets)
    goal = make_goal(target_amount=target, target_date=target_date)
    assert goal["status"] == "ACTIVE"
    assert goal["badge_criteria"] == {
        "baseline_known": True, "assets_at_creation": assets, "created_on": "2026-01-01",
        "minimum_target_amount": minimum, "minimum_period_days": 7, "eligible": eligible,
    }
    assert UserBadge.query.filter_by(user_id=1).count() == 0
    goal_clock.advance(days=7)
    balance(target)
    result = data(client.get("/api/dashboard", headers=auth()))
    assert result["goals"][0]["status"] == "COMPLETED"
    assert result["goals"][0]["progress_percent"] == 100
    assert [b["code"] for b in result["badges"]] == (["FIRST_GOAL"] if eligible else [])


@pytest.mark.parametrize("target", [9999, 10000])
def test_create_and_edit_require_strictly_more_than_current_assets(client, auth, make_goal, target):
    balance(10000)
    goal = make_goal(target_amount=11000)
    for method, url, payload in [
        (client.post, "/api/goals", {"goal_name": "경계", "target_amount": target, "target_date": "2026-01-08"}),
        (client.patch, f"/api/goals/{goal['goal_id']}", {"target_amount": target}),
    ]:
        response = method(url, headers=auth(), json=payload)
        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "INVALID_TARGET_AMOUNT"
    assert SavingGoal.query.count() == 1
    assert db.session.get(SavingGoal, goal["goal_id"]).target_amount == 11000


def test_rounding_to_100_never_completes_or_awards(client, auth, make_goal, goal_clock):
    goal = make_goal(target_amount=14700000, target_date="2026-01-08")
    goal_clock.advance(days=7)
    balance(14699999)
    for _ in range(2):
        result = data(client.get("/api/dashboard", headers=auth()))
        assert result["goals"][0]["progress_percent"] == 100
        assert result["goals"][0]["status"] == "ACTIVE"
        assert result["goals"][0]["completed_at"] is None
        assert result["badges"] == []
    assert portfolio_service.record_daily_snapshots()["failed"] == 0
    assert db.session.get(SavingGoal, goal["goal_id"]).status == "ACTIVE"
    balance(14700000)
    for _ in range(2):
        result = data(client.get("/api/dashboard", headers=auth()))
        assert result["goals"][0]["status"] == "COMPLETED"
        assert [b["code"] for b in result["badges"]] == ["FIRST_GOAL"]
    assert UserBadge.query.filter_by(user_id=1).count() == 1


def test_edits_recheck_terms_using_immutable_creation_assets_and_date(client, auth, make_goal, goal_clock):
    goal = make_goal(target_amount=1001, target_date="2026-01-02")
    assert goal["badge_criteria"]["eligible"] is False
    baseline = dict(creation_record(db.session.get(SavingGoal, goal["goal_id"])).after_value)
    goal_clock.advance(days=2)
    balance(500)
    url = f"/api/goals/{goal['goal_id']}"
    for amount, deadline, eligible in [
        (1050, "2026-01-08", True),  # Seven days from creation, five from this edit.
        (1049, "2026-01-08", False),
        (1050, "2026-01-07", False),
        (1050, "2026-01-08", True),
    ]:
        revised = data(client.patch(url, headers=auth(), json={"target_amount": amount, "target_date": deadline}))
        criteria = revised["badge_criteria"]
        assert criteria["eligible"] is eligible
        assert criteria["assets_at_creation"] == 1000
        assert criteria["minimum_target_amount"] == 1050
        assert criteria["created_on"] == "2026-01-01"
    revised = data(client.patch(url, headers=auth(), json={"goal_name": "이름만 수정"}))
    assert revised["badge_criteria"]["eligible"] is True
    assert creation_record(db.session.get(SavingGoal, goal["goal_id"])).after_value == baseline
    db.session.remove()
    assert data(client.get(url, headers=auth()))["badge_criteria"] == revised["badge_criteria"]
    assert db.session.get(SavingGoal, goal["goal_id"]).created_at == datetime(2026, 1, 1, 3)
    goal_clock.advance(days=5)  # Seven from creation, not seven from the edit.
    balance(1050)
    assert [b["code"] for b in data(client.get("/api/badges/me", headers=auth()))] == ["FIRST_GOAL"]


def test_growing_assets_do_not_raise_existing_badge_threshold(client, auth, make_goal):
    goal = make_goal(target_amount=1050, target_date="2026-01-08")
    balance(1040)
    revised = data(client.patch(f"/api/goals/{goal['goal_id']}", headers=auth(), json={"goal_name": "변경"}))
    assert revised["badge_criteria"]["minimum_target_amount"] == 1050
    assert revised["badge_criteria"]["eligible"] is True


@pytest.mark.parametrize("started,deadline,eligible", [
    (date(2026, 1, 28), "2026-02-04", True),
    (date(2026, 12, 28), "2027-01-04", True),
    (date(2028, 2, 25), "2028-03-03", True),
    (date(2028, 2, 25), "2028-03-02", False),
])
def test_period_uses_korean_calendar_days(make_goal, monkeypatch, started, deadline, eligible):
    monkeypatch.setattr(portfolio_service, "today", lambda: started)
    goal = make_goal(target_date=deadline)
    assert goal["badge_criteria"]["created_on"] == started.isoformat()
    assert goal["badge_criteria"]["eligible"] is eligible


def test_three_goals_counts_only_eligible_completions(client, auth, make_goal, goal_clock):
    make_goal(target_amount=1001, target_date="2026-01-08")
    make_goal(target_amount=1050, target_date="2026-01-07")
    first = make_goal(target_amount=1050, target_date="2026-01-08")
    make_goal(target_amount=1060, target_date="2026-01-08")
    make_goal(target_amount=1070, target_date="2026-01-08")
    goal_clock.advance(days=7)
    balance(1060)
    result = data(client.get("/api/dashboard", headers=auth()))
    assert sum(g["status"] == "COMPLETED" for g in result["goals"]) == 4
    assert [b["code"] for b in result["badges"]] == ["FIRST_GOAL"]
    balance(1070)
    assert portfolio_service.record_daily_snapshots()["failed"] == 0
    assert {b["code"] for b in data(client.get("/api/badges/me", headers=auth()))} == {"FIRST_GOAL", "THREE_GOALS"}
    data(client.delete(f"/api/goals/{first['goal_id']}", headers=auth()))
    balance(1)
    assert len(data(client.get("/api/badges/me", headers=auth()))) == 2


def test_legacy_goal_has_no_invented_baseline_and_existing_badges_remain(client, auth):
    legacy = SavingGoal(user_id=1, goal_name="기존 목표", target_amount=1500, target_date=date(2027, 1, 1))
    db.session.add(legacy)
    badge = Badge.query.filter_by(code="FIRST_GOAL").one()
    db.session.add(UserBadge(user_id=1, badge_id=badge.badge_id))
    db.session.get(User, 1).representative_badge_id = badge.badge_id
    db.session.commit()
    url = f"/api/goals/{legacy.goal_id}"
    revised = data(client.patch(url, headers=auth(), json={"target_amount": 1600}))
    assert revised["badge_criteria"]["baseline_known"] is False
    assert revised["badge_criteria"]["eligible"] is False
    balance(1600)
    result = data(client.get("/api/dashboard", headers=auth()))
    assert result["goals"][0]["status"] == "COMPLETED"
    assert [b["code"] for b in result["badges"]] == ["FIRST_GOAL"]
    assert db.session.get(User, 1).representative_badge_id == badge.badge_id


@pytest.mark.parametrize("legacy_replacement", [False, True])
def test_reused_goal_id_never_inherits_deleted_baseline(client, auth, make_goal, goal_clock, legacy_replacement):
    old = make_goal(target_amount=1050)
    data(client.delete(f"/api/goals/{old['goal_id']}", headers=auth()))
    balance(2000)
    if legacy_replacement:
        db.session.add(SavingGoal(user_id=1, goal_name="기록 없는 목표", target_amount=2001, target_date=date(2027, 1, 1)))
        db.session.commit()
        goal = data(client.get(f"/api/goals/{old['goal_id']}", headers=auth()))
        assert goal["badge_criteria"]["baseline_known"] is False
    else:
        goal = make_goal(target_amount=2001)
        assert goal["badge_criteria"]["assets_at_creation"] == 2000
        assert goal["badge_criteria"]["minimum_target_amount"] == 2100
    assert goal["goal_id"] == old["goal_id"]  # SQLite reuses the deleted maximum ID.
    goal_clock.advance(days=7)
    balance(2001)
    assert data(client.get("/api/badges/me", headers=auth())) == []


def test_failed_goal_transaction_rolls_back_baseline(client, auth, monkeypatch):
    def fail_refresh(*args):
        raise RuntimeError("simulated failure after baseline was saved")
    monkeypatch.setattr(portfolio_service, "refresh_achievements", fail_refresh)
    response = client.post("/api/goals", headers=auth(), json={
        "goal_name": "원자성", "target_amount": 1050, "target_date": "2026-01-08",
    })
    assert response.status_code == 500
    assert SavingGoal.query.count() == 0
    assert AuditLog.query.filter_by(target_type="saving_goals").count() == 0


def test_baseline_is_server_owned_and_never_exposed_on_public_profile(client, auth, make_goal):
    response = client.post("/api/goals", headers=auth(), json={
        "goal_name": "조작 시도", "target_amount": 1001, "target_date": "2026-01-08",
        "badge_criteria": {"assets_at_creation": 0, "eligible": True},
    })
    assert response.status_code == 400
    make_goal()
    data(client.patch("/api/profiles/me/visibility", headers=auth(), json={
        "show_active_goals": True, "show_goal_progress": True,
    }))
    public = data(client.get("/api/profiles/1", headers=auth(2)))
    assert "total_assets" not in public
    assert "badge_criteria" not in public["active_goals"][0]
    assert "target_amount" not in public["active_goals"][0]


def test_creation_baseline_uses_valued_total_assets_not_cash(make_goal):
    asset = MarketAsset(symbol="TEST", name="테스트 종목", market="KR", asset_type="STOCK")
    db.session.add(asset)
    db.session.flush()
    # Fixture quote is KRW 100: cash 1,000 + stock 9,000 = total 10,000.
    db.session.add(MarketHolding(user_id=1, asset_id=asset.asset_id, quantity=90,
                                 total_acquisition_cost=9000, total_acquisition_cost_krw=9000))
    db.session.commit()
    goal = make_goal(target_amount=10500)
    assert goal["badge_criteria"]["assets_at_creation"] == 10000
    assert goal["badge_criteria"]["minimum_target_amount"] == 10500


@pytest.mark.parametrize("elapsed,credited", [
    (timedelta(), False),
    (timedelta(days=6), False),
    (timedelta(days=7, seconds=-1), False),
    (timedelta(days=7), True),
    (timedelta(days=8), True),
])
@pytest.mark.parametrize("via_snapshot", [False, True])
def test_completion_and_badge_credit_are_separate_and_never_retimed(
    client, auth, make_goal, goal_clock, elapsed, credited, via_snapshot,
):
    balance(10000)
    goal = make_goal(target_amount=10500, target_date="2026-01-30")
    goal_clock.current += elapsed
    balance(10500)
    if via_snapshot:
        assert portfolio_service.record_daily_snapshots()["failed"] == 0
    result = data(client.get("/api/dashboard", headers=auth()))
    completed = result["goals"][0]
    assert completed["status"] == "COMPLETED"
    assert completed["progress_percent"] == 100
    assert completed["completed_at"] == goal_clock.current.isoformat() + "Z"
    assert completed["badge_criteria"]["eligible"] is credited
    assert [b["code"] for b in result["badges"]] == (["FIRST_GOAL"] if credited else [])

    # Waiting after early completion must not turn that same goal into credit.
    # A later asset drop also must not reverse a valid historical completion.
    goal_clock.advance(days=30)
    balance(0)
    assert portfolio_service.record_daily_snapshots()["failed"] == 0
    for _ in range(2):
        saved = data(client.get("/api/goals", headers=auth()))[0]
        assert saved["status"] == "COMPLETED"
        assert saved["completed_at"] == completed["completed_at"]
        assert saved["badge_criteria"]["eligible"] is credited
        assert saved["progress_percent"] == 100
        assert len(data(client.get("/api/badges/me", headers=auth()))) == int(credited)
    assert db.session.get(SavingGoal, goal["goal_id"]).created_at == datetime(2026, 1, 1, 3)


@pytest.mark.parametrize("target", [1, 1000000])
def test_zero_asset_goal_completes_but_never_counts_even_after_wait(client, auth, make_goal, goal_clock, target):
    balance(0)
    goal = make_goal(target_amount=target, target_date="2026-01-30")
    assert goal["badge_criteria"]["baseline_known"] is True
    assert goal["badge_criteria"]["assets_at_creation"] == 0
    assert goal["badge_criteria"]["eligible"] is False
    goal_clock.advance(days=8)
    balance(target)
    completed = data(client.get("/api/dashboard", headers=auth()))
    assert completed["goals"][0]["status"] == "COMPLETED"
    assert completed["goals"][0]["badge_criteria"]["eligible"] is False
    assert completed["badges"] == []


def test_editing_after_funding_does_not_remove_zero_creation_asset_exclusion(client, auth, make_goal, goal_clock):
    balance(0)
    goal = make_goal(target_amount=1000, target_date="2026-01-30")
    balance(100)
    goal_clock.advance(days=3)
    revised = data(client.patch(f"/api/goals/{goal['goal_id']}", headers=auth(), json={
        "target_amount": 2000, "target_date": "2026-02-01",
    }))
    assert revised["badge_criteria"]["assets_at_creation"] == 0
    assert revised["badge_criteria"]["created_on"] == "2026-01-01"
    assert revised["badge_criteria"]["eligible"] is False
    goal_clock.advance(days=7)
    balance(2000)
    assert data(client.get("/api/dashboard", headers=auth()))["goals"][0]["status"] == "COMPLETED"
    assert data(client.get("/api/badges/me", headers=auth())) == []


def test_later_zero_balance_does_not_replace_positive_creation_assets(client, auth, make_goal, goal_clock):
    goal = make_goal(target_amount=1050, target_date="2026-01-30")
    balance(0)
    revised = data(client.patch(f"/api/goals/{goal['goal_id']}", headers=auth(), json={"goal_name": "기준 유지"}))
    assert revised["badge_criteria"]["eligible"] is True
    assert revised["badge_criteria"]["assets_at_creation"] == 1000
    goal_clock.advance(days=7)
    balance(1050)
    assert [b["code"] for b in data(client.get("/api/badges/me", headers=auth()))] == ["FIRST_GOAL"]


def test_previously_awarded_badge_is_retained_for_an_early_completed_goal(client, auth, make_goal, goal_clock):
    goal = make_goal(target_amount=1050, target_date="2026-01-30")
    # Represents data saved by the previous policy; do not rewrite its status/time.
    row = db.session.get(SavingGoal, goal["goal_id"])
    row.status, row.completed_at = "COMPLETED", goal_clock.current
    badge = Badge.query.filter_by(code="FIRST_GOAL").one()
    db.session.add(UserBadge(user_id=1, badge_id=badge.badge_id))
    db.session.get(User, 1).representative_badge_id = badge.badge_id
    db.session.commit()
    goal_clock.advance(days=30)
    result = data(client.get("/api/dashboard", headers=auth()))
    assert result["goals"][0]["status"] == "COMPLETED"
    assert result["goals"][0]["completed_at"] == "2026-01-01T03:00:00Z"
    assert result["goals"][0]["badge_criteria"]["eligible"] is False
    assert [b["code"] for b in result["badges"]] == ["FIRST_GOAL"]
    assert db.session.get(User, 1).representative_badge_id == badge.badge_id


def test_completed_goal_without_completion_time_is_not_inferred_or_reopened(client, auth, make_goal, goal_clock):
    goal = make_goal(target_amount=1050)
    row = db.session.get(SavingGoal, goal["goal_id"])
    row.status = "COMPLETED"
    row.completed_at = None
    db.session.commit()
    goal_clock.advance(days=30)
    balance(1050)
    result = data(client.get("/api/dashboard", headers=auth()))
    assert result["goals"][0]["status"] == "COMPLETED"
    assert result["goals"][0]["completed_at"] is None
    assert result["goals"][0]["badge_criteria"]["eligible"] is False
    assert result["badges"] == []


@pytest.mark.parametrize("completed,credited", [
    (datetime(2026, 9, 17, 15, tzinfo=timezone.utc), False),  # Sep 18 KST, but only six days elapsed.
    (datetime(2026, 9, 18, 14, 58, 59, tzinfo=timezone.utc), False),
    (datetime(2026, 9, 18, 14, 59, tzinfo=timezone.utc), True),
    (datetime(2026, 9, 18, 14, 59), True),  # Database stores naive UTC.
])
def test_elapsed_wait_normalizes_timezones_without_using_calendar_midnight(completed, credited):
    goal = SimpleNamespace(
        created_at=datetime(2026, 9, 11, 23, 59, tzinfo=timezone(timedelta(hours=9))),
        completed_at=completed,
    )
    assert completed_after_wait(goal) is credited


def test_three_goal_badge_excludes_early_completions(client, auth, make_goal, goal_clock):
    for target in (1050, 1060, 1070):
        make_goal(target_amount=target, target_date="2026-01-30")
    make_goal(target_amount=2000, target_date="2026-01-30")
    balance(1070)
    goal_clock.advance(days=6)
    early = data(client.get("/api/dashboard", headers=auth()))
    assert sum(g["status"] == "COMPLETED" for g in early["goals"]) == 3
    assert early["badges"] == []
    goal_clock.advance(days=1)
    balance(2000)
    result = data(client.get("/api/dashboard", headers=auth()))
    assert sum(g["status"] == "COMPLETED" for g in result["goals"]) == 4
    assert [b["code"] for b in result["badges"]] == ["FIRST_GOAL"]
