"""
Asynchronous PostgreSQL database connector using asyncpg.
"""

import logging
import asyncpg
from typing import List, Dict, Any, Optional
from config import get_settings

logger = logging.getLogger("voice-agent.api.database")

pool: Optional[asyncpg.Pool] = None


async def init_pool() -> None:
    """Initialize the PostgreSQL connection pool."""
    global pool
    if pool is not None:
        return
        
    settings = get_settings()
    logger.info(f"Connecting to PostgreSQL database at {settings.pghost}:{settings.pgport}...")
    
    try:
        # Construct SSL context if necessary
        ssl_ctx = None
        if "supabase.co" in settings.pghost or settings.log_level != "DEBUG":
            import ssl
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            
        pool = await asyncpg.create_pool(
            host=settings.pghost,
            port=settings.pgport,
            database=settings.pgdatabase,
            user=settings.pguser,
            password=settings.pgpassword,
            min_size=2,
            max_size=settings.pgmax_connections,
            max_inactive_connection_lifetime=30.0,
            command_timeout=10.0,
            ssl=ssl_ctx
        )
        logger.info("PostgreSQL connection pool initialized successfully")
        
        # Self-healing migration for phone_numbers table
        try:
            logger.info("Verifying phone_numbers table exists...")
            async with pool.acquire() as conn:
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS phone_numbers (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    number VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(255),
                    provider VARCHAR(50) NOT NULL,
                    monthly_cost NUMERIC(12,2) NOT NULL DEFAULT 0.00,
                    setup_cost NUMERIC(12,2) NOT NULL DEFAULT 0.00,
                    status VARCHAR(50) NOT NULL DEFAULT 'available',
                    capabilities JSONB NOT NULL DEFAULT '{"voice": true, "sms": true}'::jsonb,
                    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
                    reseller_id UUID REFERENCES resellers(id) ON DELETE SET NULL,
                    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
                    sip_config JSONB,
                    lk_sip_trunk_id VARCHAR(255),
                    lk_sip_dispatch_rule_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_phone_numbers_number ON phone_numbers(number);
                CREATE INDEX IF NOT EXISTS idx_phone_numbers_client ON phone_numbers(client_id);
                CREATE INDEX IF NOT EXISTS idx_phone_numbers_agent ON phone_numbers(agent_id);
                """)
            logger.info("Verified phone_numbers table and indexes.")
        except Exception as e:
            logger.warning(f"Could not verify phone_numbers table: {e}")

        # Self-healing migration for agents table columns
        try:
            logger.info("Verifying agents table columns exist...")
            async with pool.acquire() as conn:
                await conn.execute("""
                ALTER TABLE agents ADD COLUMN IF NOT EXISTS voice_name VARCHAR(50) DEFAULT 'aria';
                ALTER TABLE agents ADD COLUMN IF NOT EXISTS voice_gender VARCHAR(20) DEFAULT 'female';
                ALTER TABLE agents ADD COLUMN IF NOT EXISTS guardrails JSONB DEFAULT '{}'::jsonb;
                ALTER TABLE agents ADD COLUMN IF NOT EXISTS custom_guardrails TEXT;
                ALTER TABLE agents ADD COLUMN IF NOT EXISTS knowledge_items JSONB DEFAULT '[]'::jsonb;
                """)
            logger.info("Verified agents table columns.")
        except Exception as e:
            logger.warning(f"Could not verify agents columns: {e}")

        # Self-healing migration for tools table
        try:
            logger.info("Verifying tools table exists...")
            async with pool.acquire() as conn:
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS tools (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    tool_uuid UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    category VARCHAR(50) NOT NULL DEFAULT 'http_api',
                    icon VARCHAR(50) DEFAULT 'globe',
                    icon_color VARCHAR(7) DEFAULT '#3B82F6',
                    status VARCHAR(50) NOT NULL DEFAULT 'active',
                    definition JSONB NOT NULL DEFAULT '{}'::jsonb,
                    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_tools_user ON tools(user_id);
                CREATE INDEX IF NOT EXISTS idx_tools_client ON tools(client_id);
                CREATE INDEX IF NOT EXISTS idx_tools_category ON tools(category);
                CREATE INDEX IF NOT EXISTS idx_tools_status ON tools(status);
                """)
            logger.info("Verified tools table and indexes.")
        except Exception as e:
            logger.warning(f"Could not verify tools table: {e}")

        # Self-healing migration for external_credentials table
        try:
            logger.info("Verifying external_credentials table exists...")
            async with pool.acquire() as conn:
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS external_credentials (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    credential_uuid UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
                    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    credential_type VARCHAR(50) NOT NULL DEFAULT 'none',
                    credential_data JSONB NOT NULL DEFAULT '{}'::jsonb,
                    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    UNIQUE (client_id, name)
                );
                CREATE INDEX IF NOT EXISTS idx_external_credentials_client ON external_credentials(client_id);
                CREATE INDEX IF NOT EXISTS idx_external_credentials_uuid ON external_credentials(credential_uuid);
                """)
            logger.info("Verified external_credentials table and indexes.")
        except Exception as e:
            logger.warning(f"Could not verify external_credentials table: {e}")
    except Exception as e:
        logger.critical(f"Failed to initialize PostgreSQL pool: {e}")
        raise


async def close_pool() -> None:
    """Close the database pool."""
    global pool
    if pool is None:
        return
        
    logger.info("Closing PostgreSQL connection pool...")
    await pool.close()
    pool = None
    logger.info("PostgreSQL connection pool terminated")


async def query(query_text: str, params: Optional[List[Any]] = None, client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Run a raw parameterized SQL query and return rows as dictionaries.
    Compatible with transaction connections (client) or pool fallback.
    """
    target = client if client is not None else pool
    if target is None:
        raise RuntimeError("Database pool has not been initialized.")
        
    args = params or []
    try:
        records = await target.fetch(query_text, *args)
        return [dict(r) for r in records]
    except Exception as e:
        logger.error(f"Database Query Failed: {query_text.strip()} | Error: {e}")
        raise


async def transaction(callback_coro):
    """
    Executes a callback coroutine inside a database transaction block.
    Passes the connection client to the callback.
    """
    if pool is None:
        raise RuntimeError("Database pool has not been initialized.")
        
    async with pool.acquire() as connection:
        async with connection.transaction():
            logger.debug("Database Transaction Begin")
            try:
                result = await callback_coro(connection)
                logger.debug("Database Transaction Committed")
                return result
            except Exception as e:
                logger.error(f"Database Transaction Rollback due to error: {e}")
                raise


async def test_connection() -> bool:
    """Tests the database connection health by executing a query."""
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT NOW()")
            logger.info(f"Database connection test successful. Timestamp: {val}")
            return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
