# Pokemon Chat - Mobile Demo

A real-time, mobile-friendly Pokemon chat assistant that allows users to ask questions and get instant responses about Pokemon with images and detailed information.

## Features

- 🎮 **Real-time Chat Interface** - Interactive chat with instant responses
- 📱 **Mobile-Optimized** - Responsive design tailored for mobile devices
- 🖼️ **Pokemon Images** - Official artwork and sprites
- 📊 **Detailed Information** - Stats, types, abilities, and descriptions
- 💬 **Natural Language** - Ask questions in plain English
- 🎤 **Voice Conversation** - Talk to the assistant using voice commands (NEW!)
- ⚡ **Fast Lookup** - Powered by PokeAPI for comprehensive Pokemon data
- 🎨 **Beautiful UI** - Modern, colorful design inspired by Pokemon

## Screenshots

The app features a clean, mobile-first design with:
- Gradient header with Pokemon branding
- Smooth chat bubbles for user and assistant messages
- Interactive Pokemon cards with images
- Type badges with official Pokemon colors
- Detailed stat displays with progress bars

## Technologies Used

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **API**: [PokeAPI](https://pokeapi.co/) for Pokemon data
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