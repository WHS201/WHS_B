"""Additional service data. Financial tables remain owned by their existing models."""
from datetime import datetime

from app.extensions import db
from app.models.base import TimestampMixin
from sqlalchemy.dialects.mysql import MEDIUMBLOB


class SavingGoal(TimestampMixin, db.Model):
    __tablename__ = "saving_goals"
    goal_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    goal_name = db.Column(db.String(50), nullable=False)
    target_amount = db.Column(db.BigInteger, nullable=False)
    target_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    completed_at = db.Column(db.DateTime)
    __table_args__ = (db.CheckConstraint("target_amount > 0 AND target_amount <= 1000000000", name="ck_goal_amount"),)


class AssetSnapshot(db.Model):
    __tablename__ = "asset_snapshots"
    snapshot_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    snapshot_date = db.Column(db.Date, nullable=False)
    amounts = db.Column(db.JSON, nullable=False)
    total_assets = db.Column(db.BigInteger, nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "snapshot_date", name="uq_snapshot_user_date"),)


class Badge(db.Model):
    __tablename__ = "badges"
    badge_id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    badge_type = db.Column(db.String(30), nullable=False)


class UserBadge(db.Model):
    __tablename__ = "user_badges"
    user_badge_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey("badges.badge_id"), nullable=False)
    acquired_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    badge = db.relationship("Badge")
    __table_args__ = (db.UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)


class ProfileVisibility(db.Model):
    __tablename__ = "profile_visibility_settings"
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True)
    show_joined_at = db.Column(db.Boolean, nullable=False, default=False)
    show_badges = db.Column(db.Boolean, nullable=False, default=False)
    show_active_goals = db.Column(db.Boolean, nullable=False, default=False)
    show_completed_goals = db.Column(db.Boolean, nullable=False, default=False)
    show_goal_progress = db.Column(db.Boolean, nullable=False, default=False)
    show_total_assets = db.Column(db.Boolean, nullable=False, default=False)
    show_asset_allocation = db.Column(db.Boolean, nullable=False, default=False)
    show_investment_return = db.Column(db.Boolean, nullable=False, default=False)


class Post(TimestampMixin, db.Model):
    __tablename__ = "posts"
    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    board_type = db.Column(db.String(20), nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    deleted_at = db.Column(db.DateTime)


class Comment(TimestampMixin, db.Model):
    __tablename__ = "comments"
    comment_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    deleted_at = db.Column(db.DateTime)


class PostReaction(db.Model):
    __tablename__ = "post_reactions"
    reaction_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    reaction_type = db.Column(db.String(10), nullable=False)
    __table_args__ = (db.UniqueConstraint("post_id", "user_id", name="uq_post_reaction"),)


class Report(db.Model):
    __tablename__ = "reports"
    report_id = db.Column(db.Integer, primary_key=True)
    reporter_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    target_type = db.Column(db.String(10), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    resolution_reason = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    __table_args__ = (db.UniqueConstraint("reporter_user_id", "target_type", "target_id", name="uq_report_target"),)


class Inquiry(TimestampMixin, db.Model):
    __tablename__ = "inquiries"
    inquiry_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    # Logical reference: financial reset may remove the original ledger.
    related_ledger_transaction_id = db.Column(db.Integer)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    admin_answer = db.Column(db.Text)
    answered_at = db.Column(db.DateTime)
    answered_by = db.Column(db.Integer, db.ForeignKey("users.user_id"))


class Attachment(db.Model):
    """Validated images stored transactionally; no arbitrary file paths or URLs."""
    __tablename__ = "attachments"
    attachment_id = db.Column(db.String(32), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.post_id"), index=True)
    inquiry_id = db.Column(db.Integer, db.ForeignKey("inquiries.inquiry_id"), index=True)
    mime_type = db.Column(db.String(30), nullable=False)
    data = db.deferred(db.Column(db.LargeBinary().with_variant(MEDIUMBLOB(), "mysql"), nullable=False))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.CheckConstraint("(post_id IS NULL AND inquiry_id IS NOT NULL) OR (post_id IS NOT NULL AND inquiry_id IS NULL)", name="ck_attachment_parent"),)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    audit_log_id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), index=True)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer)
    before_value = db.Column(db.JSON)
    after_value = db.Column(db.JSON)
    reason = db.Column(db.String(1000))
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class RequestBucket(db.Model):
    __tablename__ = "request_buckets"
    bucket_key = db.Column(db.String(120), primary_key=True)
    window_start = db.Column(db.BigInteger, nullable=False)
    count = db.Column(db.Integer, nullable=False)
