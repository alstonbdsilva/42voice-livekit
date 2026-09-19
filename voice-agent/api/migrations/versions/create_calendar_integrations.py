"""create calendar integrations table

Revision ID: 1a2b3c4d5e6f
Revises: 
Create Date: 2026-07-22 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create table
    op.create_table(
        'calendar_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('event_type_url', sa.String(length=512), nullable=True),
        sa.Column('provider_user_id', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('client_id', 'provider', name='unique_client_provider'),
        sa.UniqueConstraint('user_id', 'provider', name='unique_user_provider'),
        sa.CheckConstraint('client_id IS NOT NULL OR user_id IS NOT NULL', name='check_calendar_owner_not_null')
    )
    
    # 2. Add indexing
    op.create_index(
        'idx_calendar_integrations_client',
        'calendar_integrations',
        ['client_id', 'provider']
    )
    op.create_index(
        'idx_calendar_integrations_user',
        'calendar_integrations',
        ['user_id', 'provider']
    )
    op.create_index(
        'idx_calendar_integrations_active',
        'calendar_integrations',
        ['is_active']
    )


def downgrade() -> None:
    op.drop_index('idx_calendar_integrations_active', table_name='calendar_integrations')
    op.drop_index('idx_calendar_integrations_user', table_name='calendar_integrations')
    op.drop_index('idx_calendar_integrations_client', table_name='calendar_integrations')
    op.drop_table('calendar_integrations')
