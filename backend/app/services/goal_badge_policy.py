"""Goal badge baselines live in the existing, transactional CREATE audit snapshot.

Use the latest CREATE event, never the latest UPDATE: edits keep the original
baseline and a deleted/reset goal's reused ID cannot inherit an older baseline.
Legacy goals without this snapshot still work, but cannot prove badge eligibility.
"""
from datetime import date, timedelta, timezone

from app.models.features import AuditLog


MINIMUM_PERIOD_DAYS = 7


def completed_after_wait(goal):
    """Use the recorded completion, never today's date, to prevent later credit.

    Existing model timestamps are naive UTC. Normalize aware values too, so a
    change of timezone representation cannot shorten the seven-day wait.
    """
    if goal.created_at is None or goal.completed_at is None:
        return False
    created = goal.created_at.replace(tzinfo=timezone.utc) if goal.created_at.tzinfo is None else goal.created_at.astimezone(timezone.utc)
    completed = goal.completed_at.replace(tzinfo=timezone.utc) if goal.completed_at.tzinfo is None else goal.completed_at.astimezone(timezone.utc)
    return completed - created >= timedelta(days=MINIMUM_PERIOD_DAYS)


def creation_record(goal):
    return AuditLog.query.filter_by(
        target_type="saving_goals", target_id=goal.goal_id, action="CREATE",
    ).order_by(AuditLog.audit_log_id.desc()).first()


def record_creation_baseline(goal, total_assets, created_on):
    # Called only for a newly flushed goal, before its transaction is committed.
    # The query also flushes the CREATE audit event queued by the audit hook.
    record = creation_record(goal)
    if record is None or "badge_policy_version" in (record.after_value or {}):
        raise RuntimeError("A fresh goal CREATE audit snapshot is required")
    record.after_value = {
        **(record.after_value or {}),
        "badge_policy_version": 1,
        "badge_initial_assets": total_assets,
        "badge_started_on": created_on.isoformat(),
    }


def badge_criteria(goal):
    result = {
        "baseline_known": False,
        "assets_at_creation": None,
        "created_on": None,
        "minimum_target_amount": None,
        "minimum_period_days": MINIMUM_PERIOD_DAYS,
        "eligible": False,
    }
    record = creation_record(goal)
    snapshot = record.after_value if record and isinstance(record.after_value, dict) else {}
    if snapshot.get("badge_policy_version") != 1:
        return result
    assets = snapshot.get("badge_initial_assets")
    if type(assets) is not int or assets < 0:
        return result
    try:
        created_on = date.fromisoformat(snapshot["badge_started_on"])
    except (KeyError, TypeError, ValueError):
        return result
    # Integer KRW: ceil(assets * 1.05), without float or percentage rounding.
    minimum = (assets * 105 + 99) // 100
    result.update(
        baseline_known=True, assets_at_creation=assets,
        created_on=created_on.isoformat(), minimum_target_amount=minimum,
        # For active goals this reports the configured conditions. Completed
        # goals must also have reached the target after the full elapsed wait.
        eligible=(assets > 0 and goal.target_amount >= minimum
                  and (goal.target_date - created_on).days >= MINIMUM_PERIOD_DAYS
                  and (goal.status != "COMPLETED" or completed_after_wait(goal))),
    )
    return result
