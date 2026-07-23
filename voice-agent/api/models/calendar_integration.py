from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class CalendarIntegration(Base):
    """
    SQLAlchemy model representing the calendar_integrations table.
    Stores encrypted third-party credentials (like Calendly tokens) 
    associated with client organizations or specific user profiles.
    """
    __tablename__ = "calendar_integrations"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("uuid_generate_v4()")
    )
    client_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("clients.id", ondelete="CASCADE"), 
        nullable=True,
        unique=True # Unique per client organization for one provider (handled by unique constraint)
    )
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=True,
        unique=True # Unique per user account for one provider
    )
    provider = Column(String(50), nullable=False) # e.g., 'calendly'
    access_token = Column(String, nullable=False) # Cryptographically encrypted token
    refresh_token = Column(String, nullable=True) # Cryptographically encrypted refresh token
    event_type_url = Column(String(512), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.datetime.now(datetime.timezone.utc), 
        server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.datetime.now(datetime.timezone.utc), 
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
