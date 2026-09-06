import json
import time

import click

from app.extensions import db
from app.models.features import Badge, RequestBucket

BADGES = [
    ("FIRST_GOAL", "첫 목표 달성", "저축 목표 1개 달성", "GOAL"),
    ("THREE_GOALS", "목표 달성가", "저축 목표 3개 달성", "GOAL"),
    ("SAVING_SIX_PAYMENTS", "꾸준한 저축", "동일 적금 6회 정상 납입", "SAVING"),
    ("INVESTMENT_TEN_PERCENT", "투자 수익 10%", "누적 매수 원가 대비 평가·실현 합산 투자 수익률 10% 달성", "INVESTMENT"),
]


def seed_features():
    for code, name, description, kind in BADGES:
        if not Badge.query.filter_by(code=code).first():
            db.session.add(Badge(code=code, name=name, description=description, badge_type=kind))
    db.session.commit()


def register_commands(app):
    @app.cli.command("seed-features")
    def seed_command():
        """Seed the four server-awarded badge definitions (idempotent)."""
        seed_features()
        click.echo("Feature badge definitions ready.")

    @app.cli.command("snapshots")
    def snapshots_command():
        """Record today's asset snapshots and evaluate goals/badges."""
        from app.services.portfolio_service import record_daily_snapshots
        result = record_daily_snapshots()
        click.echo(json.dumps(result))
        if result["failed"]:
            raise click.ClickException("Some snapshots failed; inspect application logs.")


def cleanup_request_buckets():
    RequestBucket.query.filter(RequestBucket.window_start < int(time.time()) // 60 - 1440).delete(synchronize_session=False)
    db.session.commit()
