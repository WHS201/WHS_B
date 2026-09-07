from datetime import datetime
from io import BytesIO
from pathlib import PurePath
import uuid
import warnings

from PIL import Image, UnidentifiedImageError
from flask import request
from sqlalchemy import func

from app.extensions import db
from app.models.features import (
    Post,
    Comment,
    PostReaction,
    Report,
    Inquiry,
    Attachment,
)
from app.models.deposits_savings import LedgerTransaction
from app.services.feature_common import fail, get_row, serialize, page
from app.services.audit_service import audit


def live_post(post_id, owner=None, lock=False):
    row = get_row(Post, post_id, owner=owner, lock=lock)

    if row.deleted_at:
        fail(
            "NOT_FOUND",
            "게시글을 찾을 수 없습니다.",
            404,
        )

    return row


def live_comment(comment_id, owner=None, lock=False):
    row = get_row(
        Comment,
        comment_id,
        owner=owner,
        lock=lock,
    )

    live_post(row.post_id)

    if row.deleted_at:
        fail(
            "NOT_FOUND",
            "댓글을 찾을 수 없습니다.",
            404,
        )

    return row


def post_data(post):
    data = serialize(
        post,
        exclude=("deleted_at",),
    )

    data["reactions"] = {
        "LIKE": 0,
        "DISLIKE": 0,
    }

    for kind, count in (
        db.session.query(
            PostReaction.reaction_type,
            func.count(),
        )
        .filter_by(post_id=post.post_id)
        .group_by(PostReaction.reaction_type)
    ):
        data["reactions"][kind] = count

    data["attachments"] = attachment_list(
        post_id=post.post_id,
    )

    return data


def attachment_list(**parent):
    query = (
        Attachment.query
        .with_entities(Attachment.attachment_id)
        .filter_by(**parent)
    )

    return [
        {
            "attachment_id": a.attachment_id,
            "url": f"/api/attachments/{a.attachment_id}",
        }
        for a in query.order_by(
            Attachment.created_at,
            Attachment.attachment_id,
        )
    ]


def inquiry_data(row):
    return {
        **serialize(row),
        "attachments": attachment_list(
            inquiry_id=row.inquiry_id,
        ),
    }


def list_posts():
    query = Post.query.filter_by(
        deleted_at=None,
    )

    board = request.args.get("board_type")

    if board:
        if board not in {
            "FREE",
            "KR_STOCK",
            "US_STOCK",
            "DEPOSIT_SAVING",
        }:
            fail(
                "INVALID_REQUEST",
                "지원하지 않는 게시판입니다.",
            )

        query = query.filter_by(
            board_type=board,
        )

    search = request.args.get(
        "q",
        "",
    ).strip()

    if len(search) > 100:
        fail(
            "INVALID_REQUEST",
            "검색어는 100자 이하입니다.",
        )

    if search:
        query = query.filter(
            db.or_(
                Post.title.contains(
                    search,
                    autoescape=True,
                ),
                Post.content.contains(
                    search,
                    autoescape=True,
                ),
            )
        )

    sorting = request.args.get(
        "sort",
        "latest",
    )

    if sorting not in {
        "latest",
        "likes",
        "dislikes",
    }:
        fail(
            "INVALID_REQUEST",
            "지원하지 않는 정렬입니다.",
        )

    if sorting != "latest":
        kind = (
            "LIKE"
            if sorting == "likes"
            else "DISLIKE"
        )

        counts = (
            db.session.query(
                PostReaction.post_id,
                func.count().label("count"),
            )
            .filter_by(
                reaction_type=kind,
            )
            .group_by(
                PostReaction.post_id,
            )
            .subquery()
        )

        query = (
            query
            .outerjoin(
                counts,
                counts.c.post_id == Post.post_id,
            )
            .order_by(
                func.coalesce(
                    counts.c.count,
                    0,
                ).desc()
            )
        )

    return page(
        query.order_by(
            Post.post_id.desc(),
        ),
        post_data,
    )


def save_post(
    user_id,
    payload,
    post_id=None,
):
    row = (
        live_post(
            post_id,
            owner=user_id,
            lock=True,
        )
        if post_id
        else Post(user_id=user_id)
    )

    for key, value in payload.items():
        setattr(
            row,
            key,
            value,
        )

    db.session.add(row)
    db.session.flush()

    audit(
        "POST_UPDATE"
        if post_id
        else "POST_CREATE",
        "posts",
        row.post_id,
    )

    db.session.commit()

    return post_data(row)


def save_comment(
    user_id,
    payload,
    post_id=None,
    comment_id=None,
):
    if comment_id:
        row = live_comment(
            comment_id,
            owner=user_id,
            lock=True,
        )
    else:
        live_post(
            post_id,
            lock=True,
        )

        row = Comment(
            user_id=user_id,
            post_id=post_id,
        )

    row.content = payload["content"]

    db.session.add(row)
    db.session.flush()

    audit(
        "COMMENT_UPDATE"
        if comment_id
        else "COMMENT_CREATE",
        "comments",
        row.comment_id,
    )

    db.session.commit()

    return serialize(
        row,
        exclude=("deleted_at",),
    )


def delete_content(
    kind,
    identifier,
    owner=None,
    reason=None,
):
    row = (
        live_post(
            identifier,
            owner,
            True,
        )
        if kind == "POST"
        else live_comment(
            identifier,
            owner,
            True,
        )
    )

    row.deleted_at = datetime.utcnow()

    if kind == "POST":
        Attachment.query.filter_by(
            post_id=identifier,
        ).delete(
            synchronize_session=False,
        )

    audit(
        "CONTENT_DELETE",
        row.__tablename__,
        identifier,
        reason=reason,
    )

    db.session.commit()


def react(
    user_id,
    post_id,
    kind,
):
    live_post(
        post_id,
        lock=True,
    )

    row = PostReaction.query.filter_by(
        user_id=user_id,
        post_id=post_id,
    ).first()

    if kind == "NONE":
        if row:
            db.session.delete(row)

    elif row:
        row.reaction_type = kind

    else:
        db.session.add(
            PostReaction(
                user_id=user_id,
                post_id=post_id,
                reaction_type=kind,
            )
        )

    db.session.commit()

    return {
        "reaction_type": kind,
    }


def create_report(
    user_id,
    payload,
):
    if payload["target_type"] == "POST":
        live_post(
            payload["target_id"],
            lock=True,
        )
    else:
        live_comment(
            payload["target_id"],
            lock=True,
        )

    existing = Report.query.filter_by(
        reporter_user_id=user_id,
        target_type=payload["target_type"],
        target_id=payload["target_id"],
    ).first()

    if existing:
        fail(
            "ALREADY_REPORTED",
            "이미 신고가 접수되었습니다.",
            409,
        )

    row = Report(
        reporter_user_id=user_id,
        **payload,
    )

    db.session.add(row)
    db.session.flush()

    audit(
        "REPORT_CREATE",
        "reports",
        row.report_id,
    )

    db.session.commit()

    return serialize(row)


def create_inquiry(
    user_id,
    payload,
):
    # Serialize creation against reset,
    # which removes financial inquiry data.
    from app.services.account_service import (
        get_account_by_user_id,
    )

    get_account_by_user_id(user_id)

    ledger_id = payload.get(
        "related_ledger_transaction_id",
    )

    if ledger_id:
        get_row(
            LedgerTransaction,
            ledger_id,
            owner=user_id,
        )

    row = Inquiry(
        user_id=user_id,
        **payload,
    )

    db.session.add(row)
    db.session.flush()

    audit(
        "INQUIRY_CREATE",
        "inquiries",
        row.inquiry_id,
    )

    db.session.commit()

    return inquiry_data(row)


def upload(
    user_id,
    kind,
    parent_id,
    files,
):
    if kind == "POST":
        live_post(
            parent_id,
            owner=user_id,
            lock=True,
        )

        parent = {
            "post_id": parent_id,
        }

    else:
        get_row(
            Inquiry,
            parent_id,
            owner=user_id,
            lock=True,
        )

        parent = {
            "inquiry_id": parent_id,
        }

    if (
        not files
        or len(files)
        + Attachment.query.filter_by(
            **parent
        ).count()
        > 5
    ):
        fail(
            "IMAGE_LIMIT",
            "이미지는 1~5개까지 첨부할 수 있습니다.",
            422,
        )

    allowed = {
        ".png": (
            "PNG",
            "image/png",
        ),
        ".jpg": (
            "JPEG",
            "image/jpeg",
        ),
        ".jpeg": (
            "JPEG",
            "image/jpeg",
        ),
        ".webp": (
            "WEBP",
            "image/webp",
        ),
    }

    for file in files:
        extension = PurePath(
            file.filename or "",
        ).suffix.lower()

        if (
            extension not in allowed
            or file.mimetype
            != allowed[extension][1]
        ):
            fail(
                "INVALID_IMAGE",
                "PNG, JPEG, WebP 이미지만 허용합니다.",
                422,
            )

        raw = file.read(
            10 * 1024 * 1024 + 1
        )

        if len(raw) > 10 * 1024 * 1024:
            fail(
                "IMAGE_TOO_LARGE",
                "이미지는 파일당 10MB 이하입니다.",
                413,
            )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter(
                    "error",
                    Image.DecompressionBombWarning,
                )

                with Image.open(
                    BytesIO(raw)
                ) as image:
                    if (
                        image.format
                        != allowed[extension][0]
                        or image.width
                        * image.height
                        > 16000000
                    ):
                        fail(
                            "INVALID_IMAGE",
                            "이미지 형식 또는 해상도가 허용 범위를 벗어납니다.",
                            422,
                        )

                    image.load()

                    clean = image.convert(
                        "RGB"
                        if image.format == "JPEG"
                        else "RGBA"
                    )

                    output = BytesIO()

                    clean.save(
                        output,
                        format=allowed[extension][0],
                    )

                    encoded = output.getvalue()

                    if (
                        len(encoded)
                        > 10 * 1024 * 1024
                    ):
                        fail(
                            "IMAGE_TOO_LARGE",
                            "변환된 이미지는 10MB 이하이어야 합니다.",
                            413,
                        )

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ):
            fail(
                "INVALID_IMAGE",
                "이미지를 읽을 수 없습니다.",
                422,
            )

        db.session.add(
            Attachment(
                attachment_id=uuid.uuid4().hex,
                user_id=user_id,
                mime_type=allowed[extension][1],
                data=encoded,
                **parent,
            )
        )

    audit(
        "IMAGE_UPLOAD",
        "posts"
        if kind == "POST"
        else "inquiries",
        parent_id,
    )

    db.session.commit()

    return attachment_list(
        **parent
    )