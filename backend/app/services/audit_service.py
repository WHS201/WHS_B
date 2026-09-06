"""Append audit records in the same transaction as the underlying mutation."""
from datetime import date, datetime
from decimal import Decimal

from flask import has_request_context, request
from flask_jwt_extended import get_jwt_identity
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.features import AuditLog


def audit(action, target_type, target_id, before=None, after=None, reason=None, actor=None):
    if actor is None and has_request_context():
        try:
            identity = get_jwt_identity()
            actor = int(identity) if identity else None
        except RuntimeError:
            pass
    row = AuditLog(action=action, target_type=target_type, target_id=target_id,
                   before_value=before, after_value=after, reason=reason,
                   actor_user_id=actor, ip_address=request.remote_addr if has_request_context() else None)
    db.session.add(row)
    return row


# Only these fields are recorded. Passwords, tokens, social identifiers and
# private free-form post/inquiry content are never copied into audit JSON.
TRACKED = {
    "users": ("nickname", "role", "status", "representative_badge_id"),
    "accounts": ("balance",),
    "simulation_settings": ("initial_asset", "monthly_income", "monthly_expense", "is_initial_asset_set"),
    "saving_goals": ("goal_name", "target_amount", "target_date", "status"),
    "deposits": ("status", "principal", "payout_amount"),
    "savings": ("status", "total_paid_principal", "payout_amount"),
    "market_transactions": ("side", "quantity", "amount_krw"),
    "ledger_transactions": ("transaction_type", "amount", "balance_after"),
    "user_badges": ("badge_id",),
}


def _json(value):
    return str(value) if isinstance(value, (Decimal, date, datetime)) else value


@event.listens_for(Session, "after_flush")
def record_changes(session, context):
    for collection, action in ((session.new, "CREATE"), (session.dirty, "UPDATE"), (session.deleted, "DELETE")):
        for row in list(collection):
            table = getattr(row, "__tablename__", "")
            if table not in TRACKED:
                continue
            state = inspect(row)
            changed = [key for key in TRACKED[table] if action != "UPDATE" or state.attrs[key].history.has_changes()]
            if not changed:
                continue
            before = {key: _json(state.attrs[key].history.deleted[0] if state.attrs[key].history.deleted else getattr(row, key)) for key in changed}
            after = {key: _json(getattr(row, key)) for key in changed}
            identifier = getattr(row, list(row.__table__.primary_key.columns)[0].name)
            audit(action, table, identifier, None if action == "CREATE" else before,
                  None if action == "DELETE" else after)
