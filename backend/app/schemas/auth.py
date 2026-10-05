from marshmallow import (
    Schema,
    ValidationError,
    fields,
    validate,
    validates,
    validates_schema,
)

from app.constants import SocialProvider


def validate_password_policy(value):
    if value.strip() == "":
        raise ValidationError(
            "비밀번호는 공백만으로 구성할 수 없습니다."
        )

    if not any(
        character.isalpha()
        for character in value
    ):
        raise ValidationError(
            "비밀번호에는 문자가 포함되어야 합니다."
        )

    if not any(
        character.isdigit()
        for character in value
    ):
        raise ValidationError(
            "비밀번호에는 숫자가 포함되어야 합니다."
        )

    if not any(
        not character.isalnum()
        and not character.isspace()
        for character in value
    ):
        raise ValidationError(
            "비밀번호에는 특수문자가 포함되어야 합니다."
        )


class SignupSchema(Schema):
    username = fields.String(
        required=True,
        validate=validate.Length(
            min=4,
            max=20,
        ),
    )

    password = fields.String(
        required=True,
        validate=validate.Length(
            min=8,
            max=20,
        ),
    )

    nickname = fields.String(
        required=True,
        validate=validate.Length(
            min=2,
            max=20,
        ),
    )

    turnstile_token = fields.String(
        required=True,
        load_only=True,
    )

    @validates("username")
    def validate_username(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "아이디는 공백만으로 구성할 수 없습니다."
            )

    @validates("password")
    def validate_password(
        self,
        value,
        **kwargs,
    ):
        validate_password_policy(value)

    @validates("nickname")
    def validate_nickname(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "닉네임은 공백만으로 구성할 수 없습니다."
            )

    @validates("turnstile_token")
    def validate_turnstile_token(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "CAPTCHA 인증 정보가 필요합니다."
            )


class LoginSchema(Schema):
    username = fields.String(
        required=True,
    )

    password = fields.String(
        required=True,
    )

    @validates("username")
    def validate_username(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "아이디는 공백만으로 구성할 수 없습니다."
            )

    @validates("password")
    def validate_password(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "비밀번호는 공백만으로 구성할 수 없습니다."
            )


class PasswordChangeSchema(Schema):
    current_password = fields.String(
        required=True,
    )

    new_password = fields.String(
        required=True,
        validate=validate.Length(
            min=8,
            max=20,
        ),
    )

    @validates("current_password")
    def validate_current_password(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "현재 비밀번호를 입력해야 합니다."
            )

    @validates("new_password")
    def validate_new_password(
        self,
        value,
        **kwargs,
    ):
        validate_password_policy(value)


class WithdrawSchema(Schema):
    current_password = fields.String(
        required=False,
    )

    provider = fields.String(
        required=False,
        validate=validate.OneOf([
            SocialProvider.GOOGLE,
            SocialProvider.KAKAO,
        ]),
    )

    code = fields.String(
        required=False,
    )

    @validates("current_password")
    def validate_current_password(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "현재 비밀번호를 입력해야 합니다."
            )

    @validates("code")
    def validate_code(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "인증코드를 입력해야 합니다."
            )

    @validates_schema
    def validate_authentication(
        self,
        data,
        **kwargs,
    ):
        has_password = bool(
            data.get("current_password")
        )

        has_social = bool(
            data.get("provider")
            and data.get("code")
        )

        if not has_password and not has_social:
            raise ValidationError(
                "회원 탈퇴를 위한 인증 정보가 필요합니다."
            )


class SocialLoginSchema(Schema):
    code = fields.String(
        required=True,
    )

    @validates("code")
    def validate_code(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "인증코드를 입력해야 합니다."
            )


class SocialSignupSchema(Schema):
    social_signup_token = fields.String(
        required=True,
    )

    username = fields.String(
        required=True,
        validate=validate.Length(
            min=4,
            max=20,
        ),
    )

    @validates("social_signup_token")
    def validate_social_signup_token(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "소셜 회원가입 토큰이 필요합니다."
            )

    @validates("username")
    def validate_username(
        self,
        value,
        **kwargs,
    ):
        if value.strip() == "":
            raise ValidationError(
                "아이디는 공백만으로 구성할 수 없습니다."
            )