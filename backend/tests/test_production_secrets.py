"""Startup configuration checks use synthetic keys and never load .env files."""
import secrets

import pytest

import app as app_module


KEYS = ("SECRET_KEY", "JWT_SECRET_KEY", "SOCIAL_SIGNUP_TOKEN_SECRET")


def config(environment="production"):
    return {"TESTING": True, "APP_ENV": environment,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            **{key: secrets.token_urlsafe(32) for key in KEYS}}


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("value", [None, "", "  ", "change-me-in-env", "dev-secret", " YOUR-SECRET-KEY "])
def test_production_rejects_missing_blank_or_default_before_db_init(monkeypatch, key, value, caplog):
    settings = config()
    settings[key] = value
    def unexpected(*args, **kwargs):
        raise AssertionError("Invalid configuration must fail before DB initialization or dotenv loading")
    monkeypatch.setattr(app_module.db, "init_app", unexpected)
    monkeypatch.setattr(app_module, "load_dotenv", unexpected)
    with pytest.raises(RuntimeError, match=key) as error:
        app_module.create_app(settings)
    for other in KEYS:
        if other != key:
            assert settings[other] not in str(error.value) + caplog.text
    if value and value.strip():
        assert value not in str(error.value) + caplog.text


@pytest.mark.parametrize("key", KEYS)
def test_missing_environment_key_cannot_use_default_in_production(monkeypatch, key):
    settings = config()
    del settings[key]
    monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match=key):
        app_module.create_app(settings)


@pytest.mark.parametrize("environment", ["development", "dev", "test"])
def test_development_and_test_keep_existing_defaults(environment):
    settings = config(environment)
    settings.update({key: "change-me-in-env" for key in KEYS})
    application = app_module.create_app(settings)
    assert application.config["APP_ENV"] == environment
    with application.app_context():
        app_module.db.engine.dispose()


@pytest.mark.parametrize("environment", ["production", "prod", " PRODUCTION "])
def test_explicit_production_keys_allow_startup(environment):
    application = app_module.create_app(config(environment))
    with application.app_context():
        app_module.db.engine.dispose()


def test_production_flag_is_read_from_environment(monkeypatch):
    settings = config()
    del settings["APP_ENV"]
    settings["JWT_SECRET_KEY"] = ""
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        app_module.create_app(settings)
