"""
Main FastAPI application.
Provides REST API endpoints and LiveKit integration for the voice agent system.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_settings
from session_manager import SessionManager
from orchestrator import Orchestrator
from agents.booking_agent import BookingAgent
from agents.sales_agent import SalesAgent
from agents.support_agent import SupportAgent
from livekit import api

# Ported Backend Imports
from api import database
from api.middlewares.request_id import RequestIdMiddleware
from api.middlewares.request_logger import RequestLoggerMiddleware
from api.middlewares.rate_limiter import RateLimiterMiddleware
from api.middlewares.error_handler import register_error_handlers

from api.modules.auth.routes import router as auth_router
from api.modules.users.routes import router as users_router
from api.modules.resellers.routes import router as resellers_router
from api.modules.clients.routes import router as clients_router
from api.modules.agents.routes import router as agents_router
from api.modules.conversations.routes import router as conversations_router
from api.modules.recordings.routes import router as recordings_router
from api.modules.transcripts.routes import router as transcripts_router
from api.modules.audit.routes import router as audit_router
from api.modules.health.routes import router as health_router
from api.modules.sessions.routes import router as sessions_router
from api.modules.billing.routes import router as billing_router
from api.modules.finance.routes import router as finance_router

# Configure logging
logging.basicConfig(
    level=get_settings().log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
session_manager: Optional[SessionManager] = None
orchestrator: Optional[Orchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global session_manager, orchestrator
    
    logger.info("Starting voice agent backend...")
    
    # Initialize services
    try:
        # Initialize Database Pool (Ported from Express)
        await database.init_pool()
        
        session_manager = SessionManager()
        
        # Initialize agents
        booking_agent = BookingAgent(session_manager)
        sales_agent = SalesAgent(session_manager)
        support_agent = SupportAgent(session_manager)
        
        # Initialize orchestrator
        orchestrator = Orchestrator(
            session_manager,
            booking_agent,
            sales_agent,
            support_agent
        )
        
        # Bind components to app state for access in decoupled router layers
        app.state.session_manager = session_manager
        app.state.orchestrator = orchestrator
        
        logger.info("All services initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down voice agent backend...")
        if session_manager:
            session_manager.close()
        # Close Database Pool (Ported from Express)
        await database.close_pool()
        logger.info("Shutdown complete")



# Create FastAPI app
app = FastAPI(
    title="Voice Agent Backend",
    description="Realtime multi-agent AI voice system with LiveKit integration",
    version="1.0.0",
    lifespan=lifespan
)


# Configuration and Mounts


# 1. Mount CORS Middlewares (Express settings replication)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

# 2. Add Tracing, Logging, and Rate Limiting Middlewares (Reverse addition order for ASGI stack)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(RequestIdMiddleware)

# 3. Mount Custom Exceptional Catcher Caches
register_error_handlers(app)

# 4. Associate Module Routes
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users"])
app.include_router(resellers_router, prefix="/api/v1/resellers", tags=["Resellers"])
app.include_router(clients_router, prefix="/api/v1/clients", tags=["Clients"])
app.include_router(agents_router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(conversations_router, prefix="/api/v1/conversations", tags=["Conversations"])
app.include_router(recordings_router, prefix="/api/v1/recordings", tags=["Recordings"])
app.include_router(transcripts_router, prefix="/api/v1/transcripts", tags=["Transcripts"])
app.include_router(audit_router, prefix="/api/v1/audit-logs", tags=["Audit"])
app.include_router(health_router, prefix="/api/v1/health", tags=["Health"])
app.include_router(billing_router, prefix="/api/v1/billing", tags=["Billing"])
app.include_router(finance_router, prefix="/api/v1", tags=["Finance"])

# Root-level health endpoint mount
app.include_router(health_router, prefix="/health", tags=["Health"])

# Mount sessions router (handles /sessions, /messages, etc.)
app.include_router(sessions_router, prefix="/api/v1", tags=["Sessions"])




if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )
