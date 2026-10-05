import time
import requests

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
)

from sqlalchemy.exc import IntegrityError

from app.errors.exceptions import BusinessException
from app.extensions import db
from app.models.features import RequestBucket

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

def _client_ip():
    return (
        request.headers.get("X-Real-IP")
        or request.remote_addr
        or "unknown"
    )

def _verify_turnstile(token):
    secret_key = current_app.config.get(
        "TURNSTILE_SECRET_KEY"
    )

    if not secret_key:
        raise BusinessException(
            code="CAPTCHA_CONFIG_ERROR",
            message="CAPTCHA 설정을 확인할 수 없습니다.",
            status_code=503,
        )

    try:
        response = requests.post(
            (
                "https://challenges.cloudflare.com/"
                "turnstile/v0/siteverify"
            ),
            data={
                "secret": secret_key,
                "response": token,
                "remoteip": _client_ip(),
            },
            timeout=5,
        )

        response.raise_for_status()

        result = response.json()

    except (
        requests.RequestException,
        ValueError,
    ):
        raise BusinessException(
            code="CAPTCHA_VERIFY_FAILED",
            message="CAPTCHA 검증 중 오류가 발생했습니다.",
            status_code=503,
        )

    if (
        not result.get("success")
        or result.get("action") != "signup"
    ):
        raise BusinessException(
            code="INVALID_CAPTCHA",
            message="CAPTCHA 인증에 실패했습니다.",
            status_code=400,
        )

def _login_rate_limit():
    limit = current_app.config.get(
        "AUTH_LOGIN_REQUESTS_PER_MINUTE",
        10,
    )

    bucket_key = (
        f"auth:login:{_client_ip()}"
    )

    now = int(time.time()) // 60

    bucket = (
        RequestBucket.query
        .filter_by(bucket_key=bucket_key)
        .with_for_update()
        .first()
    )

    if bucket is None:
        try:
            with db.session.begin_nested():
                bucket = RequestBucket(
                    bucket_key=bucket_key,
                    window_start=now,
                    count=0,
                )
                db.session.add(bucket)
                db.session.flush()

        except IntegrityError:
            bucket = (
                RequestBucket.query
                .filter_by(bucket_key=bucket_key)
                .with_for_update()
                .one()
            )

    if bucket.window_start != now:
        bucket.window_start = now
        bucket.count = 0

    if bucket.count >= limit:
        raise BusinessException(
            code="RATE_LIMITED",
            message="로그인 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
            status_code=429,
        )

    bucket.count += 1
    db.session.commit()

def _signup_rate_limit():
    ip = _client_ip()

    minute_limit = current_app.config.get(
        "AUTH_SIGNUP_REQUESTS_PER_MINUTE",
        5,
    )

    day_limit = current_app.config.get(
        "AUTH_SIGNUP_REQUESTS_PER_DAY",
        20,
    )

    current_minute = int(time.time()) // 60
    current_day = int(time.time()) // 86400

    def consume(bucket_key, window_start, limit):
        bucket = (
            RequestBucket.query
            .filter_by(bucket_key=bucket_key)
            .with_for_update()
            .first()
        )

        if bucket is None:
            try:
                with db.session.begin_nested():
                    bucket = RequestBucket(
                        bucket_key=bucket_key,
                        window_start=window_start,
                        count=0,
                    )
                    db.session.add(bucket)
                    db.session.flush()

            except IntegrityError:
                bucket = (
                    RequestBucket.query
                    .filter_by(bucket_key=bucket_key)
                    .with_for_update()
                    .one()
                )

        if bucket.window_start != window_start:
            bucket.window_start = window_start
            bucket.count = 0

        if bucket.count >= limit:
            raise BusinessException(
                code="RATE_LIMITED",
                message=(
                    "회원가입 요청이 너무 많습니다. "
                    "잠시 후 다시 시도해 주세요."
                ),
                status_code=429,
            )

        bucket.count += 1

    consume(
        f"auth:signup:minute:{ip}",
        current_minute,
        minute_limit,
    )

    consume(
        f"auth:signup:day:{ip}",
        current_day,
        day_limit,
    )

    db.session.commit()

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

    _verify_turnstile(
        payload["turnstile_token"]
    )

    _signup_rate_limit()

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
    _login_rate_limit()

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
