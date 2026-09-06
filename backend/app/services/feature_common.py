from datetime import date, datetime
from decimal import Decimal
from functools import wraps
import time

from flask import current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.errors.exceptions import BusinessException
from app.models.user import User
from app.models.features import RequestBucket


def fail(code, message, status=400):
    raise BusinessException(code=code, message=message, status_code=status)


def user_id():
    return int(get_jwt_identity())


def current_user(lock=False):
    query = User.query.filter_by(user_id=user_id())
    user = (query.with_for_update() if lock else query).first()
    if user is None or user.status != "ACTIVE":
        fail("FORBIDDEN", "이용할 수 없는 계정입니다.", 403)
    return user


def require_admin():
    user = current_user()
    if user.role != "ADMIN":
        fail("FORBIDDEN", "관리자 권한이 필요합니다.", 403)
    return user


def get_row(model, identifier, owner=None, lock=False):
    key = list(model.__table__.primary_key.columns)[0].name
    query = model.query.filter(getattr(model, key) == identifier)
    if owner is not None:
        query = query.filter_by(user_id=owner)
    row = (query.with_for_update() if lock else query).first()
    if row is None:
        fail("NOT_FOUND", "항목을 찾을 수 없습니다.", 404)
    return row


def serialize(row, exclude=()):
    def value(item):
        if isinstance(item, datetime):
            return item.isoformat() + "Z"
        if isinstance(item, date):
            return item.isoformat()
        if isinstance(item, Decimal):
            return str(item)
        return item
    return {c.name: value(getattr(row, c.name)) for c in row.__table__.columns if c.name not in exclude}


def page(query, serializer=serialize):
    try:
        number = int(request.args.get("page", "1"))
        size = int(request.args.get("size", "20"))
    except ValueError:
        fail("INVALID_REQUEST", "page와 size는 정수여야 합니다.")
    if not 1 <= number <= 10000 or not 1 <= size <= 100:
        fail("INVALID_REQUEST", "page는 1~10000, size는 1~100 범위입니다.")
    return {"items": [serializer(row) for row in query.offset((number - 1) * size).limit(size)],
            "page": number, "size": size, "total": query.order_by(None).count()}


def rate_limit():
    """Database-backed fixed window shared by workers. Commit before domain work."""
    if not current_app.config.get("FEATURE_RATE_LIMIT_ENABLED", True):
        return
    key = f"{user_id()}:{request.endpoint}"
    now = int(time.time()) // 60
    limit = current_app.config["FEATURE_WRITE_REQUESTS_PER_MINUTE"] if request.method != "GET" else current_app.config["FEATURE_READ_REQUESTS_PER_MINUTE"]
    bucket = RequestBucket.query.filter_by(bucket_key=key).with_for_update().first()
    if bucket is None:
        try:
            with db.session.begin_nested():
                bucket = RequestBucket(bucket_key=key, window_start=now, count=0)
                db.session.add(bucket)
                db.session.flush()
        except IntegrityError:
            bucket = RequestBucket.query.filter_by(bucket_key=key).with_for_update().one()
    if bucket.window_start != now:
        bucket.window_start, bucket.count = now, 0
    if bucket.count >= limit:
        fail("RATE_LIMITED", "잠시 후 다시 요청해 주세요.", 429)
    bucket.count += 1
    db.session.commit()


def endpoint(admin=False):
    def decorate(fn):
        @wraps(fn)
        @jwt_required()
        def wrapped(*args, **kwargs):
            current_user()
            if admin:
                require_admin()
            rate_limit()
            try:
                return fn(*args, **kwargs)
            except IntegrityError:
                db.session.rollback()
                fail("CONFLICT", "중복 요청 또는 데이터 충돌입니다.", 409)
            except Exception:
                db.session.rollback()
                raise
        return wrapped
    return decorate
