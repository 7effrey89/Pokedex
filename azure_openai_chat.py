"""
Azure OpenAI Integration for Pokemon Chat
Uses LLM to understand natural language and call appropriate tools
"""
import os
import json
from typing import Optional, Dict, Any, List
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()


class AzureOpenAIChat:
    """Handles chat with Azure OpenAI using function calling for Pokemon tools"""
    
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-10-21"
        )
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        self.conversation_history: Dict[str, List[Dict]] = {}
        
        # Define the tools/functions available to the LLM
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_pokemon_info",
                    "description": "Get detailed information about a Pokemon including stats, types, abilities, and description. Use this when the user asks about a specific Pokemon's data, stats, or general information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pokemon_name": {
                                "type": "string",
                                "description": "The name or ID of the Pokemon to look up (e.g., 'pikachu', 'charizard', '25')"
                            }
                        },
                        "required": ["pokemon_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_pokemon_cards",
                    "description": "Search for Pokemon Trading Card Game (TCG) cards. Use this when the user asks about Pokemon cards, trading cards, TCG, card prices, or wants to see card images.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pokemon_name": {
                                "type": "string",
                                "description": "The Pokemon name to search cards for (e.g., 'pikachu', 'charizard')"
                            },
                            "card_type": {
                                "type": "string",
                                "description": "Filter by energy type: Fire, Water, Grass, Lightning, Psychic, Fighting, Darkness, Metal, Dragon, Fairy, Colorless",
                                "enum": ["Fire", "Water", "Grass", "Lightning", "Psychic", "Fighting", "Darkness", "Metal", "Dragon", "Fairy", "Colorless"]
                            },
                            "hp_min": {
                                "type": "integer",
                                "description": "Minimum HP filter (e.g., 100 for cards with at least 100 HP)"
                            },
                            "hp_max": {
                                "type": "integer",
                                "description": "Maximum HP filter"
                            },
                            "rarity": {
                                "type": "string",
                                "description": "Card rarity filter (e.g., 'Rare', 'Rare Holo', 'Common')"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pokemon_list",
                    "description": "Get a list of Pokemon. Use this when the user asks for a list, wants to see available Pokemon, or asks for random Pokemon suggestions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Number of Pokemon to return (default 10, max 50)",
                                "default": 10
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Starting position in the Pokemon list (for pagination)",
                                "default": 0
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_random_pokemon",
                    "description": "Get a random Pokemon. Use this when the user wants to discover a random Pokemon or says 'surprise me'.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_random_pokemon_from_region",
                    "description": "Get a random Pokemon from a specific region. Use when user asks for Pokemon from Kanto, Johto, Hoenn, Sinnoh, Unova, Kalos, Alola, Galar, or Paldea.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "region": {
                                "type": "string",
                                "description": "The Pokemon region (kanto, johto, hoenn, sinnoh, unova, kalos, alola, galar, paldea)",
                                "enum": ["kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "paldea"]
                            }
                        },
                        "required": ["region"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_random_pokemon_by_type",
                    "description": "Get a random Pokemon of a specific type. Use when user asks for a random Fire Pokemon, random Water Pokemon, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pokemon_type": {
                                "type": "string",
                                "description": "The Pokemon type",
                                "enum": ["normal", "fire", "water", "grass", "electric", "ice", "fighting", "poison", "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy"]
                            }
                        },
                        "required": ["pokemon_type"]
                    }
                }
<<<<<<< HEAD
=======
            },
            {
                "type": "function",
                "function": {
                    "name": "get_card_price",
                    "description": "Get pricing information for a specific Pokemon TCG card by ID. Card ID format is 'set-number' (e.g., 'sv3-25'). Returns TCGPlayer and Cardmarket prices.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "card_id": {
                                "type": "string",
                                "description": "Card ID in format 'set-number' (e.g., 'sv3-25', 'base1-4')"
                            }
                        },
                        "required": ["card_id"]
                    }
                }
>>>>>>> origin/copilot/add-mobile-chat-demo
            }
        ]
        
        self.system_prompt = """You are a friendly and knowledgeable Pokemon assistant. You help users learn about Pokemon, their stats, abilities, and trading cards.

You have access to tools to:
1. Look up Pokemon information (stats, types, abilities, descriptions) - use get_pokemon_info
2. Search Pokemon Trading Card Game (TCG) cards - use search_pokemon_cards
3. Get lists of Pokemon - use get_pokemon_list
4. Get a random Pokemon - use get_random_pokemon
5. Get a random Pokemon from a specific region (Kanto, Johto, etc.) - use get_random_pokemon_from_region
6. Get a random Pokemon of a specific type (Fire, Water, etc.) - use get_random_pokemon_by_type

Guidelines:
- Be enthusiastic about Pokemon!
- When users ask about a specific Pokemon by name, use get_pokemon_info
- When users ask about cards, trading cards, or TCG, use search_pokemon_cards
- When users ask for lists or suggestions, use get_pokemon_list
- When users want something random or say "surprise me", use get_random_pokemon
- When users ask for random Pokemon from a region like "random Kanto Pokemon", use get_random_pokemon_from_region
- When users ask for random Pokemon by type like "random Fire Pokemon", use get_random_pokemon_by_type
- If a user's request is ambiguous, ask for clarification
- Format your responses nicely with the data you receive
- If a tool returns no results, let the user know kindly and suggest alternatives
- Remember context from the conversation - if a user says "show me its cards" after asking about Pikachu, search for Pikachu cards

Keep responses concise but informative. Use emoji occasionally to be friendly! 🎮⚡"""

    def get_conversation_history(self, user_id: str) -> List[Dict]:
        """Get or initialize conversation history for a user"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = [
                {"role": "system", "content": self.system_prompt}
            ]
        return self.conversation_history[user_id]
    
    def add_message(self, user_id: str, role: str, content: str):
        """Add a message to conversation history"""
        history = self.get_conversation_history(user_id)
        history.append({"role": role, "content": content})
        
        # Keep history manageable (last 20 messages + system prompt)
        if len(history) > 21:
            self.conversation_history[user_id] = [history[0]] + history[-20:]
    
    def chat(self, message: str, user_id: str, tool_handlers: Dict[str, callable]) -> Dict[str, Any]:
        """
        Send a message and get a response, potentially using tools
        
        Args:
            message: User's message
            user_id: User identifier for conversation tracking
            tool_handlers: Dict mapping tool names to handler functions
            
        Returns:
            Dict with response message and any tool data
        """
        # Add user message to history
        self.add_message(user_id, "user", message)
        history = self.get_conversation_history(user_id)
        
        result = {
            "message": "",
            "pokemon_data": None,
            "tcg_data": None,
            "tool_calls": []
        }
        
        try:
            # First API call - may return tool calls
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=history,
                tools=self.tools,
                tool_choice="auto",
                max_completion_tokens=1000
            )
            
            assistant_message = response.choices[0].message
            
            # Check if the model wants to call tools
            if assistant_message.tool_calls:
                # Add assistant's message with tool calls to history
                history.append({
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                })
                
                # Process each tool call
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        function_args = {}
                    
                    result["tool_calls"].append({
                        "name": function_name,
                        "args": function_args
                    })
                    
                    # Execute the tool if handler exists
                    if function_name in tool_handlers:
                        try:
                            tool_result = tool_handlers[function_name](**function_args)
                        except Exception as tool_error:
                            print(f"Tool execution error for {function_name}: {tool_error}")
                            tool_result = {"error": str(tool_error)}
                        
                        # Store tool-specific data in result
                        if function_name == "get_pokemon_info":
                            result["pokemon_data"] = tool_result
                        elif function_name == "search_pokemon_cards":
                            result["tcg_data"] = tool_result
                        elif function_name in ["get_random_pokemon", "get_random_pokemon_from_region", "get_random_pokemon_by_type"]:
                            result["pokemon_data"] = tool_result
                        
                        # Add tool result to history
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result) if tool_result else "No results found"
                        })
                    else:
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"Tool {function_name} not available"
                        })
                
                # Second API call to get final response with tool results
                final_response = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=history,
                    max_completion_tokens=1000
                )
                
                result["message"] = final_response.choices[0].message.content or ""
                self.add_message(user_id, "assistant", result["message"])
            else:
                # No tool calls, just a regular response
                result["message"] = assistant_message.content or ""
                self.add_message(user_id, "assistant", result["message"])
                
        except Exception as e:
            error_msg = str(e)
            result["message"] = f"I'm sorry, I encountered an error: {error_msg}. Please try again!"
            print(f"Azure OpenAI error: {e}")
            
            # If we get a tool_calls error, clear conversation history to reset state
            if "tool_call" in error_msg.lower() or "tool_calls" in error_msg.lower():
                print(f"Clearing conversation history for user {user_id} due to tool_calls error")
                self.clear_history(user_id)
        
        return result
    
    def clear_history(self, user_id: str):
        """Clear conversation history for a user"""
        if user_id in self.conversation_history:
            self.conversation_history[user_id] = [
                {"role": "system", "content": self.system_prompt}
            ]


# Singleton instance
_azure_chat: Optional[AzureOpenAIChat] = None


def get_azure_chat() -> AzureOpenAIChat:
    """Get the singleton Azure OpenAI chat instance"""
    global _azure_chat
    if _azure_chat is None:
        _azure_chat = AzureOpenAIChat()
    return _azure_chat
