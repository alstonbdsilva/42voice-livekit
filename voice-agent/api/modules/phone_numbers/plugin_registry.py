"""
Plugin Registry.
Manages plugin lifecycle and execution.
All plugins implement a common interface.
"""

import logging
from typing import Optional, Dict, Any, List, Callable
from uuid import UUID
from abc import ABC, abstractmethod
from api import database

logger = logging.getLogger("voice-agent.api.modules.phone_numbers.plugin_registry")


class PluginInterface(ABC):
    """Base interface for all plugins."""
    
    @abstractmethod
    async def execute(self, configuration: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute plugin.
        
        Returns:
        {
            "status": "success|failed",
            "result": any,
            "error": str or None,
            "execution_time_ms": int
        }
        """
        pass
    
    @abstractmethod
    def validate_configuration(self, configuration: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        pass


class GoogleCalendarPlugin(PluginInterface):
    """Google Calendar plugin."""
    
    async def execute(self, configuration: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Google Calendar lookup."""
        try:
            # Placeholder - implement with actual Google Calendar API
            return {
                "status": "success",
                "result": {"available_slots": []},
                "error": None,
                "execution_time_ms": 0
            }
        except Exception as e:
            return {
                "status": "failed",
                "result": None,
                "error": str(e),
                "execution_time_ms": 0
            }
    
    def validate_configuration(self, configuration: Dict[str, Any]) -> bool:
        """Validate Google Calendar configuration."""
        return "calendar_id" in configuration


class CalendlyPlugin(PluginInterface):
    """Calendly plugin."""
    
    async def execute(self, configuration: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Calendly lookup."""
        try:
            # Placeholder - implement with actual Calendly API
            return {
                "status": "success",
                "result": {"available_slots": []},
                "error": None,
                "execution_time_ms": 0
            }
        except Exception as e:
            return {
                "status": "failed",
                "result": None,
                "error": str(e),
                "execution_time_ms": 0
            }
    
    def validate_configuration(self, configuration: Dict[str, Any]) -> bool:
        """Validate Calendly configuration."""
        return "calendly_url" in configuration


class HubSpotPlugin(PluginInterface):
    """HubSpot CRM plugin."""
    
    async def execute(self, configuration: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HubSpot lookup."""
        try:
            # Placeholder - implement with actual HubSpot API
            return {
                "status": "success",
                "result": {"contact": {}},
                "error": None,
                "execution_time_ms": 0
            }
        except Exception as e:
            return {
                "status": "failed",
                "result": None,
                "error": str(e),
                "execution_time_ms": 0
            }
    
    def validate_configuration(self, configuration: Dict[str, Any]) -> bool:
        """Validate HubSpot configuration."""
        return "api_key" in configuration


class SalesforcePlugin(PluginInterface):
    """Salesforce CRM plugin."""
    
    async def execute(self, configuration: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Salesforce lookup."""
        try:
            # Placeholder - implement with actual Salesforce API
            return {
                "status": "success",
                "result": {"account": {}},
                "error": None,
                "execution_time_ms": 0
            }
        except Exception as e:
            return {
                "status": "failed",
                "result": None,
                "error": str(e),
                "execution_time_ms": 0
            }
    
    def validate_configuration(self, configuration: Dict[str, Any]) -> bool:
        """Validate Salesforce configuration."""
        return "instance_url" in configuration and "api_key" in configuration


class WebhookPlugin(PluginInterface):
    """Generic webhook plugin."""
    
    async def execute(self, configuration: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute webhook call."""
        try:
            # Placeholder - implement with actual HTTP call
            return {
                "status": "success",
                "result": {},
                "error": None,
                "execution_time_ms": 0
            }
        except Exception as e:
            return {
                "status": "failed",
                "result": None,
                "error": str(e),
                "execution_time_ms": 0
            }
    
    def validate_configuration(self, configuration: Dict[str, Any]) -> bool:
        """Validate webhook configuration."""
        return "url" in configuration


class PluginRegistry:
    """Registry for managing plugins."""
    
    _plugins: Dict[str, PluginInterface] = {
        "google_calendar": GoogleCalendarPlugin(),
        "calendly": CalendlyPlugin(),
        "hubspot": HubSpotPlugin(),
        "salesforce": SalesforcePlugin(),
        "webhook": WebhookPlugin(),
    }
    
    @staticmethod
    async def create_plugin(
        name: str,
        plugin_type: str,
        user_id: str,
        client_id: Optional[str] = None,
        description: Optional[str] = None,
        configuration: Optional[Dict] = None,
        is_active: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Create a new plugin instance."""
        try:
            query = """
                INSERT INTO plugins (name, plugin_type, description, configuration, is_active, user_id, client_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, name, plugin_type, description, configuration, is_active, created_at
            """
            
            rows = await database.query(
                query,
                [name, plugin_type, description, configuration, is_active,
                 UUID(user_id), UUID(client_id) if client_id else None]
            )
            
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error creating plugin: {e}")
            return None
    
    @staticmethod
    async def get_plugin(plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin details."""
        try:
            query = """
                SELECT id, name, plugin_type, description, configuration, is_active, created_at
                FROM plugins
                WHERE id = $1
            """
            
            rows = await database.query(query, [UUID(plugin_id)])
            return rows[0] if rows else None
            
        except Exception as e:
            logger.error(f"Error getting plugin: {e}")
            return None
    
    @staticmethod
    async def get_user_plugins(user_id: str) -> List[Dict[str, Any]]:
        """Get all plugins for a user."""
        try:
            query = """
                SELECT id, name, plugin_type, description, is_active, created_at
                FROM plugins
                WHERE user_id = $1
                ORDER BY created_at DESC
            """
            
            rows = await database.query(query, [UUID(user_id)])
            return rows if rows else []
            
        except Exception as e:
            logger.error(f"Error getting user plugins: {e}")
            return []
    
    @staticmethod
    async def execute_plugin(
        plugin_type: str,
        configuration: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a plugin by type."""
        try:
            plugin = PluginRegistry._plugins.get(plugin_type)
            
            if not plugin:
                return {
                    "status": "failed",
                    "result": None,
                    "error": f"Plugin type {plugin_type} not found",
                    "execution_time_ms": 0
                }
            
            # Validate configuration
            if not plugin.validate_configuration(configuration):
                return {
                    "status": "failed",
                    "result": None,
                    "error": f"Invalid configuration for plugin {plugin_type}",
                    "execution_time_ms": 0
                }
            
            # Execute plugin
            return await plugin.execute(configuration, context)
            
        except Exception as e:
            logger.error(f"Error executing plugin: {e}")
            return {
                "status": "failed",
                "result": None,
                "error": str(e),
                "execution_time_ms": 0
            }
    
    @staticmethod
    def register_plugin(plugin_type: str, plugin: PluginInterface) -> bool:
        """Register a custom plugin."""
        try:
            PluginRegistry._plugins[plugin_type] = plugin
            logger.info(f"Registered plugin: {plugin_type}")
            return True
        except Exception as e:
            logger.error(f"Error registering plugin: {e}")
            return False
    
    @staticmethod
    def get_registered_plugins() -> List[str]:
        """Get list of registered plugin types."""
        return list(PluginRegistry._plugins.keys())
