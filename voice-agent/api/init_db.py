"""
Database Initialization Script.
Creates tables and seeds default user records.
"""

import asyncio
import logging
import sys
import os
import bcrypt

# Adjust path to import config and database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import database
from config import get_settings

# Setup console logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("voice-agent.api.init_db")

schema_sql = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resellers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    commission_pct NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    contact_email VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    minutes_balance INTEGER NOT NULL DEFAULT 0,
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(30),
    avatar_url VARCHAR(512),
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    reseller_id UUID REFERENCES resellers(id) ON DELETE SET NULL,
    client_id UUID, -- Will reference clients table once it is created
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);

CREATE TABLE IF NOT EXISTS user_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'EMAIL_VERIFICATION', 'PASSWORD_RESET'
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_tokens_hash ON user_tokens(token_hash);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(512),
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    country VARCHAR(100),
    monthly_recurring NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    contact_email VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    reseller_id UUID REFERENCES resellers(id) ON DELETE SET NULL,
    minutes_balance INTEGER NOT NULL DEFAULT 0,
    stripe_customer_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clients_reseller ON clients(reseller_id);

-- Alter users to reference clients
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_client_id;
ALTER TABLE users ADD CONSTRAINT fk_users_client_id FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    call_type VARCHAR(50) NOT NULL DEFAULT 'inbound',
    use_case VARCHAR(255),
    activity_description TEXT,
    channels VARCHAR(50)[] NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    total_calls INTEGER NOT NULL DEFAULT 0,
    total_messages INTEGER NOT NULL DEFAULT 0,
    total_minutes INTEGER NOT NULL DEFAULT 0,
    success_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    escalation_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    prompt_version INTEGER NOT NULL DEFAULT 1,
    kb_version INTEGER NOT NULL DEFAULT 1,
    total_cost NUMERIC(12,4) NOT NULL DEFAULT 0.0000,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_resellers (
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    reseller_id UUID REFERENCES resellers(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, reseller_id)
);

CREATE TABLE IF NOT EXISTS agent_clients (
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, client_id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    customer_name VARCHAR(255) NOT NULL,
    customer_contact VARCHAR(100),
    channel VARCHAR(50) NOT NULL,
    duration INTEGER NOT NULL DEFAULT 0,
    cost NUMERIC(12,4) NOT NULL DEFAULT 0.0000,
    sentiment VARCHAR(50) NOT NULL DEFAULT 'neutral',
    outcome VARCHAR(50) NOT NULL DEFAULT 'resolved',
    summary TEXT,
    intent VARCHAR(100),
    lead_score INTEGER NOT NULL DEFAULT 0,
    sentiment_score NUMERIC(3,2) NOT NULL DEFAULT 0.00,
    human_handoff BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_reason VARCHAR(255),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP WITH TIME ZONE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    duration INTEGER NOT NULL DEFAULT 0,
    size INTEGER NOT NULL DEFAULT 0,
    s3_key VARCHAR(512) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,
    full_text TEXT NOT NULL,
    lines JSONB NOT NULL DEFAULT '[]'::jsonb,
    action_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    minutes INTEGER NOT NULL DEFAULT 0,
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    reseller_id UUID REFERENCES resellers(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reseller_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reseller_id UUID NOT NULL REFERENCES resellers(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    client_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (reseller_id, plan_id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    number VARCHAR(100) UNIQUE NOT NULL,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    reseller_id UUID REFERENCES resellers(id) ON DELETE SET NULL,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    tax NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    paid_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    due_date TIMESTAMP WITH TIME ZONE NOT NULL,
    issue_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    line_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    invoice_id UUID REFERENCES invoices(id) ON DELETE SET NULL,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    reseller_id UUID REFERENCES resellers(id) ON DELETE SET NULL,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    method VARCHAR(50) NOT NULL DEFAULT 'card',
    reference VARCHAR(255),
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contracts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    number VARCHAR(100) UNIQUE NOT NULL,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    contract_value NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    auto_renewal BOOLEAN NOT NULL DEFAULT FALSE,
    payment_terms VARCHAR(100),
    billing_cycle VARCHAR(50),
    notice_period_days INTEGER DEFAULT 30,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS renewals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    value NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    renewal_date TIMESTAMP WITH TIME ZONE NOT NULL,
    probability INTEGER DEFAULT 80,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS commissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reseller_id UUID NOT NULL REFERENCES resellers(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    invoice_id UUID REFERENCES invoices(id) ON DELETE SET NULL,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    commission_pct NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(50) NOT NULL DEFAULT 'payable',
    date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS calendar_integrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    event_type_url VARCHAR(512),
    provider_user_id VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, provider),
    UNIQUE(user_id, provider),
    CHECK (client_id IS NOT NULL OR user_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_calendar_integrations_client ON calendar_integrations(client_id, provider);
CREATE INDEX IF NOT EXISTS idx_calendar_integrations_user ON calendar_integrations(user_id, provider);
CREATE INDEX IF NOT EXISTS idx_calendar_integrations_active ON calendar_integrations(is_active);

CREATE TABLE IF NOT EXISTS calendar_bookings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    integration_id UUID NOT NULL REFERENCES calendar_integrations(id) ON DELETE CASCADE,
    invitee_uri VARCHAR(512) NOT NULL,
    event_type_uri VARCHAR(512) NOT NULL,
    scheduled_event_uri VARCHAR(512),
    invitee_email VARCHAR(255) NOT NULL,
    invitee_name VARCHAR(255) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    timezone VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'scheduled',
    cancellation_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_calendar_bookings_integration ON calendar_bookings(integration_id);
CREATE INDEX IF NOT EXISTS idx_calendar_bookings_status ON calendar_bookings(status);
CREATE INDEX IF NOT EXISTS idx_calendar_bookings_invitee_uri ON calendar_bookings(invitee_uri);

CREATE TABLE IF NOT EXISTS calendar_webhooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    integration_id UUID NOT NULL REFERENCES calendar_integrations(id) ON DELETE CASCADE,
    webhook_id VARCHAR(255),
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_calendar_webhooks_integration ON calendar_webhooks(integration_id);
CREATE INDEX IF NOT EXISTS idx_calendar_webhooks_processed ON calendar_webhooks(processed);

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
"""

seed_roles_sql = """
INSERT INTO roles (name, description) VALUES
('SUPER_ADMIN', 'Super Administrator with full platform access'),
('FINANCE_ADMIN', 'Finance Administrator with billing and invoice access'),
('RESELLER', 'Reseller with client management access'),
('CLIENT', 'Client user with standard application access')
ON CONFLICT (name) DO NOTHING;
"""


async def init_db() -> None:
    logger.info("Initializing database...")
    settings = get_settings()
    
    # Initialize database pool
    await database.init_pool()
    
    try:
        # 1. Test database connection
        connected = await database.test_connection()
        if not connected:
            logger.critical("Cannot connect to database. Aborting migrations.")
            sys.exit(1)
            
        # 2. Run schema execution
        logger.info("Creating database tables and indexes...")
        # Since asyncpg execute executes multi-statement scripts, we can pass it directly
        if database.pool is None:
            logger.critical("Database pool not initialized. Aborting migrations.")
            sys.exit(1)
        async with database.pool.acquire() as conn:
            await conn.execute(schema_sql)
            await conn.execute(seed_roles_sql)
            await conn.execute("""
                ALTER TABLE agents ADD COLUMN IF NOT EXISTS call_type VARCHAR(50) NOT NULL DEFAULT 'inbound';
                ALTER TABLE agents ADD COLUMN IF NOT EXISTS use_case VARCHAR(255);
                ALTER TABLE agents ADD COLUMN IF NOT EXISTS activity_description TEXT;
                
                ALTER TABLE resellers ADD COLUMN IF NOT EXISTS minutes_balance INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE resellers ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);
                
                ALTER TABLE clients ADD COLUMN IF NOT EXISTS minutes_balance INTEGER NOT NULL DEFAULT 0;
                ALTER TABLE clients ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);

                ALTER TABLE calendar_integrations ADD COLUMN IF NOT EXISTS refresh_token TEXT;
                ALTER TABLE calendar_integrations ADD COLUMN IF NOT EXISTS provider_user_id VARCHAR(255);
            """)
            
        logger.info("Tables created and roles seeded successfully.")
        
        # 3. Seed default users
        logger.info("Seeding default users...")
        roles = await database.query("SELECT id, name FROM roles")
        roles_map = {r["name"]: r["id"] for r in roles}
        
        default_users = [
            {
                "email": "admin@42voice.com",
                "password": "Admin@42voice",
                "first_name": "Super",
                "last_name": "Admin",
                "role_name": "SUPER_ADMIN",
            },
            {
                "email": "finance@42voice.com",
                "password": "Finance@42voice",
                "first_name": "Finance",
                "last_name": "Admin",
                "role_name": "FINANCE_ADMIN",
            },
            {
                "email": "reseller@42voice.com",
                "password": "Reseller@42voice",
                "first_name": "Reseller",
                "last_name": "Admin",
                "role_name": "RESELLER",
            },
            {
                "email": "client@42voice.com",
                "password": "Client@42voice",
                "first_name": "Client",
                "last_name": "User",
                "role_name": "CLIENT",
            },
        ]
        
        salt_rounds = settings.bcrypt_salt_rounds
        
        for u in default_users:
            role_id = roles_map.get(u["role_name"])
            if not role_id:
                logger.warning(f"Role {u['role_name']} not found, skipping user {u['email']}")
                continue
                
            # Cryptographic hash password in python
            hashed = bcrypt.hashpw(u["password"].encode('utf-8'), bcrypt.gensalt(salt_rounds))
            hashed_str = hashed.decode('utf-8')
            
            await database.query(
                """INSERT INTO users (email, password_hash, first_name, last_name, role_id, is_active, is_verified)
                   VALUES ($1, $2, $3, $4, $5, true, true)
                   ON CONFLICT (email) DO UPDATE 
                   SET password_hash = EXCLUDED.password_hash,
                       first_name = EXCLUDED.first_name,
                       last_name = EXCLUDED.last_name,
                       role_id = EXCLUDED.role_id,
                       is_active = true,
                       is_verified = true""",
                [u["email"], hashed_str, u["first_name"], u["last_name"], role_id]
            )
            
        logger.info("Default users seeded successfully.")
        
        # 4. Seed default reseller
        logger.info("Seeding default reseller...")
        reseller_res = await database.query("SELECT id FROM resellers WHERE contact_email = 'reseller@42voice.com'")
        if not reseller_res:
            inserted = await database.query(
                """INSERT INTO resellers (name, country, commission_pct, contact_email, status)
                   VALUES ('Acme Reseller', 'Australia', 15.00, 'reseller@42voice.com', 'active')
                   RETURNING id"""
            )
            reseller_id = inserted[0]["id"]
        else:
            reseller_id = reseller_res[0]["id"]
            
        # 5. Seed default client
        logger.info("Seeding default client...")
        client_res = await database.query("SELECT id FROM clients WHERE contact_email = 'client@42voice.com'")
        if not client_res:
            inserted = await database.query(
                """INSERT INTO clients (name, industry, country, monthly_recurring, contact_email, status, reseller_id)
                   VALUES ('Beta Corp', 'Technology', 'Australia', 2500.00, 'client@42voice.com', 'active', $1)
                   RETURNING id""",
                [reseller_id]
            )
            client_id = inserted[0]["id"]
        else:
            client_id = client_res[0]["id"]
            
        # 6. Link users to reseller/client
        logger.info("Linking users to reseller and client relationships...")
        await database.query(
            "UPDATE users SET reseller_id = $1 WHERE email = 'reseller@42voice.com'",
            [reseller_id]
        )
        await database.query(
            "UPDATE users SET reseller_id = $1, client_id = $2 WHERE email = 'client@42voice.com'",
            [reseller_id, client_id]
        )
        
        # 7. Clean up existing operational tables
        logger.info("Cleaning up existing transcripts, recordings, conversations, and agents...")
        await database.query("DELETE FROM transcripts")
        await database.query("DELETE FROM recordings")
        await database.query("DELETE FROM conversations")
        await database.query("DELETE FROM agents")
        
        logger.info("Database schema setup and seeding completed successfully!")
        
    except Exception as e:
        logger.exception(f"Database initialization failed: {e}")
        sys.exit(1)
    finally:
        await database.close_pool()


if __name__ == "__main__":
    asyncio.run(init_db())
