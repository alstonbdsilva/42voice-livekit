import logging
from typing import Optional, Tuple, Dict, Any
from livekit import api as lk_api
from config import get_settings

logger = logging.getLogger("voice-agent.api.phone_numbers.livekit_sip")

class LiveKitSipService:
    """Service to provision and manage LiveKit SIP Trunks and Dispatch Rules."""
    
    def __init__(self):
        self.settings = get_settings()
        
    def _get_client(self) -> Optional[lk_api.LiveKitAPI]:
        """Initialize the LiveKit API client."""
        url = self.settings.livekit_url
        api_key = self.settings.livekit_api_key
        api_secret = self.settings.livekit_api_secret
        
        if not url or not api_key or not api_secret:
            logger.warning("LiveKit API credentials are not fully configured. SIP operations will be simulated.")
            return None
            
        try:
            # LiveKitAPI needs a running loop, but is instantiated on demand
            return lk_api.LiveKitAPI(url, api_key, api_secret)
        except Exception as e:
            logger.error(f"Failed to initialize LiveKitAPI client: {e}")
            return None

    async def provision_inbound_trunk(
        self, 
        number: str, 
        name: str, 
        sip_config: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Provision a SIP Inbound Trunk and a Dispatch Rule in LiveKit.
        
        Args:
            number: The phone number in E.164 format.
            name: Friendly label for the trunk.
            sip_config: Dictionary containing username, password, proxy details.
            
        Returns:
            A tuple of (trunk_id, dispatch_rule_id, warning_message).
        """
        lk = self._get_client()
        if not lk:
            return (
                f"mock-trunk-{number.replace(' ', '')}", 
                f"mock-rule-{number.replace(' ', '')}", 
                "LiveKit client not initialized. Generated mock IDs."
            )
            
        try:
            # 1. Create Inbound Trunk
            logger.info(f"Registering Inbound SIP Trunk in LiveKit for number: {number}")
            auth_username = sip_config.get("authUsername", number)
            auth_password = sip_config.get("password", "")
            auth_realm = sip_config.get("domain", "")
            
            # Format number to remove spaces/symbols for standard registration
            clean_number = number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            
            # Format number variations to ensure it matches incoming carrier headers
            numbers_list = [clean_number]
            if clean_number.startswith("+"):
                no_plus = clean_number[1:]
                if no_plus not in numbers_list:
                    numbers_list.append(no_plus)
                # Add local NZ/AU zero-prefix fallback if country code is +64 or +61
                if clean_number.startswith("+64") and len(clean_number) > 3:
                    local_nz = "0" + clean_number[3:]
                    if local_nz not in numbers_list:
                        numbers_list.append(local_nz)
                elif clean_number.startswith("+61") and len(clean_number) > 3:
                    local_au = "0" + clean_number[3:]
                    if local_au not in numbers_list:
                        numbers_list.append(local_au)
            
            trunk_info = lk_api.SIPInboundTrunkInfo(
                name=f"Trunk - {name} ({number})",
                numbers=numbers_list,
                auth_username=auth_username,
                auth_password=auth_password,
                auth_realm=auth_realm
            )
            
            trunk_request = lk_api.CreateSIPInboundTrunkRequest(trunk=trunk_info)
            trunk_response = await lk.sip.create_inbound_trunk(trunk_request)
            trunk_id = trunk_response.sip_trunk_id
            logger.info(f"Successfully created LiveKit SIP Inbound Trunk: {trunk_id}")
            
            # 2. Create Dispatch Rule
            # Routes callers to individual rooms prefixed with "sip-"
            logger.info(f"Creating SIP Dispatch Rule in LiveKit for trunk: {trunk_id}")
            
            # Create a dispatch rule that generates individual rooms
            dispatch_rule = lk_api.SIPDispatchRule(
                dispatch_rule_individual=lk_api.SIPDispatchRuleIndividual(
                    room_prefix="sip-"
                )
            )
            
            dispatch_request = lk_api.CreateSIPDispatchRuleRequest(
                name=f"Rule - {name} ({number})",
                rule=dispatch_rule,
                trunk_ids=[trunk_id],
                inbound_numbers=numbers_list
            )
            
            dispatch_response = await lk.sip.create_sip_dispatch_rule(dispatch_request)
            dispatch_rule_id = dispatch_response.sip_dispatch_rule_id
            logger.info(f"Successfully created LiveKit SIP Dispatch Rule: {dispatch_rule_id}")
            
            await lk.aclose()
            return trunk_id, dispatch_rule_id, None
            
        except Exception as e:
            logger.error(f"LiveKit SIP provisioning failed for {number}: {e}", exc_info=True)
            # Try to close connection safely
            try:
                await lk.aclose()
            except:
                pass
            return (
                f"err-trunk-{number.replace(' ', '')}", 
                f"err-rule-{number.replace(' ', '')}", 
                f"LiveKit SIP provisioning failed: {str(e)}"
            )

    async def deprovision_inbound_trunk(
        self, 
        trunk_id: str, 
        dispatch_rule_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Delete a SIP Trunk and Dispatch Rule from LiveKit.
        """
        if trunk_id.startswith("mock-") or trunk_id.startswith("err-"):
            logger.info(f"Deprovision bypassed for simulated trunk: {trunk_id}")
            return True, None
            
        lk = self._get_client()
        if not lk:
            return True, "LiveKit client not initialized. Simulated deletion."
            
        try:
            # Delete Dispatch Rule
            if dispatch_rule_id:
                logger.info(f"Deleting LiveKit SIP Dispatch Rule: {dispatch_rule_id}")
                del_rule_req = lk_api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=dispatch_rule_id)
                await lk.sip.delete_sip_dispatch_rule(del_rule_req)
                
            # Delete Trunk
            if trunk_id:
                logger.info(f"Deleting LiveKit SIP Inbound Trunk: {trunk_id}")
                del_trunk_req = lk_api.DeleteSIPTrunkRequest(sip_trunk_id=trunk_id)
                await lk.sip.delete_sip_trunk(del_trunk_req)
                
            await lk.aclose()
            return True, None
        except Exception as e:
            logger.error(f"Failed to deprovision LiveKit SIP resources (Trunk={trunk_id}, Rule={dispatch_rule_id}): {e}")
            try:
                await lk.aclose()
            except:
                pass
            return False, str(e)

    async def get_sip_status(self) -> Dict[str, Any]:
        """
        Retrieve connection status, active trunks, and active dispatch rules from LiveKit.
        """
        lk = self._get_client()
        if not lk:
            return {
                "connected": False,
                "mode": "simulated",
                "trunks": [],
                "dispatch_rules": []
            }
            
        try:
            # 1. Fetch inbound trunks
            trunks_resp = await lk.sip.list_inbound_trunk(lk_api.ListSIPInboundTrunkRequest())
            trunks = []
            for item in trunks_resp.items:
                trunks.append({
                    "id": item.sip_trunk_id,
                    "name": item.name,
                    "numbers": list(item.numbers),
                })
                
            # 2. Fetch dispatch rules
            rules_resp = await lk.sip.list_dispatch_rule(lk_api.ListSIPDispatchRuleRequest())
            rules = []
            for rule_item in rules_resp.items:
                rules.append({
                    "id": rule_item.sip_dispatch_rule_id,
                    "name": rule_item.name,
                    "trunk_ids": list(rule_item.trunk_ids),
                })
                
            await lk.aclose()
            return {
                "connected": True,
                "mode": "live",
                "trunks": trunks,
                "dispatch_rules": rules
            }
        except Exception as e:
            logger.error(f"Failed to fetch LiveKit SIP status: {e}", exc_info=True)
            try:
                await lk.aclose()
            except:
                pass
            return {
                "connected": False,
                "mode": "error",
                "error": str(e),
                "trunks": [],
                "dispatch_rules": []
            }

# Global Instance
livekit_sip_service = LiveKitSipService()
