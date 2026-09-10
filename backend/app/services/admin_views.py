"""Read-only, administrator-only presentation data. Never serialize credentials."""
from app.extensions import db
from app.models.user import User
from app.models.features import Post, Comment
from app.services.feature_common import serialize


def with_members(result, key="user_id"):
    identifiers = {item.get(key) for item in result["items"]} - {None}
    members = {
        uid: {"user_id": uid, "username": username, "nickname": nickname}
        for uid, username, nickname in db.session.query(User.user_id, User.username, User.nickname)
        .filter(User.user_id.in_(identifiers))
    }
    for item in result["items"]:
        item["member"] = members.get(item.get(key))
    return result


def report_data(row):
    target = db.session.get(Post if row.target_type == "POST" else Comment, row.target_id)
    parent = (db.session.get(Post, target.post_id)
              if target and row.target_type == "COMMENT" else target)
    deleted = not target or target.deleted_at is not None or not parent or parent.deleted_at is not None
    return {**serialize(row), "target": {
        "deleted": bool(deleted),
        "post_id": parent.post_id if parent else None,
        "title": parent.title if parent and not deleted else None,
        "content": target.content if target and not deleted else None,
        "user_id": target.user_id if target else None,
    }}


def audit_data(row):
    return {**serialize(row), "record_kind": (
        "AUTOMATIC" if row.action in {"CREATE", "UPDATE", "DELETE"} else "OPERATION"
    )}
