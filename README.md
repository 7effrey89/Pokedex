# Pokemon Chat - Mobile Demo

A real-time, mobile-friendly Pokemon chat assistant that allows users to ask questions and get instant responses about Pokemon with images and detailed information.

## 🚀 Quick Deploy to Azure

This app includes **Docker support** for seamless deployment to Azure App Service with native dependencies (face-recognition, dlib):

📦 **[Complete Deployment Guide →](docs/AZURE_DEPLOYMENT.md)**

**Quick Setup:**
1. Create Azure Container Registry (ACR)
2. Create Azure App Service (Linux Container)
3. Configure GitHub Secrets
4. Push to `main` - Auto-deploys via GitHub Actions!

**Why Docker?**
- ✅ Handles native dependencies (dlib, cmake, build-essential)
- ✅ Reliable face-recognition feature deployment
- ✅ Consistent builds across all environments
- ✅ One-command deployment

## Features

- 🎮 **Real-time Chat Interface** - Interactive chat with instant responses
- 📱 **Mobile-Optimized** - Responsive design tailored for mobile devices
- 🖼️ **Pokemon Images** - Official artwork and sprites
- 📊 **Detailed Information** - Stats, types, abilities, and descriptions
- 💬 **Natural Language** - Ask questions in plain English
- 🎤 **Voice Conversation** - Talk to the assistant using voice commands
- 👤 **Face Recognition** - Real-time user identification during voice conversations (NEW!)
- 🃏 **Trading Card Game** - Search and view Pokemon TCG cards with images (NEW!)
- 💡 **Card Context Awareness** - The assistant keeps track of the MCP card you have open and injects that card’s summary into every conversation so follow-ups can reference it directly
- 🛠️ **Tool Management** - Enable/disable features via settings modal (NEW!)
- ⚡ **Fast Lookup** - Powered by PokeAPI for comprehensive Pokemon data
- 🎨 **Beautiful UI** - Modern, colorful design inspired by Pokemon

## Screenshots

The app features a clean, mobile-first design with:
- Gradient header with Pokemon branding
- Smooth chat bubbles for user and assistant messages
- Interactive Pokemon cards with images
- Type badges with official Pokemon colors
- Detailed stat displays with progress bars
- TCG card grid with clickable card previews

## Technologies Used

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **APIs**: 
  - [PokeAPI](https://pokeapi.co/) for Pokemon game data
  - [Pokemon TCG API](https://pokemontcg.io/) for trading card data
- **Face Recognition**: face_recognition library (based on dlib)
- **Voice**: Web Speech API (Speech Recognition + Synthesis)
- **Styling**: Custom CSS with mobile-first responsive design
- **Architecture**: RESTful API with JSON responses

## PokeAPI Fair Use & Caching

- Every client-side Pokemon lookup now goes through the Flask proxy blueprint mounted at `/api/pokemon`. The proxy forwards to PokeAPI, writes the response through `CacheService`, and serves subsequent requests from disk so we comply with PokeAPI’s “locally cache resources whenever you request them” rule.
- Available proxy routes (all support `?refresh=1` to bypass the cache and pull fresh data):
   - `GET /api/pokemon/<name_or_id>` – core Pokemon payloads used by the grid, detail view, and evolution previews.
   - `GET /api/pokemon/species/<name_or_id>` – species metadata (entries, egg groups, evolution chain pointer).
   - `GET /api/pokemon/evolution-chain/<chain_id>` – deep evolution data.
   - `GET /api/pokemon/type/<type_name>` – damage relations for weakness calculations.
- The cache directory (`/cache`) keeps descriptive filenames; expiration defaults to 7 days but can be tuned in `cache/cache_config.json` or via the existing cache settings routes.
- Force-refresh actions in the UI invalidate both the chat tool cache (`get_pokemon`) and the new proxy caches by issuing `refresh=1` requests, so the next render picks up live data without manual file edits.
- Override the upstream host with the `POKEMON_API_URL` environment variable if you need to point at a mirror during development; the proxy uses that value for every outbound request.

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- **For face-recognition feature**: cmake, build-essential (Linux) or Xcode Command Line Tools (macOS)

### Setup

**Option 1: Docker (Recommended - includes all native dependencies)**

```bash
# Clone the repository
git clone https://github.com/7effrey89/Pokedex.git
cd Pokedex

# Build the Docker image
docker build -t pokedex-app .

# Run the container
docker run -p 8000:8000 --env-file .env pokedex-app

# Access at http://localhost:8000
```

**Option 2: Local Python Installation**

1. **Clone the repository**
   ```bash
   git clone https://github.com/7effrey89/Pokedex.git
   cd Pokedex
   ```

2. **Install system dependencies (for face-recognition)**
   
   **Ubuntu/Debian:**
   ```bash
   sudo apt-get update
   sudo apt-get install -y build-essential cmake libopenblas-dev liblapack-dev
   ```
   
   **macOS:**
   ```bash
   xcode-select --install
   brew install cmake
   ```

3. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   **Note:** On Windows, installing `dlib` (required by face-recognition) can be challenging. Consider using Docker or WSL2 for easier setup.

5. **Set up environment variables** (optional)
   ```bash
   cp .env.example .env
   # Edit .env if you want to add Azure OpenAI integration in the future
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

7. **Open in browser**
   - Navigate to `http://localhost:5000`
   - For mobile testing, use your local IP address (e.g., `http://192.168.1.100:5000`)

## Deploying to Azure App Service

You can host the entire experience on Azure Web Apps so the realtime chat, MCP tools, and camera scanner are available from anywhere.

### Docker + ACR Deployment (Recommended for Native Dependencies)

For reliable deployment with native dependencies like `face-recognition` (dlib, cmake), use Docker with Azure Container Registry:

📦 **See [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md) for comprehensive step-by-step instructions**

**Quick Overview:**
1. Create Azure Container Registry (ACR)
2. Create Azure App Service (Linux, Docker Container)
3. Configure GitHub Secrets (ACR credentials)
4. Push to `main` branch - GitHub Actions builds and deploys automatically

**Why Docker?**
- ✅ Handles native dependencies (dlib, cmake, build-essential)
- ✅ Consistent builds across environments
- ✅ Full control over system packages
- ✅ Reliable and reproducible deployments

### Manual Azure CLI Deployment (Alternative)

If you prefer manual deployment or don't need face recognition features:

### Prerequisites

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- An Azure subscription with permission to create App Service resources
- Python 3.11 locally (matches the runtime we deploy)

### 1. Prepare environment variables

Create or update a `.env` file with the secrets you want in production (Azure OpenAI keys, PokeAPI overrides, `POKEMON_TCG_API_KEY`, etc.). These values will be mirrored into App Service settings.

### 2. Log in and create Azure resources

> ℹ️ **Realtime voice relies on WebSockets.** Azure only enables WebSockets on Standard (S1) App Service plans and above, so choose at least `S1` for the deployment plan.

```bash
az login
RESOURCE_GROUP=pokedex-rg
LOCATION=swedencentral
APP_NAME=pokedex-chat

az group create --name $RESOURCE_GROUP --location $LOCATION
az appservice plan create \
   --name $APP_NAME-plan \
   --resource-group $RESOURCE_GROUP \
   --sku S1 \
   --is-linux
az webapp create \
   --resource-group $RESOURCE_GROUP \
   --plan $APP_NAME-plan \
   --name $APP_NAME \
   --runtime "PYTHON|3.11"
```

### 3. Push configuration to App Service

Mirror your `.env` contents (plus production-only values) into App Service settings:

```bash
az webapp config appsettings set \
   --resource-group $RESOURCE_GROUP \
   --name $APP_NAME \
   --settings \
      FLASK_ENV=production \
      FLASK_DEBUG=False \
      PORT=5000 \
      AZURE_OPENAI_ENDPOINT="https://<YourResource>.openai.azure.com/" \
      AZURE_OPENAI_API_KEY="<key>" \
      AZURE_OPENAI_DEPLOYMENT="gpt-5.1-chat" \
      AZURE_OPENAI_REALTIME_DEPLOYMENT="gpt-realtime" \
      AZURE_OPENAI_REALTIME_API_VERSION="2024-10-01-preview" \
      POKEMON_API_URL="https://pokeapi.co/api/v2" \
      POKEMON_TCG_API_KEY="<key>" \
      TCG_PAGE_SIZE=250 \
      APP_API_PASSWORD="PasswordExample" \
      USE_NATIVE_MCP=false \
      SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

Add any Azure OpenAI or MCP endpoints the same way. App settings become environment variables available to Flask when it starts.

### 4. Package and deploy the code

Create a clean build (exclude caches and local venvs) and push it with Zip Deploy:

**Linux / macOS**

```bash
zip -r pokedex.zip app.py src static templates \
         requirements.txt realtime_chat.py azure_openai_chat.py \
         tools_config.json data tcg-cache
```

**Windows (PowerShell)**

```powershell
Remove-Item pokedex.zip -ErrorAction SilentlyContinue
Compress-Archive -Path app.py,src,static,templates,data,tcg-cache, `
  azure_openai_chat.py,realtime_chat.py,requirements.txt,tools_config.json `
  -DestinationPath pokedex.zip
Get-Item pokedex.zip
```

After the archive exists locally, push it with Zip Deploy:

```bash
az webapp deploy \
   --resource-group "$RESOURCE_GROUP" \
   --name "$APP_NAME" \
   --src-path pokedex.zip \
   --type zip
```

```powershell
az webapp deploy --resource-group $env:RESOURCE_GROUP --name $env:APP_NAME --src-path "$PWD\pokedex.zip" --type zip
```

Azure's Oryx build system will automatically detect `requirements.txt`, create a virtual environment, and install all dependencies. Gunicorn starts automatically to serve the Flask application. Tail logs if you want to verify startup:

```bash
az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME
```

#### Option B — Deploy with GitHub Actions (CI/CD)

The repository includes `.github/workflows/deploy-azure-webapp.yml`, which automatically packages and deploys the app to Azure App Service. The workflow includes `requirements.txt` in the deployment, and Azure's Oryx build system handles dependency installation. To enable it:

1. **Download your publish profile** from the Azure Portal (`App Service → Deployment → Get publish profile`).
2. **Create the following GitHub Action repository secrets** in *Settings → Secrets and variables → Actions*:
   - `AZURE_WEBAPP_NAME` → the App Service name (e.g., `pokedex-chat`) - must match the name of the web app.
   - `AZURE_WEBAPP_PUBLISH_PROFILE` → paste the full contents of the downloaded publish profile XML.

3. Push to the `main` branch (default trigger) or run the workflow manually from the **Actions** tab using the *Run workflow* button. The optional `environment` input lets you tag runs as `production`, `staging`, etc.
4. Monitor the run logs to confirm the archive step and the `azure/webapps-deploy@v3` action succeed. When it finishes, the new build is live in App Service and Oryx has automatically installed all dependencies from `requirements.txt`.

> Tip: if deployment fails because of missing secrets or configuration, fix the issue and simply re-run the workflow from the failed run's page.

For more detailed information about the deployment process, see [docs/AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md).

Ask about any Pokemon using natural language:

- "Tell me about Pikachu"
- "Show me Charizard"
- "What is Mewtwo"
- "Find Bulbasaur"
- Just type a Pokemon name: "Eevee"

### Trading Card Game Queries (NEW! 🃏)

Search for Pokemon Trading Card Game cards:

- "Show me Pikachu cards"
- "Find Charizard TCG cards"
- "Search trading cards for Mewtwo"
- Click on any card to see full details including:
  - High-resolution card image
  - Attacks and abilities
  - HP and retreat cost
  - Format legality (Standard, Expanded, Unlimited)
  - Rarity and artist information

### Tool Management (NEW! 🛠️)

Click the **Tools** button in the header to manage available features:

1. **PokeAPI** 🎮 - Pokemon game data (stats, types, abilities)
2. **Pokemon TCG** 🃏 - Trading card search and display
3. **Face Identification** 👤 - Real-time user identification (NEW!)

Enable or disable tools based on your needs!

### Voice Conversation (NEW! 🎤)

Talk to the assistant using your voice:

1. **Click the "Voice" button** in the top-right corner of the header
2. **Allow microphone access** when prompted
3. **Speak your query** (e.g., "Tell me about Pikachu")
4. The assistant will:
   - Display your spoken message
   - Fetch Pokemon information
   - Show Pokemon cards with images
   - **Speak the response back to you!**

**Supported browsers**: Chrome, Edge, Safari (iOS/macOS)

For detailed setup and Azure OpenAI integration, see [VOICE_SETUP.md](VOICE_SETUP.md)

### Face Recognition (NEW! 👤)

Automatically identify users during voice conversations:

#### Setup

1. **Create profile pictures directory** (already created during installation)
   ```bash
   mkdir -p profiles_pic
   ```

2. **Add profile pictures**
   - Place photos in the `profiles_pic` directory
   - Filename (without extension) becomes the person's name
   - Examples: `John.jpg`, `Alice.png`, `Bob.jpeg`
   - Supported formats: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`

3. **Enable Face Identification**
   - Click the **Tools** button in the header
   - Toggle **Face Identification** to ON
   - Click **Save Changes**

#### How It Works

1. **When you start speaking** during a voice conversation:
   - The app captures an image from your camera
   - Compares it against photos in `profiles_pic`
   - Identifies who you are based on face matching

2. **Greeting behavior**:
   - **First time detected**: Greets you by name (e.g., "Hello, John! Nice to see you.")
   - **Same person continues**: No greeting (avoids repetition)
   - **New person starts speaking**: Greets the new person

3. **Privacy & Security**:
   - Photos are stored locally in `profiles_pic` (not committed to git)
   - Camera access only triggered during voice conversations when feature is enabled
   - Face comparison happens on your server, not sent to external services

#### Tips for Best Results

- Use clear, well-lit photos with a single face
- Front-facing photos work best
- Multiple photos per person (different angles) can improve recognition
- Keep filenames simple (e.g., `John.jpg` not `John_Smith_Photo_2023.jpg`)

#### Troubleshooting

**No greeting appears:**
- Check that Face Identification is enabled in Tools
- Verify profile pictures exist in `profiles_pic` directory
- Check browser console for error messages
- Ensure camera permissions are granted

**Wrong person identified:**
- Add more/better quality photos for accurate matching
- Ensure good lighting when using voice feature
- Remove similar-looking photos that might cause confusion

**Face not recognized:**
- Face might not be in `profiles_pic` - add a photo with your name
- Photo quality might be poor - use a clear, front-facing photo
- Camera angle might be bad - position yourself facing the camera

### Quick Actions

Use the quick action buttons for common tasks:
- **❓ Help** - Get information about what the bot can do
- **🎲 Random** - Get suggestions for Pokemon to explore
- **⭐ Popular** - See a list of popular Pokemon

### Viewing Details

- Click on any Pokemon image in the chat to see a detailed card
- The card includes:
  - High-resolution artwork
  - Full description
  - Type information
  - Height and weight
  - Abilities
  - Base stats with visual indicators

## API Endpoints

### Chat Endpoints

- `POST /api/chat` - Send a message and get a response
  ```json
  {
    "message": "Tell me about Pikachu",
    "user_id": "optional_user_id"
  }
  ```

- `POST /api/chat/stream` - Stream responses (Server-Sent Events)

### Pokemon Endpoints

- `GET /api/pokemon/<name_or_id>` - Get Pokemon data by name or ID
- `GET /api/history/<user_id>` - Get conversation history for a user
- `GET /api/health` - Health check endpoint

## Project Structure

```
Pokedex/
├── app.py                 # Flask application and routes
├── pokemon_tools.py       # Pokemon API integration
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── templates/
│   └── index.html        # Main HTML template
└── static/
    ├── css/
    │   └── style.css     # Responsive styles
    └── js/
        └── app.js        # Frontend JavaScript
```

## Future Enhancements

### Planned Features

1. **Azure OpenAI Integration** - Add real-time audio responses using Azure AI
2. **MCP Server Integration** - Connect to Pokemon Trading Card Game data
3. **Battle Simulator** - Compare Pokemon stats
4. **Team Builder** - Create and save Pokemon teams
5. **Progressive Web App (PWA)** - Offline support and installable app
6. **User Accounts** - Save conversation history and favorites
7. **Multi-language Support** - Pokemon data in different languages
8. **Voice Input** - Ask questions using voice commands

### Azure OpenAI Setup (Future)

To enable real-time audio responses:

1. Set up Azure OpenAI service
2. Add credentials to `.env`:
   ```
   AZURE_OPENAI_ENDPOINT=your_endpoint
   AZURE_OPENAI_API_KEY=your_key
   AZURE_OPENAI_DEPLOYMENT=your_deployment
   ```

3. The app is designed to integrate with:
   - [Azure OpenAI Realtime API](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/realtime-audio-quickstart)
   - [PTCG MCP Server](https://github.com/jlgrimes/ptcg-mcp)
   - [Poke MCP Server](https://github.com/NaveenBandarage/poke-mcp)

### MCP Server Setup

The app uses MCP (Model Context Protocol) servers to fetch Pokemon data. There are two modes:

#### Option 1: Client-Side Tool Handling (Default)

Set `USE_NATIVE_MCP=false` in `.env`. The Flask app handles tool calls via stdio transport. No additional setup needed - MCP servers are spawned automatically.

#### Option 2: Native MCP (HTTP/SSE Mode)

For native MCP support where the Realtime API calls MCP servers directly:

1. **Configure `.env`:**
   ```
   USE_NATIVE_MCP=true
   POKE_MCP_SERVER_URL=http://localhost:3001
   PTCG_MCP_SERVER_URL=http://localhost:3002
   ```

2. **Build MCP servers** (first time only):
   ```bash
   # Poke MCP
   cd poke-mcp
   npm install
   npm run build

   # PTCG MCP
   cd ../ptcg-mcp
   npm install
   npm run build
   ```

3. **Start MCP servers in HTTP mode** (open separate terminals):
   ```bash
   # Terminal 1 - Poke MCP (port 3001)
   cd poke-mcp
   node dist/index.js --http --port=3001

   # Terminal 2 - PTCG MCP (port 3002)
   cd ptcg-mcp
   node dist/index.js --http --port=3002
   ```

4. **Start Flask app** (third terminal):
   ```bash
   python app.py
   ```

**Note:** Native MCP requires the Realtime API to have network access to the MCP server URLs. For local development, both servers must be running before using voice features.

## Mobile Testing

### Testing on Mobile Devices

1. **Ensure devices are on the same network**
2. **Find your computer's IP address**
   - Windows: `ipconfig`
   - Mac/Linux: `ifconfig` or `ip addr`
3. **Access from mobile**
   - Navigate to `http://YOUR_IP:5000` on your mobile device
4. **Add to Home Screen** (iOS/Android)
   - Tap the share/menu button
   - Select "Add to Home Screen"
   - Opens like a native app!

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is open source and available under the MIT License.

## Acknowledgments

- [PokeAPI](https://pokeapi.co/) - The comprehensive Pokemon data API
- Pokemon is a trademark of Nintendo/Game Freak/Creatures Inc.
- This is a fan project and is not officially affiliated with Pokemon

## Support

If you encounter any issues or have questions:
1. Check the [Issues](https://github.com/7effrey89/Pokedex/issues) page
2. Create a new issue with details about your problem
3. Include your Python version and any error messages

## Credits

Developed as a mobile-friendly Pokemon chat demonstration with future integration capabilities for Azure OpenAI and MCP servers.