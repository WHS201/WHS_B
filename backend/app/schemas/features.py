from marshmallow import Schema, fields, validate, ValidationError


def nonblank(value):
    if not value.strip():
        raise ValidationError("공백만 입력할 수 없습니다.")


def text(maximum, **kwargs):
    return fields.String(validate=[validate.Length(min=1, max=maximum), nonblank], **kwargs)


class GoalSchema(Schema):
    goal_name = text(50, required=True)
    target_amount = fields.Integer(strict=True, required=True, validate=validate.Range(min=1, max=1000000000))
    target_date = fields.Date(required=True)


class PostSchema(Schema):
    board_type = fields.String(required=True, validate=validate.OneOf(["FREE", "KR_STOCK", "US_STOCK", "DEPOSIT_SAVING"]))
    title = text(100, required=True)
    content = text(10000, required=True)


class CommentSchema(Schema):
    content = text(1000, required=True)


class ReactionSchema(Schema):
    reaction_type = fields.String(required=True, validate=validate.OneOf(["LIKE", "DISLIKE", "NONE"]))


class ReportSchema(Schema):
    target_type = fields.String(required=True, validate=validate.OneOf(["POST", "COMMENT"]))
    target_id = fields.Integer(strict=True, required=True, validate=validate.Range(min=1))
    reason = text(1000, required=True)


class InquirySchema(Schema):
    title = text(100, required=True)
    content = text(5000, required=True)
    related_ledger_transaction_id = fields.Integer(strict=True, allow_none=True, validate=validate.Range(min=1))


class ProfileSchema(Schema):
    nickname = fields.String(validate=[validate.Length(min=2, max=20), nonblank])
    representative_badge_id = fields.Integer(strict=True, allow_none=True, validate=validate.Range(min=1))


class StrictBoolean(fields.Boolean):
    def _deserialize(self, value, attr, data, **kwargs):
        if type(value) is not bool:
            raise ValidationError("true 또는 false만 허용합니다.")
        return value


class VisibilitySchema(Schema):
    show_joined_at = StrictBoolean()
    show_badges = StrictBoolean()
    show_active_goals = StrictBoolean()
    show_completed_goals = StrictBoolean()
    show_goal_progress = StrictBoolean()
    show_total_assets = StrictBoolean()
    show_asset_allocation = StrictBoolean()
    show_investment_return = StrictBoolean()


class ReasonSchema(Schema):
    reason = text(1000, required=True)


class UserStatusSchema(ReasonSchema):
    status = fields.String(required=True, validate=validate.OneOf(["ACTIVE", "SUSPENDED"]))


class AdjustmentSchema(ReasonSchema):
    amount = fields.Integer(strict=True, required=True, validate=validate.Range(min=-100000000, max=100000000))


class AnswerSchema(ReasonSchema):
    answer = text(5000, required=True)


class ResolutionSchema(ReasonSchema):
    status = fields.String(required=True, validate=validate.OneOf(["RESOLVED", "REJECTED"]))


class ProductPatchSchema(ReasonSchema):
    product_name = text(200)
    description = text(10000)
    join_target = text(255)
    is_active = StrictBoolean()
    sync_locked = StrictBoolean()


class ProductOptionSchema(ReasonSchema):
    base_interest_rate = fields.Decimal(places=4, validate=validate.Range(min=0, max=99.9999))
    max_interest_rate = fields.Decimal(places=4, validate=validate.Range(min=0, max=99.9999))
    min_amount = fields.Integer(strict=True, validate=validate.Range(min=1, max=1000000000))
    max_amount = fields.Integer(strict=True, validate=validate.Range(min=1, max=1000000000))
    is_active = StrictBoolean()
    sync_locked = StrictBoolean()
