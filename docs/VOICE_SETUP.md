# Voice Conversation Setup Guide

This guide explains how to use the voice conversation features, including the new **Azure OpenAI Realtime API** for true real-time voice conversations.

## Voice Mode Options

The app supports two voice modes:

1. **Azure OpenAI Realtime API** (Recommended) - True bidirectional audio streaming
2. **Browser Speech Recognition** (Fallback) - Uses Web Speech API

## Option 1: Azure OpenAI Realtime API (Recommended)

The Realtime API provides a true conversational experience with:
- Real-time audio streaming
- Natural voice output from Azure OpenAI
- Server-side voice activity detection
- Seamless turn-taking

### Prerequisites

1. Azure account with OpenAI service
2. A **gpt-4o-realtime-preview** or **gpt-realtime** model deployment
3. API key and endpoint

### Step 1: Deploy a Realtime Model

In Azure Portal:
1. Go to your Azure OpenAI resource
2. Navigate to **Deployments**
3. Click **Create new deployment**
4. Select **gpt-4o-realtime-preview** as the model
5. Name it (e.g., `gpt-realtime`)
6. Deploy

### Step 2: Configure Environment Variables

Add to your `.env` file:

```bash
# Existing variables
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_api_key_here

# Add this for Realtime API
AZURE_OPENAI_REALTIME_DEPLOYMENT=gpt-4o-realtime-preview
AZURE_OPENAI_REALTIME_API_VERSION=2024-10-01-preview
```

### Step 3: Test the Connection

1. Start your Flask app: `python app.py`
2. Open browser to `http://localhost:5000`
3. Click the **Voice** button in the header
4. You should see "Real-time voice mode activated!" message
5. Speak naturally - the AI will respond in real-time with audio

### How It Works

```
Browser (Mic) → WebSocket → Azure OpenAI Realtime API
                    ↓
              Voice Activity Detection
                    ↓
              Speech-to-Text (Whisper)
                    ↓
              GPT-4o Response Generation
                    ↓
              Text-to-Speech
                    ↓
Browser (Speaker) ← WebSocket ← Audio Stream
```

## Option 2: Browser Speech Recognition (Fallback)

If the Realtime API is not configured, the app automatically falls back to browser-based speech recognition.

### How to Use

1. **Click the "Voice" button** in the top-right corner
2. **Grant microphone permissions** when prompted
3. **Start speaking** your Pokemon query
4. The app will:
   - Display your spoken text as a message
   - Send the text to the chat API
   - Display the response
   - Speak the response using browser text-to-speech

### Browser Support

- ✅ Chrome/Edge (Chromium-based browsers)
- ✅ Safari (iOS and macOS)
- ❌ Firefox (limited support)

## Comparison

| Feature | Realtime API | Browser Fallback |
|---------|--------------|------------------|
| Voice Quality | High (Neural TTS) | Medium (Browser TTS) |
| Latency | Low (streaming) | Higher (request/response) |
| Natural Conversation | Yes | Limited |
| Works Offline | No | Partially |
| Voice Activity Detection | Server-side (accurate) | Client-side |
| Setup Required | Azure deployment | None |

## Troubleshooting

### "Realtime API not available" message

1. Check that `AZURE_OPENAI_REALTIME_DEPLOYMENT` is set in `.env`
2. Ensure the deployment name matches exactly
3. Verify your Azure OpenAI resource has the Realtime model deployed

### WebSocket connection fails

1. Check your Azure endpoint URL is correct
2. Verify the API key is valid
3. Ensure your firewall allows WebSocket connections

### No audio playback

1. Check browser audio permissions
2. Ensure your speakers/headphones are connected
3. Try clicking somewhere on the page first (browser autoplay policy)

### Microphone not working

1. Grant microphone permissions when prompted
2. Check your system microphone settings
3. Try a different browser

## Configuration Options

The Realtime API session can be customized in `realtime_chat.py`:

```python
def get_session_config():
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "voice": "alloy",  # Options: alloy, echo, shimmer
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,  # Voice detection sensitivity
                "silence_duration_ms": 500  # How long to wait after speech ends
            }
        }
    }
```

### Available Voices

- `alloy` - Neutral and balanced
- `echo` - Warm and expressive  
- `shimmer` - Clear and bright

### Turn Detection Options

- `threshold` (0.0-1.0): Voice activity detection sensitivity
- `prefix_padding_ms`: Audio to include before speech starts
- `silence_duration_ms`: How long to wait after speech ends before processing

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser                                   │
├─────────────────────────────────────────────────────────────────┤
│  RealtimeVoiceClient (realtime-voice.js)                        │
│  ├── AudioContext (capture/playback)                            │
│  ├── MediaStream (microphone)                                   │
│  └── WebSocket connection                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ WebSocket (wss://)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Azure OpenAI Realtime API                          │
├─────────────────────────────────────────────────────────────────┤
│  ├── Input: PCM16 audio @ 24kHz                                 │
│  ├── Speech Recognition (Whisper)                               │
│  ├── GPT-4o Response Generation                                 │
│  ├── Text-to-Speech (Neural voices)                             │
│  └── Output: PCM16 audio @ 24kHz                                │
└─────────────────────────────────────────────────────────────────┘
```

## Files Created/Modified

- `realtime_chat.py` - Backend configuration for Realtime API
- `static/js/realtime-voice.js` - WebSocket client for audio streaming
- `static/js/app.js` - Updated to use Realtime API when available
- `templates/index.html` - Added realtime-voice.js script
- `app.py` - Added `/api/realtime/config` and `/api/realtime/status` endpoints

## Resources

- [Azure OpenAI Realtime API Guide](https://learn.microsoft.com/en-us/azure/ai-services/openai/realtime-audio-quickstart)
- [Web Speech API Documentation](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)
