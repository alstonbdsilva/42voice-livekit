import json
import logging
import re
from typing import Dict, Any, Optional, Tuple
import redis

from config import get_settings
from api import database
from api.modules.phone_numbers.livekit_sip import livekit_sip_service
from api.utils.phone import normalize_phone_number

logger = logging.getLogger("voice-agent.api.phone_numbers.sync_service")

class PhoneSyncService:
    """
    Synchronization and caching service for phone numbers.
    Orchestrates LiveKit sync, Redis lookup caching, and configuration event bus.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self.in_memory_cache = {}  # Fallback in-memory cache
        self._init_redis()
        
    def _init_redis(self):
        """Initialize the Redis connection pool with fallback."""
        try:
            self.redis_client = redis.Redis.from_url(
                self.settings.redis_url, 
                decode_responses=True, 
                socket_connect_timeout=2
            )
            self.redis_client.ping()
            logger.info("Sync service Redis cache initialized successfully.")
        except Exception as e:
            logger.warning(f"Redis unavailable for sync service caching, using in-memory/DB fallback: {e}")
            self.redis_client = None

    def _get_clean_number(self, number: str) -> str:
        """Helper to normalize number to canonical E.164 cache key."""
        return normalize_phone_number(number)

    # --- Caching Layer (Database -> Redis Cache -> Runtime Resolver) ---

    def get_cached_lookup(self, number: str) -> Optional[Dict[str, Any]]:
        """Retrieve routing configuration from Redis cache or in-memory fallback."""
        clean_num = self._get_clean_number(number)
        if not self.redis_client:
            return self.in_memory_cache.get(clean_num)
        try:
            cache_key = f"phone_number:lookup:{clean_num}"
            data = self.redis_client.get(cache_key)
            if data:
                logger.info(f"Cache Hit for number: {clean_num}")
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to read from Redis cache: {e}")
        return self.in_memory_cache.get(clean_num)

    def set_cached_lookup(self, number: str, lookup_data: Dict[str, Any], ttl: int = 86400):
        """Cache routing configuration in Redis and in-memory fallback."""
        clean_num = self._get_clean_number(number)
        self.in_memory_cache[clean_num] = lookup_data
        if not self.redis_client:
            return
        try:
            cache_key = f"phone_number:lookup:{clean_num}"
            self.redis_client.set(cache_key, json.dumps(lookup_data), ex=ttl)
            logger.info(f"Cached lookup config for number: {clean_num}")
        except Exception as e:
            logger.warning(f"Failed to write to Redis cache: {e}")

    def invalidate_cache(self, number: str):
        """Clear cache keys for a phone number."""
        clean_num = self._get_clean_number(number)
        if clean_num in self.in_memory_cache:
            del self.in_memory_cache[clean_num]
            
        variations = [number.strip()]
        if clean_num.startswith("+"):
            variations.append(clean_num[1:])
            if clean_num.startswith("+64") and len(clean_num) > 3:
                variations.append(f"0{clean_num[3:]}")
            elif clean_num.startswith("+61") and len(clean_num) > 3:
                variations.append(f"0{clean_num[3:]}")
        for var in variations:
            if var in self.in_memory_cache:
                del self.in_memory_cache[var]

        if not self.redis_client:
            return
        try:
            cache_keys = [
                f"phone_number:lookup:{clean_num}",
                f"phone_number:lookup:{number.strip()}"
            ]
            if clean_num.startswith("+"):
                cache_keys.append(f"phone_number:lookup:{clean_num[1:]}")
                if clean_num.startswith("+64") and len(clean_num) > 3:
                    cache_keys.append(f"phone_number:lookup:0{clean_num[3:]}")
                elif clean_num.startswith("+61") and len(clean_num) > 3:
                    cache_keys.append(f"phone_number:lookup:0{clean_num[3:]}")
            
            for key in cache_keys:
                self.redis_client.delete(key)
            logger.info(f"Invalidated cache keys for number: {clean_num}")
        except Exception as e:
            logger.warning(f"Failed to invalidate Redis cache: {e}")

    # --- LiveKit & Provider Sync ---

    async def sync_livekit_sip(self, db_record: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Synchronize local configuration state to LiveKit.
        Creates or updates LiveKit SIP trunks and dispatch rules.
        """
        number = db_record["number"]
        name = db_record["name"] or f"{db_record['provider']} DID Line"
        status = db_record["status"]
        sip_config = db_record["sip_config"]
        if isinstance(sip_config, str):
            sip_config = json.loads(sip_config)
        sip_config = sip_config or {}
        
        trunk_id = db_record.get("lk_sip_trunk_id")
        rule_id = db_record.get("lk_sip_dispatch_rule_id")

        if status == "deleted":
            # Remove LiveKit SIP Trunk & Rules
            if trunk_id:
                logger.info(f"Deprovisioning LiveKit trunk {trunk_id} for soft-deleted number {number}")
                await livekit_sip_service.deprovision_inbound_trunk(trunk_id, rule_id)
            return None, None

        if status == "pending_sip" or status == "inactive":
            # If draft, do not provision yet
            return trunk_id, rule_id

        # Update or create LiveKit SIP Trunk
        if trunk_id and not trunk_id.startswith("mock-") and not trunk_id.startswith("err-"):
            # Update existing
            logger.info(f"Sync: Updating existing trunk {trunk_id} and rule {rule_id}")
            success, err = await livekit_sip_service.update_inbound_trunk(
                trunk_id=trunk_id,
                number=number,
                name=name,
                sip_config=sip_config
            )
            if success and rule_id:
                await livekit_sip_service.update_dispatch_rule(
                    dispatch_rule_id=rule_id,
                    trunk_id=trunk_id,
                    number=number,
                    name=name
                )
        else:
            # Create/Provision new
            logger.info(f"Sync: Creating/Provisioning trunk for number {number}")
            new_trunk_id, new_rule_id, warning = await livekit_sip_service.provision_inbound_trunk(
                number=number,
                name=name,
                sip_config=sip_config
            )
            if warning:
                logger.warning(f"LiveKit Provisioning warning for {number}: {warning}")
            trunk_id = new_trunk_id
            rule_id = new_rule_id

        return trunk_id, rule_id

    def validate_provider_credentials(self, provider: str, sip_config: Optional[Dict[str, Any]]) -> bool:
        """
        Validate provider SIP credentials structure before saving/syncing.
        """
        # Twilio does not require SIP registration credentials in LiveKit
        if provider == "Twilio":
            return True
            
        if not sip_config:
            # If no sip_config is provided, register validation warning/status
            return False
        
        # Check basic credentials
        auth_username = sip_config.get("authUsername")
        password = sip_config.get("password")
        domain = sip_config.get("domain")
        
        if not auth_username or not password or not domain:
            logger.warning(f"Invalid SIP credentials for provider {provider}. Missing username, password or domain.")
            return False
            
        return True

    # --- Event Bus (Configuration Changed Notification) ---

    def publish_configuration_changed(self, number: str, action: str):
        """Publish configuration changed event to Redis Pub/Sub."""
        clean_num = self._get_clean_number(number)
        
        # Get ISO formatted timestamp string
        import datetime
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        
        event_payload = {
            "event": "phone_configuration_changed",
            "action": action,
            "number": clean_num,
            "timestamp": now_str
        }
        
        # Invalidate local lookup cache first
        self.invalidate_cache(number)
        
        if self.redis_client:
            try:
                self.redis_client.publish("channel:config_changed", json.dumps(event_payload))
                logger.info(f"Published configuration_changed event for {clean_num} on event bus.")
            except Exception as e:
                logger.warning(f"Failed to publish event on Redis Pub/Sub event bus: {e}")

    # --- High-level Phone Configuration Service Orchestration ---

    async def synchronize_phone_number(self, phone_number_id: str, action: str = "update") -> Dict[str, Any]:
        """
        Main orchestration endpoint:
        Loads current db record -> syncs LiveKit -> updates database mappings -> invalidates cache -> publishes event.
        """
        # 1. Fetch current DB record
        rows = await database.query("SELECT * FROM phone_numbers WHERE id = $1", [phone_number_id])
        if not rows:
            raise ValueError(f"Phone number with ID {phone_number_id} not found in database.")
        
        record = rows[0]
        number = record["number"]
        
        # 2. Sync to LiveKit (trunk & dispatch rules)
        trunk_id, rule_id = await self.sync_livekit_sip(record)
        
        # 3. Update database mapping if trunk/rule ids were created/changed
        if trunk_id != record.get("lk_sip_trunk_id") or rule_id != record.get("lk_sip_dispatch_rule_id"):
            await database.query(
                """UPDATE phone_numbers 
                   SET lk_sip_trunk_id = $1, 
                       lk_sip_dispatch_rule_id = $2,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = $3""",
                [trunk_id, rule_id, phone_number_id]
            )
            
        # 4. Invalidate cache and publish sync event
        self.publish_configuration_changed(number, action)
        
        # Fetch updated record
        updated_rows = await database.query("SELECT * FROM phone_numbers WHERE id = $1", [phone_number_id])
        return updated_rows[0]

# Global instance
phone_sync_service = PhoneSyncService()
