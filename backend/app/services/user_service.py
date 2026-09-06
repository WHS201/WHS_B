from flask import current_app

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from app.constants import (
    ErrorCode,
    UserStatus
)
from app.extensions import db
from app.errors.exceptions import BusinessException
from app.models.social_account import SocialAccount
from app.models.user import User
from app.services.financial_cleanup_service import (
    delete_user_financial_data
)
from app.utils.oauth import (
    get_social_profile
)


def change_password(
    user_id,
    current_password,
    new_password
):
    user = db.session.get(
        User,
        user_id
    )

    if user is None:
        raise BusinessException(
            code=ErrorCode.USER_NOT_FOUND,
            message="사용자를 찾을 수 없습니다.",
            status_code=404
        )

    if user.password_hash is None:
        raise BusinessException(
            code=ErrorCode.PASSWORD_NOT_SET,
            message=(
                "비밀번호가 설정되지 않은 "
                "사용자입니다."
            ),
            status_code=422
        )

    if not check_password_hash(
        user.password_hash,
        current_password
    ):
        raise BusinessException(
            code=(
                ErrorCode
                .CURRENT_PASSWORD_MISMATCH
            ),
            message=(
                "현재 비밀번호가 "
                "올바르지 않습니다."
            ),
            status_code=401
        )

    user.password_hash = (
        generate_password_hash(
            new_password
        )
    )

    # 기존 Access/Refresh Token 전체 무효화
    user.token_version += 1

    from app.services.audit_service import audit
    audit("PASSWORD_CHANGE", "users", user_id)

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Password change failed"
        )

        raise BusinessException(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message="서버 내부 오류가 발생했습니다.",
            status_code=500
        )


def withdraw_user(
    user_id,
    current_password=None,
    provider=None,
    code=None
):
    user = db.session.get(
        User,
        user_id
    )

    if user is None:
        raise BusinessException(
            code=ErrorCode.USER_NOT_FOUND,
            message="사용자를 찾을 수 없습니다.",
            status_code=404
        )

    if user.status == UserStatus.WITHDRAWN:
        raise BusinessException(
            code=ErrorCode.ACCOUNT_WITHDRAWN,
            message="이미 탈퇴한 계정입니다.",
            status_code=403
        )

    # 일반 회원
    if user.password_hash is not None:
        if not current_password:
            raise BusinessException(
                code=ErrorCode.INVALID_REQUEST,
                message="현재 비밀번호가 필요합니다.",
                status_code=400
            )

        if not check_password_hash(
            user.password_hash,
            current_password
        ):
            raise BusinessException(
                code=(
                    ErrorCode
                    .CURRENT_PASSWORD_MISMATCH
                ),
                message=(
                    "현재 비밀번호가 "
                    "올바르지 않습니다."
                ),
                status_code=401
            )

    # 소셜 로그인 회원
    else:
        if not provider or not code:
            raise BusinessException(
                code=ErrorCode.INVALID_REQUEST,
                message=(
                    "소셜 계정 재인증이 "
                    "필요합니다."
                ),
                status_code=400
            )

        profile = get_social_profile(
            provider=provider,
            code=code
        )

        social_account = (
            SocialAccount.query.filter_by(
                user_id=user.user_id,
                provider=provider,
                provider_user_id=(
                    profile[
                        "provider_user_id"
                    ]
                )
            ).first()
        )

        if social_account is None:
            raise BusinessException(
                code=(
                    ErrorCode
                    .SOCIAL_AUTH_FAILED
                ),
                message=(
                    "소셜 계정 재인증에 "
                    "실패했습니다."
                ),
                status_code=401
            )

    try:
        # 금융 관련 데이터 삭제
        from app.services.account_service import get_account_by_user_id
        from app.services.audit_service import audit
        get_account_by_user_id(user.user_id)
        audit("USER_WITHDRAW", "users", user.user_id)
        delete_user_financial_data(
            user.user_id
        )

        # Google/Kakao 연결 정보 삭제
        SocialAccount.query.filter_by(
            user_id=user.user_id
        ).delete(
            synchronize_session=False
        )

        # users 행은 유지하고 상태만 변경
        user.status = UserStatus.WITHDRAWN

        # 기존 Access/Refresh Token 전체 무효화
        user.token_version += 1

        db.session.commit()

    except BusinessException:
        db.session.rollback()
        raise

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "User withdrawal failed"
        )

        raise BusinessException(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message=(
                "회원 탈퇴 처리 중 "
                "오류가 발생했습니다."
            ),
            status_code=500
        )
