// Pokemon Chat App - Main JavaScript

class PokemonChatApp {
    constructor() {
        this.userId = this.generateUserId();
        this.isLoading = false;
        this.isVoiceActive = false;
        
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
        
        // Voice recognition setup
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.initializeVoiceRecognition();
        
        this.initializeEventListeners();
        this.adjustTextareaHeight();
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
    
    startVoiceConversation() {
        if (!this.recognition) {
            this.addMessage('assistant', '⚠️ Voice recognition is not supported in your browser. Please try Chrome, Edge, or Safari.');
            return;
        }
        
        this.isVoiceActive = true;
        this.voiceButton.classList.add('active');
        this.hideWelcomeMessage();
        
        // Add a system message
        this.addMessage('assistant', "🎤 Voice mode activated! Speak your Pokemon query now...");
        
        try {
            this.recognition.start();
        } catch (error) {
            console.error('Error starting recognition:', error);
            this.stopVoiceConversation();
        }
    }
    
    stopVoiceConversation() {
        this.isVoiceActive = false;
        this.voiceButton.classList.remove('active');
        this.statusText.textContent = 'Online';
        const voiceText = this.voiceButton.querySelector('.voice-text');
        if (voiceText) voiceText.textContent = 'Voice';
        
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
                    user_id: this.userId
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get response');
            }
            
            const data = await response.json();
            
            // Add assistant message to chat
            this.addMessage('assistant', data.message, data.pokemon_data);
            
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
    
    handleQuickAction(action) {
        const messages = {
            'help': 'What can you do?',
            'random': 'Show me a random Pokemon',
            'popular': 'List some popular Pokemon'
        };
        
        if (messages[action]) {
            this.messageInput.value = messages[action];
            this.sendMessage();
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
                    user_id: this.userId
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get response');
            }
            
            const data = await response.json();
            
            // Add assistant message
            this.addMessage('assistant', data.message, data.pokemon_data);
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        } finally {
            this.setLoading(false);
        }
    }
    
    addMessage(role, content, pokemonData = null) {
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
        }
        
        this.chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
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
        
        // Pokemon image
        if (pokemonData.image) {
            const img = document.createElement('img');
            img.src = pokemonData.image;
            img.alt = pokemonData.name;
            img.loading = 'lazy';
            displayDiv.appendChild(img);
        }
        
        // Pokemon info
        const infoDiv = document.createElement('div');
        infoDiv.className = 'pokemon-info';
        
        const nameDiv = document.createElement('div');
        nameDiv.className = 'pokemon-name';
        nameDiv.textContent = `${pokemonData.name} #${pokemonData.id}`;
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
