"""
Face Recognition Routes - Handle face identification endpoints
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

face_bp = Blueprint('face', __name__, url_prefix='/api/face')


@face_bp.route('/identify', methods=['POST'])
def identify_face():
    """
    Identify a user from a captured image using face recognition.
    
    Expects JSON: {"image": "base64_encoded_image"}
    Returns JSON: {
        "name": "person_name" or None,
        "confidence": float,
        "is_new_user": bool,
        "greeting_message": str or None,
        "error": str (optional)
    }
    """
    from src.tools.tool_manager import tool_manager
    
    try:
        # Check if face identification tool is enabled
        if not tool_manager.is_tool_enabled("face_identification"):
            return jsonify({
                "error": "Face identification is disabled. Enable it in the tools settings."
            }), 403

        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({"error": "Image data is required"}), 400

        base64_image = data['image']

        # Import face recognition service
        from src.services.face_recognition_service import get_face_recognition_service

        face_service = get_face_recognition_service()
        result = face_service.identify_face_from_base64(base64_image)

        if result is None:
            return jsonify({"error": "Failed to process image"}), 500

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in face identification: {e}")
        return jsonify({"error": str(e)}), 500


@face_bp.route('/status', methods=['GET'])
def get_face_recognition_status():
    """
    Get the status of the face recognition service.
    
    Returns JSON with loaded profiles and current configuration.
    """
    from src.tools.tool_manager import tool_manager
    
    try:
        if not tool_manager.is_tool_enabled("face_identification"):
            return jsonify({
                "enabled": False,
                "message": "Face identification is disabled"
            })

        from src.services.face_recognition_service import get_face_recognition_service

        face_service = get_face_recognition_service()
        status = face_service.get_status()
        status['enabled'] = True

        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting face recognition status: {e}")
        return jsonify({"error": str(e)}), 500


@face_bp.route('/reload', methods=['POST'])
def reload_face_profiles():
    """
    Reload face profiles from the profiles_pic directory.
    Useful when new profile pictures are added.
    
    Returns JSON with reload status.
    """
    from src.tools.tool_manager import tool_manager
    
    try:
        if not tool_manager.is_tool_enabled("face_identification"):
            return jsonify({
                "error": "Face identification is disabled"
            }), 403

        from src.services.face_recognition_service import get_face_recognition_service

        face_service = get_face_recognition_service()
        face_service.reload_profiles()
        status = face_service.get_status()

        return jsonify({
            "message": "Profiles reloaded successfully",
            "status": status
        })

    except Exception as e:
        logger.error(f"Error reloading face profiles: {e}")
        return jsonify({"error": str(e)}), 500


@face_bp.route('/reset', methods=['POST'])
def reset_current_user():
    """
    Reset the currently identified user.
    Next identification will trigger a greeting.
    
    Returns JSON with reset status.
    """
    from src.tools.tool_manager import tool_manager
    
    try:
        if not tool_manager.is_tool_enabled("face_identification"):
            return jsonify({
                "error": "Face identification is disabled"
            }), 403

        from src.services.face_recognition_service import get_face_recognition_service

        face_service = get_face_recognition_service()
        face_service.reset_current_user()

        return jsonify({
            "message": "Current user reset successfully"
        })

    except Exception as e:
        logger.error(f"Error resetting current user: {e}")
        return jsonify({"error": str(e)}), 500
