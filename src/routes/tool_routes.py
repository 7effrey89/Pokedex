"""
Tool Routes - Handle tool management endpoints
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

tool_bp = Blueprint('tool', __name__, url_prefix='/api/tools')


@tool_bp.route('', methods=['GET'])
def get_tools():
    """
    Get all available tools and their states
    
    Returns:
        JSON with list of all tools
    """
    from src.tools.tool_manager import tool_manager
    
    return jsonify({
        "tools": tool_manager.get_all_tools(),
        "categories": tool_manager.get_categories()
    })


@tool_bp.route('/<tool_id>', methods=['GET'])
def get_tool(tool_id):
    """
    Get a specific tool by ID
    
    Args:
        tool_id: The tool identifier
        
    Returns:
        JSON with tool data
    """
    from src.tools.tool_manager import tool_manager
    
    tool = tool_manager.get_tool(tool_id)
    if not tool:
        return jsonify({"error": f"Tool '{tool_id}' not found"}), 404
    return jsonify(tool.to_dict())


@tool_bp.route('/<tool_id>', methods=['PUT', 'PATCH'])
def update_tool(tool_id):
    """
    Update a tool's enabled state
    
    Args:
        tool_id: The tool identifier
        
    Expects JSON: {"enabled": true/false}
    Returns:
        JSON with updated tool data
    """
    from src.tools.tool_manager import tool_manager
    
    try:
        data = request.get_json()
        enabled = data.get('enabled')
        
        if enabled is None:
            return jsonify({"error": "enabled field is required"}), 400
        
        success = tool_manager.set_tool_enabled(tool_id, enabled)
        if not success:
            return jsonify({"error": f"Tool '{tool_id}' not found"}), 404
        
        tool = tool_manager.get_tool(tool_id)
        return jsonify(tool.to_dict())
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tool_bp.route('', methods=['PUT', 'PATCH'])
def update_tools():
    """
    Update multiple tools' enabled states at once
    
    Expects JSON: {"tool_states": {"tool_id": true/false, ...}}
    Returns:
        JSON with results
    """
    from src.tools.tool_manager import tool_manager
    
    try:
        data = request.get_json()
        tool_states = data.get('tool_states', {})
        
        if not tool_states:
            return jsonify({"error": "tool_states field is required"}), 400
        
        results = tool_manager.set_tools_enabled(tool_states)
        return jsonify({
            "results": results,
            "tools": tool_manager.get_all_tools()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tool_bp.route('/reset', methods=['POST'])
def reset_tools():
    """Reset all tools to their default states"""
    from src.tools.tool_manager import tool_manager
    
    tool_manager.reset_to_defaults()
    return jsonify({
        "message": "Tools reset to defaults",
        "tools": tool_manager.get_all_tools()
    })
