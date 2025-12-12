// Pokemon Chat App - Main JavaScript

class PokemonChatApp {
    constructor() {
        this.userId = this.generateUserId();
        this.isLoading = false;
        this.isVoiceActive = false;
        this.tools = [];
        this.pendingToolChanges = {};
        
        // Chain of thought tracking for current response
        this.currentToolCalls = [];
        this.currentToolCallStartTime = null;
        
        // Face recognition tracking
        this.faceRecognitionEnabled = false;
        this.currentIdentifiedUser = null;
        this.isFaceIdentifying = false;
        
        // DOM elements
        this.chatContainer = document.getElementById('chatContainer');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.loadingIndicator = document.getElementById('loadingIndicator');
        this.pokemonCardOverlay = document.getElementById('pokemonCardOverlay');
        this.pokemonCardContent = document.getElementById('pokemonCardContent');
        this.closeCardBtn = document.getElementById('closeCard');
        this.voiceButton = document.getElementById('voiceButton');
        this.statusText = document.querySelector('.status-text');
        
        // Camera scanner elements
        this.cameraButton = document.getElementById('cameraButton');
        this.cameraModalOverlay = document.getElementById('cameraModalOverlay');
        this.cameraModalClose = document.getElementById('cameraModalClose');
        this.cameraPreview = document.getElementById('cameraPreview');
        this.cameraStatusText = document.getElementById('cameraStatusText');
        this.cameraStream = null;
        this.isScanModeActive = false;
        this.shouldSendSnapshotOnNextQuestion = false;
        this.isSendingImage = false;
        this.currentCardContext = null;
        
        // Tools modal elements
        this.toolsButton = document.getElementById('toolsButton');
        this.toolsModalOverlay = document.getElementById('toolsModalOverlay');
        this.toolsModalContent = document.getElementById('toolsModalContent');
        this.toolsModalClose = document.getElementById('toolsModalClose');
        this.toolsResetBtn = document.getElementById('toolsResetBtn');
        this.toolsSaveBtn = document.getElementById('toolsSaveBtn');
        
        // TCG card modal elements
        this.tcgCardModalOverlay = document.getElementById('tcgCardModalOverlay');
        this.tcgCardModalContent = document.getElementById('tcgCardModalContent');
        this.tcgCardModalClose = document.getElementById('tcgCardModalClose');
        
        // Voice recognition setup (fallback for browsers without Realtime API support)
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        
        // Azure OpenAI Realtime Voice client
        this.realtimeVoice = null;
        this.useRealtimeApi = false; // Will be set to true if available
        this.realtimeVoiceSessionAnnounced = false;
        
        this.initializeVoice();
        
        this.initializeEventListeners();
        this.initializeToolsModal();
        this.initializeCameraControls();
        this.adjustTextareaHeight();
        this.loadTools();
    }
    
    generateUserId() {
        const stored = localStorage.getItem('pokemon_chat_user_id');
        if (stored) return stored;
        
        const newId = 'user_' + Date.now() + '_' + Math.random().toString(36).substring(2, 11);
        localStorage.setItem('pokemon_chat_user_id', newId);
        return newId;
    }
    
    initializeEventListeners() {
        // Send button click
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Enter key to send (Shift+Enter for new line)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => this.adjustTextareaHeight());
        
        // Quick action buttons
        document.querySelectorAll('.quick-action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                this.handleQuickAction(action);
            });
        });
        
        // Example chips
        document.querySelectorAll('.example-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                this.messageInput.value = chip.textContent;
                this.sendMessage();
            });
        });
        
        // Close pokemon card
        this.closeCardBtn.addEventListener('click', () => this.closePokemonCard());
        this.pokemonCardOverlay.addEventListener('click', (e) => {
            if (e.target === this.pokemonCardOverlay) {
                this.closePokemonCard();
            }
        });
        
        // Voice button
        this.voiceButton.addEventListener('click', () => this.toggleVoiceConversation());
    }
    
    initializeToolsModal() {
        // Tools button click
        if (this.toolsButton) {
            this.toolsButton.addEventListener('click', () => this.openToolsModal());
        }
        
        // Close tools modal
        if (this.toolsModalClose) {
            this.toolsModalClose.addEventListener('click', () => this.closeToolsModal());
        }
        
        if (this.toolsModalOverlay) {
            this.toolsModalOverlay.addEventListener('click', (e) => {
                if (e.target === this.toolsModalOverlay) {
                    this.closeToolsModal();
                }
            });
        }
        
        // Reset tools button
        if (this.toolsResetBtn) {
            this.toolsResetBtn.addEventListener('click', () => this.resetTools());
        }
        
        // Save tools button
        if (this.toolsSaveBtn) {
            this.toolsSaveBtn.addEventListener('click', () => this.saveToolChanges());
        }
        
        // TCG card modal close
        if (this.tcgCardModalClose) {
            this.tcgCardModalClose.addEventListener('click', () => this.closeTcgCardModal());
        }
        
        if (this.tcgCardModalOverlay) {
            this.tcgCardModalOverlay.addEventListener('click', (e) => {
                if (e.target === this.tcgCardModalOverlay) {
                    this.closeTcgCardModal();
                }
            });
        }
    }

    initializeCameraControls() {
        if (this.cameraButton) {
            this.cameraButton.addEventListener('click', () => this.openCameraModal());
        }

        if (this.cameraModalOverlay) {
            this.cameraModalOverlay.addEventListener('click', (e) => {
                if (e.target === this.cameraModalOverlay) {
                    this.closeCameraModal();
                }
            });
        }

        if (this.cameraModalClose) {
            this.cameraModalClose.addEventListener('click', () => this.closeCameraModal());
        }

    }

    async openCameraModal() {
        if (!this.cameraModalOverlay) return;
        this.cameraModalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';

        await this.startCameraPreview();
        await this.startCameraScanningSession();
    }

    closeCameraModal() {
        if (!this.cameraModalOverlay) return;
        this.cameraModalOverlay.classList.remove('active');
        document.body.style.overflow = '';
        this.stopCameraScanning();
        this.stopCameraStream();
        this.updateCameraStatus('Camera closed. Reopen to scan more.');
    }

    enableScanMode() {
        this.isScanModeActive = true;
        this.shouldSendSnapshotOnNextQuestion = true;
        this.updateCameraStatus('Scan mode active. Ask a question any time to include the current frame.');
    }

    disableScanMode() {
        this.isScanModeActive = false;
        this.shouldSendSnapshotOnNextQuestion = false;
        this.updateCameraStatus('Scan mode paused.');
    }

    async startCameraScanningSession() {
        if (this.isScanModeActive) {
            return true;
        }

        try {
            await this.activateRealtimeConversation({ announce: false });
        } catch (error) {
            console.error('Failed to start realtime session for scanning:', error);
            this.updateCameraStatus('Realtime voice session required to scan images.');
            this.showToast('Image Scanner', 'Enable realtime voice so I can describe what I see.', 'error');
            return false;
        }

        this.enableScanMode();
        return true;
    }

    stopCameraScanning() {
        if (this.isScanModeActive) {
            this.disableScanMode();
        }
    }

    async startCameraPreview() {
        if (!this.cameraPreview) return;

        if (this.cameraStream) {
            this.cameraPreview.srcObject = this.cameraStream;
            return;
        }

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.updateCameraStatus('Camera access is not supported on this device.');
            return;
        }

        try {
            this.cameraStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' },
                audio: false
            });

            this.cameraPreview.srcObject = this.cameraStream;
            await this.cameraPreview.play().catch(() => {});
            this.updateCameraStatus('Camera ready. Capture or scan when you are ready.');
        } catch (error) {
            console.error('Camera preview failed:', error);
            this.updateCameraStatus('Camera access denied or unavailable.');
            this.stopCameraStream();
        }
    }

    stopCameraStream() {
        if (this.cameraStream) {
            this.cameraStream.getTracks().forEach(track => track.stop());
            this.cameraStream = null;
        }

        if (this.cameraPreview) {
            this.cameraPreview.pause();
            this.cameraPreview.srcObject = null;
        }
    }

    async sendCameraSnapshot(mode = 'manual') {
        if (this.isSendingImage) return;
        if (!this.cameraPreview || this.cameraPreview.readyState < 2) {
            this.updateCameraStatus('Waiting for camera feed...');
            return false;
        }

        if (!this.realtimeVoice || !this.useRealtimeApi) {
            this.updateCameraStatus('Realtime session is not ready. Activate voice mode first.');
            this.showToast('Image Scanner', 'Enable Realtime voice so the model can analyze the image.', 'info');
            return false;
        }

        this.isSendingImage = true;
        this.updateCameraStatus('Sending image to GPT...');

        const prompt = null;
        const willRequestResponse = false;

        try {
            await this.activateRealtimeConversation({ announce: false });
            if (willRequestResponse) {
                this.realtimeVoice.cancelCurrentResponse();
            }
            const sent = await this.realtimeVoice.captureAndSendImage(this.cameraPreview, prompt);
            if (sent) {
                if (willRequestResponse) {
                    this.updateCameraStatus('Image sent. Waiting for the response...');
                } else {
                    this.updateCameraStatus('Image added to the context. Ask me anything whenever you are ready.');
                }
            } else {
                this.updateCameraStatus('Could not send the image.');
                this.showToast('Image Scanner', 'Failed to send the image. Try again.', 'error');
            }
            return sent;
        } catch (error) {
            console.error('Image send error:', error);
            this.updateCameraStatus('Image capture failed.');
            this.showToast('Image Scanner', 'Unable to send the image to GPT. Check your connection.', 'error');
            return false;
        } finally {
            this.isSendingImage = false;
        }
    }

    async maybeSendScanSnapshotForQuestion() {
        if (!this.isScanModeActive || !this.shouldSendSnapshotOnNextQuestion) {
            return false;
        }

        this.shouldSendSnapshotOnNextQuestion = false;
        try {
            return await this.sendCameraSnapshot('scan');
        } finally {
            if (this.isScanModeActive) {
                this.shouldSendSnapshotOnNextQuestion = true;
            }
        }
    }

    updateCameraStatus(message) {
        if (this.cameraStatusText) {
            this.cameraStatusText.textContent = message;
        }
    }
    
    async loadTools() {
        try {
            const response = await fetch('/api/tools');
            if (response.ok) {
                const data = await response.json();
                this.tools = data.tools || [];
                console.log('Tools loaded:', this.tools);
                
                // Check if face identification is enabled
                this.faceRecognitionEnabled = this.isToolEnabled('face_identification');
                console.log('Face recognition enabled:', this.faceRecognitionEnabled);
            }
        } catch (error) {
            console.error('Error loading tools:', error);
        }
    }
    
    isToolEnabled(toolId) {
        const tool = this.tools.find(t => t.id === toolId);
        return tool ? tool.enabled : false;
    }
    
    /**
     * Capture an image from the camera and identify the user via face recognition
     */
    async identifyUserFromCamera() {
        // Only proceed if face recognition is enabled
        if (!this.faceRecognitionEnabled) {
            console.log('Face recognition is disabled, skipping identification');
            return;
        }
        
        // Prevent concurrent identification requests
        if (this.isFaceIdentifying) {
            console.log('Face identification already in progress');
            return;
        }
        
        try {
            this.isFaceIdentifying = true;
            
            // Get user media (camera)
            const stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'user',  // Use front camera
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                } 
            });
            
            // Create video element
            const video = document.createElement('video');
            video.srcObject = stream;
            video.autoplay = true;
            
            // Wait for video to be ready
            await new Promise((resolve) => {
                video.onloadedmetadata = () => {
                    video.play();
                    resolve();
                };
            });
            
            // Wait a bit for camera to adjust
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Capture frame from video
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);
            
            // Convert to base64
            const base64Image = canvas.toDataURL('image/jpeg', 0.8);
            
            // Stop video stream
            stream.getTracks().forEach(track => track.stop());
            
            // Send to backend for identification
            const response = await fetch('/api/face/identify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    image: base64Image
                })
            });
            
            const result = await response.json();
            
            console.log('Face identification result:', result);
            
            // Handle the result
            if (result.name && result.is_new_user && result.greeting_message) {
                // New user detected - greet them
                this.currentIdentifiedUser = result.name;
                this.addMessage('assistant', result.greeting_message);
                console.log(`Greeting new user: ${result.name}`);
            } else if (result.name && !result.is_new_user) {
                // Same user as before - update tracking but don't greet
                this.currentIdentifiedUser = result.name;
                console.log(`Same user detected: ${result.name}, no greeting`);
            } else if (result.error) {
                // Error occurred
                console.log('Face identification error:', result.error);
            } else {
                // No face detected or not recognized
                console.log('No user identified');
            }
            
        } catch (error) {
            console.error('Error during face identification:', error);
        } finally {
            this.isFaceIdentifying = false;
        }
    }
    
    async openToolsModal() {
        if (!this.toolsModalOverlay) return;
        
        this.toolsModalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        this.pendingToolChanges = {};
        
        // Load and render tools
        await this.loadTools();
        this.renderToolsModal();
    }
    
    renderToolsModal() {
        if (!this.toolsModalContent) return;
        
        if (this.tools.length === 0) {
            this.toolsModalContent.innerHTML = '<div class="tools-empty">No tools available</div>';
            return;
        }
        
        const toolsHTML = this.tools.map(tool => `
            <div class="tool-item" data-tool-id="${tool.id}">
                <div class="tool-info">
                    <div class="tool-icon">${tool.icon}</div>
                    <div class="tool-details">
                        <div class="tool-name">${tool.name}</div>
                        <div class="tool-description">${tool.description}</div>
                    </div>
                </div>
                <label class="tool-toggle">
                    <input type="checkbox" 
                           class="tool-checkbox" 
                           data-tool-id="${tool.id}" 
                           ${tool.enabled ? 'checked' : ''}>
                    <span class="tool-toggle-slider"></span>
                </label>
            </div>
        `).join('');
        
        this.toolsModalContent.innerHTML = toolsHTML;
        
        // Add event listeners to checkboxes
        this.toolsModalContent.querySelectorAll('.tool-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const toolId = e.target.dataset.toolId;
                this.pendingToolChanges[toolId] = e.target.checked;
            });
        });
    }
    
    closeToolsModal() {
        if (this.toolsModalOverlay) {
            this.toolsModalOverlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    }
    
    async saveToolChanges() {
        if (Object.keys(this.pendingToolChanges).length === 0) {
            this.closeToolsModal();
            return;
        }
        
        try {
            const response = await fetch('/api/tools', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_states: this.pendingToolChanges })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.tools = data.tools || [];
                this.closeToolsModal();
                this.addMessage('assistant', '✅ Tool settings updated successfully!');
            } else {
                throw new Error('Failed to save tool settings');
            }
        } catch (error) {
            console.error('Error saving tools:', error);
            this.addMessage('assistant', '❌ Failed to save tool settings. Please try again.');
        }
    }
    
    async resetTools() {
        try {
            const response = await fetch('/api/tools/reset', { method: 'POST' });
            
            if (response.ok) {
                const data = await response.json();
                this.tools = data.tools || [];
                this.renderToolsModal();
                this.pendingToolChanges = {};
            }
        } catch (error) {
            console.error('Error resetting tools:', error);
        }
    }
    
    closeTcgCardModal() {
        if (this.tcgCardModalOverlay) {
            this.tcgCardModalOverlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    }
    
    showTcgCardDetail(card) {
        if (!this.tcgCardModalOverlay || !this.tcgCardModalContent) return;
        this.setCardContext(card);
        
        // Support both formats: card.images.large (raw API) and card.imageLarge/card.image (formatted)
        const largeImage = card.images?.large || card.imageLarge || card.images?.small || card.image;
        const setName = card.set?.name || card.set || 'Unknown Set';
        
        const cardHTML = `
            <div class="tcg-card-detail">
                <div class="tcg-card-image">
                    <img src="${largeImage}" alt="${card.name}">
                </div>
                <div class="tcg-card-info">
                    <h2>${card.name}</h2>
                    <p class="tcg-card-set">${setName} - ${card.number || ''}</p>
                    
                    ${card.types ? `
                        <div class="tcg-card-types">
                            ${card.types.map(t => `<span class="type-badge type-${t.toLowerCase()}">${t}</span>`).join('')}
                        </div>
                    ` : ''}
                    
                    ${card.hp ? `<p class="tcg-card-hp">HP: ${card.hp}</p>` : ''}
                    
                    ${card.subtypes?.length ? `
                        <p class="tcg-card-subtypes">Subtypes: ${card.subtypes.join(', ')}</p>
                    ` : ''}
                    
                    ${card.abilities?.length ? `
                        <div class="tcg-card-abilities">
                            <h3>Abilities</h3>
                            ${card.abilities.map(a => `
                                <div class="tcg-ability">
                                    <strong>${a.name}</strong>: ${a.text}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    ${card.attacks?.length ? `
                        <div class="tcg-card-attacks">
                            <h3>Attacks</h3>
                            ${card.attacks.map(a => `
                                <div class="tcg-attack">
                                    <strong>${a.name}</strong> ${a.damage ? `- ${a.damage}` : ''}
                                    ${a.text ? `<p>${a.text}</p>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    
                    ${card.rarity ? `<p class="tcg-card-rarity">Rarity: ${card.rarity}</p>` : ''}
                    ${card.artist ? `<p class="tcg-card-artist">Artist: ${card.artist}</p>` : ''}
                    
                    ${card.legalities ? `
                        <div class="tcg-card-legalities">
                            <h3>Format Legality</h3>
                            <div class="legality-badges">
                                ${Object.entries(card.legalities).map(([format, status]) => `
                                    <span class="legality-badge ${status.toLowerCase()}">${format}: ${status}</span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        this.tcgCardModalContent.innerHTML = cardHTML;
        this.tcgCardModalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    /**
     * Initialize voice - try Realtime API first, fall back to browser Speech Recognition
     */
    async initializeVoice() {
        // First, check if Azure OpenAI Realtime API is available
        if (window.RealtimeVoiceClient && RealtimeVoiceClient.isSupported()) {
            try {
                const statusResponse = await fetch('/api/realtime/status');
                const status = await statusResponse.json();
                
                if (status.available) {
                    console.log('Azure OpenAI Realtime API available, initializing...');
                    this.initializeRealtimeVoice();
                    return;
                } else {
                    console.log('Realtime API not configured:', status.message);
                }
            } catch (error) {
                console.log('Could not check Realtime API status:', error);
            }
        }
        
        // Fall back to browser Speech Recognition
        console.log('Using browser Speech Recognition (fallback)');
        this.initializeVoiceRecognition();
    }
    
    /**
     * Initialize Azure OpenAI Realtime Voice client
     */
    initializeRealtimeVoice() {
        this.realtimeVoice = new RealtimeVoiceClient({
            debug: true,
            
            onStatusChange: (status, message) => {
                console.log('Realtime status:', status, message);
                this.updateVoiceStatus(status, message);
            },
            
            onTranscript: (text, role) => {
                if (role === 'user') {
                    this.addMessage('user', text);
                    this.hideWelcomeMessage();
                        void this.maybeSendScanSnapshotForQuestion();
                    // Clear tool calls for new conversation turn
                    this.currentToolCalls = [];
                }
            },
            
            onResponse: (text, isPartial) => {
                if (!isPartial && text) {
                    // Full response received - extract any pokemon/tcg data from tool results
                    let pokemonData = null;
                    let tcgData = null;
                    
                    // Check tool results for displayable data
                    for (const toolCall of this.currentToolCalls) {
                        if (toolCall.result && toolCall.success) {
                            // Check for Pokemon data
                            if (toolCall.result.name && toolCall.result.types && toolCall.result.image) {
                                pokemonData = toolCall.result;
                            }
                            // Check for TCG card data
                            if (toolCall.result.cards && toolCall.result.cards.length > 0) {
                                tcgData = toolCall.result;
                            }
                        }
                    }
                    
                    this.addMessage('assistant', text, pokemonData, tcgData);
                }
            },
            
            onError: (error) => {
                console.error('Realtime voice error:', error);
                this.addMessage('assistant', `⚠️ Voice error: ${error}`);
            },
            
            onAudioStart: () => {
                this.updateVoiceStatus('speaking', 'Speaking...');
            },
            
            onAudioEnd: () => {
                if (this.isVoiceActive) {
                    this.updateVoiceStatus('listening', 'Listening...');
                }
            },
            
            onToolCall: (toolName, args) => {
                console.log('Tool called:', toolName, args);
                
                // Track tool call for chain of thought
                this.currentToolCallStartTime = Date.now();
                const toolCallEntry = {
                    toolName: toolName,
                    args: args,
                    result: null,
                    success: null,
                    duration: null,
                    timestamp: new Date().toISOString()
                };
                this.currentToolCalls.push(toolCallEntry);
                
                // Format tool name for display
                const displayName = toolName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                
                // Format args for display (show key details)
                let argsSummary = '';
                if (args) {
                    if (args.name) argsSummary = args.name;
                    else if (args.pokemon) argsSummary = args.pokemon;
                    else if (args.query) argsSummary = args.query;
                    else if (args.pokemon_name) argsSummary = args.pokemon_name;
                }
                
                // Show loading indicator (same as gpt-5-chat)
                this.setLoading(true);
                
                // Update status to show what tool is being called
                this.updateVoiceStatus('processing', `${displayName}${argsSummary ? `: ${argsSummary}` : ''}...`);
            },
            
            onToolResult: (toolName, args, result, success) => {
                console.log('Tool result:', toolName, success, result);
                
                // Update the last tool call entry with result
                const duration = this.currentToolCallStartTime ? Date.now() - this.currentToolCallStartTime : null;
                if (this.currentToolCalls.length > 0) {
                    const lastEntry = this.currentToolCalls[this.currentToolCalls.length - 1];
                    if (lastEntry.toolName === toolName) {
                        lastEntry.result = result;
                        lastEntry.success = success;
                        lastEntry.duration = duration;
                    }
                }
                
                // Hide loading indicator (same as gpt-5-chat)
                this.setLoading(false);
                
                // Update status back to listening
                if (this.isVoiceActive) {
                    this.updateVoiceStatus('listening', 'Listening...');
                }
                
                // Log result for debugging
                const displayName = toolName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                if (!success) {
                    console.warn(`Tool ${displayName} failed:`, result.error || 'Unknown error');
                }
                
                if (success && result && result.assistant_text) {
                    const displayData = result.pokemon_data || result;
                    this.addMessage('assistant', result.assistant_text, displayData, result.tcg_data);
                }
            },
            
            onSpeechStarted: () => {
                // Trigger face identification when user starts speaking
                console.log('Speech started - triggering face identification');
                this.identifyUserFromCamera();
            }
        });
        
        this.useRealtimeApi = true;
        console.log('Realtime Voice client initialized');
    }
    
    /**
     * Update voice status display
     */
    updateVoiceStatus(status, message) {
        if (this.statusText) {
            const statusMap = {
                'ready': 'Ready',
                'connecting': 'Connecting...',
                'connected': 'Connected',
                'session_ready': 'Voice Ready',
                'recording': 'Listening...',
                'listening': 'Listening...',
                'processing': 'Processing...',
                'speaking': 'Speaking...',
                'disconnected': 'Offline',
                'error': 'Error'
            };
            this.statusText.textContent = statusMap[status] || message || 'Online';
        }
        
        // Update button appearance
        if (status === 'recording' || status === 'listening' || status === 'speaking') {
            this.voiceButton?.classList.add('active');
        } else if (status === 'disconnected' || status === 'error' || status === 'ready') {
            if (!this.isVoiceActive) {
                this.voiceButton?.classList.remove('active');
            }
        }
    }

    initializeVoiceRecognition() {
        // Check if browser supports Speech Recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            console.warn('Speech Recognition not supported in this browser');
            if (this.voiceButton) {
                this.voiceButton.style.display = 'none';
            }
            return;
        }
        
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';
        
        this.recognition.onstart = () => {
            console.log('Voice recognition started');
            this.isVoiceActive = true;
            this.voiceButton.classList.add('active');
            this.statusText.textContent = 'Listening...';
            const voiceText = this.voiceButton.querySelector('.voice-text');
            if (voiceText) voiceText.textContent = 'Listening';
        };
        
        this.recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            console.log('Voice input:', transcript);
            
            // Display user's spoken message
            this.addMessage('user', transcript);
            this.hideWelcomeMessage();
            void this.maybeSendScanSnapshotForQuestion();
            
            // Process the message
            this.processVoiceMessage(transcript);
        };
        
        this.recognition.onerror = (event) => {
            console.error('Voice recognition error:', event.error);
            this.stopVoiceConversation();
            
            if (event.error === 'no-speech') {
                this.addMessage('assistant', "I didn't hear anything. Please try again!");
            } else if (event.error === 'not-allowed') {
                this.addMessage('assistant', "Microphone access denied. Please enable microphone permissions.");
            }
        };
        
        this.voiceRetryCount = 0;
        this.maxVoiceRetries = 3;
        
        this.recognition.onend = () => {
            console.log('Voice recognition ended');
            if (this.isVoiceActive) {
                // Auto-restart if still in voice mode (for continuous conversation)
                setTimeout(() => {
                    if (this.isVoiceActive && !this.isLoading && this.voiceRetryCount < this.maxVoiceRetries) {
                        try {
                            this.recognition.start();
                            this.voiceRetryCount = 0; // Reset on successful start
                        } catch (error) {
                            this.voiceRetryCount++;
                            console.error('Voice restart failed, retry count:', this.voiceRetryCount);
                            if (this.voiceRetryCount >= this.maxVoiceRetries) {
                                this.stopVoiceConversation();
                                this.addMessage('assistant', 'Voice recognition stopped due to repeated errors. Please try again.');
                            }
                        }
                    }
                }, 1000);
            }
        };
    }
    
    toggleVoiceConversation() {
        if (this.isVoiceActive) {
            this.stopVoiceConversation();
        } else {
            this.startVoiceConversation();
        }
    }
    
    async startVoiceConversation() {
        // Use Realtime API if available
        if (this.useRealtimeApi && this.realtimeVoice) {
            try {
                await this.activateRealtimeConversation({ announce: true });
                return;
            } catch (error) {
                console.error('Error starting realtime voice:', error);
                this.addMessage('assistant', `⚠️ Could not start voice: ${error.message}. Falling back to browser voice...`);
                this.isVoiceActive = false;
                this.voiceButton.classList.remove('active');
                this.realtimeVoiceSessionAnnounced = false;
                
                // Fall back to browser recognition
                this.useRealtimeApi = false;
                this.initializeVoiceRecognition();
                this.startVoiceConversation();
                return;
            }
        }

        // Fallback: Browser Speech Recognition
        if (!this.recognition) {
            this.addMessage('assistant', '⚠️ Voice recognition is not supported in your browser. Please try Chrome, Edge, or Safari.');
            return;
        }
        
        this.isVoiceActive = true;
        this.voiceButton.classList.add('active');
        this.hideWelcomeMessage();
        
        // Add a system message
        this.addMessage('assistant', "🎤 Voice mode activated! (Browser speech recognition). Speak your Pokemon query now...");
        
        try {
            this.recognition.start();
        } catch (error) {
            console.error('Error starting recognition:', error);
            this.stopVoiceConversation();
        }
    }

    async activateRealtimeConversation({ announce = false } = {}) {
        if (!this.useRealtimeApi) {
            throw new Error('Realtime API is not enabled');
        }

        if (!this.realtimeVoice) {
            throw new Error('Realtime voice client is not initialized');
        }

        if (!this.realtimeVoice.isConnected) {
            await this.realtimeVoice.connect();
        }

        if (!this.realtimeVoice.isRecording) {
            await this.realtimeVoice.startRecording();
        }

        const becameActive = !this.isVoiceActive;
        if (becameActive) {
            this.isVoiceActive = true;
            this.voiceButton?.classList.add('active');
            this.hideWelcomeMessage();
        }

        if (announce && becameActive && !this.realtimeVoiceSessionAnnounced) {
            this.addMessage('assistant', "🎤 **Real-time voice mode activated!** Using Azure OpenAI Realtime API. Just speak naturally and I'll respond in real-time.");
            this.realtimeVoiceSessionAnnounced = true;
        }
    }
    
    stopVoiceConversation() {
        this.isVoiceActive = false;
        this.voiceButton.classList.remove('active');
        this.statusText.textContent = 'Online';
        const voiceText = this.voiceButton.querySelector('.voice-text');
        if (voiceText) voiceText.textContent = 'Voice';
        
        // Stop Realtime API if active
        if (this.useRealtimeApi && this.realtimeVoice) {
            this.realtimeVoice.cancelCurrentResponse();
            this.realtimeVoice.stopRecording();
            // Don't disconnect - keep connection for quick restart
        }
        
        // Stop browser recognition
        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (error) {
                console.error('Error stopping recognition:', error);
            }
        }
        
        // Stop any ongoing speech
        if (this.synthesis) {
            this.synthesis.cancel();
        }
        
        this.addMessage('assistant', '🔇 Voice mode deactivated.');
        this.realtimeVoiceSessionAnnounced = false;
    }
    
    async processVoiceMessage(message) {
        this.setLoading(true);
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    user_id: this.userId,
                    card_context: this.getCardContextPayload()
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get response');
            }
            
            const data = await response.json();
            
            // Add assistant message to chat
            this.addMessage('assistant', data.message, data.pokemon_data, data.tcg_data);
            
            // Speak the response
            this.speakText(data.message);
            
        } catch (error) {
            console.error('Error processing voice message:', error);
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
            this.speakText('Sorry, I encountered an error. Please try again.');
        } finally {
            this.setLoading(false);
        }
    }
    
    speakText(text) {
        if (!this.synthesis) return;
        
        // Cancel any ongoing speech
        this.synthesis.cancel();
        
        // Text cleaning patterns for speech
        const TEXT_CLEANING_PATTERNS = {
            BOLD_MARKERS: /\*\*/g,
            NEWLINES: /\n/g,
            BULLET_POINTS: /•/g,
            POKEMON_NUMBERS: /#\d+/g
        };
        
        const MAX_SPEECH_LENGTH = 500;
        
        // Clean the text for speech (remove markdown and special characters)
        const cleanText = text
            .replace(TEXT_CLEANING_PATTERNS.BOLD_MARKERS, '')
            .replace(TEXT_CLEANING_PATTERNS.NEWLINES, ' ')
            .replace(TEXT_CLEANING_PATTERNS.BULLET_POINTS, '')
            .replace(TEXT_CLEANING_PATTERNS.POKEMON_NUMBERS, '')
            .substring(0, MAX_SPEECH_LENGTH);
        
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        
        utterance.onend = () => {
            console.log('Speech finished');
        };
        
        this.synthesis.speak(utterance);
    }
    
    adjustTextareaHeight() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }
    
    async handleQuickAction(action) {
        if (action === 'random') {
            await this.triggerRandomQuickAction();
            return;
        }

        const messages = {
            'help': 'What can you do?',
            'popular': 'List some popular Pokemon'
        };
        
        if (messages[action]) {
            this.messageInput.value = messages[action];
            this.sendMessage();
        }
    }

    async triggerRandomQuickAction() {
        const userMessage = 'Show me a random Pokemon';
        this.addMessage('user', userMessage);
        this.hideWelcomeMessage();
        this.setLoading(true);

        try {
            const response = await fetch(`/api/random-pokemon?user_id=${encodeURIComponent(this.userId)}`);
            if (!response.ok) {
                throw new Error('Failed to fetch a random Pokemon');
            }

            const data = await response.json();
            const toolResult = data.result || {};
            const assistantText = toolResult.assistant_text || `Here's a random Pokémon!`;
            this.addMessage('assistant', assistantText, toolResult);
            await this.recordQuickActionContext(userMessage, assistantText, toolResult);
        } catch (error) {
            console.error('Random quick action failed:', error);
            this.addMessage('assistant', 'Sorry, I could not fetch a random Pokémon right now. Try again later.');
        } finally {
            this.setLoading(false);
        }
    }

    async recordQuickActionContext(userMessage, assistantText, pokemonData) {
        const cardContext = this.getCardContextPayload();
        try {
            await fetch('/api/chat/record', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.userId,
                    user_message: userMessage,
                    assistant_text: assistantText,
                    pokemon_data: pokemonData,
                    card_context: cardContext
                })
            });
        } catch (error) {
            console.error('Failed to record quick action context:', error);
        }
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isLoading) return;
        
        // Clear input and hide welcome message
        this.messageInput.value = '';
        this.adjustTextareaHeight();
        this.hideWelcomeMessage();
        
        // Add user message to chat
        this.addMessage('user', message);
        // Mirror the text into the realtime context so voice/history stays in sync
        if (this.useRealtimeApi && this.realtimeVoice?.isConnected) {
            void this.realtimeVoice.sendContextMessage(message);
        }
        void this.maybeSendScanSnapshotForQuestion();
        
        // Show loading indicator
        this.setLoading(true);
        
        try {
            // Send message to backend
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    user_id: this.userId,
                    card_context: this.getCardContextPayload()
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get response');
            }
            
            const data = await response.json();
            
            // Add assistant message
            this.addMessage('assistant', data.message, data.pokemon_data, data.tcg_data);
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        } finally {
            this.setLoading(false);
        }
    }
    
    /**
     * Show a toast notification
     * @param {string} title - Toast title
     * @param {string} message - Toast message
     * @param {string} type - Toast type: 'tool', 'success', 'error', 'info'
     * @param {number} duration - Duration in ms (0 = no auto-hide)
     * @returns {HTMLElement} The toast element for manual removal
     */
    showToast(title, message, type = 'info', duration = 3000) {
        // Ensure toast container exists
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Icon based on type
        const icons = {
            tool: '<div class="toast-spinner"></div>',
            success: '<span class="toast-icon">✅</span>',
            error: '<span class="toast-icon">❌</span>',
            info: '<span class="toast-icon">ℹ️</span>'
        };
        
        toast.innerHTML = `
            ${icons[type] || icons.info}
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                ${message ? `<div class="toast-message">${message}</div>` : ''}
            </div>
        `;
        
        container.appendChild(toast);
        
        // Auto-hide after duration (if not 0)
        if (duration > 0) {
            setTimeout(() => {
                this.hideToast(toast);
            }, duration);
        }
        
        return toast;
    }
    
    /**
     * Hide a toast notification with animation
     * @param {HTMLElement} toast - The toast element to hide
     */
    hideToast(toast) {
        if (toast && toast.parentNode) {
            toast.classList.add('hiding');
            setTimeout(() => {
                toast.remove();
            }, 300); // Match animation duration
        }
    }
    
    addMessage(role, content, pokemonData = null, tcgData = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message-bubble ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Format message content (support markdown-like formatting)
        const formattedContent = this.formatMessage(content);
        contentDiv.innerHTML = formattedContent;
        
        messageDiv.appendChild(contentDiv);
        
        // Add timestamp
        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        messageDiv.appendChild(timestamp);
        
        // Add pokemon display if data is provided
        if (pokemonData && role === 'assistant') {
            const pokemonDisplay = this.createPokemonDisplay(pokemonData);
            messageDiv.appendChild(pokemonDisplay);
            this.setCardContext(pokemonData);
        }
        
        // Add TCG cards display if data is provided
        if (tcgData && tcgData.cards && role === 'assistant') {
            const tcgDisplay = this.createTcgCardsDisplay(tcgData);
            messageDiv.appendChild(tcgDisplay);
        }
        
        // Add chain of thought accordion for assistant messages with tool calls
        if (role === 'assistant' && this.currentToolCalls.length > 0) {
            const cotAccordion = this.createChainOfThoughtAccordion(this.currentToolCalls);
            messageDiv.appendChild(cotAccordion);
            // Clear tool calls for next response
            this.currentToolCalls = [];
        }
        
        this.chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    /**
     * Create a Chain of Thought accordion showing tool calls and results
     */
    createChainOfThoughtAccordion(toolCalls) {
        const accordion = document.createElement('div');
        accordion.className = 'chain-of-thought';
        
        // Toggle button
        const toggle = document.createElement('button');
        toggle.className = 'cot-toggle';
        toggle.innerHTML = `
            <span class="cot-toggle-icon">▶</span>
            <span>🔍 Chain of Thought (${toolCalls.length} tool call${toolCalls.length > 1 ? 's' : ''})</span>
        `;
        toggle.addEventListener('click', () => {
            accordion.classList.toggle('expanded');
        });
        accordion.appendChild(toggle);
        
        // Content area
        const content = document.createElement('div');
        content.className = 'cot-content';
        
        toolCalls.forEach((call, index) => {
            const step = document.createElement('div');
            step.className = `cot-step ${call.success === true ? 'success' : call.success === false ? 'error' : 'pending'}`;
            
            // Step header
            const header = document.createElement('div');
            header.className = 'cot-step-header';
            const icon = call.success === true ? '✅' : call.success === false ? '❌' : '⏳';
            const displayName = call.toolName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            header.innerHTML = `<span class="cot-step-icon">${icon}</span> Step ${index + 1}: ${displayName}`;
            step.appendChild(header);
            
            // Parameters
            if (call.args && Object.keys(call.args).length > 0) {
                const paramsLabel = document.createElement('div');
                paramsLabel.className = 'cot-label';
                paramsLabel.textContent = 'Parameters';
                step.appendChild(paramsLabel);
                
                const params = document.createElement('div');
                params.className = 'cot-params';
                params.textContent = JSON.stringify(call.args, null, 2);
                step.appendChild(params);
            }
            
            // Result
            if (call.result !== null) {
                const resultLabel = document.createElement('div');
                resultLabel.className = 'cot-label';
                resultLabel.textContent = 'Result';
                step.appendChild(resultLabel);
                
                const result = document.createElement('div');
                result.className = `cot-result ${call.success ? '' : 'error'}`;
                
                // Truncate large results for display
                let resultText = JSON.stringify(call.result, null, 2);
                if (resultText.length > 2000) {
                    resultText = resultText.substring(0, 2000) + '\n... (truncated)';
                }
                result.textContent = resultText;
                step.appendChild(result);
            }
            
            // Duration
            if (call.duration) {
                const duration = document.createElement('div');
                duration.className = 'cot-duration';
                duration.textContent = `⏱️ ${call.duration}ms`;
                step.appendChild(duration);
            }
            
            content.appendChild(step);
        });
        
        accordion.appendChild(content);
        return accordion;
    }
    
    createTcgCardsDisplay(tcgData) {
        const displayDiv = document.createElement('div');
        displayDiv.className = 'tcg-cards-display';
        
        // Header - support both total_count and count properties
        const totalCount = tcgData.total_count || tcgData.count || tcgData.cards.length;
        const header = document.createElement('div');
        header.className = 'tcg-cards-header';
        header.innerHTML = `<span class="tcg-icon">🃏</span> Trading Cards (${totalCount} found)`;
        displayDiv.appendChild(header);
        
        // Cards grid
        const cardsGrid = document.createElement('div');
        cardsGrid.className = 'tcg-cards-grid';
        
        tcgData.cards.slice(0, 6).forEach(card => {
            const cardDiv = document.createElement('div');
            cardDiv.className = 'tcg-card-preview';
            
            // Support both formats: card.images.small (raw API) and card.image (formatted)
            const imageUrl = card.images?.small || card.image;
            if (imageUrl) {
                const img = document.createElement('img');
                img.src = imageUrl;
                img.alt = card.name;
                img.loading = 'lazy';
                cardDiv.appendChild(img);
            }
            
            const cardName = document.createElement('div');
            cardName.className = 'tcg-card-name';
            cardName.textContent = card.name;
            cardDiv.appendChild(cardName);
            
            // Click to show full card details
            cardDiv.addEventListener('click', () => {
                this.showTcgCardDetail(card);
            });
            
            cardsGrid.appendChild(cardDiv);
        });
        
        displayDiv.appendChild(cardsGrid);
        
        return displayDiv;
    }

    formatMessage(text) {
        // Convert markdown-like formatting to HTML
        let formatted = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // Bold
            .replace(/\n/g, '<br>')  // Line breaks
            .replace(/- (.*?)(?=<br>|$)/g, '• $1');  // List items
        
        return formatted;
    }
    
    createPokemonDisplay(pokemonData) {
        const displayDiv = document.createElement('div');
        displayDiv.className = 'pokemon-display';
        
        // Pokemon image - prefer `image`, fallback to `sprite` or show nothing
        const imageUrl = pokemonData.image || pokemonData.sprite || pokemonData.imageUrl || null;
        if (imageUrl) {
            const img = document.createElement('img');
            img.src = imageUrl;
            img.alt = pokemonData.name || 'Pokemon';
            img.loading = 'lazy';
            displayDiv.appendChild(img);
        }
        
        // Pokemon info
        const infoDiv = document.createElement('div');
        infoDiv.className = 'pokemon-info';
        
        const nameDiv = document.createElement('div');
        nameDiv.className = 'pokemon-name';
        // Fallback: if name/id missing, use MCP text block if available
        if (pokemonData.name && pokemonData.id) {
            nameDiv.textContent = `${pokemonData.name} #${pokemonData.id}`;
        } else if (pokemonData.mcp_text) {
            // Extract first header line or show the mcp markdown text trimmed
            const headerMatch = pokemonData.mcp_text.match(/^#\s*(.+?)\s*(?:\(#(\d+)\))?/m);
            if (headerMatch) {
                const n = headerMatch[1].trim();
                const id = headerMatch[2] ? ` #${headerMatch[2]}` : '';
                nameDiv.textContent = `${n}${id}`;
            } else {
                nameDiv.textContent = pokemonData.mcp_text.split('\n')[0].trim();
            }
        } else {
            nameDiv.textContent = 'Unknown Pokémon';
        }
        infoDiv.appendChild(nameDiv);
        
        // Types
        if (pokemonData.types && pokemonData.types.length > 0) {
            const typesDiv = document.createElement('div');
            typesDiv.className = 'pokemon-types';
            
            pokemonData.types.forEach(type => {
                const badge = document.createElement('span');
                badge.className = `type-badge type-${type.toLowerCase()}`;
                badge.textContent = type;
                typesDiv.appendChild(badge);
            });
            
            infoDiv.appendChild(typesDiv);
        }
        
        displayDiv.appendChild(infoDiv);
        
        // Click to show detailed card
        displayDiv.addEventListener('click', () => {
            this.showPokemonCard(pokemonData);
        });
        
        return displayDiv;
    }
    
    showPokemonCard(pokemonData) {
        this.setCardContext(pokemonData);
        // Clear previous content
        this.pokemonCardContent.innerHTML = '';
        
        // Create detailed card content
        const cardHTML = `
            <div class="pokemon-card-header">
                ${pokemonData.image ? `<img src="${pokemonData.image}" alt="${pokemonData.name}" style="max-width: 250px; margin: 0 auto; display: block;">` : ''}
                <h2 style="text-align: center; margin-top: 1rem; color: var(--text-primary);">${pokemonData.name}</h2>
                <p style="text-align: center; color: var(--text-secondary);">#${String(pokemonData.id).padStart(3, '0')}</p>
            </div>
            
            ${pokemonData.description ? `
                <div style="margin-top: 1.5rem;">
                    <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Description</h3>
                    <p style="color: var(--text-secondary); line-height: 1.6;">${pokemonData.description}</p>
                </div>
            ` : ''}
            
            <div style="margin-top: 1.5rem;">
                <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Types</h3>
                <div class="pokemon-types">
                    ${pokemonData.types.map(type => `
                        <span class="type-badge type-${type.toLowerCase()}">${type}</span>
                    `).join('')}
                </div>
            </div>
            
            <div style="margin-top: 1.5rem; display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div>
                    <h4 style="color: var(--text-primary); margin-bottom: 0.25rem;">Height</h4>
                    <p style="color: var(--text-secondary);">${pokemonData.height}m</p>
                </div>
                <div>
                    <h4 style="color: var(--text-primary); margin-bottom: 0.25rem;">Weight</h4>
                    <p style="color: var(--text-secondary);">${pokemonData.weight}kg</p>
                </div>
            </div>
            
            ${pokemonData.abilities && pokemonData.abilities.length > 0 ? `
                <div style="margin-top: 1.5rem;">
                    <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Abilities</h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                        ${pokemonData.abilities.map(ability => `
                            <span style="background: var(--background-color); padding: 0.5rem 1rem; border-radius: 12px; font-size: 0.875rem;">
                                ${ability.replace('-', ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                            </span>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
            
            ${pokemonData.stats ? `
                <div style="margin-top: 1.5rem;">
                    <h3 style="color: var(--text-primary); margin-bottom: 0.75rem;">Base Stats</h3>
                    ${Object.entries(pokemonData.stats).map(([stat, value]) => `
                        <div style="margin-bottom: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                                <span style="font-size: 0.875rem; color: var(--text-secondary); text-transform: capitalize;">
                                    ${stat.replace('-', ' ')}
                                </span>
                                <span style="font-size: 0.875rem; font-weight: 600; color: var(--text-primary);">${value}</span>
                            </div>
                            <div style="background: var(--border-color); height: 8px; border-radius: 4px; overflow: hidden;">
                                <div style="background: var(--primary-color); height: 100%; width: ${Math.min((value / 255) * 100, 100)}%; transition: width 0.3s ease;"></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        `;
        
        this.pokemonCardContent.innerHTML = cardHTML;
        this.pokemonCardOverlay.classList.add('active');
        
        // Prevent body scroll when card is open
        document.body.style.overflow = 'hidden';
    }
    
    closePokemonCard() {
        this.pokemonCardOverlay.classList.remove('active');
        document.body.style.overflow = '';
        this.clearCardContext();
    }

    setCardContext(pokemonData) {
        const summary = this.buildCardContextSummary(pokemonData);
        if (!summary) {
            return;
        }

        if (this.currentCardContext?.summary === summary) {
            this.currentCardContext.data = pokemonData;
            return;
        }

        this.currentCardContext = {
            summary: summary,
            data: pokemonData
        };

        if (this.useRealtimeApi && this.realtimeVoice?.isConnected) {
            void this.realtimeVoice.sendContextMessage(summary);
        }
    }

    clearCardContext() {
        this.currentCardContext = null;
    }

    getCardContextPayload() {
        return this.currentCardContext?.summary || null;
    }

    buildCardContextSummary(card) {
        if (!card) return null;

        const name = card.name || card.title || card.pokemon_name || card.pokemon || 'Unknown card';
        if (!name) return null;

        const cardId = card.id || card.card_id || card.number || card.dex_id || card.tcgplayerId;
        const idLabel = cardId ? ( /^[0-9]+$/.test(String(cardId)) ? `#${String(cardId).padStart(3, '0')}` : `ID: ${cardId}` ) : null;
        const header = [name, idLabel].filter(Boolean).join(' ');
        const descriptors = [];

        if (Array.isArray(card.types) && card.types.length) {
            descriptors.push(`Types: ${card.types.join('/')}`);
        }

        if (card.hp) {
            descriptors.push(`HP: ${card.hp}`);
        }

        if (card.rarity) {
            descriptors.push(`Rarity: ${card.rarity}`);
        }

        if (Array.isArray(card.abilities) && card.abilities.length) {
            const abilityNames = card.abilities.map(a => a.name || a).join(', ');
            descriptors.push(`Abilities: ${abilityNames}`);
        }

        if (card.stats) {
            const statPairs = Object.entries(card.stats)
                .map(([stat, value]) => `${stat.replace(/-/g, ' ')} ${value}`);
            if (statPairs.length) {
                descriptors.push(`Stats: ${statPairs.join(', ')}`);
            }
        }

        const setName = card.set && (typeof card.set === 'string' ? card.set : card.set.name || card.set.id);
        if (setName) {
            descriptors.push(`Set: ${setName}`);
        }

        const description = card.description || card.flavor_text || card.mcp_text;
        const normalizedDescription = description ? description.replace(/\s+/g, ' ').trim() : '';
        if (normalizedDescription) {
            descriptors.push(`Description: ${normalizedDescription}`);
        }

        const summaryParts = [`User is viewing the MCP card ${header}.`];
        if (descriptors.length) {
            summaryParts.push(descriptors.join(' | '));
        }

        const cardDetails = {
            id: cardId || null,
            name,
            set: setName || null,
            rarity: card.rarity || null,
            hp: card.hp || null,
            types: card.types || [],
            artist: card.artist || null
        };
        if (Array.isArray(card.attacks) && card.attacks.length) {
            cardDetails.attacks = card.attacks.map(a => `${a.name || 'Attack'}${a.damage ? ` (${a.damage})` : ''}`);
        }

        summaryParts.push(`Card data: ${JSON.stringify(cardDetails)}`);
        summaryParts.push('Source: MCP trading card search results.');

        return summaryParts.join(' ');
    }
    
    hideWelcomeMessage() {
        const welcomeMessage = this.chatContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
    }
    
    setLoading(loading) {
        this.isLoading = loading;
        this.sendButton.disabled = loading;
        this.messageInput.disabled = loading;
        
        if (loading) {
            this.loadingIndicator.classList.add('active');
        } else {
            this.loadingIndicator.classList.remove('active');
        }
    }
    
    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.pokemonChatApp = new PokemonChatApp();
    
    // Add some helpful console messages
    console.log('%c🎮 Pokemon Chat App Started! ', 'background: #EE6B2F; color: white; padding: 5px 10px; border-radius: 5px; font-weight: bold;');
    console.log('Ask me about any Pokemon!');
});

// Handle page visibility changes (pause/resume)
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('App paused');
    } else {
        console.log('App resumed');
    }
});

// Service Worker registration (for PWA capabilities - optional enhancement)
if ('serviceWorker' in navigator) {
    // Uncomment to enable PWA features
    // navigator.serviceWorker.register('/sw.js').then(registration => {
    //     console.log('Service Worker registered:', registration);
    // }).catch(error => {
    //     console.log('Service Worker registration failed:', error);
    // });
}
