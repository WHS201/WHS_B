"""Exercise real migrations against isolated data, including production SQL output."""
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade
from sqlalchemy import event, inspect, text

from app import create_app
from app.extensions import db


MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")
BASELINE = "89db6f2f8dd9"
FEATURE_REVISION = "c71e90b2a614"
FEATURE_TABLES = {
    "asset_snapshots", "attachments", "audit_logs", "badges", "comments",
    "inquiries", "post_reactions", "posts", "profile_visibility_settings",
    "reports", "request_buckets", "saving_goals", "user_badges",
}
BADGE_CODES = {
    "FIRST_GOAL", "THREE_GOALS", "SAVING_SIX_PAYMENTS", "INVESTMENT_TEN_PERCENT",
}
LEGACY_TABLES = ("users", "accounts", "financial_products", "financial_product_options")


def _read_legacy_rows(columns):
    """Use the baseline columns so added defaults do not hide legacy changes."""
    with db.engine.connect() as connection:
        return {
            table: [dict(row) for row in connection.execute(text(
                f"SELECT {', '.join(columns[table])} FROM {table}"
            )).mappings()]
            for table in LEGACY_TABLES
        }


@pytest.fixture
def baseline_database(tmp_path):
    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp_path / "migration.sqlite").as_posix(),
        "JWT_SECRET_KEY": "isolated-migration-tests-secret-at-least-32-characters",
        "FEATURE_RATE_LIMIT_ENABLED": False,
    })
    with application.app_context():
        engine = db.engine

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        upgrade(directory=MIGRATIONS, revision=BASELINE)
        inspector = inspect(engine)
        baseline_tables = set(inspector.get_table_names())
        baseline_columns = {
            table: [column["name"] for column in inspector.get_columns(table)]
            for table in LEGACY_TABLES
        }
        # The old schema has no audit table, so insert a deployment's existing
        # rows directly instead of invoking current ORM audit hooks or defaults.
        with engine.begin() as connection:
            parameters = {"created": datetime(2026, 8, 20, 12, 30), "balance": 123456789}
            connection.execute(text("""
                INSERT INTO users
                    (user_id, username, password_hash, nickname, role, status,
                     representative_badge_id, failed_login_count, login_locked_until,
                     token_version, created_at, updated_at)
                VALUES (41, 'legacy_user', 'fixture-hash', '기존 사용자', 'USER', 'ACTIVE',
                        NULL, 0, NULL, 3, :created, :created)
            """), parameters)
            connection.execute(text("""
                INSERT INTO accounts
                    (account_id, user_id, account_number, balance, created_at, updated_at)
                VALUES (17, 41, '123456789012', :balance, :created, :created)
            """), parameters)
            connection.execute(text("""
                INSERT INTO financial_products
                    (product_id, external_product_code, bank_name, product_name,
                     product_type, description, join_target, is_active, created_at, updated_at)
                VALUES (9, 'legacy-product', '기존 은행', '기존 예금', 'DEPOSIT',
                        '배포 전 상품 설명', '개인', 1, :created, :created)
            """), parameters)
            connection.execute(text("""
                INSERT INTO financial_product_options
                    (option_id, product_id, term_months, base_interest_rate,
                     max_interest_rate, interest_method, min_amount, max_amount, is_active)
                VALUES (11, 9, 12, 3.2500, 4.5000, 'SIMPLE', 10000, 100000000, 1)
            """))
        original_rows = _read_legacy_rows(baseline_columns)
        try:
            yield {
                "tables": baseline_tables,
                "columns": baseline_columns,
                "rows": original_rows,
            }
        finally:
            db.session.remove()
            engine.dispose()


def test_upgrade_preserves_legacy_data_and_seeds_badges(baseline_database):
    upgrade(directory=MIGRATIONS, revision="head")

    assert set(inspect(db.engine).get_table_names()) == baseline_database["tables"] | FEATURE_TABLES
    assert _read_legacy_rows(baseline_database["columns"]) == baseline_database["rows"]
    with db.engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == FEATURE_REVISION
        assert connection.execute(text("SELECT balance FROM accounts WHERE account_id=17")).scalar_one() == 123456789
        for table in ("financial_products", "financial_product_options"):
            assert connection.execute(text(f"SELECT sync_locked FROM {table}")).scalar_one() == 0
        badges = connection.execute(text("SELECT code, name, description, badge_type FROM badges")).mappings().all()
        assert len(badges) == 4
        assert {badge["code"] for badge in badges} == BADGE_CODES
        assert all(badge["name"] and badge["description"] and badge["badge_type"] for badge in badges)

    # An ordinary repeated deployment at head must not duplicate the seed data.
    upgrade(directory=MIGRATIONS, revision="head")
    with db.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM badges")).scalar_one() == 4


def test_upgraded_schema_matches_application_metadata(baseline_database):
    upgrade(directory=MIGRATIONS, revision="head")
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={
            "compare_type": True,
            "compare_server_default": True,
        })
        differences = compare_metadata(context, db.metadata)
    assert differences == []


def test_downgrade_removes_feature_schema_and_preserves_legacy_data(baseline_database):
    upgrade(directory=MIGRATIONS, revision="head")
    with db.engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO user_badges (user_badge_id, user_id, badge_id, acquired_at)
            SELECT 1, 41, badge_id, '2026-09-01 00:00:00'
            FROM badges WHERE code='FIRST_GOAL'
        """))
        connection.execute(text("""
            INSERT INTO posts (post_id, user_id, board_type, title, content, created_at, updated_at)
            VALUES (1, 41, 'FREE', '마이그레이션 검증', '첨부파일과 댓글이 있는 게시글',
                    '2026-09-01 00:00:00', '2026-09-01 00:00:00')
        """))
        connection.execute(text("""
            INSERT INTO comments (comment_id, post_id, user_id, content, created_at, updated_at)
            VALUES (1, 1, 41, '댓글', '2026-09-01 00:00:00', '2026-09-01 00:00:00')
        """))
        connection.execute(text("""
            INSERT INTO attachments
                (attachment_id, user_id, post_id, inquiry_id, mime_type, data, created_at)
            VALUES ('fixture-attachment', 41, 1, NULL, 'image/png', :data, '2026-09-01 00:00:00')
        """), {"data": b"migration-fixture"})

    downgrade(directory=MIGRATIONS, revision=BASELINE)

    inspector = inspect(db.engine)
    assert set(inspector.get_table_names()) == baseline_database["tables"]
    for table, columns in baseline_database["columns"].items():
        assert [column["name"] for column in inspector.get_columns(table)] == columns
    assert _read_legacy_rows(baseline_database["columns"]) == baseline_database["rows"]
    with db.engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == BASELINE


def test_mysql_offline_upgrade_uses_mediumblob_without_connecting(monkeypatch):
    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "mysql+pymysql://migration_test@127.0.0.1/migration_test",
        "JWT_SECRET_KEY": "isolated-migration-tests-secret-at-least-32-characters",
        "FEATURE_RATE_LIMIT_ENABLED": False,
    })
    output = StringIO()
    with application.app_context():
        engine = db.engine

        def reject_connection(*args, **kwargs):
            pytest.fail("Offline migration generation must not connect to a database")

        monkeypatch.setattr(engine, "connect", reject_connection)
        try:
            with redirect_stdout(output):
                upgrade(directory=MIGRATIONS, revision="head", sql=True)
        finally:
            db.session.remove()
            engine.dispose()

    sql = output.getvalue()
    assert "CREATE TABLE attachments" in sql
    assert "data MEDIUMBLOB NOT NULL" in sql
    assert "ALTER TABLE financial_products ADD COLUMN sync_locked" in sql
    assert "ALTER TABLE financial_product_options ADD COLUMN sync_locked" in sql
    assert all(code in sql for code in BADGE_CODES)
    assert FEATURE_REVISION in sql
