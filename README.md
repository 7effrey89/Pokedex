# Pokemon Chat - Mobile Demo

A real-time, mobile-friendly Pokemon chat assistant that allows users to ask questions and get instant responses about Pokemon with images and detailed information.

## Features

- 🎮 **Real-time Chat Interface** - Interactive chat with instant responses
- 📱 **Mobile-Optimized** - Responsive design tailored for mobile devices
- 🖼️ **Pokemon Images** - Official artwork and sprites
- 📊 **Detailed Information** - Stats, types, abilities, and descriptions
- 💬 **Natural Language** - Ask questions in plain English
- 🎤 **Voice Conversation** - Talk to the assistant using voice commands
<<<<<<< HEAD
- 👤 **Face Recognition** - Real-time user identification during voice conversations (NEW!)
=======
>>>>>>> origin/copilot/add-mobile-chat-demo
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
<<<<<<< HEAD
- **Face Recognition**: face_recognition library (based on dlib)
=======
>>>>>>> origin/copilot/add-mobile-chat-demo
- **Voice**: Web Speech API (Speech Recognition + Synthesis)
- **Styling**: Custom CSS with mobile-first responsive design
- **Architecture**: RESTful API with JSON responses

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/7effrey89/Pokedex.git
   cd Pokedex
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables** (optional)
   ```bash
   cp .env.example .env
   # Edit .env if you want to add Azure OpenAI integration in the future
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Open in browser**
   - Navigate to `http://localhost:5000`
   - For mobile testing, use your local IP address (e.g., `http://192.168.1.100:5000`)

## Usage

### Basic Queries

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
<<<<<<< HEAD
3. **Face Identification** 👤 - Real-time user identification (NEW!)
=======
>>>>>>> origin/copilot/add-mobile-chat-demo

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

<<<<<<< HEAD
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

=======
>>>>>>> origin/copilot/add-mobile-chat-demo
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