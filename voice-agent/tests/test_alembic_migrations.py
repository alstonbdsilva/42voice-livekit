"""
Tests for Alembic Migrations and Schema Consistency.
Validates:
1. Empty Postgres database -> alembic upgrade head succeeds
2. calendar_integrations schema matches production specification
3. workflow platform tables (workflows, workflow_versions, workflow_runs, workflow_run_events) match specification
4. agents.published_workflow_version_id column and foreign key constraint
5. Alembic downgrade and re-upgrade paths
6. Startup / init_db does not mutate or compete with Alembic in production mode
"""

import unittest
import asyncio
import os
import subprocess
import asyncpg
from alembic.config import Config
from alembic import command


TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/testdb")
TEST_DB_HOST = "localhost"
TEST_DB_PORT = 54329
TEST_DB_USER = "postgres"
TEST_DB_PASSWORD = "postgres"
TEST_DB_NAME = "testdb"


class TestAlembicMigrations(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Create base parent tables required for foreign keys (clients, users, agents, conversations, recordings)
        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=TEST_DB_NAME,
        )
        try:
            # Clean database schema completely
            await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            
            # Create base tables that migrations reference via foreign keys
            await conn.execute("""
                CREATE TABLE clients (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE users (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE agents (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE conversations (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    customer_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE recordings (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    filename VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
        finally:
            await conn.close()

    def _get_alembic_config(self) -> Config:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ini_path = os.path.join(here, "alembic.ini")
        cfg = Config(ini_path)
        cfg.set_main_option("sqlalchemy.url", f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}")
        return cfg

    async def test_01_empty_postgres_alembic_upgrade_head(self):
        """Test that running alembic upgrade head against a clean DB succeeds."""
        cfg = self._get_alembic_config()
        # Set environment variable for env.py
        os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"
        
        # Upgrade to head
        command.upgrade(cfg, "head")

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=TEST_DB_NAME,
        )
        try:
            # Check alembic_version contains head
            row = await conn.fetchrow("SELECT version_num FROM alembic_version;")
            self.assertIsNotNone(row)
            self.assertEqual(row["version_num"], "2b3c4d5e6f7a")

            # Check tables exist
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
            )
            table_names = {t["table_name"] for t in tables}
            self.assertIn("calendar_integrations", table_names)
            self.assertIn("workflows", table_names)
            self.assertIn("workflow_versions", table_names)
            self.assertIn("workflow_runs", table_names)
            self.assertIn("workflow_run_events", table_names)
        finally:
            await conn.close()

    async def test_02_calendar_integrations_schema_fidelity(self):
        """Test that calendar_integrations schema matches production specification."""
        cfg = self._get_alembic_config()
        os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"
        command.upgrade(cfg, "head")

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=TEST_DB_NAME,
        )
        try:
            # Columns
            cols = await conn.fetch(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'calendar_integrations';"
            )
            col_map = {c["column_name"]: c for c in cols}
            expected_cols = [
                "id", "client_id", "user_id", "provider", "access_token",
                "refresh_token", "event_type_url", "provider_user_id",
                "is_active", "created_at", "updated_at"
            ]
            for col in expected_cols:
                self.assertIn(col, col_map, f"Missing column {col} in calendar_integrations")

            # Constraints (check constraint and unique constraints)
            constraints = await conn.fetch("""
                SELECT tc.constraint_type, tc.constraint_name
                FROM information_schema.table_constraints tc
                WHERE tc.table_name = 'calendar_integrations';
            """)
            c_types = {c["constraint_type"] for c in constraints}
            self.assertIn("PRIMARY KEY", c_types)
            self.assertIn("FOREIGN KEY", c_types)
            self.assertIn("UNIQUE", c_types)
            self.assertIn("CHECK", c_types)

            # Indexes
            indexes = await conn.fetch("""
                SELECT indexname FROM pg_indexes WHERE tablename = 'calendar_integrations';
            """)
            idx_names = {i["indexname"] for i in indexes}
            self.assertIn("idx_calendar_integrations_client", idx_names)
            self.assertIn("idx_calendar_integrations_user", idx_names)
            self.assertIn("idx_calendar_integrations_active", idx_names)
        finally:
            await conn.close()

    async def test_03_workflow_platform_schema_fidelity(self):
        """Test that workflow platform tables and agent pinning match specification."""
        cfg = self._get_alembic_config()
        os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"
        command.upgrade(cfg, "head")

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=TEST_DB_NAME,
        )
        try:
            # 1. workflows
            wf_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'workflows';")
            wf_col_names = {c["column_name"] for c in wf_cols}
            self.assertTrue({"id", "client_id", "user_id", "name", "description", "status", "created_at", "updated_at"}.issubset(wf_col_names))

            # 2. workflow_versions (unique constraint on workflow_id, version_number)
            wv_constraints = await conn.fetch("""
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'workflow_versions' AND constraint_type = 'UNIQUE';
            """)
            self.assertTrue(len(wv_constraints) >= 1)

            # 3. agents.published_workflow_version_id column & FK
            agent_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'agents';")
            agent_col_names = {c["column_name"] for c in agent_cols}
            self.assertIn("published_workflow_version_id", agent_col_names)

            agent_fks = await conn.fetch("""
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'agents' AND constraint_type = 'FOREIGN KEY';
            """)
            agent_fk_names = {c["constraint_name"] for c in agent_fks}
            self.assertIn("agents_published_workflow_version_id_fkey", agent_fk_names)

            # 4. workflow_runs unique run_id
            wr_unique = await conn.fetch("""
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'workflow_runs' AND constraint_type = 'UNIQUE';
            """)
            self.assertTrue(len(wr_unique) >= 1)

            # 5. workflow_run_events unique (run_id, sequence_number)
            wre_unique = await conn.fetch("""
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'workflow_run_events' AND constraint_type = 'UNIQUE';
            """)
            self.assertTrue(len(wre_unique) >= 1)
        finally:
            await conn.close()

    async def test_04_downgrade_and_reupgrade(self):
        """Test that alembic downgrade and re-upgrade work cleanly."""
        cfg = self._get_alembic_config()
        os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"
        
        # Upgrade to head
        command.upgrade(cfg, "head")

        # Downgrade 1 revision (to 1a2b3c4d5e6f)
        command.downgrade(cfg, "-1")

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=TEST_DB_NAME,
        )
        try:
            row = await conn.fetchrow("SELECT version_num FROM alembic_version;")
            self.assertEqual(row["version_num"], "1a2b3c4d5e6f")

            # Check workflow tables were dropped
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
            )
            table_names = {t["table_name"] for t in tables}
            self.assertNotIn("workflows", table_names)
            self.assertNotIn("workflow_versions", table_names)
            self.assertIn("calendar_integrations", table_names)
        finally:
            await conn.close()

        # Downgrade to base
        command.downgrade(cfg, "base")

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=TEST_DB_NAME,
        )
        try:
            # Check calendar_integrations was also dropped
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
            )
            table_names = {t["table_name"] for t in tables}
            self.assertNotIn("calendar_integrations", table_names)
        finally:
            await conn.close()

        # Re-upgrade to head
        command.upgrade(cfg, "head")
        
        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=TEST_DB_NAME,
        )
        try:
            row = await conn.fetchrow("SELECT version_num FROM alembic_version;")
            self.assertEqual(row["version_num"], "2b3c4d5e6f7a")
        finally:
            await conn.close()

    async def test_05_init_db_in_production_does_not_create_workflow_tables(self):
        """Test that init_db with ENVIRONMENT=production does not silently create workflow tables."""
        # Ensure ENVIRONMENT is set to production and AUTO_BOOTSTRAP_DB is false
        os.environ["ENVIRONMENT"] = "production"
        os.environ["AUTO_BOOTSTRAP_DB"] = "false"
        
        from api.init_db import init_db
        from config import get_settings
        
        # Point settings to test DB
        os.environ["PGHOST"] = TEST_DB_HOST
        os.environ["PGPORT"] = str(TEST_DB_PORT)
        os.environ["PGDATABASE"] = TEST_DB_NAME
        os.environ["PGUSER"] = TEST_DB_USER
        os.environ["PGPASSWORD"] = TEST_DB_PASSWORD

        # Run init_db
        try:
            await init_db()
        except Exception:
            pass

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=TEST_DB_NAME,
        )
        try:
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
            )
            table_names = {t["table_name"] for t in tables}
            # Workflow tables must NOT have been created by init_db
            self.assertNotIn("workflows", table_names)
            self.assertNotIn("workflow_versions", table_names)
            self.assertNotIn("workflow_runs", table_names)
        finally:
            await conn.close()


if __name__ == "__main__":
    unittest.main()
