/**
 * Azure OpenAI Realtime API WebSocket Client
 * Handles real-time voice conversation with bidirectional audio streaming
 */

class RealtimeVoiceClient {
    constructor(options = {}) {
        this.wsUrl = null;
        this.apiKey = null;
        this.ws = null;
        this.audioContext = null;
        this.playbackContext = null; // Separate context for playback
        this.mediaStream = null;
        this.audioWorklet = null;
        this.isConnected = false;
        this.isRecording = false;
        this.sessionConfig = null;
        this.tools = [];
        this.useNativeMcp = false; // If true, API handles tool calls automatically
        this.supportsImageInput = false; // If true, can send images to the conversation
        this.apiSettingsProvider = options.apiSettingsProvider || null;
        this.languagePreferenceProvider = options.languagePreferenceProvider || null;
        this.languagePreference = options.languagePreference || 'english';
        
        // Audio playback queue and buffering
        this.audioQueue = [];
        this.isPlaying = false;
        this.minBufferChunks = 3; // Wait for this many chunks before starting playback
        this.currentAudioSources = []; // Track active audio sources for cancellation
        this.currentResponseId = null; // Track current response for interruption
        this.isResponseActive = false; // Track if AI is currently responding
        this.audioBytesSent = 0; // Track bytes sent to avoid empty buffer commits
        this.minAudioBytesForCommit = 3200; // Minimum ~100ms at 16kHz 16-bit mono
        
        // Callbacks
        this.onStatusChange = options.onStatusChange || (() => {});
        this.onTranscript = options.onTranscript || (() => {});
        this.onResponse = options.onResponse || (() => {});
        this.onError = options.onError || (() => {});
        this.onAudioStart = options.onAudioStart || (() => {});
        this.onAudioEnd = options.onAudioEnd || (() => {});
        this.onToolCall = options.onToolCall || (() => {});
        this.onToolResult = options.onToolResult || (() => {});
        this.onSpeechStarted = options.onSpeechStarted || (() => {}); // Face recognition trigger
        this.onPlaybackLevel = options.onPlaybackLevel || (() => {});

        // Audio settings
        this.sampleRate = 24000; // Azure OpenAI Realtime uses 24kHz
        this.inputSampleRate = 16000;
        this.preferredVoice = options.preferredVoice || 'alloy';
        
        // Debug mode
        this.debug = options.debug || false;
    }
    
    log(...args) {
        if (this.debug) {
            console.log('[RealtimeVoice]', ...args);
        }
    }

    getLanguagePreference() {
        const allowed = ['english', 'danish', 'cantonese'];
        const rawValue = typeof this.languagePreferenceProvider === 'function'
            ? this.languagePreferenceProvider()
            : this.languagePreference;
        const normalized = (rawValue || 'english').toLowerCase();
        const selected = allowed.includes(normalized) ? normalized : 'english';
        this.languagePreference = selected;
        return selected;
    }
    
    /**
     * Initialize the client by fetching configuration from the server
     */
    async initialize() {
        try {
            this.onStatusChange('initializing', 'Checking realtime availability...');
            
            const apiSettings = typeof this.apiSettingsProvider === 'function'
                ? this.apiSettingsProvider()
                : null;

            if (!apiSettings) {
                throw new Error('Add API credentials in Settings to unlock realtime voice.');
            }

            const languagePreference = this.getLanguagePreference();

            const response = await fetch('/api/realtime/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_settings: apiSettings,
                    voice: this.preferredVoice,
                    language: languagePreference
                })
            });

            if (!response.ok) {
                const errorBody = await response.json().catch(() => ({}));
                throw new Error(errorBody.error || 'Realtime API not available');
            }
            const data = await response.json();
            
            if (!data.available) {
                throw new Error(data.error || 'Realtime API not available');
            }
            
            this.wsUrl = data.ws_url;
            this.apiKey = data.api_key;
            this.sessionConfig = data.session_config;
            this.tools = data.tools || [];
            this.useNativeMcp = data.use_native_mcp || false;
            this.supportsImageInput = data.supports_image_input || false;
            
            this.log('Configuration loaded:', { 
                wsUrl: this.wsUrl, 
                hasKey: !!this.apiKey,
                useNativeMcp: this.useNativeMcp,
                supportsImageInput: this.supportsImageInput
            });
            this.onStatusChange('ready', 'Realtime voice ready');
            
            return true;
        } catch (error) {
            this.log('Initialization error:', error);
            this.onError(error.message);
            this.onStatusChange('error', error.message);
            return false;
        }
    }
    
    /**
     * Connect to Azure OpenAI Realtime API via WebSocket
     */
    async connect() {
        if (this.isConnected) {
            this.log('Already connected');
            return true;
        }
        
        if (!this.wsUrl || !this.apiKey) {
            const initialized = await this.initialize();
            if (!initialized) return false;
        }
        
        return new Promise((resolve, reject) => {
            try {
                this.onStatusChange('connecting', 'Connecting to Azure OpenAI...');
                
                // Create WebSocket connection with API key header
                this.ws = new WebSocket(this.wsUrl, [], {
                    headers: {
                        'api-key': this.apiKey
                    }
                });
                
                // For browsers that don't support headers in WebSocket constructor
                // We'll use the URL parameter approach
                const wsUrlWithKey = `${this.wsUrl}&api-key=${this.apiKey}`;
                this.ws = new WebSocket(wsUrlWithKey);
                
                this.ws.onopen = () => {
                    this.log('WebSocket connected');
                    this.isConnected = true;
                    this.onStatusChange('connected', 'Connected to Azure OpenAI');
                    
                    // Send session configuration
                    this.sendSessionConfig();
                    
                    resolve(true);
                };
                
                this.ws.onmessage = (event) => {
                    this.handleMessage(event.data);
                };
                
                this.ws.onerror = (error) => {
                    this.log('WebSocket error:', error);
                    this.onError('WebSocket connection error');
                    this.onStatusChange('error', 'Connection error');
                    reject(error);
                };
                
                this.ws.onclose = (event) => {
                    this.log('WebSocket closed:', event.code, event.reason);
                    this.isConnected = false;
                    this.isRecording = false;
                    this.onStatusChange('disconnected', 'Disconnected');
                };
                
            } catch (error) {
                this.log('Connection error:', error);
                this.onError(error.message);
                reject(error);
            }
        });
    }
    
    /**
     * Send session configuration after connection
     */
    sendSessionConfig() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        const sourceConfig = this.sessionConfig ? JSON.parse(JSON.stringify(this.sessionConfig)) : null;
        const config = sourceConfig || {
            type: "session.update",
            session: {
                modalities: ["text", "audio"],
                instructions: "You are PokéChat, a friendly Pokemon assistant. Keep responses conversational and concise.",
                voice: this.preferredVoice || "alloy",
                input_audio_format: "pcm16",
                output_audio_format: "pcm16",
                turn_detection: {
                    type: "server_vad",
                    threshold: 0.5,
                    prefix_padding_ms: 300,
                    silence_duration_ms: 500
                }
            }
        };
        
        config.session = config.session || {};
        config.session.voice = this.preferredVoice || config.session.voice || 'alloy';

        // Add tools if available
        if (this.tools.length > 0) {
            config.session.tools = this.tools;
            config.session.tool_choice = "auto";
        }
        
        this.sessionConfig = config;
        this.log('Sending session config:', config);
        this.ws.send(JSON.stringify(config));
    }

    setVoicePreference(voice) {
        if (!voice) {
            return;
        }
        this.preferredVoice = voice;
        if (this.sessionConfig?.session) {
            this.sessionConfig.session.voice = voice;
        }

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const payload = {
                type: 'session.update',
                session: { voice }
            };
            try {
                this.ws.send(JSON.stringify(payload));
                this.log('Voice updated to', voice);
                this.sendSessionConfig();
            } catch (error) {
                this.log('Error sending voice update:', error);
            }
        }
    }

    async playVoicePreview(voiceName) {
        const targetVoice = voiceName || this.preferredVoice || 'alloy';
        this.setVoicePreference(targetVoice);

        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.log('Cannot play voice preview - WebSocket not connected');
            return false;
        }

        const displayName = targetVoice.charAt(0).toUpperCase() + targetVoice.slice(1);
        const prompt = `Say only: Hi! This is the ${displayName} voice.`;

        try {
            this.ws.send(JSON.stringify({
                type: 'conversation.item.create',
                item: {
                    type: 'message',
                    role: 'user',
                    content: [
                        {
                            type: 'input_text',
                            text: prompt
                        }
                    ]
                }
            }));

            this.ws.send(JSON.stringify({ type: 'response.create' }));
            return true;
        } catch (error) {
            this.log('Voice preview error:', error);
            return false;
        }
    }
    
    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            this.log('Received message:', message.type);
            
            switch (message.type) {
                case 'session.created':
                    this.log('Session created:', message.session);
                    this.onStatusChange('session_ready', 'Session ready - you can speak now');
                    break;
                    
                case 'session.updated':
                    this.log('Session updated:', message.session);
                    break;
                    
                case 'input_audio_buffer.speech_started':
                    this.log('Speech detected - interrupting AI');
                    this.onStatusChange('listening', 'Listening...');
                    // Interrupt any ongoing AI response
                    this.cancelCurrentResponse();
                    // Trigger face recognition callback
                    this.onSpeechStarted();
                    break;
                    
                case 'input_audio_buffer.speech_stopped':
                    this.log('Speech stopped');
                    this.onStatusChange('processing', 'Processing...');
                    break;
                    
                case 'conversation.item.input_audio_transcription.completed':
                    this.log('User transcript:', message.transcript);
                    this.onTranscript(message.transcript, 'user');
                    break;
                    
                case 'response.audio_transcript.delta':
                    // Partial transcript of AI response
                    this.onResponse(message.delta, true);
                    break;
                    
                case 'response.audio_transcript.done':
                    // Complete transcript of AI response
                    this.log('AI response transcript:', message.transcript);
                    this.onResponse(message.transcript, false);
                    break;
                    
                case 'response.audio.delta':
                    // Audio chunk from AI
                    this.handleAudioChunk(message.delta);
                    break;
                    
                case 'response.audio.done':
                    this.log('Audio response complete');
                    this.onAudioEnd();
                    break;
                    
                case 'response.function_call_arguments.done':
                    // Only handle tool calls client-side if NOT using native MCP
                    // With native MCP, the API handles tool calls automatically
                    if (!this.useNativeMcp) {
                        this.log('Tool call (client-handled):', message.name, message.arguments);
                        this.handleToolCall(message);
                    } else {
                        // Native MCP - API handles it, but we still notify the UI
                        this.log('Tool call (native MCP):', message.name, '- handled by API');
                        const args = JSON.parse(message.arguments || '{}');
                        this.onToolCall(message.name, args);
                        
                        // Set a timeout to warn if native MCP seems stuck
                        this.nativeMcpTimeout = setTimeout(() => {
                            this.log('Warning: Native MCP tool call may be stuck or unsupported');
                            this.onToolResult(message.name, args, { 
                                warning: 'Native MCP may not be supported. Try setting USE_NATIVE_MCP=false in .env' 
                            }, false);
                        }, 15000); // 15 second timeout warning
                    }
                    break;
                    
                case 'response.done':
                    this.log('Response complete');
                    this.isResponseActive = false;
                    // Clear native MCP timeout if set
                    if (this.nativeMcpTimeout) {
                        clearTimeout(this.nativeMcpTimeout);
                        this.nativeMcpTimeout = null;
                    }
                    this.onStatusChange('ready', 'Ready');
                    break;
                
                case 'response.cancelled':
                    this.log('Response was cancelled (interrupted)');
                    this.isResponseActive = false;
                    // Clear native MCP timeout if set
                    if (this.nativeMcpTimeout) {
                        clearTimeout(this.nativeMcpTimeout);
                        this.nativeMcpTimeout = null;
                    }
                    this.onStatusChange('ready', 'Ready');
                    break;
                
                case 'response.created':
                    this.log('Response started');
                    this.isResponseActive = true;
                    break;
                    
                case 'error':
                    // Ignore "no active response" errors from cancellation attempts
                    const errorMsg = message.error?.message || 'Unknown error';
                    if (errorMsg.includes('no active response')) {
                        this.log('Ignoring cancellation error (no active response)');
                    } else {
                        this.log('Error:', message.error);
                        this.onError(errorMsg);
                    }
                    break;
                    
                default:
                    this.log('Unhandled message type:', message.type);
            }
        } catch (error) {
            this.log('Error parsing message:', error);
        }
    }
    
    /**
     * Handle audio chunks from the AI response
     */
    handleAudioChunk(base64Audio) {
        if (!base64Audio) return;
        
        try {
            // Decode base64 audio
            const binaryString = atob(base64Audio);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            
            // Convert to Int16Array (PCM16)
            const int16Array = new Int16Array(bytes.buffer);
            
            // Queue for playback
            this.audioQueue.push(int16Array);
            
            // Start playback when we have enough buffered (reduces stuttering)
            if (!this.isPlaying && this.audioQueue.length >= this.minBufferChunks) {
                this.onAudioStart();
                this.playAudioQueueSmooth();
            }
        } catch (error) {
            this.log('Error processing audio chunk:', error);
        }
    }
    
    /**
     * Play queued audio chunks with smooth continuous playback
     * Uses scheduled playback to eliminate gaps between chunks
     */
    async playAudioQueueSmooth() {
        if (this.isPlaying) return;
        
        this.isPlaying = true;
        
        if (!this.playbackContext) {
            this.playbackContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate
            });
        }
        
        // Resume if suspended
        if (this.playbackContext.state === 'suspended') {
            await this.playbackContext.resume();
        }
        
        // Track when next audio should start (for gapless playback)
        let nextStartTime = this.playbackContext.currentTime + 0.05; // Small initial delay
        
        const processQueue = async () => {
            while (this.audioQueue.length > 0 || this.isPlaying) {
                if (this.audioQueue.length === 0) {
                    // Wait a bit for more audio to arrive
                    await new Promise(resolve => setTimeout(resolve, 50));
                    
                    // If still empty after waiting, we're done
                    if (this.audioQueue.length === 0) {
                        break;
                    }
                }
                
                // Combine multiple small chunks for smoother playback
                const chunksToPlay = [];
                let totalSamples = 0;
                const maxSamplesPerBuffer = this.sampleRate * 0.5; // Max 500ms per buffer
                
                while (this.audioQueue.length > 0 && totalSamples < maxSamplesPerBuffer) {
                    const chunk = this.audioQueue.shift();
                    chunksToPlay.push(chunk);
                    totalSamples += chunk.length;
                }
                
                if (chunksToPlay.length === 0) continue;
                
                // Combine chunks into single buffer
                const combinedArray = new Float32Array(totalSamples);
                let offset = 0;
                for (const chunk of chunksToPlay) {
                    for (let i = 0; i < chunk.length; i++) {
                        combinedArray[offset + i] = chunk[i] / 32768.0;
                    }
                    offset += chunk.length;
                }

                // Estimate playback energy for visualizers
                let rms = 0;
                if (totalSamples > 0) {
                    let sumSquares = 0;
                    for (let i = 0; i < totalSamples; i++) {
                        const sample = combinedArray[i];
                        sumSquares += sample * sample;
                    }
                    rms = Math.sqrt(sumSquares / totalSamples);
                }
                const normalizedEnergy = Math.min(1, rms * 4);
                this.onPlaybackLevel(normalizedEnergy);
                
                // Create audio buffer
                const audioBuffer = this.playbackContext.createBuffer(1, totalSamples, this.sampleRate);
                audioBuffer.getChannelData(0).set(combinedArray);
                
                // Schedule playback at precise time (gapless)
                const source = this.playbackContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.playbackContext.destination);
                
                // Track this source so we can cancel it during interruption
                this.currentAudioSources.push(source);
                source.onended = () => {
                    const index = this.currentAudioSources.indexOf(source);
                    if (index > -1) {
                        this.currentAudioSources.splice(index, 1);
                    }
                };
                
                // If we've fallen behind, catch up
                const now = this.playbackContext.currentTime;
                if (nextStartTime < now) {
                    nextStartTime = now + 0.01;
                }
                
                source.start(nextStartTime);
                nextStartTime += audioBuffer.duration;
                
                // Wait until this chunk is mostly done before processing more
                const waitTime = (nextStartTime - this.playbackContext.currentTime - 0.1) * 1000;
                if (waitTime > 0) {
                    await new Promise(resolve => setTimeout(resolve, Math.min(waitTime, 200)));
                }
            }
            
            this.isPlaying = false;
            this.onPlaybackLevel(0);
            this.onAudioEnd();
        };
        
        processQueue();
    }
    
    /**
     * Cancel the current AI response (for interruption handling)
     */
    cancelCurrentResponse() {
        // 1. Clear the audio queue
        this.audioQueue = [];
        
        this.onPlaybackLevel(0);
        // 2. Stop all playing audio sources
        for (const source of this.currentAudioSources) {
            try {
                source.stop();
            } catch (e) {
                // Source may have already finished
            }
        }
        this.currentAudioSources = [];
        this.isPlaying = false;
        
        // 3. Only send cancel message if there's an active response
        if (this.isResponseActive && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.log('Cancelling current response...');
            this.ws.send(JSON.stringify({
                type: 'response.cancel'
            }));
            this.isResponseActive = false;
            this.log('Sent response.cancel to API');
        } else {
            this.log('No active response to cancel, just clearing audio');
        }
        
        this.onAudioEnd();
    }
    
    /**
     * Handle tool calls from the AI
     */
    async handleToolCall(message) {
        const toolName = message.name;
        const args = JSON.parse(message.arguments || '{}');
        const callId = message.call_id;
        
        this.log('Executing tool:', toolName, args);
        this.onToolCall(toolName, args);
        
        let result = {};
        let success = false;
        
        try {
            // Handle frontend-only tools (UI actions)
            if (toolName === 'show_pokemon_index') {
                if (window.showPokemonIndexCanvas) {
                    const indexResult = window.showPokemonIndexCanvas();
                    if (indexResult && !indexResult.error) {
                        result = {
                            success: true,
                            message: 'Showing the Pokemon index grid'
                        };
                        success = true;
                    } else {
                        result = { error: indexResult?.error || 'Unable to show the Pokemon index right now.' };
                        success = false;
                    }
                } else {
                    result = { error: 'Pokemon index view is not available in this context.' };
                    success = false;
                }

                this.log('Frontend tool result:', result);
                this.onToolResult(toolName, args, result, success);

                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'conversation.item.create',
                        item: {
                            type: 'function_call_output',
                            call_id: callId,
                            output: JSON.stringify(result)
                        }
                    }));
                    this.ws.send(JSON.stringify({
                        type: 'response.create'
                    }));
                }

                return;
            }

            if (toolName === 'show_tcg_card_by_index') {
                const cardIndex = args.card_index;
                const pokemonName = args.pokemon_name;
                if (window.showTcgCardByIndex) {
                    const cardResult = window.showTcgCardByIndex(cardIndex, pokemonName);
                    if (cardResult.success) {
                        result = { 
                            success: true, 
                            message: `Showing TCG card #${cardIndex}${pokemonName ? ` for ${pokemonName}` : ''}`,
                            card: cardResult.card,
                            pokemon_name: pokemonName
                        };
                        success = true;
                    } else {
                        result = { error: cardResult.error };
                        success = false;
                    }
                } else {
                    result = { error: 'TCG card gallery not currently displayed' };
                    success = false;
                }
                
                this.log('Frontend tool result:', result);
                this.onToolResult(toolName, args, result, success);
                
                // Send tool result back to the API
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'conversation.item.create',
                        item: {
                            type: 'function_call_output',
                            call_id: callId,
                            output: JSON.stringify(result)
                        }
                    }));
                    
                    // Request the model to continue
                    this.ws.send(JSON.stringify({
                        type: 'response.create'
                    }));
                }
                
                return; // Exit early for frontend-only tools
            }
            
            // Call the dedicated tool execution endpoint for backend tools
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: toolName,
                    arguments: args
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                result = data.result || data;
                success = true;
                this.log('Tool result:', result);
            } else {
                const errorData = await response.json();
                result = { error: errorData.error || 'Tool execution failed' };
            }
        } catch (error) {
            this.log('Tool call error:', error);
            result = { error: error.message };
        }
        
        // Notify about tool result
        this.onToolResult(toolName, args, result, success);
        
        // Send tool result back to the API
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'conversation.item.create',
                item: {
                    type: 'function_call_output',
                    call_id: callId,
                    output: JSON.stringify(result)
                }
            }));
            
            // Request the model to continue
            this.ws.send(JSON.stringify({
                type: 'response.create'
            }));
        }
    }
    
    /**
     * Start recording audio from the microphone
     */
    async startRecording() {
        if (this.isRecording) return;
        
        // Reset audio bytes counter for new recording session
        this.audioBytesSent = 0;
        
        try {
            // Request microphone access
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: this.inputSampleRate,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });
            
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                    sampleRate: this.sampleRate
                });
            }
            
            // Resume audio context if suspended
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
            
            // Create audio processing pipeline
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);
            const processor = this.audioContext.createScriptProcessor(4096, 1, 1);
            
            processor.onaudioprocess = (event) => {
                if (!this.isRecording || !this.isConnected) return;
                
                const inputData = event.inputBuffer.getChannelData(0);
                
                // Resample to 24kHz and convert to PCM16
                const resampledData = this.resampleAudio(inputData, this.audioContext.sampleRate, this.sampleRate);
                const pcm16Data = this.float32ToPcm16(resampledData);
                
                // Send to WebSocket
                this.sendAudioChunk(pcm16Data);
            };
            
            source.connect(processor);
            processor.connect(this.audioContext.destination);
            
            this.audioWorklet = { source, processor };
            this.isRecording = true;
            
            this.onStatusChange('recording', 'Listening...');
            this.log('Recording started');
            
        } catch (error) {
            this.log('Recording error:', error);
            this.onError('Microphone access denied or not available');
            throw error;
        }
    }
    
    /**
     * Stop recording audio
     */
    stopRecording() {
        if (!this.isRecording) return;
        
        this.isRecording = false;
        
        if (this.audioWorklet) {
            this.audioWorklet.processor.disconnect();
            this.audioWorklet.source.disconnect();
            this.audioWorklet = null;
        }
        
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        
        // Only commit if we have enough audio data (at least 100ms)
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            if (this.audioBytesSent >= this.minAudioBytesForCommit) {
                this.ws.send(JSON.stringify({
                    type: 'input_audio_buffer.commit'
                }));
                this.onStatusChange('processing', 'Processing...');
            } else {
                // Not enough audio - clear the buffer instead
                this.log(`Audio buffer too small (${this.audioBytesSent} bytes), clearing instead of committing`);
                this.ws.send(JSON.stringify({
                    type: 'input_audio_buffer.clear'
                }));
                this.onStatusChange('ready', 'Ready');
            }
        }
        
        // Reset bytes counter for next recording
        this.audioBytesSent = 0;
        this.log('Recording stopped');
    }
    
    /**
     * Send audio chunk to the WebSocket
     */
    sendAudioChunk(pcm16Data) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        // Track bytes sent for commit validation
        this.audioBytesSent += pcm16Data.byteLength;
        
        // Convert to base64
        const base64Audio = this.arrayBufferToBase64(pcm16Data.buffer);
        
        this.ws.send(JSON.stringify({
            type: 'input_audio_buffer.append',
            audio: base64Audio
        }));
    }
    
    /**
     * Resample audio data to target sample rate
     */
    resampleAudio(inputData, inputSampleRate, outputSampleRate) {
        if (inputSampleRate === outputSampleRate) {
            return inputData;
        }
        
        const ratio = inputSampleRate / outputSampleRate;
        const outputLength = Math.round(inputData.length / ratio);
        const output = new Float32Array(outputLength);
        
        for (let i = 0; i < outputLength; i++) {
            const srcIndex = i * ratio;
            const srcIndexFloor = Math.floor(srcIndex);
            const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1);
            const fraction = srcIndex - srcIndexFloor;
            
            output[i] = inputData[srcIndexFloor] * (1 - fraction) + inputData[srcIndexCeil] * fraction;
        }
        
        return output;
    }
    
    /**
     * Convert Float32 audio to PCM16
     */
    float32ToPcm16(float32Array) {
        const pcm16 = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const s = Math.max(-1, Math.min(1, float32Array[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return pcm16;
    }
    
    /**
     * Convert ArrayBuffer to base64
     */
    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary);
    }
    
    /**
     * Send a text message (for testing or fallback)
     */
    sendTextMessage(text) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.onError('Not connected');
            return;
        }
        this.sendConversationItem([{ type: 'input_text', text: text }], { triggerResponse: true });
    }

    sendContextMessage(text) {
        if (!text) return;
        this.sendConversationItem([{ type: 'input_text', text: text }], { triggerResponse: false });
    }

    sendConversationItem(content, { triggerResponse = true } = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.onError('Not connected to voice service');
            return false;
        }

        this.ws.send(JSON.stringify({
            type: 'conversation.item.create',
            item: {
                type: 'message',
                role: 'user',
                content: content
            }
        }));

        if (triggerResponse) {
            this.ws.send(JSON.stringify({
                type: 'response.create'
            }));
        }

        return true;
    }
    
    /**
     * Disconnect from the WebSocket
     */
    disconnect() {
        this.stopRecording();
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        if (this.playbackContext) {
            this.playbackContext.close();
            this.playbackContext = null;
        }
        
        this.isConnected = false;
        this.audioQueue = [];
        this.isPlaying = false;
        
        this.onStatusChange('disconnected', 'Disconnected');
        this.log('Disconnected');
    }
    
    /**
     * Toggle recording state
     */
    async toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            if (!this.isConnected) {
                await this.connect();
            }
            await this.startRecording();
        }
    }
    
    /**
     * Send an image to the conversation
     * @param {string} imageDataUrl - Base64 data URL of the image (e.g., "data:image/png;base64,...")
     * @param {string} prompt - Optional text prompt to accompany the image
     */
    async sendImage(imageDataUrl, prompt = null) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.log('Cannot send image: WebSocket not connected');
            this.onError('Not connected to voice service');
            return false;
        }
        
        this.log('Sending image to conversation');
        
        // Create conversation item with image
        const content = [
            {
                type: 'input_image',
                image_url: imageDataUrl
            }
        ];
        
        // Add text prompt if provided
        if (prompt) {
            content.push({
                type: 'input_text',
                text: prompt
            });
        }
        
        // Send the image as a conversation item
        this.ws.send(JSON.stringify({
            type: 'conversation.item.create',
            item: {
                type: 'message',
                role: 'user',
                content: content
            }
        }));
        
        // Trigger a response if we included a prompt
        if (prompt) {
            this.ws.send(JSON.stringify({
                type: 'response.create'
            }));
        }
        
        this.log('Image sent successfully');
        return true;
    }
    
    /**
     * Update session instructions with user context (e.g., identified user's name)
     * @param {string} userName - The identified user's name
     */
    updateUserContext(userName) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('Cannot update user context - WebSocket not connected');
            return false;
        }

        console.log(`🎯 Injecting user identity: ${userName}`);

        // Method 1: Update session instructions (always safe to do)
        if (this.sessionConfig && this.sessionConfig.session) {
            const baseInstructions = this.sessionConfig.session.instructions || '';
            const userContextInstruction = `\n\nIMPORTANT: You are speaking with ${userName}. Address them by name naturally in your conversation.`;

            let updatedInstructions;
            if (baseInstructions.includes('IMPORTANT: You are speaking with')) {
                updatedInstructions = baseInstructions.replace(
                    /\n\nIMPORTANT: You are speaking with [^.]+\. Address them by name naturally in your conversation\./,
                    userContextInstruction
                );
            } else {
                updatedInstructions = baseInstructions + userContextInstruction;
            }

            this.sessionConfig.session.instructions = updatedInstructions;

            const voiceSetting = this.preferredVoice || this.sessionConfig.session.voice || 'alloy';
            this.sessionConfig.session.voice = voiceSetting;

            const sessionUpdate = {
                type: 'session.update',
                session: {
                    instructions: updatedInstructions,
                    voice: voiceSetting
                }
            };

            console.log('📤 Sending session.update with user context');
            this.ws.send(JSON.stringify(sessionUpdate));
        }

        // Method 2: Inject as conversation item, but only when no response is active
        const injectConversationItem = () => {
            if (this.isResponseActive) {
                console.log('⏳ Response active, waiting to inject conversation item...');
                // Wait and retry
                setTimeout(injectConversationItem, 500);
                return;
            }

            const userContextMessage = {
                type: 'conversation.item.create',
                item: {
                    type: 'message',
                    role: 'system',
                    content: [
                        {
                            type: 'input_text',
                            text: `The user you are speaking with is named ${userName}. Remember to use their name naturally in conversation.`
                        }
                    ]
                }
            };

            console.log('📤 Sending conversation.item.create with user identity');
            this.ws.send(JSON.stringify(userContextMessage));

            // Commit the conversation item
            setTimeout(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN && !this.isResponseActive) {
                    const commitMessage = {
                        type: 'response.create'
                    };
                    console.log('📤 Committing user context to conversation');
                    this.ws.send(JSON.stringify(commitMessage));
                }
            }, 100);
        };

        // Start the injection process
        injectConversationItem();

        return true;
    }

    /**
     * Update session instructions with canvas context (Pokemon or card currently displayed)
     * @param {string} canvasContext - Description of what's displayed in the canvas
     */
    updateCanvasContext(canvasContext) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('Cannot update canvas context - WebSocket not connected');
            return false;
        }

        console.log(`🎯 Injecting canvas context into system prompt`);

        if (this.sessionConfig && this.sessionConfig.session) {
            const baseInstructions = this.sessionConfig.session.instructions || '';
            
            // Remove old canvas context if it exists
            let cleanedInstructions = baseInstructions.replace(
                /\n\nCURRENT CANVAS CONTENT:[\s\S]*?(?=\n\n[A-Z]|$)/,
                ''
            ).trim();

            // Add new canvas context if provided
            let updatedInstructions;
            if (canvasContext) {
                const canvasContextInstruction = `\n\nCURRENT CANVAS CONTENT: ${canvasContext}. When the user asks about "this Pokemon", "this card", "it", or similar references, they are referring to what's currently displayed in the canvas.`;
                updatedInstructions = cleanedInstructions + canvasContextInstruction;
            } else {
                updatedInstructions = cleanedInstructions;
            }

            this.sessionConfig.session.instructions = updatedInstructions;

            const voiceSetting = this.preferredVoice || this.sessionConfig.session.voice || 'alloy';
            this.sessionConfig.session.voice = voiceSetting;

            const sessionUpdate = {
                type: 'session.update',
                session: {
                    instructions: updatedInstructions,
                    voice: voiceSetting
                }
            };

            console.log('📤 Sending session.update with canvas context');
            this.ws.send(JSON.stringify(sessionUpdate));
        }

        return true;
    }

    /**
     * Send an image from a File object
     * @param {File} file - Image file to send
     * @param {string} prompt - Optional text prompt
     */
    async sendImageFile(file, prompt = null) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = async (e) => {
                const result = await this.sendImage(e.target.result, prompt);
                resolve(result);
            };
            reader.onerror = (e) => {
                this.log('Error reading file:', e);
                reject(e);
            };
            reader.readAsDataURL(file);
        });
    }
    
    /**
     * Capture image from video element and send
     * @param {HTMLVideoElement} videoElement - Video element to capture from
     * @param {string} prompt - Optional text prompt
     */
    async captureAndSendImage(videoElement, prompt = null) {
        const canvas = document.createElement('canvas');
        canvas.width = videoElement.videoWidth;
        canvas.height = videoElement.videoHeight;
        
        const ctx = canvas.getContext('2d');
        ctx.drawImage(videoElement, 0, 0);
        
        const imageDataUrl = canvas.toDataURL('image/jpeg', 0.8);
        return this.sendImage(imageDataUrl, prompt);
    }
    
    /**
     * Check if realtime voice is supported
     */
    static isSupported() {
        return !!(
            navigator.mediaDevices &&
            navigator.mediaDevices.getUserMedia &&
            (window.AudioContext || window.webkitAudioContext) &&
            window.WebSocket
        );
    }
}

// Export for use in main app
window.RealtimeVoiceClient = RealtimeVoiceClient;
