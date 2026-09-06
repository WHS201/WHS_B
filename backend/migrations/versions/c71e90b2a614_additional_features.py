"""Add goals, portfolio snapshots, community, support and audit data.

Revision ID: c71e90b2a614
Revises: 89db6f2f8dd9
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "c71e90b2a614"
down_revision = "89db6f2f8dd9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('financial_products', sa.Column('sync_locked', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('financial_product_options', sa.Column('sync_locked', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.create_table('badges',
    sa.Column('badge_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('badge_type', sa.String(length=30), nullable=False),
    sa.PrimaryKeyConstraint('badge_id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('request_buckets',
    sa.Column('bucket_key', sa.String(length=120), nullable=False),
    sa.Column('window_start', sa.BigInteger(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('bucket_key')
    )
    op.create_table('asset_snapshots',
    sa.Column('snapshot_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('snapshot_date', sa.Date(), nullable=False),
    sa.Column('amounts', sa.JSON(), nullable=False),
    sa.Column('total_assets', sa.BigInteger(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('snapshot_id'),
    sa.UniqueConstraint('user_id', 'snapshot_date', name='uq_snapshot_user_date')
    )
    op.create_index(op.f('ix_asset_snapshots_user_id'), 'asset_snapshots', ['user_id'], unique=False)
    op.create_table('audit_logs',
    sa.Column('audit_log_id', sa.Integer(), nullable=False),
    sa.Column('actor_user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('before_value', sa.JSON(), nullable=True),
    sa.Column('after_value', sa.JSON(), nullable=True),
    sa.Column('reason', sa.String(length=1000), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('audit_log_id')
    )
    op.create_index(op.f('ix_audit_logs_actor_user_id'), 'audit_logs', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_table('inquiries',
    sa.Column('inquiry_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('related_ledger_transaction_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('admin_answer', sa.Text(), nullable=True),
    sa.Column('answered_at', sa.DateTime(), nullable=True),
    sa.Column('answered_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['answered_by'], ['users.user_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('inquiry_id')
    )
    op.create_index(op.f('ix_inquiries_user_id'), 'inquiries', ['user_id'], unique=False)
    op.create_table('posts',
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('board_type', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('post_id')
    )
    op.create_index(op.f('ix_posts_board_type'), 'posts', ['board_type'], unique=False)
    op.create_index(op.f('ix_posts_user_id'), 'posts', ['user_id'], unique=False)
    op.create_table('profile_visibility_settings',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('show_joined_at', sa.Boolean(), nullable=False),
    sa.Column('show_badges', sa.Boolean(), nullable=False),
    sa.Column('show_active_goals', sa.Boolean(), nullable=False),
    sa.Column('show_completed_goals', sa.Boolean(), nullable=False),
    sa.Column('show_goal_progress', sa.Boolean(), nullable=False),
    sa.Column('show_total_assets', sa.Boolean(), nullable=False),
    sa.Column('show_asset_allocation', sa.Boolean(), nullable=False),
    sa.Column('show_investment_return', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('reports',
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('reporter_user_id', sa.Integer(), nullable=False),
    sa.Column('target_type', sa.String(length=10), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('reason', sa.String(length=1000), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('resolution_reason', sa.String(length=1000), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('resolved_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['reporter_user_id'], ['users.user_id'], ),
    sa.ForeignKeyConstraint(['resolved_by'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('report_id'),
    sa.UniqueConstraint('reporter_user_id', 'target_type', 'target_id', name='uq_report_target')
    )
    op.create_table('saving_goals',
    sa.Column('goal_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('goal_name', sa.String(length=50), nullable=False),
    sa.Column('target_amount', sa.BigInteger(), nullable=False),
    sa.Column('target_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('target_amount > 0 AND target_amount <= 1000000000', name='ck_goal_amount'),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('goal_id')
    )
    op.create_index(op.f('ix_saving_goals_user_id'), 'saving_goals', ['user_id'], unique=False)
    op.create_table('user_badges',
    sa.Column('user_badge_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('badge_id', sa.Integer(), nullable=False),
    sa.Column('acquired_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['badge_id'], ['badges.badge_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('user_badge_id'),
    sa.UniqueConstraint('user_id', 'badge_id', name='uq_user_badge')
    )
    op.create_table('attachments',
    sa.Column('attachment_id', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=True),
    sa.Column('inquiry_id', sa.Integer(), nullable=True),
    sa.Column('mime_type', sa.String(length=30), nullable=False),
    sa.Column('data', sa.LargeBinary().with_variant(mysql.MEDIUMBLOB(), 'mysql'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('(post_id IS NULL AND inquiry_id IS NOT NULL) OR (post_id IS NOT NULL AND inquiry_id IS NULL)', name='ck_attachment_parent'),
    sa.ForeignKeyConstraint(['inquiry_id'], ['inquiries.inquiry_id'], ),
    sa.ForeignKeyConstraint(['post_id'], ['posts.post_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('attachment_id')
    )
    op.create_index(op.f('ix_attachments_inquiry_id'), 'attachments', ['inquiry_id'], unique=False)
    op.create_index(op.f('ix_attachments_post_id'), 'attachments', ['post_id'], unique=False)
    op.create_table('comments',
    sa.Column('comment_id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.post_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('comment_id')
    )
    op.create_index(op.f('ix_comments_post_id'), 'comments', ['post_id'], unique=False)
    op.create_table('post_reactions',
    sa.Column('reaction_id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('reaction_type', sa.String(length=10), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.post_id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    sa.PrimaryKeyConstraint('reaction_id'),
    sa.UniqueConstraint('post_id', 'user_id', name='uq_post_reaction')
    )
    badge_table = sa.table('badges', sa.column('code', sa.String), sa.column('name', sa.String),
                           sa.column('description', sa.String), sa.column('badge_type', sa.String))
    op.bulk_insert(badge_table, [
        {'code': 'FIRST_GOAL', 'name': '첫 목표 달성', 'description': '저축 목표 1개 달성', 'badge_type': 'GOAL'},
        {'code': 'THREE_GOALS', 'name': '목표 달성가', 'description': '저축 목표 3개 달성', 'badge_type': 'GOAL'},
        {'code': 'SAVING_SIX_PAYMENTS', 'name': '꾸준한 저축', 'description': '동일 적금 6회 정상 납입', 'badge_type': 'SAVING'},
        {'code': 'INVESTMENT_TEN_PERCENT', 'name': '투자 수익 10%', 'description': '누적 매수 원가 대비 평가·실현 합산 투자 수익률 10% 달성', 'badge_type': 'INVESTMENT'},
    ])


def downgrade():
    op.drop_column('financial_product_options', 'sync_locked')
    op.drop_column('financial_products', 'sync_locked')
    op.drop_table('post_reactions')
    op.drop_index(op.f('ix_comments_post_id'), table_name='comments')
    op.drop_table('comments')
    op.drop_index(op.f('ix_attachments_post_id'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_inquiry_id'), table_name='attachments')
    op.drop_table('attachments')
    op.drop_table('user_badges')
    op.drop_index(op.f('ix_saving_goals_user_id'), table_name='saving_goals')
    op.drop_table('saving_goals')
    op.drop_table('reports')
    op.drop_table('profile_visibility_settings')
    op.drop_index(op.f('ix_posts_user_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_board_type'), table_name='posts')
    op.drop_table('posts')
    op.drop_index(op.f('ix_inquiries_user_id'), table_name='inquiries')
    op.drop_table('inquiries')
    op.drop_index(op.f('ix_audit_logs_created_at'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_user_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_asset_snapshots_user_id'), table_name='asset_snapshots')
    op.drop_table('asset_snapshots')
    op.drop_table('request_buckets')
    op.drop_table('badges')
