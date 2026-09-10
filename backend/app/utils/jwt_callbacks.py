from flask import jsonify

from app.constants import (
    ErrorCode,
    UserStatus,
)
from app.extensions import db
from app.models.user import User


def _get_user(jwt_payload):
    user_id = jwt_payload.get("sub")

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    return db.session.get(
        User,
        user_id,
    )


def register_jwt_callbacks(jwt):

    @jwt.token_in_blocklist_loader
    def check_token_revoked(
        jwt_header,
        jwt_payload,
    ):
        user = _get_user(jwt_payload)

        if user is None:
            return False

        token_version = jwt_payload.get(
            "token_version"
        )

        return (
            token_version
            != user.token_version
        )

    @jwt.token_verification_loader
    def verify_user_status(
        jwt_header,
        jwt_payload,
    ):
        user = _get_user(jwt_payload)

        if user is None:
            return False

        return (
            user.status
            == UserStatus.ACTIVE
        )

    @jwt.token_verification_failed_loader
    def user_status_failed(
        jwt_header,
        jwt_payload,
    ):
        user = _get_user(jwt_payload)

        if user is None:
            return jsonify({
                "success": False,
                "error": {
                    "code": ErrorCode.USER_NOT_FOUND,
                    "message": "사용자를 찾을 수 없습니다.",
                },
            }), 404

        if user.status == UserStatus.SUSPENDED:
            return jsonify({
                "success": False,
                "error": {
                    "code": ErrorCode.ACCOUNT_SUSPENDED,
                    "message": "정지된 계정입니다.",
                },
            }), 403

        if user.status == UserStatus.WITHDRAWN:
            return jsonify({
                "success": False,
                "error": {
                    "code": ErrorCode.ACCOUNT_WITHDRAWN,
                    "message": "탈퇴한 계정입니다.",
                },
            }), 403

        return jsonify({
            "success": False,
            "error": {
                "code": ErrorCode.INVALID_TOKEN,
                "message": "유효하지 않은 토큰입니다.",
            },
        }), 401

    @jwt.unauthorized_loader
    def missing_token(error):
        return jsonify({
            "success": False,
            "error": {
                "code": ErrorCode.AUTH_REQUIRED,
                "message": "인증 토큰이 필요합니다.",
            },
        }), 401

    @jwt.invalid_token_loader
    def invalid_token(error):
        return jsonify({
            "success": False,
            "error": {
                "code": ErrorCode.INVALID_TOKEN,
                "message": "유효하지 않은 토큰입니다.",
            },
        }), 401

    @jwt.expired_token_loader
    def expired_token(
        jwt_header,
        jwt_payload,
    ):
        return jsonify({
            "success": False,
            "error": {
                "code": ErrorCode.TOKEN_EXPIRED,
                "message": "토큰이 만료되었습니다.",
            },
        }), 401

    @jwt.revoked_token_loader
    def revoked_token(
        jwt_header,
        jwt_payload,
    ):
        user = _get_user(jwt_payload)
        message = ("정지된 계정입니다." if user and user.status == UserStatus.SUSPENDED
                   else "계정 상태가 변경되어 다시 로그인해야 합니다.")
        return jsonify({
            "success": False,
            "error": {
                "code": ErrorCode.TOKEN_REVOKED,
                "message": message,
            },
        }), 401
