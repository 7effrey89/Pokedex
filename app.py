"""
Flask backend for Pokemon Chat Demo
Provides API endpoints for real-time chat with Pokemon lookup capabilities

The app is organized using Flask blueprints by feature area:
- chat_routes: Chat and messaging
- realtime_routes: Realtime voice API
- tool_routes: Tool management
- cache_routes: Cache management
- face_routes: Face recognition
"""
import os
import logging
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Register blueprints
from src.routes import chat_bp, realtime_bp, tool_bp, cache_bp, face_bp, pokeapi_bp

app.register_blueprint(chat_bp)
app.register_blueprint(realtime_bp)
app.register_blueprint(tool_bp)
app.register_blueprint(cache_bp)
app.register_blueprint(face_bp)
app.register_blueprint(pokeapi_bp)


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health():
    """
    Health check endpoint for container readiness/liveness probes.
    Returns quickly with minimal payload and proper headers.
    """
    response = jsonify({"status": "healthy", "service": "Pokemon Chat Demo"})
    response.headers['Content-Type'] = 'application/json'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response, 200


if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('profiles_pic', exist_ok=True)
    os.makedirs('cache', exist_ok=True)
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
