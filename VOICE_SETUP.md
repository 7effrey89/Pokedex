# Voice Conversation Setup Guide

This guide explains how to use the voice conversation feature and how to initialize real-time conversations with Azure OpenAI.

## Quick Start - Browser Voice Mode

The app now includes a built-in **Voice** button in the header that allows real-time voice conversations using your browser's native speech recognition.

### How to Activate Voice Conversation

1. **Click the "Voice" button** in the top-right corner of the header
2. **Grant microphone permissions** when prompted by your browser
3. **Start speaking** your Pokemon query (e.g., "Tell me about Pikachu")
4. The app will:
   - Display your spoken text as a message
   - Process the query and fetch Pokemon data
   - Show the Pokemon card with images and stats
   - **Speak the response back to you** using text-to-speech

### Visual Indicators

- **Inactive State**: White/transparent button with microphone icon
- **Active State**: Red button with pulsing animation and "Listening..." status
- **Processing**: "Online" status changes to show current state

### Browser Support

Voice mode works in:
- ✅ Chrome/Edge (Chromium-based browsers)
- ✅ Safari (iOS and macOS)
- ❌ Firefox (limited support)

If your browser doesn't support voice, the button will be hidden automatically.

## How It Works

### 1. Voice Input (Speech Recognition)
```javascript
// Browser's Speech Recognition API
const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
recognition.continuous = false;
recognition.lang = 'en-US';

recognition.onresult = (event) => {
  const transcript = event.results[0][0].transcript;
  // Process the spoken text
};
```

### 2. Pokemon Query Processing
```javascript
// Send to backend API
fetch('/api/chat', {
  method: 'POST',
  body: JSON.stringify({
    message: transcript,  // The spoken text
    user_id: userId
  })
})
```

### 3. Visual Display
The response includes structured Pokemon data:
```json
{
  "pokemon_data": {
    "name": "Pikachu",
    "image": "https://...",
    "types": ["electric"],
    "stats": { "hp": 35, "attack": 55, ... }
  }
}
```

### 4. Voice Output (Text-to-Speech)
```javascript
// Browser's Speech Synthesis API
const utterance = new SpeechSynthesisUtterance(responseText);
speechSynthesis.speak(utterance);
```

## Azure OpenAI Realtime API Integration

For production-grade real-time conversations with advanced AI capabilities, you can integrate Azure OpenAI's Realtime API.

### Prerequisites

1. Azure account with OpenAI service
2. Realtime API deployment
3. API key and endpoint

### Step 1: Set Environment Variables

Edit `.env` file:
```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_DEPLOYMENT=gpt-4o-realtime-preview
```

### Step 2: Install Azure SDK

Add to `requirements.txt`:
```
azure-ai-openai>=1.0.0b1
openai>=1.3.0
```

### Step 3: Backend Implementation

Create `realtime_handler.py`:

```python
import os
from openai import AzureOpenAI
from pokemon_tools import PokemonTools

class RealtimeHandler:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-10-01-preview"
        )
        self.pokemon_tools = PokemonTools()
    
    def process_audio_stream(self, audio_data):
        """Process incoming audio and return response"""
        # 1. Send audio to Azure OpenAI Realtime API
        response = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_data
        )
        
        text_input = response.text
        
        # 2. Detect Pokemon query
        pokemon_data = None
        if self.is_pokemon_query(text_input):
            pokemon_data = self.pokemon_tools.get_pokemon(
                self.extract_pokemon_name(text_input)
            )
        
        # 3. Generate AI response with function calling
        chat_response = self.client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            messages=[
                {"role": "system", "content": "You are a Pokemon expert assistant."},
                {"role": "user", "content": text_input}
            ],
            functions=[{
                "name": "get_pokemon_info",
                "description": "Get Pokemon information including stats and images",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Pokemon name"}
                    }
                }
            }]
        )
        
        return {
            "text": chat_response.choices[0].message.content,
            "pokemon_data": pokemon_data,
            "audio": self.text_to_speech(chat_response.choices[0].message.content)
        }
    
    def text_to_speech(self, text):
        """Convert text response to audio"""
        response = self.client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        return response.content
```

### Step 4: WebSocket Setup

Add to `requirements.txt`:
```
flask-socketio==5.3.0
python-socketio==5.10.0
```

Update `app.py`:
```python
from flask_socketio import SocketIO, emit
from realtime_handler import RealtimeHandler

socketio = SocketIO(app, cors_allowed_origins="*")
realtime_handler = RealtimeHandler()

@socketio.on('audio_stream')
def handle_audio_stream(data):
    """Handle incoming audio chunks from client"""
    try:
        result = realtime_handler.process_audio_stream(data['audio'])
        
        # Send back text response and Pokemon data
        emit('chat_response', {
            'message': result['text'],
            'pokemon_data': result['pokemon_data']
        })
        
        # Send back audio response
        emit('audio_response', {
            'audio': result['audio']
        })
    except Exception as e:
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
```

### Step 5: Frontend WebSocket Integration

Update `static/js/app.js`:

```javascript
// Add at the top
const socket = io();

class PokemonChatApp {
    constructor() {
        // ... existing code ...
        this.audioContext = new AudioContext();
        this.setupWebSocket();
    }
    
    setupWebSocket() {
        socket.on('chat_response', (data) => {
            this.addMessage('assistant', data.message, data.pokemon_data);
        });
        
        socket.on('audio_response', (data) => {
            this.playAudioResponse(data.audio);
        });
    }
    
    async startAzureVoiceConversation() {
        // Start recording audio
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        
        mediaRecorder.ondataavailable = (event) => {
            // Send audio chunks to server via WebSocket
            socket.emit('audio_stream', {
                audio: event.data,
                user_id: this.userId
            });
        };
        
        mediaRecorder.start(1000); // Send chunks every second
    }
    
    playAudioResponse(audioData) {
        // Play audio response from Azure
        const audio = new Audio();
        audio.src = URL.createObjectURL(new Blob([audioData]));
        audio.play();
    }
}
```

## Feature Comparison

| Feature | Browser Voice | Azure OpenAI Realtime |
|---------|--------------|---------------------|
| Speech Recognition | ✅ Built-in | ✅ Whisper (better quality) |
| Text-to-Speech | ✅ Built-in | ✅ Neural TTS (more natural) |
| Natural Language | ⚠️ Basic | ✅ Advanced GPT-4 |
| Latency | Fast | Moderate (network) |
| Cost | Free | Paid (per API call) |
| Setup | None | Azure account required |
| Offline Support | ✅ (recognition only) | ❌ Requires internet |

## Troubleshooting

### Browser Voice Mode

**Problem**: Voice button doesn't appear
- **Solution**: Use Chrome, Edge, or Safari. Firefox has limited support.

**Problem**: "Microphone access denied"
- **Solution**: Click the lock icon in the address bar and allow microphone access.

**Problem**: Voice recognition stops after one query
- **Solution**: This is expected. Click the voice button again to continue.

### Azure Integration

**Problem**: "Module not found: azure-ai-openai"
- **Solution**: Run `pip install azure-ai-openai openai`

**Problem**: "Authentication failed"
- **Solution**: Verify your API key and endpoint in `.env` file

**Problem**: High latency
- **Solution**: Consider using a closer Azure region or implementing audio buffering

## Next Steps

1. ✅ **Current**: Browser-based voice with Web Speech API
2. 🔄 **Phase 2**: Add WebSocket support for real-time streaming
3. 🔄 **Phase 3**: Integrate Azure OpenAI Realtime API
4. 🔄 **Phase 4**: Add MCP server tools (PTCG, Poke-MCP) for card data
5. 🔄 **Phase 5**: Implement conversation memory and context

## Resources

- [Web Speech API Documentation](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)
- [Azure OpenAI Realtime API Guide](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/realtime-audio-quickstart)
- [Flask-SocketIO Documentation](https://flask-socketio.readthedocs.io/)
- [PTCG MCP Server](https://github.com/jlgrimes/ptcg-mcp)
- [Poke MCP Server](https://github.com/NaveenBandarage/poke-mcp)
