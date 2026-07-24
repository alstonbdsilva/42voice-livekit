"""
Compliance Engine.
Manages recording consent, GDPR, HIPAA, and regional compliance.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.compliance_engine")


class ComplianceEngine:
    """Engine for managing compliance rules."""
    
    @staticmethod
    async def set_compliance_rule(
        tenant_id: str,
        country_code: Optional[str] = None,
        region: Optional[str] = None,
        consent_type: str = "one_party",
        recording_allowed: bool = True,
        emergency_calling_allowed: bool = True,
        gdpr_compliant: bool = False,
        hipaa_compliant: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Set compliance rule."""
        try:
            query = """
                INSERT INTO compliance_rules 
                (tenant_id, country_code, region, consent_type, recording_allowed,
                 emergency_calling_allowed, gdpr_compliant, hipaa_compliant)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (tenant_id, country_code, region) DO UPDATE
                SET consent_type = $4, recording_allowed = $5, emergency_calling_allowed = $6,
                    gdpr_compliant = $7, hipaa_compliant = $8, updated_at = CURRENT_TIMESTAMP
                RETURNING id, tenant_id, country_code, region, consent_type, created_at
            """
            
            rows = await database.query(
                query,
                [UUID(tenant_id), country_code, region, consent_type, recording_allowed,
                 emergency_calling_allowed, gdpr_compliant, hipaa_compliant]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error setting compliance rule: {e}")
            return None
    
    @staticmethod
    async def check_recording_allowed(
        tenant_id: str,
        country_code: Optional[str] = None,
        region: Optional[str] = None
    ) -> bool:
        """Check if recording is allowed."""
        try:
            query = """
                SELECT recording_allowed FROM compliance_rules
                WHERE tenant_id = $1
                AND (country_code = $2 OR country_code IS NULL)
                AND (region = $3 OR region IS NULL)
                ORDER BY country_code DESC, region DESC
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(tenant_id), country_code, region])
            
            if rows:
                return rows[0].get("recording_allowed", True)
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking recording allowed: {e}")
            return True
    
    @staticmethod
    async def check_emergency_calling_allowed(
        tenant_id: str,
        country_code: Optional[str] = None
    ) -> bool:
        """Check if emergency calling is allowed."""
        try:
            query = """
                SELECT emergency_calling_allowed FROM compliance_rules
                WHERE tenant_id = $1
                AND (country_code = $2 OR country_code IS NULL)
                ORDER BY country_code DESC
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(tenant_id), country_code])
            
            if rows:
                return rows[0].get("emergency_calling_allowed", True)
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking emergency calling allowed: {e}")
            return True
    
    @staticmethod
    async def get_consent_type(
        tenant_id: str,
        country_code: Optional[str] = None,
        region: Optional[str] = None
    ) -> str:
        """Get required consent type."""
        try:
            query = """
                SELECT consent_type FROM compliance_rules
                WHERE tenant_id = $1
                AND (country_code = $2 OR country_code IS NULL)
                AND (region = $3 OR region IS NULL)
                ORDER BY country_code DESC, region DESC
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(tenant_id), country_code, region])
            
            if rows:
                return rows[0].get("consent_type", "one_party")
            
            return "one_party"
            
        except Exception as e:
            logger.error(f"Error getting consent type: {e}")
            return "one_party"
    
    @staticmethod
    async def is_gdpr_compliant(tenant_id: str) -> bool:
        """Check if tenant is GDPR compliant."""
        try:
            query = """
                SELECT gdpr_compliant FROM compliance_rules
                WHERE tenant_id = $1
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(tenant_id)])
            
            if rows:
                return rows[0].get("gdpr_compliant", False)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking GDPR compliance: {e}")
            return False
    
    @staticmethod
    async def is_hipaa_compliant(tenant_id: str) -> bool:
        """Check if tenant is HIPAA compliant."""
        try:
            query = """
                SELECT hipaa_compliant FROM compliance_rules
                WHERE tenant_id = $1
                LIMIT 1
            """
            
            rows = await database.query(query, [UUID(tenant_id)])
            
            if rows:
                return rows[0].get("hipaa_compliant", False)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking HIPAA compliance: {e}")
            return False
