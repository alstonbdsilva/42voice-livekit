"""create platform model configurations and agent assignment

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-09-19 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3c4d5e6f7a8b'
down_revision: Union[str, Sequence[str], None] = '2b3c4d5e6f7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create platform_model_configurations table
    op.create_table(
        'platform_model_configurations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        
        # STT Configuration
        sa.Column('stt_provider', sa.String(length=50), nullable=False, server_default='deepgram'),
        sa.Column('stt_model', sa.String(length=100), nullable=True),
        sa.Column('stt_credential_source', sa.String(length=50), nullable=False, server_default='platform'),
        sa.Column('stt_credential_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('stt_options', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text('\'{}\'::jsonb')),
        
        # LLM Configuration
        sa.Column('llm_provider', sa.String(length=50), nullable=False, server_default='openai'),
        sa.Column('llm_model', sa.String(length=100), nullable=True),
        sa.Column('llm_credential_source', sa.String(length=50), nullable=False, server_default='platform'),
        sa.Column('llm_credential_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('llm_options', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text('\'{}\'::jsonb')),
        
        # TTS Configuration
        sa.Column('tts_provider', sa.String(length=50), nullable=False, server_default='openai'),
        sa.Column('tts_model', sa.String(length=100), nullable=True),
        sa.Column('tts_voice', sa.String(length=100), nullable=True),
        sa.Column('tts_credential_source', sa.String(length=50), nullable=False, server_default='platform'),
        sa.Column('tts_credential_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tts_options', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text('\'{}\'::jsonb')),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['stt_credential_id'], ['external_credentials.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['llm_credential_id'], ['external_credentials.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tts_credential_id'], ['external_credentials.id'], ondelete='SET NULL')
    )
    op.create_index('idx_platform_model_configs_client', 'platform_model_configurations', ['client_id'])
    op.create_index('idx_platform_model_configs_user', 'platform_model_configurations', ['user_id'])
    op.create_index('idx_platform_model_configs_status', 'platform_model_configurations', ['status'])

    # 2. Add platform_model_configuration_id column to agents table
    op.add_column(
        'agents',
        sa.Column('platform_model_configuration_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'agents_platform_model_configuration_id_fkey',
        'agents',
        'platform_model_configurations',
        ['platform_model_configuration_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('idx_agents_platform_model_configuration', 'agents', ['platform_model_configuration_id'])


def downgrade() -> None:
    # 1. Remove column from agents
    op.drop_constraint('agents_platform_model_configuration_id_fkey', 'agents', type_='foreignkey')
    op.drop_index('idx_agents_platform_model_configuration', table_name='agents')
    op.drop_column('agents', 'platform_model_configuration_id')

    # 2. Drop platform_model_configurations table
    op.drop_index('idx_platform_model_configs_status', table_name='platform_model_configurations')
    op.drop_index('idx_platform_model_configs_user', table_name='platform_model_configurations')
    op.drop_index('idx_platform_model_configs_client', table_name='platform_model_configurations')
    op.drop_table('platform_model_configurations')
