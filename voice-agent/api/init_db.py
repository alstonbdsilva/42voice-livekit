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
    number VARCHAR(20) NOT NULL UNIQUE,
    provider VARCHAR(50) NOT NULL,
    provider_id VARCHAR(255),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    call_type VARCHAR(50) NOT NULL DEFAULT 'inbound',
    friendly_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_phone_numbers_user ON phone_numbers(user_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_client ON phone_numbers(client_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_number ON phone_numbers(number);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_status ON phone_numbers(status);

CREATE TABLE IF NOT EXISTS phone_number_agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 0,
    routing_strategy VARCHAR(50) NOT NULL DEFAULT 'priority',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phone_number_id, agent_id),
    CHECK (priority >= 0)
);

CREATE INDEX IF NOT EXISTS idx_phone_number_agents_phone ON phone_number_agents(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_agents_agent ON phone_number_agents(agent_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_agents_priority ON phone_number_agents(phone_number_id, priority);
CREATE INDEX IF NOT EXISTS idx_phone_number_agents_status ON phone_number_agents(status);

CREATE TABLE IF NOT EXISTS agent_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL UNIQUE REFERENCES agents(id) ON DELETE CASCADE,
    availability VARCHAR(50) NOT NULL DEFAULT 'available',
    current_active_calls INTEGER NOT NULL DEFAULT 0,
    max_concurrent_calls INTEGER NOT NULL DEFAULT 5,
    today_calls INTEGER NOT NULL DEFAULT 0,
    last_call_at TIMESTAMP WITH TIME ZONE,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (current_active_calls >= 0),
    CHECK (max_concurrent_calls > 0),
    CHECK (today_calls >= 0),
    CHECK (availability IN ('available', 'busy', 'offline', 'paused', 'maintenance'))
);

CREATE INDEX IF NOT EXISTS idx_agent_status_agent ON agent_status(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_status_availability ON agent_status(availability);
CREATE INDEX IF NOT EXISTS idx_agent_status_active_calls ON agent_status(current_active_calls);
CREATE INDEX IF NOT EXISTS idx_agent_status_last_seen ON agent_status(last_seen);

ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS is_primary BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS max_concurrent_calls INTEGER DEFAULT 5;
ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS business_hours_timezone VARCHAR(100);
ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS after_hours_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_phone_number_agents_primary ON phone_number_agents(phone_number_id, is_primary);

CREATE TABLE IF NOT EXISTS business_hours_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    timezone VARCHAR(100) NOT NULL,
    monday JSONB,
    tuesday JSONB,
    wednesday JSONB,
    thursday JSONB,
    friday JSONB,
    saturday JSONB,
    sunday JSONB,
    holiday_calendar JSONB,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_business_hours_user ON business_hours_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_business_hours_client ON business_hours_profiles(client_id);

ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS business_hours_profile_id UUID REFERENCES business_hours_profiles(id) ON DELETE SET NULL;
ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS after_hours_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_phone_numbers_business_hours ON phone_numbers(business_hours_profile_id);

ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS answered_calls INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS missed_calls INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS failed_calls INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS average_call_duration INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS last_call_started TIMESTAMP WITH TIME ZONE;
ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS last_call_ended TIMESTAMP WITH TIME ZONE;
ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS total_calls INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP WITH TIME ZONE;
ALTER TABLE agent_status ADD COLUMN IF NOT EXISTS health_status VARCHAR(50) NOT NULL DEFAULT 'unknown';

CREATE INDEX IF NOT EXISTS idx_agent_status_health ON agent_status(health_status);
CREATE INDEX IF NOT EXISTS idx_agent_status_heartbeat ON agent_status(last_heartbeat);

CREATE TABLE IF NOT EXISTS routing_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID NOT NULL UNIQUE REFERENCES phone_numbers(id) ON DELETE CASCADE,
    routing_strategy VARCHAR(50) NOT NULL,
    last_selected_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_routing_state_phone ON routing_state(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_routing_state_strategy ON routing_state(routing_strategy);

ALTER TABLE phone_number_agents DROP COLUMN IF EXISTS business_hours_timezone;
ALTER TABLE phone_number_agents DROP COLUMN IF EXISTS after_hours_agent_id;

ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS skills JSONB;
ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS languages JSONB;
ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS departments JSONB;
ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS cost_weight NUMERIC(5,2) DEFAULT 1.0;
ALTER TABLE phone_number_agents ADD COLUMN IF NOT EXISTS routing_weight NUMERIC(5,2) DEFAULT 1.0;

CREATE TABLE IF NOT EXISTS phone_number_agent_priority_check (
    phone_number_id UUID NOT NULL,
    priority INTEGER NOT NULL,
    PRIMARY KEY (phone_number_id, priority),
    FOREIGN KEY (phone_number_id) REFERENCES phone_numbers(id) ON DELETE CASCADE
);

ALTER TABLE phone_numbers ADD COLUMN IF NOT EXISTS routing_mode VARCHAR(50) NOT NULL DEFAULT 'direct';

ALTER TABLE agents ADD COLUMN IF NOT EXISTS agent_type VARCHAR(50) NOT NULL DEFAULT 'voice';

DROP TABLE IF EXISTS router_agents CASCADE;

CREATE TABLE IF NOT EXISTS capabilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL),
    UNIQUE(name, user_id, client_id)
);

CREATE INDEX IF NOT EXISTS idx_capabilities_user ON capabilities(user_id);
CREATE INDEX IF NOT EXISTS idx_capabilities_client ON capabilities(client_id);
CREATE INDEX IF NOT EXISTS idx_capabilities_name ON capabilities(name);

CREATE TABLE IF NOT EXISTS agent_capabilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    capability_id UUID NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, capability_id),
    CHECK (priority >= 0)
);

CREATE INDEX IF NOT EXISTS idx_agent_capabilities_agent ON agent_capabilities(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_capabilities_capability ON agent_capabilities(capability_id);
CREATE INDEX IF NOT EXISTS idx_agent_capabilities_priority ON agent_capabilities(capability_id, priority);

CREATE TABLE IF NOT EXISTS intent_capabilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intent_name VARCHAR(255) NOT NULL,
    capability_id UUID NOT NULL REFERENCES capabilities(id) ON DELETE CASCADE,
    confidence_threshold NUMERIC(3,2) NOT NULL DEFAULT 0.7,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL),
    CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1),
    UNIQUE(intent_name, capability_id, user_id, client_id)
);

CREATE INDEX IF NOT EXISTS idx_intent_capabilities_intent ON intent_capabilities(intent_name);
CREATE INDEX IF NOT EXISTS idx_intent_capabilities_capability ON intent_capabilities(capability_id);
CREATE INDEX IF NOT EXISTS idx_intent_capabilities_user ON intent_capabilities(user_id);
CREATE INDEX IF NOT EXISTS idx_intent_capabilities_client ON intent_capabilities(client_id);

CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    entry_capability_id UUID REFERENCES capabilities(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL),
    UNIQUE(name, user_id, client_id)
);

CREATE INDEX IF NOT EXISTS idx_workflows_user ON workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_workflows_client ON workflows(client_id);
CREATE INDEX IF NOT EXISTS idx_workflows_active ON workflows(is_active);
CREATE INDEX IF NOT EXISTS idx_workflows_entry_capability ON workflows(entry_capability_id);

CREATE TABLE IF NOT EXISTS intent_workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intent_name VARCHAR(255) NOT NULL,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    confidence_threshold NUMERIC(3,2) NOT NULL DEFAULT 0.7,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL),
    CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1),
    UNIQUE(intent_name, workflow_id, user_id, client_id)
);

CREATE INDEX IF NOT EXISTS idx_intent_workflows_intent ON intent_workflows(intent_name);
CREATE INDEX IF NOT EXISTS idx_intent_workflows_workflow ON intent_workflows(workflow_id);
CREATE INDEX IF NOT EXISTS idx_intent_workflows_user ON intent_workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_intent_workflows_client ON intent_workflows(client_id);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL,
    configuration JSONB,
    next_step_id UUID REFERENCES workflow_steps(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (step_type IN ('intent', 'condition', 'action', 'capability', 'api', 'plugin', 'wait', 'end')),
    CHECK (step_order >= 0)
);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_workflow ON workflow_steps(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_order ON workflow_steps(workflow_id, step_order);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_type ON workflow_steps(step_type);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_next ON workflow_steps(next_step_id);

CREATE TABLE IF NOT EXISTS workflow_conditions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_step_id UUID NOT NULL REFERENCES workflow_steps(id) ON DELETE CASCADE,
    condition_type VARCHAR(100) NOT NULL,
    configuration JSONB NOT NULL,
    true_step_id UUID REFERENCES workflow_steps(id) ON DELETE SET NULL,
    false_step_id UUID REFERENCES workflow_steps(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (condition_type IN ('intent_match', 'entity_exists', 'business_hours', 'customer_exists', 
                              'crm_status', 'vip_customer', 'language', 'sentiment', 'confidence_score', 'custom_expression'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_conditions_step ON workflow_conditions(workflow_step_id);
CREATE INDEX IF NOT EXISTS idx_workflow_conditions_type ON workflow_conditions(condition_type);
CREATE INDEX IF NOT EXISTS idx_workflow_conditions_true_step ON workflow_conditions(true_step_id);
CREATE INDEX IF NOT EXISTS idx_workflow_conditions_false_step ON workflow_conditions(false_step_id);

CREATE TABLE IF NOT EXISTS workflow_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_step_id UUID NOT NULL REFERENCES workflow_steps(id) ON DELETE CASCADE,
    action_type VARCHAR(100) NOT NULL,
    configuration JSONB NOT NULL,
    execution_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (action_type IN ('assign_capability', 'assign_agent', 'assign_group', 'lookup_crm', 
                           'search_knowledge_base', 'google_calendar', 'calendly', 'webhook', 
                           'rest_api', 'database_query', 'update_context', 'transfer_agent', 
                           'notify_supervisor', 'plugin')),
    CHECK (execution_order >= 0)
);

CREATE INDEX IF NOT EXISTS idx_workflow_actions_step ON workflow_actions(workflow_step_id);
CREATE INDEX IF NOT EXISTS idx_workflow_actions_type ON workflow_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_workflow_actions_order ON workflow_actions(workflow_step_id, execution_order);

CREATE TABLE IF NOT EXISTS plugins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    plugin_type VARCHAR(100) NOT NULL,
    description TEXT,
    configuration JSONB,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL),
    UNIQUE(name, user_id, client_id)
);

CREATE INDEX IF NOT EXISTS idx_plugins_user ON plugins(user_id);
CREATE INDEX IF NOT EXISTS idx_plugins_client ON plugins(client_id);
CREATE INDEX IF NOT EXISTS idx_plugins_type ON plugins(plugin_type);
CREATE INDEX IF NOT EXISTS idx_plugins_active ON plugins(is_active);

CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    current_step_id UUID REFERENCES workflow_steps(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    execution_context JSONB,
    workflow_context JSONB,
    customer_context JSONB,
    plugin_results JSONB,
    extracted_entities JSONB,
    memory JSONB,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('running', 'paused', 'completed', 'failed', 'escalated'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_session ON workflow_executions(session_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_current_step ON workflow_executions(current_step_id);

CREATE TABLE IF NOT EXISTS workflow_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (event_type IN ('call_started', 'call_ended', 'workflow_started', 'workflow_completed', 
                          'workflow_failed', 'agent_assigned', 'agent_transferred', 'conversation_handoff',
                          'plugin_executed', 'customer_verified', 'supervisor_notified', 'supervisor_escalated'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_events_execution ON workflow_events(execution_id);
CREATE INDEX IF NOT EXISTS idx_workflow_events_type ON workflow_events(event_type);
CREATE INDEX IF NOT EXISTS idx_workflow_events_created ON workflow_events(created_at);

CREATE TABLE IF NOT EXISTS supervisor_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    message TEXT,
    context JSONB,
    action_taken VARCHAR(100),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (alert_type IN ('low_confidence', 'hallucination', 'repeated_failure', 'negative_sentiment', 
                          'compliance_risk', 'long_silence', 'repeated_transfers')),
    CHECK (severity IN ('info', 'warning', 'critical')),
    CHECK (action_taken IN ('notify', 'takeover', 'escalate', 'terminate', 'restart', NULL))
);

CREATE INDEX IF NOT EXISTS idx_supervisor_alerts_execution ON supervisor_alerts(execution_id);
CREATE INDEX IF NOT EXISTS idx_supervisor_alerts_type ON supervisor_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_supervisor_alerts_severity ON supervisor_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_supervisor_alerts_resolved ON supervisor_alerts(resolved);

CREATE TABLE IF NOT EXISTS workflow_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    execution_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    escalation_count INTEGER DEFAULT 0,
    average_execution_time_ms INTEGER DEFAULT 0,
    average_step_time_ms INTEGER DEFAULT 0,
    average_plugin_time_ms INTEGER DEFAULT 0,
    last_execution_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflow_metrics_workflow ON workflow_metrics(workflow_id);

CREATE TABLE IF NOT EXISTS oauth_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider VARCHAR(50) NOT NULL,
    tenant_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (provider IN ('google', 'outlook', 'calendly')),
    CHECK (status IN ('active', 'expired', 'revoked', 'error')),
    UNIQUE(provider, tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_oauth_connections_tenant ON oauth_connections(tenant_id);
CREATE INDEX IF NOT EXISTS idx_oauth_connections_user ON oauth_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_connections_provider ON oauth_connections(provider);
CREATE INDEX IF NOT EXISTS idx_oauth_connections_status ON oauth_connections(status);

CREATE TABLE IF NOT EXISTS calendar_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    oauth_connection_id UUID NOT NULL REFERENCES oauth_connections(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    calendar_id VARCHAR(255) NOT NULL,
    calendar_name VARCHAR(255) NOT NULL,
    timezone VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (provider IN ('google', 'outlook', 'calendly')),
    UNIQUE(oauth_connection_id, calendar_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_connections_oauth ON calendar_connections(oauth_connection_id);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_provider ON calendar_connections(provider);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_primary ON calendar_connections(is_primary);
CREATE INDEX IF NOT EXISTS idx_calendar_connections_active ON calendar_connections(is_active);

CREATE TABLE IF NOT EXISTS agent_calendar_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    calendar_connection_id UUID NOT NULL REFERENCES calendar_connections(id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT FALSE,
    booking_enabled BOOLEAN DEFAULT TRUE,
    meeting_duration_minutes INTEGER DEFAULT 30,
    buffer_before_minutes INTEGER DEFAULT 0,
    buffer_after_minutes INTEGER DEFAULT 0,
    booking_window_days INTEGER DEFAULT 90,
    minimum_notice_minutes INTEGER DEFAULT 0,
    maximum_advance_booking_days INTEGER DEFAULT 365,
    timezone VARCHAR(100),
    auto_confirm BOOLEAN DEFAULT TRUE,
    auto_cancel BOOLEAN DEFAULT FALSE,
    auto_reschedule BOOLEAN DEFAULT FALSE,
    maximum_meetings_per_day INTEGER DEFAULT 10,
    working_hours_override JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, calendar_connection_id),
    CHECK (meeting_duration_minutes > 0),
    CHECK (buffer_before_minutes >= 0),
    CHECK (buffer_after_minutes >= 0),
    CHECK (booking_window_days > 0),
    CHECK (minimum_notice_minutes >= 0),
    CHECK (maximum_advance_booking_days > 0),
    CHECK (maximum_meetings_per_day > 0)
);

CREATE INDEX IF NOT EXISTS idx_agent_calendar_connections_agent ON agent_calendar_connections(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_calendar_connections_calendar ON agent_calendar_connections(calendar_connection_id);
CREATE INDEX IF NOT EXISTS idx_agent_calendar_connections_primary ON agent_calendar_connections(is_primary);
CREATE INDEX IF NOT EXISTS idx_agent_calendar_connections_booking ON agent_calendar_connections(booking_enabled);

CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_calendar_connection_id UUID NOT NULL REFERENCES agent_calendar_connections(id) ON DELETE CASCADE,
    provider_event_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    timezone VARCHAR(100),
    attendees JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'confirmed',
    is_recurring BOOLEAN DEFAULT FALSE,
    recurring_rule VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (provider IN ('google', 'outlook', 'calendly')),
    CHECK (status IN ('confirmed', 'tentative', 'cancelled', 'pending')),
    UNIQUE(provider, provider_event_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_agent_calendar ON calendar_events(agent_calendar_connection_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_provider ON calendar_events(provider);
CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_end_time ON calendar_events(end_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_status ON calendar_events(status);

CREATE TABLE IF NOT EXISTS calendar_bookings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    agent_calendar_connection_id UUID NOT NULL REFERENCES agent_calendar_connections(id) ON DELETE CASCADE,
    calendar_event_id UUID REFERENCES calendar_events(id) ON DELETE SET NULL,
    customer_name VARCHAR(255),
    customer_email VARCHAR(255),
    customer_phone VARCHAR(20),
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    timezone VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    confirmation_sent BOOLEAN DEFAULT FALSE,
    reminder_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('pending', 'confirmed', 'cancelled', 'rescheduled', 'completed'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_bookings_session ON calendar_bookings(session_id);
CREATE INDEX IF NOT EXISTS idx_calendar_bookings_agent_calendar ON calendar_bookings(agent_calendar_connection_id);
CREATE INDEX IF NOT EXISTS idx_calendar_bookings_status ON calendar_bookings(status);
CREATE INDEX IF NOT EXISTS idx_calendar_bookings_start_time ON calendar_bookings(start_time);

CREATE TABLE IF NOT EXISTS calendar_selection_strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    strategy VARCHAR(50) NOT NULL DEFAULT 'primary',
    configuration JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (strategy IN ('primary', 'round_robin', 'least_busy', 'manual', 'workflow_defined')),
    UNIQUE(agent_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_selection_strategies_agent ON calendar_selection_strategies(agent_id);
CREATE INDEX IF NOT EXISTS idx_calendar_selection_strategies_strategy ON calendar_selection_strategies(strategy);

CREATE TABLE IF NOT EXISTS slot_reservations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_calendar_connection_id UUID NOT NULL REFERENCES agent_calendar_connections(id) ON DELETE CASCADE,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    customer_email VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'reserved',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('reserved', 'confirmed', 'expired', 'released')),
    UNIQUE(agent_calendar_connection_id, start_time, end_time)
);

CREATE INDEX IF NOT EXISTS idx_slot_reservations_agent_calendar ON slot_reservations(agent_calendar_connection_id);
CREATE INDEX IF NOT EXISTS idx_slot_reservations_status ON slot_reservations(status);
CREATE INDEX IF NOT EXISTS idx_slot_reservations_expires_at ON slot_reservations(expires_at);
CREATE INDEX IF NOT EXISTS idx_slot_reservations_start_time ON slot_reservations(start_time);

CREATE TABLE IF NOT EXISTS calendar_webhooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    calendar_connection_id UUID NOT NULL REFERENCES calendar_connections(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    webhook_id VARCHAR(255),
    webhook_url VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    last_ping_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (provider IN ('google', 'outlook', 'calendly')),
    CHECK (status IN ('active', 'inactive', 'failed', 'expired'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_webhooks_calendar ON calendar_webhooks(calendar_connection_id);
CREATE INDEX IF NOT EXISTS idx_calendar_webhooks_provider ON calendar_webhooks(provider);
CREATE INDEX IF NOT EXISTS idx_calendar_webhooks_status ON calendar_webhooks(status);

CREATE TABLE IF NOT EXISTS calendar_sync_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    calendar_connection_id UUID NOT NULL REFERENCES calendar_connections(id) ON DELETE CASCADE,
    sync_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    events_synced INTEGER DEFAULT 0,
    events_created INTEGER DEFAULT 0,
    events_updated INTEGER DEFAULT 0,
    events_deleted INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (sync_type IN ('full', 'incremental', 'webhook', 'reconciliation')),
    CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_sync_logs_calendar ON calendar_sync_logs(calendar_connection_id);
CREATE INDEX IF NOT EXISTS idx_calendar_sync_logs_status ON calendar_sync_logs(status);
CREATE INDEX IF NOT EXISTS idx_calendar_sync_logs_sync_type ON calendar_sync_logs(sync_type);
CREATE INDEX IF NOT EXISTS idx_calendar_sync_logs_completed_at ON calendar_sync_logs(completed_at);

CREATE TABLE IF NOT EXISTS calendar_health (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    calendar_connection_id UUID NOT NULL REFERENCES calendar_connections(id) ON DELETE CASCADE,
    oauth_status VARCHAR(50) NOT NULL DEFAULT 'active',
    webhook_status VARCHAR(50) NOT NULL DEFAULT 'active',
    sync_status VARCHAR(50) NOT NULL DEFAULT 'healthy',
    last_successful_sync TIMESTAMP WITH TIME ZONE,
    last_failed_sync TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    rate_limit_remaining INTEGER,
    rate_limit_reset_at TIMESTAMP WITH TIME ZONE,
    consecutive_failures INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (oauth_status IN ('active', 'expired', 'revoked', 'error')),
    CHECK (webhook_status IN ('active', 'inactive', 'failed', 'expired')),
    CHECK (sync_status IN ('healthy', 'degraded', 'unhealthy')),
    UNIQUE(calendar_connection_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_health_calendar ON calendar_health(calendar_connection_id);
CREATE INDEX IF NOT EXISTS idx_calendar_health_oauth_status ON calendar_health(oauth_status);
CREATE INDEX IF NOT EXISTS idx_calendar_health_sync_status ON calendar_health(sync_status);

CREATE TABLE IF NOT EXISTS calendar_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    calendar_connection_id UUID REFERENCES calendar_connections(id) ON DELETE SET NULL,
    agent_calendar_connection_id UUID REFERENCES agent_calendar_connections(id) ON DELETE SET NULL,
    booking_id UUID REFERENCES calendar_bookings(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    actor_type VARCHAR(50) NOT NULL,
    actor_id VARCHAR(255),
    details JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (action IN ('connected', 'disconnected', 'booking_created', 'booking_updated', 
                      'booking_cancelled', 'webhook_received', 'token_refreshed', 'sync_completed', 
                      'booking_failed', 'slot_reserved', 'slot_released', 'conflict_detected')),
    CHECK (actor_type IN ('system', 'user', 'webhook', 'scheduler')),
    CHECK (status IN ('success', 'failed', 'warning'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_audit_logs_calendar ON calendar_audit_logs(calendar_connection_id);
CREATE INDEX IF NOT EXISTS idx_calendar_audit_logs_booking ON calendar_audit_logs(booking_id);
CREATE INDEX IF NOT EXISTS idx_calendar_audit_logs_action ON calendar_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_calendar_audit_logs_created_at ON calendar_audit_logs(created_at);

CREATE TABLE IF NOT EXISTS calendar_attendees (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    calendar_event_id UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
    name VARCHAR(255),
    email VARCHAR(255) NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    is_organizer BOOLEAN DEFAULT FALSE,
    response_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (response_status IN ('pending', 'accepted', 'declined', 'tentative')),
    UNIQUE(calendar_event_id, email)
);

CREATE INDEX IF NOT EXISTS idx_calendar_attendees_event ON calendar_attendees(calendar_event_id);
CREATE INDEX IF NOT EXISTS idx_calendar_attendees_email ON calendar_attendees(email);
CREATE INDEX IF NOT EXISTS idx_calendar_attendees_response ON calendar_attendees(response_status);

CREATE TABLE IF NOT EXISTS booking_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_calendar_connection_id UUID NOT NULL REFERENCES agent_calendar_connections(id) ON DELETE CASCADE,
    maximum_meetings_per_day INTEGER DEFAULT 10,
    maximum_concurrent_meetings INTEGER DEFAULT 1,
    minimum_notice_minutes INTEGER DEFAULT 0,
    maximum_advance_booking_days INTEGER DEFAULT 365,
    allow_weekend_booking BOOLEAN DEFAULT FALSE,
    allow_holiday_booking BOOLEAN DEFAULT FALSE,
    lunch_break_start TIME,
    lunch_break_end TIME,
    preferred_booking_start TIME,
    preferred_booking_end TIME,
    blackout_dates JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (maximum_meetings_per_day > 0),
    CHECK (maximum_concurrent_meetings > 0),
    UNIQUE(agent_calendar_connection_id)
);

CREATE INDEX IF NOT EXISTS idx_booking_policies_agent_calendar ON booking_policies(agent_calendar_connection_id);

CREATE TABLE IF NOT EXISTS calendar_conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    booking_id UUID NOT NULL REFERENCES calendar_bookings(id) ON DELETE CASCADE,
    conflict_type VARCHAR(100) NOT NULL,
    conflicting_event_id UUID REFERENCES calendar_events(id) ON DELETE SET NULL,
    details JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (conflict_type IN ('overlapping_meeting', 'duplicate_request', 'calendar_conflict', 
                             'recurring_conflict', 'booking_window_violation', 'policy_violation'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_conflicts_booking ON calendar_conflicts(booking_id);
CREATE INDEX IF NOT EXISTS idx_calendar_conflicts_type ON calendar_conflicts(conflict_type);
CREATE INDEX IF NOT EXISTS idx_calendar_conflicts_resolved ON calendar_conflicts(resolved);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key VARCHAR(255) NOT NULL,
    operation_type VARCHAR(100) NOT NULL,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(idempotency_key, operation_type)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_keys_key ON idempotency_keys(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_operation ON idempotency_keys(operation_type);
CREATE INDEX IF NOT EXISTS idx_idempotency_keys_created ON idempotency_keys(created_at);

CREATE TABLE IF NOT EXISTS phone_number_provider_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    api_key VARCHAR(500),
    api_secret VARCHAR(500),
    account_id VARCHAR(255),
    webhook_url VARCHAR(500),
    webhook_secret VARCHAR(500),
    sip_domain VARCHAR(255),
    sip_user VARCHAR(255),
    sip_password VARCHAR(255),
    configuration JSONB,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (provider IN ('twilio', 'telnyx', 'plivo', 'signalwire', 'exotel', 'sip')),
    CHECK (status IN ('active', 'inactive', 'error', 'suspended')),
    UNIQUE(tenant_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_phone_number_provider_configs_tenant ON phone_number_provider_configs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_provider_configs_provider ON phone_number_provider_configs(provider);
CREATE INDEX IF NOT EXISTS idx_phone_number_provider_configs_status ON phone_number_provider_configs(status);

CREATE TABLE IF NOT EXISTS phone_numbers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_number_id VARCHAR(255),
    e164_number VARCHAR(20) NOT NULL,
    friendly_name VARCHAR(255),
    country_code VARCHAR(2),
    region VARCHAR(100),
    timezone VARCHAR(100),
    capabilities JSONB DEFAULT '{"voice": true, "sms": false, "mms": false, "whatsapp": false}',
    status VARCHAR(50) NOT NULL DEFAULT 'provisioning',
    routing_mode VARCHAR(50) DEFAULT 'direct',
    business_hours_id UUID REFERENCES business_hours_profiles(id) ON DELETE SET NULL,
    recording_policy VARCHAR(50) DEFAULT 'never_record',
    spam_protection_enabled BOOLEAN DEFAULT TRUE,
    emergency_calling_enabled BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (provider IN ('twilio', 'telnyx', 'plivo', 'signalwire', 'exotel', 'sip')),
    CHECK (status IN ('provisioning', 'active', 'inactive', 'suspended', 'released')),
    CHECK (routing_mode IN ('direct', 'intent')),
    CHECK (recording_policy IN ('always_record', 'never_record', 'consent_required', 'country_based', 'workflow_based', 'agent_based')),
    UNIQUE(tenant_id, e164_number)
);

CREATE INDEX IF NOT EXISTS idx_phone_numbers_tenant ON phone_numbers(tenant_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_e164 ON phone_numbers(e164_number);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_provider ON phone_numbers(provider);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_status ON phone_numbers(status);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_routing_mode ON phone_numbers(routing_mode);

CREATE TABLE IF NOT EXISTS phone_number_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    assignment_type VARCHAR(50) NOT NULL,
    workflow_id UUID REFERENCES workflows(id) ON DELETE SET NULL,
    agent_group_id UUID REFERENCES agent_groups(id) ON DELETE SET NULL,
    router_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    default_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (assignment_type IN ('workflow', 'agent_group', 'router_agent', 'default_agent')),
    UNIQUE(phone_number_id, assignment_type)
);

CREATE INDEX IF NOT EXISTS idx_phone_number_assignments_phone_number ON phone_number_assignments(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_assignments_workflow ON phone_number_assignments(workflow_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_assignments_agent_group ON phone_number_assignments(agent_group_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_assignments_type ON phone_number_assignments(assignment_type);

CREATE TABLE IF NOT EXISTS phone_number_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL,
    inbound_calls INTEGER DEFAULT 0,
    outbound_calls INTEGER DEFAULT 0,
    missed_calls INTEGER DEFAULT 0,
    failed_calls INTEGER DEFAULT 0,
    busy_calls INTEGER DEFAULT 0,
    total_inbound_minutes INTEGER DEFAULT 0,
    total_outbound_minutes INTEGER DEFAULT 0,
    inbound_cost DECIMAL(10, 4) DEFAULT 0,
    outbound_cost DECIMAL(10, 4) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phone_number_id, usage_date)
);

CREATE INDEX IF NOT EXISTS idx_phone_number_usage_phone_number ON phone_number_usage(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_usage_date ON phone_number_usage(usage_date);

CREATE TABLE IF NOT EXISTS phone_number_spam_list (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,
    list_type VARCHAR(50) NOT NULL,
    reason VARCHAR(255),
    spam_score INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (list_type IN ('blacklist', 'whitelist')),
    UNIQUE(tenant_id, phone_number, list_type)
);

CREATE INDEX IF NOT EXISTS idx_phone_number_spam_list_tenant ON phone_number_spam_list(tenant_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_spam_list_phone_number ON phone_number_spam_list(phone_number);
CREATE INDEX IF NOT EXISTS idx_phone_number_spam_list_type ON phone_number_spam_list(list_type);

CREATE TABLE IF NOT EXISTS phone_number_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID REFERENCES phone_numbers(id) ON DELETE SET NULL,
    tenant_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    actor_type VARCHAR(50) NOT NULL,
    actor_id VARCHAR(255),
    details JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (action IN ('purchased', 'released', 'assigned', 'unassigned', 'activated', 'suspended', 
                      'configuration_updated', 'webhook_received', 'call_initiated', 'call_completed', 
                      'call_failed', 'recording_started', 'recording_stopped', 'spam_detected')),
    CHECK (actor_type IN ('system', 'user', 'webhook', 'scheduler')),
    CHECK (status IN ('success', 'failed', 'warning'))
);

CREATE INDEX IF NOT EXISTS idx_phone_number_audit_logs_phone_number ON phone_number_audit_logs(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_audit_logs_tenant ON phone_number_audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_phone_number_audit_logs_action ON phone_number_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_phone_number_audit_logs_created_at ON phone_number_audit_logs(created_at);

CREATE TABLE IF NOT EXISTS phone_calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    call_id VARCHAR(255) NOT NULL,
    from_number VARCHAR(20) NOT NULL,
    to_number VARCHAR(20) NOT NULL,
    call_type VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'initiated',
    duration_seconds INTEGER DEFAULT 0,
    cost DECIMAL(10, 4) DEFAULT 0,
    recording_url VARCHAR(500),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (call_type IN ('manual', 'workflow', 'campaign', 'scheduled', 'api', 'retry')),
    CHECK (direction IN ('inbound', 'outbound')),
    CHECK (status IN ('initiated', 'ringing', 'active', 'completed', 'failed', 'missed', 'busy')),
    UNIQUE(phone_number_id, call_id)
);

CREATE INDEX IF NOT EXISTS idx_phone_calls_phone_number ON phone_calls(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_phone_calls_call_id ON phone_calls(call_id);
CREATE INDEX IF NOT EXISTS idx_phone_calls_direction ON phone_calls(direction);
CREATE INDEX IF NOT EXISTS idx_phone_calls_status ON phone_calls(status);
CREATE INDEX IF NOT EXISTS idx_phone_calls_created_at ON phone_calls(created_at);

CREATE TABLE IF NOT EXISTS call_state_machine (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id VARCHAR(255) NOT NULL,
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    current_state VARCHAR(50) NOT NULL,
    previous_state VARCHAR(50),
    state_data JSONB,
    transition_reason VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (current_state IN ('initiated', 'ringing', 'answered', 'active', 'hold', 'transferred', 'conference', 'completed', 'failed', 'busy', 'no_answer', 'cancelled')),
    UNIQUE(call_id)
);

CREATE INDEX IF NOT EXISTS idx_call_state_machine_call_id ON call_state_machine(call_id);
CREATE INDEX IF NOT EXISTS idx_call_state_machine_phone_number ON call_state_machine(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_call_state_machine_state ON call_state_machine(current_state);

CREATE TABLE IF NOT EXISTS call_state_transitions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id VARCHAR(255) NOT NULL,
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    reason VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (from_state IN ('initiated', 'ringing', 'answered', 'active', 'hold', 'transferred', 'conference', 'completed', 'failed', 'busy', 'no_answer', 'cancelled')),
    CHECK (to_state IN ('initiated', 'ringing', 'answered', 'active', 'hold', 'transferred', 'conference', 'completed', 'failed', 'busy', 'no_answer', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_call_state_transitions_call_id ON call_state_transitions(call_id);
CREATE INDEX IF NOT EXISTS idx_call_state_transitions_from_state ON call_state_transitions(from_state);
CREATE INDEX IF NOT EXISTS idx_call_state_transitions_to_state ON call_state_transitions(to_state);
CREATE INDEX IF NOT EXISTS idx_call_state_transitions_created_at ON call_state_transitions(created_at);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    webhook_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB,
    signature VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (provider IN ('twilio', 'telnyx', 'plivo', 'signalwire', 'exotel', 'sip')),
    CHECK (event_type IN ('incoming_call', 'call_ringing', 'call_answered', 'call_completed', 'call_failed', 'busy', 'no_answer', 'recording_ready', 'recording_completed', 'voicemail', 'dtmf', 'transfer', 'provider_disconnect')),
    CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'duplicate')),
    UNIQUE(provider, webhook_id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_phone_number ON webhook_deliveries(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_provider ON webhook_deliveries(provider);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_status ON webhook_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_event_type ON webhook_deliveries(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_created_at ON webhook_deliveries(created_at);

CREATE TABLE IF NOT EXISTS call_transfers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_call_id VARCHAR(255) NOT NULL,
    to_call_id VARCHAR(255),
    from_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    to_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    transfer_type VARCHAR(50) NOT NULL,
    transfer_method VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'initiated',
    reason VARCHAR(255),
    warm_transfer_duration_seconds INTEGER,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (transfer_type IN ('ai_to_ai', 'ai_to_human', 'human_to_ai', 'agent_to_agent', 'agent_group', 'queue')),
    CHECK (transfer_method IN ('blind', 'warm', 'consult', 'sip_refer')),
    CHECK (status IN ('initiated', 'ringing', 'connected', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_call_transfers_from_call ON call_transfers(from_call_id);
CREATE INDEX IF NOT EXISTS idx_call_transfers_to_call ON call_transfers(to_call_id);
CREATE INDEX IF NOT EXISTS idx_call_transfers_from_agent ON call_transfers(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_call_transfers_to_agent ON call_transfers(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_call_transfers_status ON call_transfers(status);
CREATE INDEX IF NOT EXISTS idx_call_transfers_created_at ON call_transfers(created_at);

CREATE TABLE IF NOT EXISTS call_queues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    queue_name VARCHAR(255) NOT NULL,
    queue_type VARCHAR(50) NOT NULL DEFAULT 'fifo',
    priority_enabled BOOLEAN DEFAULT FALSE,
    max_wait_time_seconds INTEGER DEFAULT 3600,
    overflow_destination VARCHAR(255),
    callback_enabled BOOLEAN DEFAULT FALSE,
    estimated_wait_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (queue_type IN ('fifo', 'priority', 'overflow', 'callback')),
    UNIQUE(phone_number_id, queue_name)
);

CREATE INDEX IF NOT EXISTS idx_call_queues_phone_number ON call_queues(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_call_queues_queue_type ON call_queues(queue_type);

CREATE TABLE IF NOT EXISTS call_queue_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    queue_id UUID NOT NULL REFERENCES call_queues(id) ON DELETE CASCADE,
    call_id VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL,
    wait_time_seconds INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'waiting',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('waiting', 'offered', 'connected', 'abandoned', 'callback_scheduled'))
);

CREATE INDEX IF NOT EXISTS idx_call_queue_members_queue ON call_queue_members(queue_id);
CREATE INDEX IF NOT EXISTS idx_call_queue_members_call_id ON call_queue_members(call_id);
CREATE INDEX IF NOT EXISTS idx_call_queue_members_status ON call_queue_members(status);

CREATE TABLE IF NOT EXISTS number_portability (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    port_type VARCHAR(50) NOT NULL,
    current_carrier VARCHAR(255),
    target_carrier VARCHAR(255),
    foc_status VARCHAR(50),
    approval_status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (port_type IN ('port_in', 'port_out')),
    CHECK (foc_status IN ('pending', 'approved', 'rejected', 'completed')),
    CHECK (approval_status IN ('pending', 'approved', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_number_portability_phone_number ON number_portability(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_number_portability_port_type ON number_portability(port_type);

CREATE TABLE IF NOT EXISTS sip_trunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    trunk_name VARCHAR(255) NOT NULL,
    sip_domain VARCHAR(255) NOT NULL,
    sip_user VARCHAR(255),
    sip_password VARCHAR(255),
    sip_port INTEGER DEFAULT 5060,
    use_tls BOOLEAN DEFAULT TRUE,
    use_srtp BOOLEAN DEFAULT TRUE,
    codec_list VARCHAR(255) DEFAULT 'PCMU,PCMA,G729',
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(50) DEFAULT 'unknown',
    last_registration TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, sip_domain)
);

CREATE INDEX IF NOT EXISTS idx_sip_trunks_tenant ON sip_trunks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sip_trunks_is_active ON sip_trunks(is_active);
CREATE INDEX IF NOT EXISTS idx_sip_trunks_health_status ON sip_trunks(health_status);

CREATE TABLE IF NOT EXISTS recording_lifecycle (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id VARCHAR(255) NOT NULL,
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    recording_url VARCHAR(500),
    recording_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    is_paused BOOLEAN DEFAULT FALSE,
    dual_channel BOOLEAN DEFAULT FALSE,
    stereo BOOLEAN DEFAULT FALSE,
    pci_paused BOOLEAN DEFAULT FALSE,
    retention_days INTEGER DEFAULT 30,
    encrypted BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (recording_status IN ('pending', 'recording', 'paused', 'completed', 'failed', 'deleted'))
);

CREATE INDEX IF NOT EXISTS idx_recording_lifecycle_call_id ON recording_lifecycle(call_id);
CREATE INDEX IF NOT EXISTS idx_recording_lifecycle_phone_number ON recording_lifecycle(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_recording_lifecycle_status ON recording_lifecycle(recording_status);

CREATE TABLE IF NOT EXISTS compliance_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    country_code VARCHAR(2),
    region VARCHAR(100),
    consent_type VARCHAR(50) NOT NULL,
    recording_allowed BOOLEAN DEFAULT TRUE,
    emergency_calling_allowed BOOLEAN DEFAULT TRUE,
    gdpr_compliant BOOLEAN DEFAULT FALSE,
    hipaa_compliant BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (consent_type IN ('one_party', 'two_party', 'country_based')),
    UNIQUE(tenant_id, country_code, region)
);

CREATE INDEX IF NOT EXISTS idx_compliance_rules_tenant ON compliance_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_compliance_rules_country ON compliance_rules(country_code);

CREATE TABLE IF NOT EXISTS number_pools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    pool_name VARCHAR(255) NOT NULL,
    pool_type VARCHAR(50) NOT NULL,
    selection_strategy VARCHAR(50) NOT NULL DEFAULT 'round_robin',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (pool_type IN ('country', 'department', 'campaign', 'sales', 'support')),
    CHECK (selection_strategy IN ('round_robin', 'least_used', 'priority', 'random', 'workflow_defined')),
    UNIQUE(tenant_id, pool_name)
);

CREATE INDEX IF NOT EXISTS idx_number_pools_tenant ON number_pools(tenant_id);
CREATE INDEX IF NOT EXISTS idx_number_pools_pool_type ON number_pools(pool_type);

CREATE TABLE IF NOT EXISTS number_pool_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pool_id UUID NOT NULL REFERENCES number_pools(id) ON DELETE CASCADE,
    phone_number_id UUID NOT NULL REFERENCES phone_numbers(id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pool_id, phone_number_id)
);

CREATE INDEX IF NOT EXISTS idx_number_pool_members_pool ON number_pool_members(pool_id);
CREATE INDEX IF NOT EXISTS idx_number_pool_members_phone_number ON number_pool_members(phone_number_id);

CREATE TABLE IF NOT EXISTS telephony_health (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID REFERENCES phone_numbers(id) ON DELETE CASCADE,
    sip_trunk_id UUID REFERENCES sip_trunks(id) ON DELETE CASCADE,
    carrier_health VARCHAR(50) DEFAULT 'unknown',
    provider_health VARCHAR(50) DEFAULT 'unknown',
    sip_registration_status VARCHAR(50) DEFAULT 'unknown',
    webhook_health VARCHAR(50) DEFAULT 'unknown',
    recording_health VARCHAR(50) DEFAULT 'unknown',
    call_success_rate DECIMAL(5, 2) DEFAULT 100,
    provider_latency_ms INTEGER DEFAULT 0,
    packet_loss_percent DECIMAL(5, 2) DEFAULT 0,
    jitter_ms INTEGER DEFAULT 0,
    mos_score DECIMAL(3, 1) DEFAULT 4.0,
    last_check TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telephony_health_phone_number ON telephony_health(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_telephony_health_sip_trunk ON telephony_health(sip_trunk_id);
CREATE INDEX IF NOT EXISTS idx_telephony_health_carrier_health ON telephony_health(carrier_health);

CREATE TABLE IF NOT EXISTS distributed_locks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lock_key VARCHAR(255) NOT NULL,
    owner_id VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    acquired_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(lock_key, resource_type, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_distributed_locks_lock_key ON distributed_locks(lock_key);
CREATE INDEX IF NOT EXISTS idx_distributed_locks_expires_at ON distributed_locks(expires_at);
CREATE INDEX IF NOT EXISTS idx_distributed_locks_resource ON distributed_locks(resource_type, resource_id);

CREATE TABLE IF NOT EXISTS telephony_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number_id UUID REFERENCES phone_numbers(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    call_setup_latency_ms INTEGER DEFAULT 0,
    ring_duration_ms INTEGER DEFAULT 0,
    talk_duration_ms INTEGER DEFAULT 0,
    post_dial_delay_ms INTEGER DEFAULT 0,
    transfer_latency_ms INTEGER DEFAULT 0,
    webhook_latency_ms INTEGER DEFAULT 0,
    provider_response_time_ms INTEGER DEFAULT 0,
    sip_response_codes JSONB,
    retry_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    circuit_breaker_state VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(phone_number_id, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_telephony_metrics_phone_number ON telephony_metrics(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_telephony_metrics_date ON telephony_metrics(metric_date);

CREATE TABLE IF NOT EXISTS agent_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL),
    UNIQUE(name, user_id, client_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_groups_user ON agent_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_groups_client ON agent_groups(client_id);

CREATE TABLE IF NOT EXISTS agent_group_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    group_id UUID NOT NULL REFERENCES agent_groups(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_id, agent_id),
    CHECK (priority >= 0)
);

CREATE INDEX IF NOT EXISTS idx_agent_group_members_group ON agent_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_agent_group_members_agent ON agent_group_members(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_group_members_priority ON agent_group_members(group_id, priority);

ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS target_type VARCHAR(50) NOT NULL DEFAULT 'agent';
ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS target_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL;
ALTER TABLE capabilities ADD COLUMN IF NOT EXISTS target_group_id UUID REFERENCES agent_groups(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_capabilities_target_agent ON capabilities(target_agent_id);
CREATE INDEX IF NOT EXISTS idx_capabilities_target_group ON capabilities(target_group_id);

CREATE TABLE IF NOT EXISTS conversation_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) NOT NULL UNIQUE,
    phone_number_id UUID REFERENCES phone_numbers(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    current_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    current_capability_id UUID REFERENCES capabilities(id) ON DELETE SET NULL,
    current_workflow_id UUID REFERENCES workflows(id) ON DELETE SET NULL,
    detected_intent VARCHAR(255),
    intent_confidence NUMERIC(3,2),
    conversation_history JSONB,
    session_state JSONB,
    extracted_entities JSONB,
    user_context JSONB,
    workflow_context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (user_id IS NOT NULL OR client_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_session ON conversation_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_phone ON conversation_sessions(phone_number_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_user ON conversation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_client ON conversation_sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_agent ON conversation_sessions(current_agent_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_capability ON conversation_sessions(current_capability_id);

CREATE TABLE IF NOT EXISTS conversation_participants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversation_participants_session ON conversation_participants(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_participants_agent ON conversation_participants(agent_id);

CREATE TABLE IF NOT EXISTS conversation_handoffs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    from_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    to_agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    workflow_id UUID REFERENCES workflows(id) ON DELETE SET NULL,
    capability_id UUID REFERENCES capabilities(id) ON DELETE SET NULL,
    detected_intent VARCHAR(255),
    confidence NUMERIC(3,2),
    reason VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversation_handoffs_session ON conversation_handoffs(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_handoffs_from_agent ON conversation_handoffs(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_conversation_handoffs_to_agent ON conversation_handoffs(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_conversation_handoffs_workflow ON conversation_handoffs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_conversation_handoffs_capability ON conversation_handoffs(capability_id);
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
