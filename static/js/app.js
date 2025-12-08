// Pokemon Chat App - Main JavaScript

class PokemonChatApp {
    constructor() {
        this.userId = this.generateUserId();
        this.isLoading = false;
        this.isVoiceActive = false;
        this.tools = [];
        this.pendingToolChanges = {};
        
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
        
        // Voice recognition setup
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.initializeVoiceRecognition();
        
        this.initializeEventListeners();
        this.initializeToolsModal();
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
    
    async loadTools() {
        try {
            const response = await fetch('/api/tools');
            if (response.ok) {
                const data = await response.json();
                this.tools = data.tools || [];
                console.log('Tools loaded:', this.tools);
            }
        } catch (error) {
            console.error('Error loading tools:', error);
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
        
        const cardHTML = `
            <div class="tcg-card-detail">
                <div class="tcg-card-image">
                    <img src="${card.images?.large || card.images?.small}" alt="${card.name}">
                </div>
                <div class="tcg-card-info">
                    <h2>${card.name}</h2>
                    <p class="tcg-card-set">${card.set?.name || 'Unknown Set'} - ${card.number || ''}</p>
                    
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
            this.addMessage('assistant', data.message, data.pokemon_data, data.tcg_data);
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        } finally {
            this.setLoading(false);
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
        }
        
        // Add TCG cards display if data is provided
        if (tcgData && tcgData.cards && role === 'assistant') {
            const tcgDisplay = this.createTcgCardsDisplay(tcgData);
            messageDiv.appendChild(tcgDisplay);
        }
        
        this.chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    createTcgCardsDisplay(tcgData) {
        const displayDiv = document.createElement('div');
        displayDiv.className = 'tcg-cards-display';
        
        // Header
        const header = document.createElement('div');
        header.className = 'tcg-cards-header';
        header.innerHTML = `<span class="tcg-icon">🃏</span> Trading Cards (${tcgData.total_count} found)`;
        displayDiv.appendChild(header);
        
        // Cards grid
        const cardsGrid = document.createElement('div');
        cardsGrid.className = 'tcg-cards-grid';
        
        tcgData.cards.slice(0, 6).forEach(card => {
            const cardDiv = document.createElement('div');
            cardDiv.className = 'tcg-card-preview';
            
            if (card.images?.small) {
                const img = document.createElement('img');
                img.src = card.images.small;
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
