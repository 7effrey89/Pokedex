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


def _sanitize_endpoint(value: str) -> str:
    endpoint = (value or '').strip().rstrip('/')

    project_marker = '/api/projects/'
    project_idx = endpoint.find(project_marker)
    if project_idx != -1:
        endpoint = endpoint[:project_idx]

    if endpoint.endswith('/openai'):
        endpoint = endpoint[:-len('/openai')]
    elif '/openai/' in endpoint:
        endpoint = endpoint.split('/openai/', 1)[0]

    return endpoint.rstrip('/')

# --- Authentication helpers ---------------------------------------------------

def _is_service_principal_mode() -> bool:
    return os.getenv("AZURE_AUTH_MODE", "key").strip().lower() == "service_principal"


_DEFAULT_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


def _get_token_provider():
    """Return a bearer-token provider using service-principal credentials."""
    from azure.identity import ClientSecretCredential, get_bearer_token_provider
    credential = ClientSecretCredential(
        tenant_id=os.getenv("AZURE_TENANT_ID", ""),
        client_id=os.getenv("AZURE_CLIENT_ID", ""),
        client_secret=os.getenv("AZURE_CLIENT_SECRET", ""),
    )
    scope = os.getenv("AZURE_TOKEN_SCOPE", _DEFAULT_TOKEN_SCOPE)
    return get_bearer_token_provider(credential, scope)

# ------------------------------------------------------------------------------


class AzureOpenAIChat:
    """Handles chat with Azure OpenAI using function calling for Pokemon tools"""
    
    def __init__(self):
        self.use_sp = _is_service_principal_mode()
        self.default_config = {
            "endpoint": _sanitize_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")),
            "api_key": os.getenv("AZURE_OPENAI_API_KEY", "") if not self.use_sp else "",
            "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4"),
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            "auth_mode": 'service_principal' if self.use_sp else 'api_key'
        }
        self.default_client: Optional[AzureOpenAI] = None
        self.conversation_history: Dict[str, List[Dict]] = {}
        
        # Tools and system prompt from shared registry (single source of truth)
        from src.tools.tool_definitions import get_tools_chat_completions_format, get_system_prompt_chat
        self.tools = get_tools_chat_completions_format()
        self.system_prompt = get_system_prompt_chat()

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

    def _update_canvas_context(self, user_id: str, context: str):
        """Update the canvas context system message in conversation history.
        Replaces any previous canvas context to keep history clean."""
        history = self.get_conversation_history(user_id)
        # Remove any previous canvas context message
        self.conversation_history[user_id] = [
            msg for msg in history
            if not (msg.get('role') == 'system' and msg.get('content', '').startswith('Canvas context:'))
        ]
        # Insert canvas context right after the system prompt
        history = self.get_conversation_history(user_id)
        history.insert(1, {
            "role": "system",
            "content": f"Canvas context: {context}"
        })
    
    def _get_client(self, override_config: Optional[Dict[str, str]] = None):
        cfg = (override_config or self.default_config).copy()
        cfg["endpoint"] = _sanitize_endpoint(cfg.get("endpoint") or "")
        has_api_key = bool(cfg.get("api_key"))
        auth_mode = str(cfg.get("auth_mode") or ('service_principal' if self.use_sp and not has_api_key else 'api_key')).strip().lower()

        # Determine whether to use service principal for this call:
        # - Prefer the explicit auth_mode when supplied
        # - Otherwise, use SP when globally enabled and no API key is present
        use_sp_for_call = auth_mode == 'service_principal'

        if use_sp_for_call:
            if not cfg.get("endpoint") or not cfg.get("deployment"):
                raise ValueError("Azure OpenAI credentials missing: endpoint and/or deployment")
        else:
            missing = [key for key in ("endpoint", "api_key", "deployment") if not cfg.get(key)]
            if missing:
                raise ValueError(f"Azure OpenAI credentials missing: {', '.join(missing)}")

        api_version = cfg.get("api_version") or "2024-10-21"

        if use_sp_for_call:
            token_provider = _get_token_provider()

            if override_config:
                client = AzureOpenAI(
                    azure_endpoint=cfg["endpoint"],
                    azure_ad_token_provider=token_provider,
                    api_version=api_version
                )
                return client, cfg["deployment"]

            if self.default_client is None:
                self.default_client = AzureOpenAI(
                    azure_endpoint=cfg["endpoint"],
                    azure_ad_token_provider=token_provider,
                    api_version=api_version
                )
            return self.default_client, cfg["deployment"]

        # Standard Azure OpenAI with API key
        if override_config:
            client = AzureOpenAI(
                azure_endpoint=cfg["endpoint"],
                api_key=cfg["api_key"],
                api_version=api_version
            )
            return client, cfg["deployment"]

        if self.default_client is None:
            self.default_client = AzureOpenAI(
                azure_endpoint=cfg["endpoint"],
                api_key=cfg["api_key"],
                api_version=api_version
            )
        return self.default_client, cfg["deployment"]

    def chat(self, message: str, user_id: str, tool_handlers: Dict[str, callable], client_config: Optional[Dict[str, str]] = None, canvas_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a message and get a response, potentially using tools
        
        Args:
            message: User's message
            user_id: User identifier for conversation tracking
            tool_handlers: Dict mapping tool names to handler functions
            canvas_context: Optional description of what the user is currently viewing
            
        Returns:
            Dict with response message and any tool data
        """
        # Inject canvas context so the LLM knows what the user is looking at
        if canvas_context:
            self._update_canvas_context(user_id, canvas_context)

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
            client, deployment = self._get_client(client_config)
            # First API call - may return tool calls
            response = client.chat.completions.create(
                model=deployment,
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
                        elif isinstance(tool_result, dict) and "_action" in tool_result:
                            # Frontend navigation/UI actions — collect them all
                            if "frontend_actions" not in result:
                                result["frontend_actions"] = []
                            result["frontend_actions"].append(tool_result)
                        
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
                final_response = client.chat.completions.create(
                    model=deployment,
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
            error_msg = self._format_user_facing_error(e)
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

    def _format_user_facing_error(self, error: Exception) -> str:
        raw_message = str(error)
        lowered = raw_message.lower()

        if 'permissiondenied' in lowered and 'chat/completions' in lowered:
            return (
                'The current Azure service principal can access realtime voice, but it is not allowed to use chat completions. '
                'Grant this principal a role on the target Azure AI Foundry or Azure OpenAI resource that includes '
                '`Microsoft.CognitiveServices/accounts/OpenAI/deployments/chat/completions/action`, '
                'or switch chat auth to an API key in Settings.'
            )

        if 'permissiondenied' in lowered or 'principal does not have access to api/operation' in lowered:
            return (
                'Azure accepted the request but denied this principal for the requested model operation. '
                'Check the role assignment for the configured service principal, or switch to API-key auth for chat.'
            )

        return raw_message


# Singleton instance
_azure_chat: Optional[AzureOpenAIChat] = None


def get_azure_chat() -> AzureOpenAIChat:
    """Get the singleton Azure OpenAI chat instance"""
    global _azure_chat
    if _azure_chat is None:
        _azure_chat = AzureOpenAIChat()
    return _azure_chat
