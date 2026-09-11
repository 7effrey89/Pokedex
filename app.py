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
from src.routes.realtime_socket_routes import init_realtime_socket_routes

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'pokedex-demo-session-secret-key-3289a')
CORS(app)
init_realtime_socket_routes(app)

# Persistent storage must exist before any blueprint touches the databases.
from src.config import PROJECT_ROOT, get_storage_paths
from src.db.database import UsersDatabase

_storage_paths = get_storage_paths()
_storage_paths.ensure_directories()


def _promote_packaged_seed_data() -> None:
    """Copy the image-baked catalog and Pokemon assets into an empty persistent root.

    Azure App Service starts persistent storage empty on first boot. Without
    this, a fresh /home/data has no catalog even though the image ships one.
    """
    if _storage_paths.data_root == PROJECT_ROOT:
        return
    if _storage_paths.catalog_database.is_file():
        return
    packaged_database = PROJECT_ROOT / "data" / "pokedex.sqlite3"
    if not packaged_database.is_file():
        return

    import shutil

    logger.info("Promoting packaged seed catalog into persistent storage: %s", _storage_paths.data_root)
    shutil.copy2(packaged_database, _storage_paths.catalog_database)
    packaged_assets = PROJECT_ROOT / "data" / "assets"
    if packaged_assets.is_dir():
        shutil.copytree(packaged_assets, _storage_paths.data_root / "data" / "assets", dirs_exist_ok=True)


_promote_packaged_seed_data()
UsersDatabase().initialize()

# Register blueprints
from src.routes import chat_bp, realtime_bp, tool_bp, cache_bp, face_bp, pokeapi_bp, tcg_image_bp, admin_bp, account_bp

app.register_blueprint(chat_bp)
app.register_blueprint(realtime_bp)
app.register_blueprint(tool_bp)
app.register_blueprint(cache_bp)
app.register_blueprint(face_bp)
app.register_blueprint(pokeapi_bp)
app.register_blueprint(tcg_image_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(account_bp)


@app.route('/')
@app.route('/pokemon/<path:subpath>')
@app.route('/tcg/<path:subpath>')
def index(subpath=None):
    """Serve the main page — SPA catch-all for client-side routing"""
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health():
    """
    Health check endpoint for container readiness/liveness probes.
    Returns quickly with minimal payload and proper headers.
    """
    response = jsonify({"status": "healthy", "service": "Pokemon Chat Demo"})
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('cache', exist_ok=True)
    
    # Run the app
    port = int(os.environ.get('PORT', 5050))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    # Threaded so one slow request (e.g. a cold metadata build) can't stall every other request.
    app.run(host='0.0.0.0', port=port, debug=debug_mode, threaded=True)
