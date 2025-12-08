"""
MCP Client for Pokemon TCG Server
Communicates with the ptcg-mcp server via stdio transport
"""
import subprocess
import json
import os
import threading
import queue
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
            
            # Initialize the connection
            self._initialize()
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
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
                    break
                    
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    response = json.loads(line)
                    self.response_queue.put(response)
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON output from server: {line}")
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Error reading from server: {e}")
                break
    
    def _send_request(self, method: str, params: Dict[str, Any], timeout: float = 30.0) -> Optional[Dict]:
        """Send a JSON-RPC request and wait for response"""
        if not self.process or not self.process.stdin:
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
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            
            # Wait for response with matching ID
            start_id = self.request_id
            try:
                response = self.response_queue.get(timeout=timeout)
                if response.get("id") == start_id:
                    return response
            except queue.Empty:
                logger.error(f"Timeout waiting for response to {method}")
                return None
                
        except Exception as e:
            logger.error(f"Error sending request: {e}")
            return None
            
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
            
        self._initialized = False

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
        
        result = self.client.call_tool("pokemon-card-search", arguments)
        
        if result and "content" in result:
            for content in result["content"]:
                if content.get("type") == "text":
                    try:
                        return {"cards": json.loads(content["text"])}
                    except json.JSONDecodeError:
                        return {"message": content["text"]}
        
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
