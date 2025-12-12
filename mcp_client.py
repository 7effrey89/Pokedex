"""
MCP Client for Pokemon TCG Server
Communicates with the ptcg-mcp server via stdio transport
"""
import subprocess
import json
import os
import threading
import queue
import time
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with MCP servers via stdio"""
    
    def __init__(self, server_command: List[str], cwd: Optional[str] = None):
        self.server_command = server_command
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self.response_queue = queue.Queue()
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        self._initialized = False
        
    def start(self) -> bool:
        """Start the MCP server process"""
        try:
            logger.info(f"Starting MCP server: {' '.join(self.server_command)}")
            self.process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            self.running = True
            self.reader_thread = threading.Thread(target=self._read_responses, daemon=True)
            self.reader_thread.start()
            
            # Start stderr reader for debugging
            self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
            self.stderr_thread.start()
            
            # Initialize the connection
            self._initialize()
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
    def _read_stderr(self):
        """Background thread to read stderr from the server for debugging"""
        while self.running and self.process and self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    logger.info(f"[MCP stderr] {line}")
            except Exception as e:
                if self.running:
                    logger.error(f"Error reading stderr: {e}")
                break
    
    def _initialize(self):
        """Send initialize request to server"""
        response = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "pokedex-client",
                "version": "1.0.0"
            }
        })
        
        if response:
            # Send initialized notification
            self._send_notification("notifications/initialized", {})
            self._initialized = True
            logger.info("MCP client initialized successfully")
        
    def _read_responses(self):
        """Background thread to read responses from the server"""
        while self.running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    logger.warning("[MCP] Server stdout closed (empty line)")
                    break
                    
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    response = json.loads(line)
                    # Check if full JSON logging is enabled via env var
                    full_json = os.environ.get('MCP_LOG_FULL_JSON', 'false').lower() == 'true'
                    if full_json:
                        try:
                            pretty = json.dumps(response, indent=2, ensure_ascii=False)
                            logger.info(f"[MCP] Received response id={response.get('id')}:\n{pretty}")
                        except Exception:
                            logger.info(f"[MCP] Received response id={response.get('id')}: {str(response)}")
                    else:
                        logger.info(f"[MCP] Received response id={response.get('id')}: {str(response)[:300]}...")
                    self.response_queue.put(response)
                except json.JSONDecodeError:
                    logger.info(f"[MCP] Non-JSON output from server: {line[:200]}")
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Error reading from server: {e}")
                break
    
    def _send_request(self, method: str, params: Dict[str, Any], timeout: float = 120.0) -> Optional[Dict]:
        """Send a JSON-RPC request and wait for response
        
        Note: Pokemon TCG API can be slow (60+ seconds), so we use a 120s timeout by default.
        """
        if not self.process or not self.process.stdin:
            logger.error("[MCP] Cannot send request - no process or stdin")
            return None
            
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }
        
        try:
            request_json = json.dumps(request) + "\n"
            logger.info(f"[MCP] Sending request: {request_json.strip()}")
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            
            # Wait for response with matching ID
            expected_id = self.request_id
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    remaining_timeout = timeout - (time.time() - start_time)
                    if remaining_timeout <= 0:
                        break
                    response = self.response_queue.get(timeout=min(remaining_timeout, 5.0))
                    response_id = response.get("id")
                    
                    if response_id == expected_id:
                        return response
                    else:
                        # Got a different response (possibly from an earlier timed-out request)
                        # Log it and continue waiting for our response
                        logger.warning(f"[MCP] Got response for id={response_id}, expected {expected_id}, discarding...")
                        
                except queue.Empty:
                    # Check if process is still running
                    if self.process.poll() is not None:
                        logger.error(f"[MCP] Server process died (exit code: {self.process.returncode})")
                        return None
                    # Continue waiting
                    continue
                    
            logger.error(f"[MCP] Timeout waiting for response to {method} (id={expected_id})")
            return None
                
        except Exception as e:
            logger.error(f"[MCP] Error sending request: {e}")
            return None
    
    def _send_notification(self, method: str, params: Dict[str, Any]):
        """Send a JSON-RPC notification (no response expected)"""
        if not self.process or not self.process.stdin:
            return
            
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        try:
            notification_json = json.dumps(notification) + "\n"
            self.process.stdin.write(notification_json)
            self.process.stdin.flush()
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict]:
        """Call a tool on the MCP server"""
        if not self._initialized:
            logger.error("MCP client not initialized")
            return None
            
        response = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if response and "result" in response:
            return response["result"]
        elif response and "error" in response:
            logger.error(f"Tool call error: {response['error']}")
            return {"error": response["error"]}
            
        return None
    
    def list_tools(self) -> List[Dict]:
        """List available tools on the MCP server"""
        if not self._initialized:
            return []
            
        response = self._send_request("tools/list", {})
        
        if response and "result" in response:
            return response["result"].get("tools", [])
            
        return []
    
    def stop(self):
        """Stop the MCP server process"""
        self.running = False
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        
        # Reset state for clean restart
        self._initialized = False
        self.request_id = 0
        # Clear the response queue to avoid ID mismatches after restart
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break

    def is_running(self) -> bool:
        """Check if the server process is running"""
        return self.process is not None and self.process.poll() is None


class PokemonTCGMCPClient:
    """High-level client for Pokemon TCG MCP server"""
    
    def __init__(self, mcp_server_path: str):
        self.mcp_server_path = mcp_server_path
        self.client: Optional[MCPClient] = None
        
    def start(self) -> bool:
        """Start the Pokemon TCG MCP server"""
        if self.client and self.client.is_running():
            return True
            
        # Use node to run the compiled JavaScript
        dist_path = os.path.join(self.mcp_server_path, "dist", "index.js")
        
        if not os.path.exists(dist_path):
            logger.error(f"MCP server not built. Run 'npm run build' in {self.mcp_server_path}")
            return False
            
        self.client = MCPClient(
            server_command=["node", dist_path],
            cwd=self.mcp_server_path
        )
        
        return self.client.start()
    
    def search_cards(
        self,
        name: Optional[str] = None,
        types: Optional[List[str]] = None,
        supertype: Optional[str] = None,
        subtypes: Optional[List[str]] = None,
        hp: Optional[str] = None,
        rarity: Optional[str] = None,
        artist: Optional[str] = None,
        set_id: Optional[str] = None,
        page_size: int = 20
    ) -> Dict:
        """Search for Pokemon TCG cards"""
        if not self.client or not self.client.is_running():
            if not self.start():
                return {"error": "Failed to start MCP server"}
        
        arguments = {}
        if name:
            arguments["name"] = name
            logger.info(f"[TCG] Adding name parameter: '{name}'")
        else:
            logger.warning(f"[TCG] WARNING: name parameter is empty/None!")
        if types:
            # MCP server expects types as a single string, not a list
            if isinstance(types, list):
                arguments["types"] = types[0] if types else None
            else:
                arguments["types"] = types
        if supertype:
            arguments["supertype"] = supertype
        if subtypes:
            # MCP server expects subtypes as a single string
            if isinstance(subtypes, list):
                arguments["subtypes"] = subtypes[0] if subtypes else None
            else:
                arguments["subtypes"] = subtypes
        if hp:
            arguments["hp"] = hp
        if rarity:
            arguments["rarity"] = rarity
        if artist:
            arguments["artist"] = artist
        if set_id:
            arguments["set"] = set_id
        arguments["pageSize"] = page_size
        
        logger.info(f"[TCG] Calling pokemon-card-search with args: {arguments}")
        result = self.client.call_tool("pokemon-card-search", arguments)
        logger.info(f"[TCG] Raw MCP response: {json.dumps(result, indent=2) if result else 'None'}")
        
        # If result is None, the server might have died - try restarting once
        if result is None:
            logger.warning("[TCG] Got None response, attempting server restart...")
            self.stop()
            time.sleep(0.5)  # Give the old process time to fully terminate
            if self.start():
                logger.info("[TCG] Server restarted successfully, waiting for initialization...")
                time.sleep(1.0)  # Give the server time to initialize
                logger.info("[TCG] Retrying call...")
                result = self.client.call_tool("pokemon-card-search", arguments)
                logger.info(f"[TCG] Retry MCP response: {json.dumps(result, indent=2) if result else 'None'}")
            else:
                logger.error("[TCG] Failed to restart server")
                return {"error": "Failed to restart MCP server"}
        
        if result and "content" in result:
            for content in result["content"]:
                if content.get("type") == "text":
                    text_content = content["text"]
                    logger.info(f"[TCG] Text content from MCP: {text_content[:500] if len(text_content) > 500 else text_content}")
                    try:
                        parsed = json.loads(text_content)
                        logger.info(f"[TCG] Parsed as JSON array with {len(parsed)} items")
                        return {"cards": parsed}
                    except json.JSONDecodeError:
                        logger.info(f"[TCG] Not JSON, returning as message")
                        return {"message": text_content}
        
        return result or {"error": "No response from server"}
    
    def get_card_price(self, card_id: str) -> Dict:
        """Get price information for a specific card"""
        if not self.client or not self.client.is_running():
            if not self.start():
                return {"error": "Failed to start MCP server"}
        
        result = self.client.call_tool("pokemon-card-price", {"cardId": card_id})
        
        if result and "content" in result:
            for content in result["content"]:
                if content.get("type") == "text":
                    try:
                        return json.loads(content["text"])
                    except json.JSONDecodeError:
                        return {"message": content["text"]}
        
        return result or {"error": "No response from server"}
    
    def stop(self):
        """Stop the MCP server"""
        if self.client:
            self.client.stop()
            self.client = None


# Singleton instance
_tcg_mcp_client: Optional[PokemonTCGMCPClient] = None


def get_tcg_mcp_client() -> PokemonTCGMCPClient:
    """Get the singleton Pokemon TCG MCP client"""
    global _tcg_mcp_client
    
    if _tcg_mcp_client is None:
        # Get the path to the ptcg-mcp folder relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mcp_server_path = os.path.join(current_dir, "ptcg-mcp")
        _tcg_mcp_client = PokemonTCGMCPClient(mcp_server_path)
    
    return _tcg_mcp_client


# ============= Poke MCP Client (Pokemon Data) =============

class PokeMCPClient:
    """Client for the poke-mcp server (Pokemon data from PokeAPI via MCP)"""
    
    def __init__(self, server_path: str):
        """
        Initialize the Poke MCP client
        
        Args:
            server_path: Path to the poke-mcp folder
        """
        self.server_path = server_path
        self.client: Optional[MCPClient] = None
        
    def _ensure_client(self) -> MCPClient:
        """Ensure the MCP client is started"""
        if self.client is None or not self.client.running:
            dist_path = os.path.join(self.server_path, "dist", "index.js")
            
            if not os.path.exists(dist_path):
                raise FileNotFoundError(
                    f"Poke MCP server not found at {dist_path}. "
                    f"Please run 'npm install && npm run build' in {self.server_path}"
                )
            
            self.client = MCPClient(
                server_command=["node", dist_path],
                cwd=self.server_path
            )
            
            if not self.client.start():
                raise RuntimeError("Failed to start Poke MCP server")
                
        return self.client
    
    def get_pokemon(self, name: str) -> Dict:
        """Get Pokemon information by name or ID"""
        try:
            client = self._ensure_client()
            result = client.call_tool("get-pokemon", {"name": name.lower()})
            return result
        except Exception as e:
            logger.error(f"Error getting Pokemon via MCP: {e}")
            return {"error": str(e)}
    
    def get_random_pokemon(self) -> Dict:
        """Get a random Pokemon"""
        try:
            client = self._ensure_client()
            result = client.call_tool("random-pokemon", {})
            return result
        except Exception as e:
            logger.error(f"Error getting random Pokemon via MCP: {e}")
            return {"error": str(e)}
    
    def get_random_pokemon_from_region(self, region: str) -> Dict:
        """Get a random Pokemon from a specific region"""
        try:
            client = self._ensure_client()
            result = client.call_tool("random-pokemon-from-region", {"region": region.lower()})
            return result
        except Exception as e:
            logger.error(f"Error getting random Pokemon from region via MCP: {e}")
            return {"error": str(e)}
    
    def get_random_pokemon_by_type(self, pokemon_type: str) -> Dict:
        """Get a random Pokemon of a specific type"""
        try:
            client = self._ensure_client()
            result = client.call_tool("random-pokemon-by-type", {"type": pokemon_type.lower()})
            return result
        except Exception as e:
            logger.error(f"Error getting random Pokemon by type via MCP: {e}")
            return {"error": str(e)}
    
    def close(self):
        """Close the MCP client connection"""
        if self.client:
            self.client.stop()
            self.client = None


# Singleton instance for Poke MCP
_poke_mcp_client: Optional[PokeMCPClient] = None


def get_poke_mcp_client() -> PokeMCPClient:
    """Get the singleton Poke MCP client"""
    global _poke_mcp_client
    
    if _poke_mcp_client is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mcp_server_path = os.path.join(current_dir, "poke-mcp")
        _poke_mcp_client = PokeMCPClient(mcp_server_path)
    
    return _poke_mcp_client


def get_pokemon_via_mcp(name: str) -> Dict:
    """Get Pokemon info using the Poke MCP server"""
    client = get_poke_mcp_client()
    return client.get_pokemon(name)


def get_random_pokemon_via_mcp() -> Dict:
    """Get a random Pokemon using the Poke MCP server"""
    client = get_poke_mcp_client()
    return client.get_random_pokemon()


def get_random_pokemon_from_region_via_mcp(region: str) -> Dict:
    """Get a random Pokemon from a region using the Poke MCP server"""
    client = get_poke_mcp_client()
    return client.get_random_pokemon_from_region(region)


def get_random_pokemon_by_type_via_mcp(pokemon_type: str) -> Dict:
    """Get a random Pokemon by type using the Poke MCP server"""
    client = get_poke_mcp_client()
    return client.get_random_pokemon_by_type(pokemon_type)


def search_tcg_cards(**kwargs) -> Dict:
    """Search for Pokemon TCG cards using the MCP server"""
    client = get_tcg_mcp_client()
    return client.search_cards(**kwargs)


def get_tcg_card_price(card_id: str) -> Dict:
    """Get price information for a Pokemon TCG card"""
    client = get_tcg_mcp_client()
    return client.get_card_price(card_id)


def format_cards_for_display(result: Dict) -> Dict:
    """Format card results for display in the UI"""
    if "error" in result:
        return result
    
    if "message" in result:
        return {"message": result["message"]}
    
    cards = result.get("cards", [])
    
    if not cards:
        return {"message": "No cards found matching your criteria."}
    
    formatted_cards = []
    for card in cards:
        formatted_card = {
            "id": card.get("id"),
            "name": card.get("name"),
            "supertype": card.get("supertype"),
            "subtypes": card.get("subtypes", []),
            "hp": card.get("hp"),
            "types": card.get("types", []),
            "set": card.get("set"),
            "rarity": card.get("rarity"),
            "artist": card.get("artist"),
            "image": card.get("image"),
            "imageLarge": card.get("imageLarge"),
            "tcgplayerUrl": card.get("tcgplayerUrl"),
            "attacks": card.get("attacks", [])
        }
        formatted_cards.append(formatted_card)
    
    return {
        "cards": formatted_cards,
        "count": len(formatted_cards)
    }
