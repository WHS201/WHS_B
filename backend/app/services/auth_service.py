from datetime import (
    datetime,
    timedelta,
    timezone,
)

from flask import current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
)
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from app.constants import (
    ErrorCode,
    SocialProvider,
    UserRole,
    UserStatus,
)
from app.errors.exceptions import BusinessException
from app.extensions import db
from app.models.account import Account
from app.models.simulation_setting import SimulationSetting
from app.models.social_account import SocialAccount
from app.models.user import User
from app.utils.account_number import generate_account_number
from app.utils.oauth import get_social_profile
from app.utils.social_signup_token import (
    create_social_signup_token,
    decode_social_signup_token,
)


ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
REFRESH_TOKEN_EXPIRES = timedelta(days=7)


def _utc_now():
    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=None)
    )


def _commit():
    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Database commit failed"
        )

        raise BusinessException(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message="서버 내부 오류가 발생했습니다.",
            status_code=500,
        )


def _create_token_pair(user):
    additional_claims = {
        "role": user.role,
        "token_version": user.token_version,
    }

    access_token = create_access_token(
        identity=str(user.user_id),
        additional_claims=additional_claims,
        expires_delta=ACCESS_TOKEN_EXPIRES,
    )

    refresh_token = create_refresh_token(
        identity=str(user.user_id),
        additional_claims=additional_claims,
        expires_delta=REFRESH_TOKEN_EXPIRES,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": 1800,
    }


def _check_user_status(user):
    if user.status == UserStatus.SUSPENDED.value:
        raise BusinessException(
            code=ErrorCode.ACCOUNT_SUSPENDED,
            message="정지된 계정입니다.",
            status_code=403,
        )

    if user.status == UserStatus.WITHDRAWN.value:
        raise BusinessException(
            code=ErrorCode.ACCOUNT_WITHDRAWN,
            message="탈퇴한 계정입니다.",
            status_code=403,
        )


def _validate_social_nickname(nickname):
    if not isinstance(nickname, str):
        raise BusinessException(
            code=ErrorCode.INVALID_SOCIAL_PROFILE,
            message=(
                "소셜 계정의 닉네임 정보를 "
                "사용할 수 없습니다."
            ),
            status_code=422,
        )

    if (
        nickname.strip() == ""
        or len(nickname) < 2
        or len(nickname) > 20
    ):
        raise BusinessException(
            code=ErrorCode.INVALID_SOCIAL_PROFILE,
            message=(
                "소셜 계정의 닉네임이 "
                "서비스 조건을 만족하지 않습니다."
            ),
            status_code=422,
        )

    return nickname


def signup(
    username,
    password,
    nickname,
):
    existing_user = (
        User.query.filter_by(
            username=username
        ).first()
    )

    if existing_user is not None:
        raise BusinessException(
            code=ErrorCode.DUPLICATE_USERNAME,
            message="이미 사용 중인 아이디입니다.",
            status_code=409,
        )

    user = User(
        username=username,
        password_hash=generate_password_hash(
            password
        ),
        nickname=nickname,
        role=UserRole.USER.value,
        status=UserStatus.ACTIVE.value,
        failed_login_count=0,
        token_version=0,
    )

    try:
        db.session.add(user)

        # user_id를 먼저 생성하기 위해 DB에 반영하되
        # 아직 commit하지 않는다.
        db.session.flush()

        account = Account(
            user_id=user.user_id,
            account_number=generate_account_number(),
            balance=0,
        )

        simulation_setting = SimulationSetting(
            user_id=user.user_id,
        )

        db.session.add(account)
        db.session.add(simulation_setting)

        # 사용자, 계좌, 시뮬레이션 설정을
        # 하나의 작업으로 저장한다.
        db.session.commit()

    except BusinessException:
        db.session.rollback()
        raise

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Signup failed"
        )

        raise BusinessException(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=(
                "회원가입 처리 중 "
                "오류가 발생했습니다."
            ),
            status_code=500,
        )

    return {
        "user_id": user.user_id,
    }


def login(
    username,
    password,
):
    user = (
        User.query.filter_by(
            username=username
        ).first()
    )

    if user is None:
        current_app.logger.warning(
            "Login failed: user not found"
        )

        raise BusinessException(
            code=ErrorCode.INVALID_CREDENTIALS,
            message=(
                "아이디 또는 비밀번호가 "
                "올바르지 않습니다."
            ),
            status_code=401,
        )

    now = _utc_now()

    # 아직 5분 로그인 제한 시간이 지나지 않은 경우
    if (
        user.login_locked_until is not None
        and user.login_locked_until > now
    ):
        raise BusinessException(
            code=ErrorCode.LOGIN_LOCKED,
            message=(
                "로그인이 일시적으로 "
                "제한되었습니다."
            ),
            status_code=403,
        )

    # 5분 제한 시간이 끝난 경우 실패 횟수 초기화
    if (
        user.login_locked_until is not None
        and user.login_locked_until <= now
    ):
        user.failed_login_count = 0
        user.login_locked_until = None

    password_valid = (
        user.password_hash is not None
        and check_password_hash(
            user.password_hash,
            password,
        )
    )

    if not password_valid:
        user.failed_login_count = (
            user.failed_login_count or 0
        ) + 1

        if user.failed_login_count >= 5:
            user.login_locked_until = (
                now + timedelta(minutes=5)
            )

        current_app.logger.warning(
            "Login failed for user_id=%s",
            user.user_id,
        )

        _commit()

        if user.failed_login_count >= 5:
            raise BusinessException(
                code=ErrorCode.LOGIN_LOCKED,
                message=(
                    "로그인이 일시적으로 "
                    "제한되었습니다."
                ),
                status_code=403,
            )

        raise BusinessException(
            code=ErrorCode.INVALID_CREDENTIALS,
            message=(
                "아이디 또는 비밀번호가 "
                "올바르지 않습니다."
            ),
            status_code=401,
        )

    _check_user_status(user)

    # 로그인 성공 시 실패 횟수 초기화
    user.failed_login_count = 0
    user.login_locked_until = None

    _commit()

    return _create_token_pair(user)


def refresh_access_token(
    user_id,
    token_version,
):
    user = db.session.get(
        User,
        user_id,
    )

    if user is None:
        raise BusinessException(
            code=ErrorCode.USER_NOT_FOUND,
            message="사용자를 찾을 수 없습니다.",
            status_code=404,
        )

    _check_user_status(user)

    if user.token_version != token_version:
        raise BusinessException(
            code=ErrorCode.TOKEN_REVOKED,
            message="이미 무효화된 토큰입니다.",
            status_code=401,
        )

    access_token = create_access_token(
        identity=str(user.user_id),
        additional_claims={
            "role": user.role,
            "token_version": user.token_version,
        },
        expires_delta=ACCESS_TOKEN_EXPIRES,
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 1800,
    }


def logout(user_id):
    user = db.session.get(
        User,
        user_id,
    )

    if user is None:
        raise BusinessException(
            code=ErrorCode.USER_NOT_FOUND,
            message="사용자를 찾을 수 없습니다.",
            status_code=404,
        )

    # 기존 Access/Refresh Token 전체 무효화
    user.token_version += 1

    _commit()


def social_login(
    provider,
    code,
):
    profile = get_social_profile(
        provider=provider,
        code=code,
    )

    social_account = (
        SocialAccount.query.filter_by(
            provider=provider,
            provider_user_id=profile[
                "provider_user_id"
            ],
        ).first()
    )

    # 처음 로그인하는 소셜 계정
    if social_account is None:
        nickname = _validate_social_nickname(
            profile.get("nickname")
        )

        signup_token = create_social_signup_token(
            provider=provider,
            provider_user_id=profile[
                "provider_user_id"
            ],
            nickname=nickname,
        )

        return {
            "signup_required": True,
            "social_signup_token": signup_token,
            "nickname": nickname,
        }

    # 이미 회원가입한 소셜 사용자
    user = db.session.get(
        User,
        social_account.user_id,
    )

    if user is None:
        raise BusinessException(
            code=ErrorCode.USER_NOT_FOUND,
            message="사용자를 찾을 수 없습니다.",
            status_code=404,
        )

    _check_user_status(user)

    result = _create_token_pair(user)

    return {
        "signup_required": False,
        **result,
    }


def social_signup(
    social_signup_token,
    username,
):
    social_data = decode_social_signup_token(
        social_signup_token
    )

    existing_user = (
        User.query.filter_by(
            username=username
        ).first()
    )

    if existing_user is not None:
        raise BusinessException(
            code=ErrorCode.DUPLICATE_USERNAME,
            message="이미 사용 중인 아이디입니다.",
            status_code=409,
        )

    provider = social_data.get(
        "provider"
    )

    if provider not in (
        SocialProvider.GOOGLE,
        SocialProvider.KAKAO,
    ):
        raise BusinessException(
            code=ErrorCode.INVALID_SOCIAL_SIGNUP_TOKEN,
            message=(
                "유효하지 않은 "
                "소셜 회원가입 토큰입니다."
            ),
            status_code=401,
        )

    provider_user_id = social_data.get(
        "provider_user_id"
    )

    nickname = social_data.get(
        "nickname"
    )

    if (
        not provider_user_id
        or not nickname
    ):
        raise BusinessException(
            code=ErrorCode.INVALID_SOCIAL_SIGNUP_TOKEN,
            message=(
                "유효하지 않은 "
                "소셜 회원가입 토큰입니다."
            ),
            status_code=401,
        )

    existing_social = (
        SocialAccount.query.filter_by(
            provider=provider,
            provider_user_id=provider_user_id,
        ).first()
    )

    if existing_social is not None:
        raise BusinessException(
            code=ErrorCode.SOCIAL_ACCOUNT_ALREADY_EXISTS,
            message="이미 연결된 소셜 계정입니다.",
            status_code=409,
        )

    user = User(
        username=username,
        password_hash=None,
        nickname=nickname,
        role=UserRole.USER.value,
        status=UserStatus.ACTIVE.value,
        failed_login_count=0,
        token_version=0,
    )

    try:
        db.session.add(user)

        db.session.flush()

        social_account = SocialAccount(
            user_id=user.user_id,
            provider=provider,
            provider_user_id=provider_user_id,
        )

        account = Account(
            user_id=user.user_id,
            account_number=generate_account_number(),
            balance=0,
        )

        simulation_setting = SimulationSetting(
            user_id=user.user_id,
        )

        db.session.add(social_account)
        db.session.add(account)
        db.session.add(simulation_setting)

        # User + SocialAccount + Account + SimulationSetting을
        # 하나의 작업으로 저장한다.
        db.session.commit()

    except BusinessException:
        db.session.rollback()
        raise

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Social signup failed"
        )

        raise BusinessException(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=(
                "소셜 회원가입 처리 중 "
                "오류가 발생했습니다."
            ),
            status_code=500,
        )

    tokens = _create_token_pair(user)

    return {
        "user_id": user.user_id,
        **tokens,
    }