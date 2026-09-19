"""create workflow platform tables and agent pinning

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-09-19 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2b3c4d5e6f7a'
down_revision = '1a2b3c4d5e6f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create workflows table
    op.create_table(
        'workflows',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('idx_workflows_client', 'workflows', ['client_id'])
    op.create_index('idx_workflows_user', 'workflows', ['user_id'])
    op.create_index('idx_workflows_status', 'workflows', ['status'])

    # 2. Create workflow_versions table
    op.create_table(
        'workflow_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('lifecycle_status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text('\'{"nodes": [], "edges": []}\'::jsonb')),
        sa.Column('ui_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text('\'{}\'::jsonb')),
        sa.Column('schema_version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('engine_version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('validation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text('\'{}\'::jsonb')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('workflow_id', 'version_number', name='unique_workflow_version_number')
    )
    op.create_index('idx_workflow_versions_workflow', 'workflow_versions', ['workflow_id'])
    op.create_index('idx_workflow_versions_status', 'workflow_versions', ['lifecycle_status'])

    # 3. Add published_workflow_version_id column to agents
    op.add_column(
        'agents',
        sa.Column('published_workflow_version_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_agents_published_workflow_version',
        'agents',
        'workflow_versions',
        ['published_workflow_version_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('idx_agents_published_workflow_version', 'agents', ['published_workflow_version_id'])

    # 4. Create workflow_runs table
    op.create_table(
        'workflow_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('run_id', sa.String(length=255), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('workflow_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('room_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_category', sa.String(length=100), nullable=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recording_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('safe_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text('\'{}\'::jsonb')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', name='unique_workflow_run_id'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workflow_version_id'], ['workflow_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recording_id'], ['recordings.id'], ondelete='SET NULL')
    )
    op.create_index('idx_workflow_runs_run_id', 'workflow_runs', ['run_id'])
    op.create_index('idx_workflow_runs_agent', 'workflow_runs', ['agent_id'])
    op.create_index('idx_workflow_runs_version', 'workflow_runs', ['workflow_version_id'])
    op.create_index('idx_workflow_runs_status', 'workflow_runs', ['status'])

    # 5. Create workflow_run_events table
    op.create_table(
        'workflow_run_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('run_id', sa.String(length=255), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('node_id', sa.String(length=255), nullable=True),
        sa.Column('edge_id', sa.String(length=255), nullable=True),
        sa.Column('safe_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text('\'{}\'::jsonb')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['workflow_runs.run_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('run_id', 'sequence_number', name='unique_workflow_run_event_seq')
    )
    op.create_index('idx_workflow_run_events_run', 'workflow_run_events', ['run_id'])


def downgrade() -> None:
    # 1. Drop workflow_run_events
    op.drop_index('idx_workflow_run_events_run', table_name='workflow_run_events')
    op.drop_table('workflow_run_events')

    # 2. Drop workflow_runs
    op.drop_index('idx_workflow_runs_status', table_name='workflow_runs')
    op.drop_index('idx_workflow_runs_version', table_name='workflow_runs')
    op.drop_index('idx_workflow_runs_agent', table_name='workflow_runs')
    op.drop_index('idx_workflow_runs_run_id', table_name='workflow_runs')
    op.drop_table('workflow_runs')

    # 3. Drop agents.published_workflow_version_id
    op.drop_index('idx_agents_published_workflow_version', table_name='agents')
    op.drop_constraint('fk_agents_published_workflow_version', 'agents', type_='foreignkey')
    op.drop_column('agents', 'published_workflow_version_id')

    # 4. Drop workflow_versions
    op.drop_index('idx_workflow_versions_status', table_name='workflow_versions')
    op.drop_index('idx_workflow_versions_workflow', table_name='workflow_versions')
    op.drop_table('workflow_versions')

    # 5. Drop workflows
    op.drop_index('idx_workflows_status', table_name='workflows')
    op.drop_index('idx_workflows_user', table_name='workflows')
    op.drop_index('idx_workflows_client', table_name='workflows')
    op.drop_table('workflows')
