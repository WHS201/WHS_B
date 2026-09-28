from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from app.constants import SocialProvider
from app.schemas.auth import (
    LoginSchema,
    SignupSchema,
    SocialLoginSchema,
    SocialSignupSchema,
)
from app.services import auth_service


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/api/auth",
)


def _token_response(result, message, status_code=200):
    access_token = result.pop("access_token", None)
    refresh_token = result.pop("refresh_token", None)
    response = jsonify({
        "success": True,
        "data": result,
        "message": message,
    })
    if access_token:
        set_access_cookies(response, access_token)
    if refresh_token:
        set_refresh_cookies(response, refresh_token)
    return response, status_code


@auth_bp.post("/signup")
def signup():
    payload = SignupSchema().load(
        request.get_json(silent=True) or {}
    )

    result = auth_service.signup(
        username=payload["username"],
        password=payload["password"],
        nickname=payload["nickname"],
    )

    return jsonify({
        "success": True,
        "data": result,
        "message": "회원가입에 성공했습니다.",
    }), 201


@auth_bp.post("/login")
def login():
    payload = LoginSchema().load(
        request.get_json(silent=True) or {}
    )

    result = auth_service.login(
        username=payload["username"],
        password=payload["password"],
    )

    return _token_response(result, "로그인에 성공했습니다.")


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = int(
        get_jwt_identity()
    )

    claims = get_jwt()

    result = auth_service.refresh_access_token(
        user_id=user_id,
        token_version=claims.get(
            "token_version"
        ),
    )

    access_token = result.pop("access_token")
    response = jsonify({
        "success": True,
        "data": result,
        "message": "토큰 재발급에 성공했습니다.",
    })
    set_access_cookies(response, access_token)
    return response, 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    user_id = int(
        get_jwt_identity()
    )

    auth_service.logout(
        user_id=user_id
    )

    response = jsonify({
        "success": True,
        "data": {},
        "message": "로그아웃에 성공했습니다.",
    })
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.post("/google")
def google_login():
    payload = SocialLoginSchema().load(
        request.get_json(silent=True) or {}
    )

    result = auth_service.social_login(
        provider=SocialProvider.GOOGLE,
        code=payload["code"],
    )

    if result["signup_required"]:
        message = (
            "소셜 회원가입이 필요합니다."
        )
    else:
        message = (
            "Google 로그인에 성공했습니다."
        )

    return _token_response(result, message)


@auth_bp.post("/kakao")
def kakao_login():
    payload = SocialLoginSchema().load(
        request.get_json(silent=True) or {}
    )

    result = auth_service.social_login(
        provider=SocialProvider.KAKAO,
        code=payload["code"],
    )

    if result["signup_required"]:
        message = (
            "소셜 회원가입이 필요합니다."
        )
    else:
        message = (
            "Kakao 로그인에 성공했습니다."
        )

    return _token_response(result, message)


@auth_bp.post("/social/signup")
def social_signup():
    payload = SocialSignupSchema().load(
        request.get_json(silent=True) or {}
    )

    result = auth_service.social_signup(
        social_signup_token=payload[
            "social_signup_token"
        ],
        username=payload["username"],
    )

    return _token_response(
        result,
        "소셜 회원가입에 성공했습니다.",
        201,
    )
