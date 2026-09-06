from app.extensions import db
from app.models.user import User
from app.models.features import ProfileVisibility, SavingGoal, UserBadge
from app.schemas.features import VisibilitySchema
from app.services.feature_common import fail, get_row, serialize
from app.services.portfolio_service import valuation, badge_data, goal_data
from app.services.audit_service import audit
from app.services.account_service import get_account_by_user_id


def visibility(user_id):
    row = db.session.get(ProfileVisibility, user_id)
    return {key: bool(getattr(row, key, False)) for key in VisibilitySchema().fields}


def update_visibility(user_id, payload):
    get_account_by_user_id(user_id)
    get_row(User, user_id, lock=True)
    row = db.session.get(ProfileVisibility, user_id)
    if row is None:
        row = ProfileVisibility(user_id=user_id)
        db.session.add(row)
    before = visibility(user_id)
    for key, value in payload.items():
        setattr(row, key, value)
    audit("PROFILE_VISIBILITY_UPDATE", "users", user_id, before=before, after=payload)
    db.session.commit()
    return visibility(user_id)


def update_profile(user_id, payload):
    get_account_by_user_id(user_id)
    user = get_row(User, user_id, lock=True)
    badge_id = payload.get("representative_badge_id")
    if badge_id is not None and not UserBadge.query.filter_by(user_id=user_id, badge_id=badge_id).first():
        fail("BADGE_NOT_OWNED", "획득한 뱃지만 대표 뱃지로 선택할 수 있습니다.", 422)
    for key, value in payload.items():
        setattr(user, key, value)
    db.session.commit()
    return {"user_id": user.user_id, "nickname": user.nickname,
            "representative_badge_id": user.representative_badge_id}


def profile(target_id, viewer_id):
    user = get_row(User, target_id)
    if user.status != "ACTIVE":
        fail("NOT_FOUND", "프로필을 찾을 수 없습니다.", 404)
    own = target_id == viewer_id
    flags = visibility(target_id)
    result = {"user_id": user.user_id, "nickname": user.nickname}
    if own:
        result["visibility"] = flags
    if own or flags["show_joined_at"]:
        result["created_at"] = user.created_at.isoformat() + "Z"
    if own or flags["show_badges"]:
        result["badges"] = badge_data(target_id)
        result["representative_badge_id"] = user.representative_badge_id
    needs_value = own or any(flags[k] for k in ("show_total_assets", "show_asset_allocation", "show_investment_return", "show_goal_progress"))
    portfolio = valuation(target_id) if needs_value else None
    if own or flags["show_total_assets"]:
        result["total_assets"] = portfolio["total_assets"]
    if own or flags["show_asset_allocation"]:
        result["allocation_percent"] = portfolio["allocation_percent"]
    if own or flags["show_investment_return"]:
        result["investment_return_percent"] = portfolio["investment_return_percent"]
    for state, key in (("ACTIVE", "active_goals"), ("COMPLETED", "completed_goals")):
        if own or flags[f"show_{key}"]:
            goals = []
            for goal in SavingGoal.query.filter_by(user_id=target_id, status=state):
                item = {"goal_id": goal.goal_id, "goal_name": goal.goal_name, "status": goal.status,
                        "target_date": goal.target_date.isoformat()}
                # Target amounts plus a progress ratio reveal total assets. For
                # other viewers expose the ratio only, never the underlying amount.
                if own:
                    item["target_amount"] = goal.target_amount
                if own or flags["show_goal_progress"]:
                    item["progress_percent"] = round(portfolio["total_assets"] / goal.target_amount * 100, 4)
                goals.append(item)
            result[key] = goals
    return result
