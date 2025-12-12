"""
Tool Manager for Pokemon Chat Application
Manages available tools and their enabled/disabled states
"""
import json
import os
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum


class ToolCategory(Enum):
    """Categories for organizing tools"""
    POKEMON_DATA = "pokemon_data"
    TRADING_CARDS = "trading_cards"
    UTILITIES = "utilities"
<<<<<<< HEAD
    IDENTIFICATION = "identification"
=======
>>>>>>> origin/copilot/add-mobile-chat-demo


@dataclass
class Tool:
    """Represents a tool that can be enabled/disabled"""
    id: str
    name: str
    description: str
    category: str
    icon: str
    enabled: bool = True
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ToolManager:
    """
    Manages tools for the Pokemon Chat application.
    Allows dynamic enabling/disabling of tools.
    """
    
    # Default tools configuration
    DEFAULT_TOOLS = {
        "pokeapi": Tool(
            id="pokeapi",
            name="PokeAPI (API)",
            description="Look up Pokemon game data including stats, types, abilities, and descriptions from PokeAPI",
            category=ToolCategory.POKEMON_DATA.value,
            icon="🎮",
            enabled=True
        ),
        "pokemon_tcg": Tool(
            id="pokemon_tcg",
            name="Pokemon TCG (API)",
            description="Search Pokemon Trading Card Game cards directly via the TCG API",
            category=ToolCategory.TRADING_CARDS.value,
            icon="🃏",
            enabled=True
        ),
<<<<<<< HEAD
        "pokemon_tcg_mcp": Tool(
            id="pokemon_tcg_mcp",
            name="Pokemon TCG (MCP)",
            description="Search Pokemon TCG cards via the MCP server - provides structured tool-based access",
            category=ToolCategory.TRADING_CARDS.value,
            icon="🔌",
            enabled=False
        ),
        "poke_mcp": Tool(
            id="poke_mcp",
            name="Poke MCP (MCP)",
            description="Get Pokemon data via MCP server - supports random Pokemon by region/type",
            category=ToolCategory.POKEMON_DATA.value,
            icon="🌍",
            enabled=False
        ),
        "face_identification": Tool(
            id="face_identification",
            name="Face Identification",
            description="Identify users in real-time using facial recognition. PRIVACY: Captures images from camera when speaking. Images processed locally on your server. Photos stored in profiles_pic directory. Disable anytime in settings.",
            category=ToolCategory.IDENTIFICATION.value,
            icon="👤",
            enabled=False
        ),
=======
        # NOTE: MCP server tools disabled - using direct APIs instead
        # "pokemon_tcg_mcp": Tool(
        #     id="pokemon_tcg_mcp",
        #     name="Pokemon TCG (MCP)",
        #     description="Search Pokemon TCG cards via the MCP server - provides structured tool-based access",
        #     category=ToolCategory.TRADING_CARDS.value,
        #     icon="🔌",
        #     enabled=False
        # ),
        # "poke_mcp": Tool(
        #     id="poke_mcp",
        #     name="Poke MCP (MCP)",
        #     description="Get Pokemon data via MCP server - supports random Pokemon by region/type",
        #     category=ToolCategory.POKEMON_DATA.value,
        #     icon="🌍",
        #     enabled=False
        # ),
>>>>>>> origin/copilot/add-mobile-chat-demo
    }
    
    def __init__(self, config_path: str = None):
        """
        Initialize the tool manager
        
        Args:
            config_path: Optional path to persist tool configuration
        """
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "tools_config.json")
        self.tools: Dict[str, Tool] = {}
        self._load_tools()
    
    def _load_tools(self):
        """Load tools from config file or use defaults"""
        # Start with default tools
        for tool_id, tool in self.DEFAULT_TOOLS.items():
            self.tools[tool_id] = Tool(**asdict(tool))
        
        # Override with saved config if exists
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    saved_config = json.load(f)
                    for tool_id, enabled in saved_config.items():
                        if tool_id in self.tools:
                            self.tools[tool_id].enabled = enabled
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading tools config: {e}")
    
    def _save_tools(self):
        """Save tool enabled states to config file"""
        try:
            config = {tool_id: tool.enabled for tool_id, tool in self.tools.items()}
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            print(f"Error saving tools config: {e}")
    
    def get_tool(self, tool_id: str) -> Optional[Tool]:
        """Get a specific tool by ID"""
        return self.tools.get(tool_id)
    
    def get_all_tools(self) -> List[Dict]:
        """Get all tools as a list of dictionaries"""
        return [tool.to_dict() for tool in self.tools.values()]
    
    def get_enabled_tools(self) -> List[Tool]:
        """Get only enabled tools"""
        return [tool for tool in self.tools.values() if tool.enabled]
    
    def get_enabled_tool_ids(self) -> List[str]:
        """Get IDs of enabled tools"""
        return [tool.id for tool in self.tools.values() if tool.enabled]
    
    def is_tool_enabled(self, tool_id: str) -> bool:
        """Check if a specific tool is enabled"""
        tool = self.tools.get(tool_id)
        return tool.enabled if tool else False
    
    def set_tool_enabled(self, tool_id: str, enabled: bool) -> bool:
        """
        Enable or disable a specific tool
        
        Args:
            tool_id: The tool identifier
            enabled: Whether to enable (True) or disable (False)
            
        Returns:
            True if successful, False if tool not found
        """
        if tool_id not in self.tools:
            return False
        
        self.tools[tool_id].enabled = enabled
        self._save_tools()
        return True
    
    def set_tools_enabled(self, tool_states: Dict[str, bool]) -> Dict[str, bool]:
        """
        Set multiple tools enabled/disabled at once
        
        Args:
            tool_states: Dict mapping tool_id to enabled state
            
        Returns:
            Dict showing which updates succeeded
        """
        results = {}
        for tool_id, enabled in tool_states.items():
            results[tool_id] = self.set_tool_enabled(tool_id, enabled)
        return results
    
    def reset_to_defaults(self):
        """Reset all tools to their default enabled states"""
        for tool_id, default_tool in self.DEFAULT_TOOLS.items():
            if tool_id in self.tools:
                self.tools[tool_id].enabled = default_tool.enabled
        self._save_tools()
    
    def register_tool(self, tool: Tool) -> bool:
        """
        Register a new tool
        
        Args:
            tool: The tool to register
            
        Returns:
            True if registered, False if already exists
        """
        if tool.id in self.tools:
            return False
        
        self.tools[tool.id] = tool
        self._save_tools()
        return True
    
    def get_tools_by_category(self, category: str) -> List[Tool]:
        """Get all tools in a specific category"""
        return [tool for tool in self.tools.values() if tool.category == category]
    
    def get_categories(self) -> List[Dict]:
        """Get all tool categories with their tools"""
        categories = {}
        for tool in self.tools.values():
            if tool.category not in categories:
                categories[tool.category] = {
                    "id": tool.category,
                    "name": tool.category.replace("_", " ").title(),
                    "tools": []
                }
            categories[tool.category]["tools"].append(tool.to_dict())
        
        return list(categories.values())


# Global tool manager instance
tool_manager = ToolManager()
