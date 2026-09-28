import os
from datetime import timedelta

from flask import Flask, jsonify
from marshmallow import ValidationError

from app.errors.exceptions import BusinessException
from app.extensions import db, jwt, migrate
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException


def _validate_production_secrets(config):
    if str(config.get("APP_ENV", "")).strip().lower() not in {"production", "prod"}:
        return
    defaults = {"change-me-in-env", "change-me", "changeme", "dev-secret", "dev-secret-key", "your-secret-key", "your-jwt-secret-key"}
    invalid = []
    for name in ("SECRET_KEY", "JWT_SECRET_KEY", "SOCIAL_SIGNUP_TOKEN_SECRET"):
        value = config.get(name)
        if not isinstance(value, str) or not value.strip() or value.strip().lower() in defaults:
            invalid.append(name)
    if invalid:
        # Report field names only. Never include secret values or the config.
        raise RuntimeError("Production requires non-default signing secrets: " + ", ".join(invalid))


def create_app(test_config=None):
    if test_config is None:
        load_dotenv()
    app = Flask(__name__)
    app.config["APP_ENV"] = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development"))

    # --- 설정 ---
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///dev.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "change-me-in-env"
    )

    app.config["SOCIAL_SIGNUP_TOKEN_SECRET"] = os.environ.get(
        "SOCIAL_SIGNUP_TOKEN_SECRET", "change-me-in-env"
    )

    app.config["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET_KEY", "change-me-in-env"
    )

    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["JWT_COOKIE_SECURE"] = (
        os.environ.get("JWT_COOKIE_SECURE", "false").lower() == "true"
    )
    app.config["JWT_COOKIE_SAMESITE"] = "Lax"
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True
    app.config["JWT_ACCESS_COOKIE_PATH"] = "/"
    app.config["JWT_REFRESH_COOKIE_PATH"] = "/api/auth"
    app.config["JWT_ACCESS_CSRF_COOKIE_PATH"] = "/"
    app.config["JWT_REFRESH_CSRF_COOKIE_PATH"] = "/"

    app.config["GOOGLE_CLIENT_ID"] = os.environ.get(
        "GOOGLE_CLIENT_ID"
    )

    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get(
        "GOOGLE_CLIENT_SECRET"
    )

    app.config["GOOGLE_REDIRECT_URI"] = os.environ.get(
        "GOOGLE_REDIRECT_URI"
    )

    app.config["KAKAO_REST_API_KEY"] = os.environ.get(
        "KAKAO_REST_API_KEY"
    )

    app.config["KAKAO_CLIENT_SECRET"] = os.environ.get(
        "KAKAO_CLIENT_SECRET"
    )

    app.config["KAKAO_REDIRECT_URI"] = os.environ.get(
        "KAKAO_REDIRECT_URI"
    )

    app.config.update(
        MAX_CONTENT_LENGTH=51 * 1024 * 1024,
        FEATURE_RATE_LIMIT_ENABLED=True,
        FEATURE_WRITE_REQUESTS_PER_MINUTE=int(os.environ.get("FEATURE_WRITE_REQUESTS_PER_MINUTE", "30")),
        FEATURE_READ_REQUESTS_PER_MINUTE=int(os.environ.get("FEATURE_READ_REQUESTS_PER_MINUTE", "120")),
    )
    if test_config is not None:
        app.config.update(test_config)
    _validate_production_secrets(app.config)

    # --- 확장 초기화 ---
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    from app.utils.jwt_callbacks import register_jwt_callbacks
    register_jwt_callbacks(jwt)


    # --- 모델 import (Flask-Migrate가 인식하려면 반드시 필요) ---
    # 각자 담당 모델을 여기에 추가한다.
    from app.models.user import User  # noqa
    from app.models.account import Account  # noqa
    from app.models.social_account import SocialAccount  # noqa
    from app.models import features  # noqa
    from app.services import audit_service  # noqa: registers transactional audit hooks
    from app.models.market import MarketAsset, MarketHolding, MarketTransaction  # noqa
    from app.models.deposits_savings import (  # noqa
        Deposit, DepositPreferenceCondition, EarlyTerminationRateRule,
        FinancialProduct, FinancialProductOption, LedgerEntry, LedgerTransaction,
        ProductPreferenceCondition, Saving, SavingPayment,
        SavingPreferenceCondition,
    )

    # --- Blueprint 등록 ---
    # 각자 담당 라우트를 여기에 추가한다.
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.users import users_bp
    app.register_blueprint(users_bp)

    from app.routes.investments import investments_bp
    app.register_blueprint(investments_bp)

    from app.routes.products import products_bp
    from app.routes.deposits import deposits_bp
    from app.routes.savings import savings_bp
    app.register_blueprint(products_bp)
    app.register_blueprint(deposits_bp)
    app.register_blueprint(savings_bp)

    from app.routes.simulation import simulation_bp
    app.register_blueprint(simulation_bp)

    from app.routes.monthly_income import monthly_income_bp
    app.register_blueprint(monthly_income_bp)

    from app.routes.account import account_bp
    app.register_blueprint(account_bp)

    from app.routes.health import health_bp
    app.register_blueprint(health_bp)

    from app.routes.features import features_bp
    from app.routes.admin import admin_bp
    app.register_blueprint(features_bp)
    app.register_blueprint(admin_bp)
    from app.services.feature_setup import register_commands
    register_commands(app)

    # --- 공통 에러 핸들러 (개발 가이드 8번) ---
    @app.errorhandler(BusinessException)
    def handle_business_exception(e):
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": {"code": e.code, "message": e.message}
        }), e.status_code

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": {
                "code": "INVALID_REQUEST",
                "message": str(e.messages)
            }
        }), 400

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": "요청한 경로를 찾을 수 없습니다."}
        }), 404

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        db.session.rollback()
        if isinstance(e, HTTPException):
            return jsonify({"success": False, "error": {"code": e.name.upper().replace(" ", "_"),
                            "message": e.description}}), e.code
        # 예상 못한 서버 오류는 내부 정보를 노출하지 않는다 (개발 가이드 8번)
        app.logger.exception(e)
        return jsonify({
            "success": False,
            "error": {"code": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."}
        }), 500

    return app
