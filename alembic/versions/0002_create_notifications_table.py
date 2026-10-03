"""Create notifications table

Revision ID: 0002_create_notifications_table
Revises: 0001_create_users_table
Create Date: 2026-10-03 11:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_create_notifications_table'
down_revision: Union[str, None] = '0001_create_users_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

notification_type_enum = sa.Enum(
    'ORDER_CONFIRMED', 'PASSWORD_RESET', 'WELCOME', 'SECURITY_ALERT', 'GENERAL',
    name='notification_type_enum'
)
notification_channel_enum = sa.Enum(
    'EMAIL', 'IN_APP',
    name='notification_channel_enum'
)
notification_status_enum = sa.Enum(
    'PENDING', 'PROCESSING', 'SENT', 'FAILED',
    name='notification_status_enum'
)

def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Uuid(as_uuid=True), nullable=False),
        sa.Column('type', notification_type_enum, nullable=False),
        sa.Column('channel', notification_channel_enum, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', notification_status_enum, server_default='PENDING', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_status'), 'notifications', ['status'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_idempotency_key'), 'notifications', ['idempotency_key'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_idempotency_key'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_status'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')

    notification_status_enum.drop(op.get_bind(), checkfirst=True)
    notification_channel_enum.drop(op.get_bind(), checkfirst=True)
    notification_type_enum.drop(op.get_bind(), checkfirst=True)
