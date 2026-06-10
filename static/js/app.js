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
        // Context viewer: accumulate all tool calls across turns (last 50)
        this._contextViewerToolCalls = [];
        this._contextViewerChatHistory = null;

        // Face recognition tracking
        this.faceRecognitionEnabled = false;
        this.currentIdentifiedUser = null;
        this.isFaceIdentifying = false;
        this.lastFaceIdentificationTime = 0;
        this.faceIdentificationCooldown = 10000; // 10 seconds cooldown between identifications
        this.pendingRealtimeUserName = null;
        this.lastAppliedRealtimeUserName = null;
        this.faceIdOverlayEnabled = this.loadFaceIdOverlayPreference();
        this.voicePreference = this.loadVoiceActorPreference();
        this.criesEnabled = this.loadCryPreference();
        this.scrollResetEnabled = this.loadScrollResetPreference();
        this.spriteStyle = this.loadSpriteStyle();
        this.apiSettings = this.loadApiSettings();
        this.currency = typeof CurrencyConverter !== 'undefined' ? CurrencyConverter.getCurrency() : 'USD';
        this.cardCollection = typeof CardCollectionStore !== 'undefined' ? new CardCollectionStore() : null;
        this.cameraMode = 'insights';
        this.pendingCardScan = null;
        this.currentScannerMatch = null;
        this.scannerAttemptCount = 0;
        this.lastScannerFrame = null;

        // Pokemon viewing status tracking (stored in cookies)
        this.viewingStatus = this.loadViewingStatus();

        // DOM elements
        this.chatContainer = document.getElementById('chatContainer');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.loadingIndicator = document.getElementById('loadingIndicator');
        this.loadingIndicatorLabel = document.getElementById('loadingIndicatorLabel');
        this.loadingRotomTooltipTarget = document.getElementById('loadingRotomTooltipTarget');
        this.pokemonCardOverlay = document.getElementById('pokemonCardOverlay');
        this.pokemonCardContent = document.getElementById('pokemonCardContent');
        this.closeCardBtn = document.getElementById('closeCard');
        this.voiceButton = document.getElementById('voiceButton');
        this.statusText = document.querySelector('.status-text');
        this.voiceBackendIndicator = document.getElementById('voiceBackendIndicator');
        this.voiceBackendValue = document.getElementById('voiceBackendValue');
        this.activeLoadingCount = 0;
        this.activeLoadingRequests = new Map();
        this.loadingRequestSequence = 0;
        this.manualLoadingToken = null;
        this.voiceBackendState = {
            mode: 'checking',
            label: 'Checking...',
            detail: 'Checking whether GPT Realtime voice is available.'
        };
        this.fetchInterceptorInstalled = false;
        this.initializeHeaderLights();

        // Camera scanner elements
        this.cameraButton = document.getElementById('cameraButton');
        this.cameraModalOverlay = document.getElementById('cameraModalOverlay');
        this.cameraModalClose = document.getElementById('cameraModalClose');
        this.cameraModal = document.getElementById('cameraModal');
        this.cameraModalSubtitle = document.getElementById('cameraModalSubtitle');
        this.cameraPreview = document.getElementById('cameraPreview');
        this.cameraStatusText = document.getElementById('cameraStatusText');
        this.cameraSwitchButton = document.getElementById('cameraSwitchButton');
        this.cameraSwitchText = document.getElementById('cameraSwitchText');
        this.cameraIdentifyButton = document.getElementById('cameraIdentifyButton');
        this.cameraInsightsModeBtn = document.getElementById('cameraInsightsModeBtn');
        this.cameraCollectionModeBtn = document.getElementById('cameraCollectionModeBtn');
        this.cameraCollectionPanel = document.getElementById('cameraCollectionPanel');
        this.cameraIdentifiedCardImage = document.getElementById('cameraIdentifiedCardImage');
        this.cameraPreviewPlaceholder = document.getElementById('cameraPreviewPlaceholder');
        this.cameraIdentifiedCardTitle = document.getElementById('cameraIdentifiedCardTitle');
        this.cameraIdentifiedCardMeta = document.getElementById('cameraIdentifiedCardMeta');
        this.cameraPreviewTags = document.getElementById('cameraPreviewTags');
        this.cameraAcceptCardBtn = document.getElementById('cameraAcceptCardBtn');
        this.cameraRejectCardBtn = document.getElementById('cameraRejectCardBtn');
        this.cameraHintSection = document.getElementById('cameraHintSection');
        this.cameraHintInput = document.getElementById('cameraHintInput');
        this.cameraHintSubmitBtn = document.getElementById('cameraHintSubmitBtn');
        this.cameraHistoryList = document.getElementById('cameraHistoryList');
        this.cameraSummaryList = document.getElementById('cameraSummaryList');
        this.cameraPreviewCard = document.getElementById('cameraPreviewCard');
        this.cameraSaveCollectionBtn = document.getElementById('cameraSaveCollectionBtn');
        this.cameraFacingMode = 'environment';
        this.cameraStream = null;
        this.isScanModeActive = false;
        this.shouldSendSnapshotOnNextQuestion = false;
        this.isSendingImage = false;
        this.currentCardContext = null;

        // Face profile capture elements (Settings modal)
        this.faceProfileVideo = document.getElementById('faceProfileVideo');
        this.faceProfileStatus = document.getElementById('faceProfileStatus');
        this.faceProfileNameInput = document.getElementById('faceProfileNameInput');
        this.faceProfilePreviewWrapper = document.getElementById('faceProfilePreviewWrapper');
        this.faceProfilePreview = document.getElementById('faceProfilePreview');
        this.faceProfileStartButton = document.getElementById('faceProfileStartButton');
        this.faceProfileCaptureButton = document.getElementById('faceProfileCaptureButton');
        this.faceProfileSaveButton = document.getElementById('faceProfileSaveButton');
        this.faceProfileCameraStream = null;
        this.faceProfileCaptureDataUrl = null;
        this.isSavingFaceProfile = false;
        this.faceProfileControlsInitialized = false;
        this.isFaceProfileCameraStarting = false;

        // Canvas context tracking
        this.currentCanvasState = {
            type: 'grid', // 'grid', 'pokemon', 'tcg-gallery', 'tcg-detail'
            data: null
        };

        // Hover context tracking (what the user's mouse is pointing at)
        this.hoveredItem = null; // { type: 'pokemon'|'tcg-card', summary: '...' }
        this._hoverContextTimer = null;

        // Tools modal elements
        this.toolsButton = document.getElementById('toolsButton');
        this.toolsModalOverlay = document.getElementById('toolsModalOverlay');
        this.toolsModalContent = document.getElementById('toolsModalContent');
        this.toolsModalClose = document.getElementById('toolsModalClose');
        this.toolsResetBtn = document.getElementById('toolsResetBtn');
        this.toolsSaveBtn = document.getElementById('toolsSaveBtn');
        this.apiModeInputs = Array.from(document.querySelectorAll('input[name="apiMode"]'));
        this.appPasswordPanel = document.getElementById('appPasswordPanel');
        this.appPasswordInput = document.getElementById('appApiPassword');
        this.customApiFields = document.getElementById('customApiFields');
        this.apiSettingsStatus = document.getElementById('apiSettingsStatus');
        this.apiSettingsSaveBtn = document.getElementById('apiSettingsSaveBtn');
        this.realtimeLanguageSelect = document.getElementById('realtimeLanguageSelect');
        this.collectionExportBtn = document.getElementById('collectionExportBtn');
        this.collectionImportBtn = document.getElementById('collectionImportBtn');
        this.collectionImportInput = document.getElementById('collectionImportInput');
        this.collectionImportStatus = document.getElementById('collectionImportStatus');

        // TCG card modal elements
        this.tcgCardModalOverlay = document.getElementById('tcgCardModalOverlay');
        this.tcgCardModalContent = document.getElementById('tcgCardModalContent');
        this.tcgCardModalClose = document.getElementById('tcgCardModalClose');

        // New layout elements
        this.chatSidebar = document.getElementById('chatSidebar');
        this.chatToggleBtn = document.getElementById('chatToggleBtn');
        this.chatCloseBtn = document.getElementById('chatCloseBtn');
        this.chatClearBtn = document.getElementById('chatClearBtn');
        this.mainCanvas = document.getElementById('mainCanvas');
        this.pokemonGridView = document.getElementById('pokemonGridView');
        this.pokemonList = document.getElementById('pokemonList');
        this.pokemonDetailView = document.getElementById('pokemonDetailView');
        this.tcgCardsView = document.getElementById('tcgCardsView');
        this.tcgCardDetailView = document.getElementById('tcgCardDetailView');
        this.tcgDatabaseViewEl = document.getElementById('tcgDatabaseView');

        // Initialize view classes
        this.gridView = new PokemonGridView(this);
        this.detailView = new PokemonDetailView(this);
        this.tcgGallery = new TcgCardsGalleryView(this);
        this.tcgDetail = new TcgCardDetailView(this);
        this.tcgDatabase = new TcgDatabaseView(this);

        // Pokemon data
        this.allPokemons = [];
        this.MAX_POKEMON = 1025; // All Pokemon up to Gen 9
        this.currentPokemonName = null; // Store current Pokemon name for card searches
        this.currentSpeciesName = null; // Base species name (e.g. 'charizard' even for mega forms)

        // Pokemon generations for separators
        this.generations = [
            { name: 'Generation I (Kanto)', start: 1, end: 151 },
            { name: 'Generation II (Johto)', start: 152, end: 251 },
            { name: 'Generation III (Hoenn)', start: 252, end: 386 },
            { name: 'Generation IV (Sinnoh)', start: 387, end: 493 },
            { name: 'Generation V (Unova)', start: 494, end: 649 },
            { name: 'Generation VI (Kalos)', start: 650, end: 721 },
            { name: 'Generation VII (Alola)', start: 722, end: 809 },
            { name: 'Generation VIII (Galar)', start: 810, end: 905 },
            { name: 'Generation IX (Paldea)', start: 906, end: 1025 }
        ];

        // Initialize search view (after generations is set)
        this.searchView = new PokemonSearchView(this);

        // View history for navigation
        this.viewHistory = ['grid']; // Start at grid view
        this.currentViewIndex = 0;
        this.currentTcgData = null; // Store last TCG data for forward navigation

        // Cache configuration
        this.cacheConfig = null;
        this.pokeapiBaseUrl = 'https://pokeapi.co/api/v2';

        // Voice recognition setup (fallback for browsers without Realtime API support)
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.availableSpeechVoices = [];
        this.initializeSpeechVoices();

        // Azure OpenAI Realtime Voice client
        this.realtimeVoice = null;
        this.useRealtimeApi = false; // Will be set to true if available
        this.realtimeVoiceSessionAnnounced = false;
        this.voicePreviewPending = false;
        this.restartingRealtimeVoice = null;

        this.installFetchInterceptor();
        this.initializeApiSettingsControls();
        this.initializeVoice();

        this.initializeEventListeners();
        this.initializeToolsModal();
        this.initializeCameraControls();
        this.initializeChatSidebar();
        this.initializeFaceProfileCaptureControls();
        this.cardCollection?.subscribe(() => this.handleCardCollectionUpdated());
        this.handleCardCollectionUpdated();
        this.adjustTextareaHeight();
        this.loadTools();
        this.loadCacheConfig();
        // Preload TCG data in background so it's ready when user navigates there
        this.tcgDatabase.preload();
        this.routeFromUrl(); // Route based on current URL instead of always showing grid
    }
    
    /**
     * Route to the correct view based on the current browser URL.
     * Called once on startup so refresh/direct links restore the right screen.
     */
    async routeFromUrl() {
        const path = window.location.pathname;
        
        // Suppress pushState during initial routing to avoid extra history entries
        this._suppressPushState = true;
        
        // /tcg/database  →  TCG Database (all sets)
        if (path === '/tcg/database' || path === '/tcg/database/') {
            await this.tcgDatabase.show();
            this._suppressPushState = false;
            history.replaceState({ viewKey: 'tcg-database' }, '', '/tcg/database');
            return;
        }
        
        // /tcg/set/:setId  →  TCG gallery for an expansion/set
        const setMatch = path.match(/^\/tcg\/set\/([^\/]+)\/?$/);
        if (setMatch) {
            const setId = decodeURIComponent(setMatch[1]);
            await this.gridView.show();
            try {
                const response = await fetch('/api/realtime/tool', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tool_name: 'search_cards_by_set',
                        arguments: { set_id: setId }
                    })
                });
                if (response.ok) {
                    const data = await response.json();
                    if (data.result && data.result.cards && data.result.cards.length > 0) {
                        this.tcgGallery.currentSort = 'default';
                        this.tcgGallery.display(data.result);
                        this._suppressPushState = false;
                        history.replaceState({ viewKey: 'tcg' }, '', path);
                        return;
                    }
                }
            } catch (err) {
                console.warn('Failed to load TCG set from URL:', err);
            }
            this._suppressPushState = false;
            history.replaceState({ viewKey: 'grid' }, '', '/');
            return;
        }
        
        // /pokemon/:name/cards  →  TCG gallery for that Pokemon
        const cardsMatch = path.match(/^\/pokemon\/([^\/]+)\/cards\/?$/);
        if (cardsMatch) {
            const pokemonName = decodeURIComponent(cardsMatch[1]);
            // Show grid first to ensure Pokemon list is loaded
            await this.gridView.show();
            // Find the Pokemon to set context
            const pokemon = this.allPokemons?.find(p => p.name === pokemonName);
            if (pokemon) {
                this.currentPokemonName = pokemonName;
                await this.viewPokemonCards();
            } else {
                this.currentPokemonName = pokemonName;
                await this.viewPokemonCards();
            }
            this._suppressPushState = false;
            history.replaceState({ viewKey: 'tcg' }, '', path);
            return;
        }
        
        // /tcg/:cardId  →  TCG card detail
        const tcgMatch = path.match(/^\/tcg\/([^\/]+)\/?$/);
        if (tcgMatch) {
            const cardId = decodeURIComponent(tcgMatch[1]);
            await this.gridView.show();
            try {
                const response = await fetch('/api/realtime/tool', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tool_name: 'get_card_details',
                        arguments: { card_id: cardId }
                    })
                });
                if (response.ok) {
                    const data = await response.json();
                    if (data.result && !data.result.error) {
                        await this.tcgDetail.show(data.result);
                        this._suppressPushState = false;
                        history.replaceState({ viewKey: `tcg-detail-${cardId}` }, '', path);
                        return;
                    }
                }
            } catch (err) {
                console.warn('Failed to load TCG card from URL:', err);
            }
            this._suppressPushState = false;
            history.replaceState({ viewKey: 'grid' }, '', '/');
            return;
        }
        
        // /pokemon/:nameOrId  →  Pokemon detail
        const pokemonMatch = path.match(/^\/pokemon\/([^\/]+)\/?$/);
        if (pokemonMatch) {
            const identifier = decodeURIComponent(pokemonMatch[1]);
            await this.gridView.show();
            await this.detailView.loadPokemon(identifier);
            this._suppressPushState = false;
            history.replaceState({ viewKey: `pokemon-${identifier}` }, '', path);
            return;
        }
        
        // Default: show grid
        this._suppressPushState = false;
        this.gridView.show();
        history.replaceState({ viewKey: 'grid' }, '', '/');
    }
    
    /**
     * Handle browser back/forward button (popstate event).
     * Re-routes based on the URL the browser navigated to.
     */
    async handlePopState(e) {
        const path = window.location.pathname;
        
        // /tcg/database
        if (path === '/tcg/database' || path === '/tcg/database/') {
            this.tcgDatabase.showWithoutHistory();
            return;
        }
        
        // /tcg/set/:setId
        const setMatch = path.match(/^\/tcg\/set\/([^\/]+)\/?$/);
        if (setMatch && this.currentTcgData) {
            this.tcgGallery.displayWithoutHistory(this.currentTcgData);
            return;
        }
        
        // /pokemon/:name/cards
        const cardsMatch = path.match(/^\/pokemon\/([^\/]+)\/cards\/?$/);
        if (cardsMatch && this.currentTcgData) {
            this.tcgGallery.displayWithoutHistory(this.currentTcgData);
            return;
        }
        
        // /tcg/:cardId
        const tcgMatch = path.match(/^\/tcg\/([^\/]+)\/?$/);
        if (tcgMatch && this.currentTcgData?.cards) {
            const cardId = decodeURIComponent(tcgMatch[1]);
            const card = this.currentTcgData.cards.find(c => c.id === cardId);
            if (card) {
                await this.tcgDetail.showWithoutHistory(card);
                return;
            }
        }
        
        // /pokemon/:nameOrId
        const pokemonMatch = path.match(/^\/pokemon\/([^\/]+)\/?$/);
        if (pokemonMatch) {
            const identifier = decodeURIComponent(pokemonMatch[1]);
            // Try numeric first, then name
            const numId = parseInt(identifier);
            await this.detailView.loadPokemonWithoutHistory(isNaN(numId) ? identifier : numId);
            return;
        }
        
        // Default: grid
        this.gridView.showWithoutHistory();
    }

    generateUserId() {
        try {
            const stored = localStorage.getItem('pokemon_chat_user_id');
            if (stored) {
                return stored;
            }
        } catch (error) {
            console.warn('Unable to read stored user id:', error);
        }

        const newId = 'user_' + Date.now() + '_' + Math.random().toString(36).substring(2, 11);

        try {
            localStorage.setItem('pokemon_chat_user_id', newId);
        } catch (error) {
            console.warn('Unable to persist generated user id:', error);
        }

        return newId;
    }

    initializeFaceProfileCaptureControls() {
        const hasFaceProfileElements = this.faceProfileVideo ||
            this.faceProfileStartButton ||
            this.faceProfileCaptureButton ||
            this.faceProfileSaveButton ||
            this.faceProfileNameInput;

        if (!hasFaceProfileElements) {
            return;
        }

        if (!this.faceProfileControlsInitialized) {
            if (this.faceProfileStartButton) {
                this.faceProfileStartButton.addEventListener('click', () => this.toggleFaceProfileCamera());
            }

            if (this.faceProfileCaptureButton) {
                this.faceProfileCaptureButton.addEventListener('click', () => this.captureFaceProfilePhoto());
            }

            if (this.faceProfileSaveButton) {
                this.faceProfileSaveButton.addEventListener('click', () => this.saveFaceProfilePhoto());
            }

            if (this.faceProfileNameInput) {
                this.faceProfileNameInput.addEventListener('input', () => {
                    this.cacheFaceCapture({ name: this.faceProfileNameInput.value.trim() });
                    this.updateFaceProfileUIState();
                });
            }

            this.faceProfileControlsInitialized = true;
        }

        this.restoreCachedFaceProfileData();

        if (!this.faceProfileCameraStream) {
            this.updateFaceProfileStatus('Camera idle. Tap Start Camera to begin.');
        }

        this.updateFaceProfileUIState();
    }

    ensureFaceProfileCameraActive() {
        if (!this.faceProfileVideo) {
            return;
        }

        if (this.faceProfileCameraStream || this.isFaceProfileCameraStarting) {
            return;
        }

        this.startFaceProfileCamera();
    }

    restoreCachedFaceProfileData() {
        if (this.faceProfileNameInput) {
            const detectedName = this.currentIdentifiedUser;
            this.faceProfileNameInput.value = detectedName || this.loadCachedFaceCaptureName();
        }

        const cachedImage = this.loadCachedFaceCaptureImage();
        if (cachedImage && this.faceProfilePreview && this.faceProfilePreviewWrapper) {
            this.faceProfilePreview.src = cachedImage;
            this.faceProfilePreviewWrapper.hidden = false;
            this.faceProfileCaptureDataUrl = cachedImage;
        } else if (this.faceProfilePreviewWrapper) {
            this.faceProfilePreviewWrapper.hidden = true;
        }
    }

    loadCachedFaceCaptureName() {
        try {
            return localStorage.getItem('pokedex_last_face_name') || '';
        } catch (error) {
            console.warn('Unable to read cached face name:', error);
            return '';
        }
    }

    loadCachedFaceCaptureImage() {
        try {
            return localStorage.getItem('pokedex_last_face_capture') || '';
        } catch (error) {
            console.warn('Unable to read cached face capture:', error);
            return '';
        }
    }

    updateFaceProfileUIState() {
        const hasStream = Boolean(this.faceProfileCameraStream);
        if (this.faceProfileStartButton) {
            this.faceProfileStartButton.textContent = hasStream ? 'Stop Camera' : 'Start Camera';
        }
        if (this.faceProfileCaptureButton) {
            this.faceProfileCaptureButton.disabled = !hasStream;
        }

        const hasName = !!(this.faceProfileNameInput && this.faceProfileNameInput.value.trim());
        const canSave = Boolean(hasName && this.faceProfileCaptureDataUrl && !this.isSavingFaceProfile);
        if (this.faceProfileSaveButton) {
            this.faceProfileSaveButton.disabled = !canSave;
        }
    }

    updateFaceProfileStatus(message) {
        if (this.faceProfileStatus) {
            this.faceProfileStatus.textContent = message;
        }
    }

    async toggleFaceProfileCamera() {
        if (this.faceProfileCameraStream) {
            this.stopFaceProfileCamera();
            this.updateFaceProfileStatus('Camera idle. Tap Start Camera to begin.');
            this.updateFaceProfileUIState();
            return;
        }

        await this.startFaceProfileCamera();
    }

    async startFaceProfileCamera() {
        if (!this.faceProfileVideo || this.isFaceProfileCameraStarting) {
            return;
        }

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.updateFaceProfileStatus('Camera access is not supported on this device.');
            return;
        }

        this.isFaceProfileCameraStarting = true;
        this.updateFaceProfileStatus('Requesting camera permission...');

        try {
            this.faceProfileCameraStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: 'user' } },
                audio: false
            });

            this.faceProfileVideo.srcObject = this.faceProfileCameraStream;
            await this.faceProfileVideo.play().catch(() => {});
            this.updateFaceProfileStatus('Camera ready. Capture your face when centered.');
        } catch (error) {
            console.error('Face profile camera failed:', error);
            this.updateFaceProfileStatus('Camera access denied or unavailable.');
            this.stopFaceProfileCamera();
        } finally {
            this.isFaceProfileCameraStarting = false;
            this.updateFaceProfileUIState();
        }
    }

    stopFaceProfileCamera() {
        if (this.faceProfileCameraStream) {
            this.faceProfileCameraStream.getTracks().forEach(track => track.stop());
            this.faceProfileCameraStream = null;
        }

        if (this.faceProfileVideo) {
            this.faceProfileVideo.pause();
            this.faceProfileVideo.srcObject = null;
        }

        this.isFaceProfileCameraStarting = false;
    }

    captureFaceProfilePhoto() {
        if (!this.faceProfileVideo || this.faceProfileVideo.readyState < 2) {
            this.updateFaceProfileStatus('Camera is still warming up.');
            return;
        }

        const dataUrl = this.getFaceCropDataUrl(this.faceProfileVideo);
        if (!dataUrl) {
            this.updateFaceProfileStatus('Unable to capture the image.');
            this.showToast('Face Profile', 'Could not capture a frame. Try again.', 'error');
            return;
        }

        this.faceProfileCaptureDataUrl = dataUrl;
        if (this.faceProfilePreview) {
            this.faceProfilePreview.src = dataUrl;
        }
        if (this.faceProfilePreviewWrapper) {
            this.faceProfilePreviewWrapper.hidden = false;
        }

        this.updateFaceProfileStatus('Great! Name it and tap Save Profile to add it to face ID.');
        this.cacheFaceCapture({ image: dataUrl });
        this.updateFaceProfileUIState();
    }

    getFaceCropDataUrl(videoElement) {
        if (!videoElement) {
            return null;
        }

        const videoWidth = videoElement.videoWidth;
        const videoHeight = videoElement.videoHeight;

        if (!videoWidth || !videoHeight) {
            return null;
        }

        const outputWidth = 512;
        const outputHeight = 640;
        const desiredRatio = outputWidth / outputHeight; // Keep portrait output without distortion

        let cropWidth = videoWidth * 0.55;
        let cropHeight = cropWidth / desiredRatio;

        if (cropHeight > videoHeight * 0.9) {
            cropHeight = videoHeight * 0.9;
            cropWidth = cropHeight * desiredRatio;
        }

        if (cropWidth > videoWidth) {
            cropWidth = videoWidth * 0.9;
            cropHeight = cropWidth / desiredRatio;
        }

        const sourceX = (videoWidth - cropWidth) / 2;
        const sourceY = (videoHeight - cropHeight) / 2;

        const canvas = document.createElement('canvas');
        canvas.width = outputWidth;
        canvas.height = outputHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            return null;
        }

        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, outputWidth, outputHeight);
        ctx.save();
        ctx.beginPath();
        ctx.ellipse(outputWidth / 2, outputHeight / 2, outputWidth * 0.4, outputHeight * 0.45, 0, 0, Math.PI * 2);
        ctx.closePath();
        ctx.clip();

        ctx.drawImage(
            videoElement,
            sourceX,
            sourceY,
            cropWidth,
            cropHeight,
            0,
            0,
            outputWidth,
            outputHeight
        );
        ctx.restore();

        return canvas.toDataURL('image/png');
    }

    cacheFaceCapture({ image = null, name = null } = {}) {
        try {
            if (typeof localStorage === 'undefined') {
                return;
            }

            if (image) {
                localStorage.setItem('pokedex_last_face_capture', image);
            }

            if (typeof name === 'string') {
                if (name) {
                    localStorage.setItem('pokedex_last_face_name', name);
                } else {
                    localStorage.removeItem('pokedex_last_face_name');
                }
            }
        } catch (error) {
            console.warn('Unable to cache face capture locally:', error);
        }
    }

    resetFaceProfilePreview() {
        this.faceProfileCaptureDataUrl = null;
        if (this.faceProfilePreview) {
            this.faceProfilePreview.src = '';
        }
        if (this.faceProfilePreviewWrapper) {
            this.faceProfilePreviewWrapper.hidden = true;
        }
    }

    async saveFaceProfilePhoto() {
        if (!this.faceProfileNameInput) {
            return;
        }

        const name = this.faceProfileNameInput.value.trim();
        if (!name) {
            this.showToast('Face Profile', 'Give this photo a name before saving.', 'info');
            this.faceProfileNameInput.focus();
            return;
        }

        if (!this.faceProfileCaptureDataUrl) {
            this.showToast('Face Profile', 'Capture a photo first.', 'info');
            return;
        }

        if (this.isSavingFaceProfile) {
            return;
        }

        this.isSavingFaceProfile = true;
        this.updateFaceProfileUIState();
        this.updateFaceProfileStatus('Saving profile photo...');

        try {
            const response = await fetch('/api/face/profiles', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image: this.faceProfileCaptureDataUrl,
                    name
                })
            });

            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.error || 'Unable to save profile photo.');
            }

            const savedName = data?.profile?.displayName || name;
            this.updateFaceProfileStatus('Profile saved! I can now recognize you by this photo.');
            this.showToast('Face Profile', `Saved ${savedName}`, 'success');
            this.cacheFaceCapture({ image: this.faceProfileCaptureDataUrl, name: savedName });
            this.resetFaceProfilePreview();
        } catch (error) {
            console.error('Failed to save profile photo:', error);
            const message = error.message || 'Could not save profile photo.';
            this.updateFaceProfileStatus(message);
            this.showToast('Face Profile', message, 'error');
        } finally {
            this.isSavingFaceProfile = false;
            this.updateFaceProfileUIState();
        }

    }

        // ====================
        // API Settings Management
        // ====================

        getDefaultApiSettings() {
            return {
                mode: 'app',
                appPassword: '',
                realtimeLanguage: 'english',
                custom: {
                    chatEndpoint: '',
                    chatKey: '',
                    chatDeployment: '',
                    realtimeEndpoint: '',
                    realtimeKey: '',
                    realtimeDeployment: '',
                    realtimeApiVersion: '',
                    tcgApiKey: ''
                }
            };
        }

        loadApiSettings() {
            const defaults = this.getDefaultApiSettings();
            try {
                if (typeof localStorage === 'undefined') {
                    return { ...defaults };
                }
                const raw = localStorage.getItem('pokedex_api_settings_v1');
                if (!raw) {
                    return { ...defaults };
                }

                const parsed = JSON.parse(raw);
                return {
                    ...defaults,
                    ...parsed,
                    custom: {
                        ...defaults.custom,
                        ...(parsed.custom || {})
                    }
                };
            } catch (error) {
                console.warn('Unable to parse stored API settings:', error);
                return { ...defaults };
            }
        }

        persistApiSettings() {
            try {
                if (typeof localStorage === 'undefined') {
                    return;
                }
                localStorage.setItem('pokedex_api_settings_v1', JSON.stringify(this.apiSettings));
            } catch (error) {
                console.warn('Unable to persist API settings:', error);
            }
        }

        initializeApiSettingsControls() {
            // Controls might not exist on lightweight embeds
            if (!this.apiModeInputs || this.apiModeInputs.length === 0) {
                return;
            }

            const mode = this.apiSettings?.mode || 'app';
            this.apiModeInputs.forEach((input) => {
                input.checked = input.value === mode;
                const card = input.closest('.api-radio-card');
                if (card) {
                    card.classList.toggle('selected', input.checked);
                }
                input.addEventListener('change', () => {
                    if (input.checked) {
                        this.apiSettings.mode = input.value;
                        this.persistApiSettings();
                        this.updateApiSettingsUI();
                        this.updateApiSettingsStatus('Mode updated.', 'info');
                    }
                });
            });

            if (this.appPasswordInput) {
                this.appPasswordInput.value = this.apiSettings.appPassword || '';
                this.appPasswordInput.addEventListener('input', (event) => {
                    this.apiSettings.appPassword = event.target.value;
                    this.persistApiSettings();
                });
            }

            this.bindApiField('customChatEndpoint', 'custom.chatEndpoint');
            this.bindApiField('customChatKey', 'custom.chatKey');
            this.bindApiField('customChatDeployment', 'custom.chatDeployment');
            this.bindApiField('customRealtimeEndpoint', 'custom.realtimeEndpoint');
            this.bindApiField('customRealtimeKey', 'custom.realtimeKey');
            this.bindApiField('customRealtimeDeployment', 'custom.realtimeDeployment');
            this.bindApiField('customRealtimeApiVersion', 'custom.realtimeApiVersion');
            this.bindApiField('customTcgApiKey', 'custom.tcgApiKey');
            this.initializeRealtimeLanguageControl();

            if (this.apiSettingsSaveBtn) {
                this.apiSettingsSaveBtn.addEventListener('click', (event) => {
                    event.preventDefault();
                    const payload = this.buildApiSettingsPayload('chat', { notifyOnError: true });
                    if (payload) {
                        this.updateApiSettingsStatus('API settings saved locally.', 'success');
                        this.showToast('API Access', 'Settings saved to this browser.', 'success', 2500);

                        // Attempt to reinitialize realtime voice if unlocked
                        if (!this.useRealtimeApi && window.RealtimeVoiceClient?.isSupported()) {
                            this.initializeVoice();
                        }
                    }
                });
            }

            this.updateApiSettingsUI();
        }

        bindApiField(elementId, path) {
            const element = document.getElementById(elementId);
            if (!element) {
                return;
            }

            element.value = this.getApiSettingsValue(path);
            element.addEventListener('input', (event) => {
                this.setApiSettingsValue(path, event.target.value);
            });
        }

        getApiSettingsValue(path) {
            const parts = path.split('.');
            let current = this.apiSettings;
            for (const part of parts) {
                if (!current || typeof current !== 'object') {
                    return '';
                }
                current = current[part];
            }
            return typeof current === 'string' ? current : (current ?? '');
        }

        setApiSettingsValue(path, value) {
            const parts = path.split('.');
            let current = this.apiSettings;
            for (let index = 0; index < parts.length - 1; index += 1) {
                const part = parts[index];
                if (!current[part] || typeof current[part] !== 'object') {
                    current[part] = {};
                }
                current = current[part];
            }
            current[parts[parts.length - 1]] = value;
            this.persistApiSettings();
        }

        updateApiSettingsUI() {
            const mode = this.apiSettings?.mode || 'app';
            if (this.appPasswordPanel) {
                this.appPasswordPanel.hidden = mode !== 'app';
            }
            if (this.customApiFields) {
                this.customApiFields.hidden = mode !== 'custom';
            }
            if (this.apiModeInputs) {
                this.apiModeInputs.forEach((input) => {
                    const selected = input.value === mode;
                    input.checked = selected;
                    const card = input.closest('.api-radio-card');
                    if (card) {
                        card.classList.toggle('selected', selected);
                    }
                });
            }
        }

        updateApiSettingsStatus(message, type = 'info') {
            if (!this.apiSettingsStatus) {
                return;
            }
            this.apiSettingsStatus.textContent = message;
            this.apiSettingsStatus.classList.remove('api-status-success', 'api-status-error');
            if (type === 'success') {
                this.apiSettingsStatus.classList.add('api-status-success');
            } else if (type === 'error') {
                this.apiSettingsStatus.classList.add('api-status-error');
            }
        }

        normalizeRealtimeLanguagePreference(input) {
            const allowed = ['english', 'danish', 'cantonese'];
            const normalized = (input || '').toLowerCase();
            return allowed.includes(normalized) ? normalized : 'english';
        }

        getRealtimeLanguagePreference() {
            return this.normalizeRealtimeLanguagePreference(this.apiSettings?.realtimeLanguage || 'english');
        }

        getRealtimeLanguageLabel(language) {
            const labels = {
                english: 'English',
                danish: 'Danish',
                cantonese: 'Cantonese'
            };
            return labels[this.normalizeRealtimeLanguagePreference(language)] || 'English';
        }

        setRealtimeLanguagePreference(language) {
            const normalized = this.normalizeRealtimeLanguagePreference(language);
            if (!this.apiSettings) {
                this.apiSettings = this.loadApiSettings();
            }
            this.apiSettings.realtimeLanguage = normalized;
            this.persistApiSettings();
            if (this.realtimeLanguageSelect) {
                this.realtimeLanguageSelect.value = normalized;
            }
            return normalized;
        }

        initializeRealtimeLanguageControl() {
            if (!this.realtimeLanguageSelect) {
                return;
            }

            this.realtimeLanguageSelect.value = this.getRealtimeLanguagePreference();

            if (this.realtimeLanguageSelect.dataset.listenerAttached === 'true') {
                return;
            }

            this.realtimeLanguageSelect.addEventListener('change', async (event) => {
                const previous = this.getRealtimeLanguagePreference();
                const selected = this.normalizeRealtimeLanguagePreference(event.target.value);
                if (selected === previous) {
                    return;
                }

                this.setRealtimeLanguagePreference(selected);
                const readableLabel = this.getRealtimeLanguageLabel(selected);
                this.updateApiSettingsStatus(`Realtime language set to ${readableLabel}.`, 'info');
                this.showToast('Realtime Language', `Realtime voice replies will be in ${readableLabel}.`, 'success', 2800);

                if (this.useRealtimeApi) {
                    try {
                        await this.restartRealtimeVoiceClient({ resumeVoice: this.isVoiceActive });
                    } catch (error) {
                        console.warn('Failed to restart realtime voice after language change:', error);
                        this.showToast('Realtime Language', 'Language saved, restart voice manually if needed.', 'warning', 3200);
                    }
                }
            });

            this.realtimeLanguageSelect.dataset.listenerAttached = 'true';
        }

        buildApiSettingsPayload(target = 'chat', options = {}) {
            const settings = this.apiSettings || this.loadApiSettings();
            const notifyOnError = Boolean(options.notifyOnError);

            if (!settings) {
                if (notifyOnError) {
                    this.updateApiSettingsStatus('No API settings found.', 'error');
                }
                return null;
            }

            const mode = settings.mode || 'app';
            if (mode === 'custom') {
                const custom = settings.custom || {};
                const chatEndpoint = (custom.chatEndpoint || '').trim();
                const chatKey = (custom.chatKey || '').trim();
                const chatDeployment = (custom.chatDeployment || '').trim();

                if (!chatEndpoint || !chatKey || !chatDeployment) {
                    if (notifyOnError) {
                        this.updateApiSettingsStatus('Provide endpoint, key, and deployment for chat.', 'error');
                        this.showToast('API Access', 'Add your Azure endpoint, key, and deployment before continuing.', 'warning', 4500);
                    }
                    return null;
                }

                const realtimeEndpoint = (custom.realtimeEndpoint || chatEndpoint).trim();
                const realtimeKey = (custom.realtimeKey || chatKey).trim();
                const realtimeDeployment = (custom.realtimeDeployment || chatDeployment).trim();
                const realtimeApiVersion = (custom.realtimeApiVersion || '').trim();
                const tcgApiKey = (custom.tcgApiKey || '').trim();

                const payload = {
                    mode: 'custom',
                    custom: {
                        chat_endpoint: chatEndpoint,
                        chat_api_key: chatKey,
                        chat_deployment: chatDeployment,
                        realtime_endpoint: realtimeEndpoint,
                        realtime_api_key: realtimeKey,
                        realtime_deployment: realtimeDeployment
                    }
                };

                if (realtimeApiVersion) {
                    payload.custom.realtime_api_version = realtimeApiVersion;
                }

                if (tcgApiKey) {
                    payload.custom.tcg_api_key = tcgApiKey;
                }

                return payload;
            }

            if (mode === 'app') {
                const password = (settings.appPassword || '').trim();
                if (!password) {
                    if (notifyOnError) {
                        this.updateApiSettingsStatus('Enter the password to unlock built-in credentials.', 'error');
                        this.showToast('API Access', 'Enter the password before using the built-in credentials.', 'warning', 4500);
                    }
                    return null;
                }

                return {
                    mode: 'app',
                    app_password: password
                };
            }

            if (notifyOnError) {
                this.updateApiSettingsStatus('Select an API mode to continue.', 'error');
            }
            return null;
        }

        async extractApiError(response, fallbackMessage = 'Request failed') {
            if (!response) {
                return fallbackMessage;
            }

            const statusSuffix = response.status ? ` (HTTP ${response.status})` : '';

            try {
                const jsonClone = response.clone();
                const data = await jsonClone.json();
                if (data?.error) {
                    return `${data.error}${statusSuffix}`;
                }
                if (typeof data?.message === 'string') {
                    return `${data.message}${statusSuffix}`;
                }
            } catch (jsonError) {
                try {
                    const textClone = response.clone();
                    const text = await textClone.text();
                    if (text) {
                        return `${text}${statusSuffix}`;
                    }
                } catch (textError) {
                    console.warn('Unable to read error response body', textError);
                }
            }

            return `${fallbackMessage}${statusSuffix}`;
        }

    clearViewingStatus() {
        this.viewingStatus = {};
        document.cookie = 'pokemonViewingStatus=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
        // Re-render grid to remove badges
        this.gridView.renderPokemonGrid();
    }
    
    markPokemonViewed(pokemonId, level = 'detail') {
        // level: 'detail' (pokeball), 'tcg-gallery' (greatball), 'tcg-detail' (ultraball)
        const currentLevel = this.viewingStatus[pokemonId] || 'none';
        const levels = { 'none': 0, 'detail': 1, 'tcg-gallery': 2, 'tcg-detail': 3 };
        
        if (levels[level] > levels[currentLevel]) {
            this.viewingStatus[pokemonId] = level;
            this.saveViewingStatus();
        }
    }
    
    getViewingBadge(pokemonId) {
        const status = this.viewingStatus[pokemonId];
        if (!status) return null;
        
        const badges = {
            'detail': '⚪', // Pokeball
            'tcg-gallery': '🔵', // Great Ball (blue)
            'tcg-detail': '🟡' // Ultra Ball (yellow/gold)
        };
        return badges[status] || null;
    }
    
    async forceRefreshCurrentPokemon() {
        const pokemonNameEl = this.pokemonDetailView.querySelector('.pokemon-name');
        if (!pokemonNameEl) return;
        
        const pokemonName = pokemonNameEl.textContent.toLowerCase();
        console.log('🔄 Force refreshing Pokemon:', pokemonName);
        
        try {
            const invalidateResponse = await fetch('/api/cache/invalidate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool: 'get_pokemon',
                    params: { pokemon_name: pokemonName }
                })
            });
            if (!invalidateResponse.ok) {
                throw new Error('Failed to invalidate chat cache');
            }

            const warmupResponses = await Promise.all([
                fetch(`/api/pokemon/${pokemonName}?refresh=1`),
                fetch(`/api/pokemon/species/${pokemonName}?refresh=1`)
            ]);
            warmupResponses.forEach(res => {
                if (!res.ok) {
                    throw new Error('Failed to refresh Pokemon proxy cache');
                }
            });
            console.log('✅ Cache refreshed, reloading...');
            await this.detailView.loadPokemon(pokemonName);
        } catch (error) {
            console.error('❌ Error force refreshing:', error);
            alert('Failed to refresh Pokemon data');
        }
    }
    
    initializeEventListeners() {
        // Browser back/forward button support
        window.addEventListener('popstate', (e) => this.handlePopState(e));
        
        // Send button click
        if (this.sendButton) {
            this.sendButton.addEventListener('click', () => this.sendMessage());
        }
        
        // Enter key to send (Shift+Enter for new line)
        if (this.messageInput) {
            this.messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // Auto-resize textarea
            this.messageInput.addEventListener('input', () => this.adjustTextareaHeight());
        }
        
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
                if (this.messageInput) {
                    this.messageInput.value = chip.textContent;
                    this.sendMessage();
                }
            });
        });
        
        // Close pokemon card (old overlay - now hidden)
        if (this.closeCardBtn) {
            this.closeCardBtn.addEventListener('click', () => this.closePokemonCard());
        }
        if (this.pokemonCardOverlay) {
            this.pokemonCardOverlay.addEventListener('click', (e) => {
                if (e.target === this.pokemonCardOverlay) {
                    this.closePokemonCard();
                }
            });
        }
        
        // Voice button
        if (this.voiceButton) {
            this.voiceButton.addEventListener('click', () => this.toggleVoiceConversation());
        }
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

    initializeChatSidebar() {
        // Chat toggle button
        if (this.chatToggleBtn) {
            this.chatToggleBtn.addEventListener('click', () => this.toggleChatSidebar());
        }
        
        // Chat close button
        if (this.chatCloseBtn) {
            this.chatCloseBtn.addEventListener('click', () => this.closeChatSidebar());
        }

        // Chat clear button
        if (this.chatClearBtn) {
            this.chatClearBtn.addEventListener('click', () => this.clearChatHistory());
        }
        
        // View Cards button in Pokemon detail
        const viewCardsBtn = document.getElementById('viewCardsBtn');
        if (viewCardsBtn) {
            viewCardsBtn.addEventListener('click', () => this.viewPokemonCards());
        }

        // Back to grid from TCG view button
        const backToGridFromTcgBtn = document.getElementById('backToGridFromTcg');
        if (backToGridFromTcgBtn) {
            backToGridFromTcgBtn.addEventListener('click', () => this.gridView.show());
        }
        
        // Footer buttons
        const helpBtn = document.getElementById('helpBtn');
        if (helpBtn) {
            helpBtn.addEventListener('click', () => this.showHelpModal());
        }
        
        const indexBtnFooter = document.getElementById('indexBtnFooter');
        if (indexBtnFooter) {
            indexBtnFooter.addEventListener('click', () => this.gridView.show());
        }

        const tcgDbBtnFooter = document.getElementById('tcgDbBtnFooter');
        if (tcgDbBtnFooter) {
            tcgDbBtnFooter.addEventListener('click', () => this.tcgDatabase.show());
        }

        const randomPokemonBtn = document.getElementById('randomPokemonBtn');
        if (randomPokemonBtn) {
            randomPokemonBtn.addEventListener('click', () => this.getRandomPokemon());
        }
        
        const toolsBtnFooter = document.getElementById('toolsBtnFooter');
        if (toolsBtnFooter) {
            toolsBtnFooter.addEventListener('click', () => this.openToolsModal());
        }
        
        const backBtnFooter = document.getElementById('backBtnFooter');
        if (backBtnFooter) {
            backBtnFooter.addEventListener('click', () => this.navigateBack());
        }
        
        const forwardBtnFooter = document.getElementById('forwardBtnFooter');
        if (forwardBtnFooter) {
            forwardBtnFooter.addEventListener('click', () => this.navigateForward());
        }
        
        // Pokemon detail dropdown menu
        const pokemonDetailMenuBtn = document.getElementById('pokemonDetailMenuBtn');
        const pokemonDetailDropdown = document.getElementById('pokemonDetailDropdown');
        const forceRefreshPokemon = document.getElementById('forceRefreshPokemon');
        
        if (pokemonDetailMenuBtn && pokemonDetailDropdown) {
            pokemonDetailMenuBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                pokemonDetailDropdown.classList.toggle('active');
            });
            
            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!pokemonDetailMenuBtn.contains(e.target) && !pokemonDetailDropdown.contains(e.target)) {
                    pokemonDetailDropdown.classList.remove('active');
                }
            });
        }
        
        if (forceRefreshPokemon) {
            forceRefreshPokemon.addEventListener('click', async () => {
                if (pokemonDetailDropdown) pokemonDetailDropdown.classList.remove('active');
                await this.forceRefreshCurrentPokemon();
            });
        }
        
        // View cards dropdown menu
        const viewCardsDropdownBtn = document.getElementById('viewCardsDropdownBtn');
        const viewCardsDropdown = document.getElementById('viewCardsDropdown');
        const forceRefreshCards = document.getElementById('forceRefreshCards');
        
        if (viewCardsDropdownBtn && viewCardsDropdown) {
            viewCardsDropdownBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                viewCardsDropdown.classList.toggle('active');
            });
            
            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!viewCardsDropdownBtn.contains(e.target) && !viewCardsDropdown.contains(e.target)) {
                    viewCardsDropdown.classList.remove('active');
                }
            });
        }
        
        if (forceRefreshCards) {
            forceRefreshCards.addEventListener('click', async () => {
                if (viewCardsDropdown) viewCardsDropdown.classList.remove('active');
                await this.forceRefreshTcgCards();
            });
        }
        
        // Clear viewing history button
        const clearViewingHistoryBtn = document.getElementById('clearViewingHistoryBtn');
        if (clearViewingHistoryBtn) {
            clearViewingHistoryBtn.addEventListener('click', () => {
                if (confirm('Are you sure you want to clear your viewing history? This will remove all badges from the Pokemon grid.')) {
                    this.clearViewingStatus();
                    alert('Viewing history cleared!');
                }
            });
        }
        
        // Help modal
        const helpModalOverlay = document.getElementById('helpModalOverlay');
        const helpModalClose = document.getElementById('helpModalClose');
        if (helpModalClose) {
            helpModalClose.addEventListener('click', () => this.closeHelpModal());
        }
        if (helpModalOverlay) {
            helpModalOverlay.addEventListener('click', (e) => {
                if (e.target === helpModalOverlay) {
                    this.closeHelpModal();
                }
            });
        }
        
        // Close sidebar when clicking outside on mobile
        if (this.chatSidebar) {
            document.addEventListener('click', (e) => {
                if (window.innerWidth <= 900 && 
                    this.chatSidebar.classList.contains('open') &&
                    !this.chatSidebar.contains(e.target) &&
                    !this.chatToggleBtn.contains(e.target)) {
                    this.closeChatSidebar();
                }
            });
        }
    }

    initializeHeaderLights() {
        this.powerLightElement = document.querySelector('.power-light');
        this.indicatorLights = Array.from(document.querySelectorAll('.indicator-light'));
        this.powerLightLevel = 0;
        this.powerLightTargetLevel = 0;
        this.powerLightAnimationFrame = null;
        this.indicatorPulseTimeout = null;
        this.indicatorFlashTimeouts = [];
        this.indicatorLoadingActive = false;
        this.powerLightVoiceActive = false;

        if (this.powerLightElement) {
            this.powerLightElement.style.setProperty('--power-light-level', '0');
        }
    }

    toggleChatSidebar() {
        if (this.chatSidebar) {
            this.chatSidebar.classList.toggle('open');
        }
    }

    openChatSidebar() {
        if (this.chatSidebar) {
            this.chatSidebar.classList.add('open');
        }
    }

    closeChatSidebar() {
        if (this.chatSidebar) {
            this.chatSidebar.classList.remove('open');
        }
    }

    // Delegate to PokemonGridView
    async loadPokemonGrid() {
        await this.gridView.loadPokemonGrid();
    }

    displayPokemons(pokemons) {
        this.gridView.renderPokemonGrid(pokemons);
    }

    async showPokemonDetail(id, name) {
        console.log(`Showing details for Pokemon: ${name} (ID: ${id})`);
        await this.detailView.loadPokemon(id);
    }
    
    /**
     * Public API: Show a Pokemon in the canvas by ID or name
     * Can be called from tool results, grid clicks, or external integrations
     */
    async showPokemonInCanvas(pokemonIdOrName) {
        console.log('🎯 showPokemonInCanvas called with:', pokemonIdOrName);
        
        // If it's a number or numeric string, treat as ID
        const pokemonId = parseInt(pokemonIdOrName);
        if (!isNaN(pokemonId) && pokemonId > 0) {
            console.log('📍 Loading Pokemon by ID:', pokemonId);
            await this.detailView.loadPokemon(pokemonId);
            return;
        }
        
        // Otherwise, treat as name and look it up
        const pokemonName = String(pokemonIdOrName).toLowerCase();
        console.log('🔍 Searching for Pokemon by name:', pokemonName);
        
        // Try to find in our loaded list first
        const foundPokemon = this.allPokemons.find(p => 
            p.name.toLowerCase() === pokemonName
        );
        
        if (foundPokemon) {
            console.log('✅ Found Pokemon in list:', pokemonName, 'ID:', foundPokemon.id);
            await this.detailView.loadPokemon(foundPokemon.id);
        } else {
            // Fallback: try direct API call with name
            console.log('🌐 Attempting direct API call for:', pokemonName);
            try {
                await this.detailView.loadPokemon(pokemonName);
            } catch (error) {
                console.error('❌ Error loading Pokemon:', pokemonName, error);
            }
        }
    }

    /**
     * Detect a Pokemon name mentioned in a user message.
     * Returns the matching Pokemon object or null.
     */
    detectPokemonInMessage(message) {
        if (!message || this.allPokemons.length === 0) return null;
        const lower = message.toLowerCase();
        // Sort by name length descending so "mr. mime" matches before "mr"
        const sorted = [...this.allPokemons].sort((a, b) => b.name.length - a.name.length);
        for (const p of sorted) {
            // Match whole-word (word boundary) to avoid partial matches like "odd" in "oddish"
            const escaped = p.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            if (new RegExp(`\\b${escaped}\\b`, 'i').test(lower)) {
                return p;
            }
        }
        return null;
    }

    /**
     * Public API: Show a TCG card by its index in the current gallery
     * Used by GPT realtime to show cards by number (e.g., "show card 5")
     * @param {number} cardIndex - 1-based card number
     * @param {string} pokemonName - Optional Pokemon name for context/validation
     */
    showTcgCardByIndex(cardIndex, pokemonName = null) {
        console.log('🃏 showTcgCardByIndex called with:', { cardIndex, pokemonName });
        
        if (!this.currentTcgCards || !Array.isArray(this.currentTcgCards)) {
            console.error('❌ No TCG cards loaded in gallery');
            return { error: 'No TCG cards are currently loaded. Please search for cards first.' };
        }
        
        // Convert to 0-based index
        const index = parseInt(cardIndex) - 1;
        
        if (isNaN(index) || index < 0 || index >= this.currentTcgCards.length) {
            console.error('❌ Invalid card index:', cardIndex);
            return { error: `Invalid card number. Please choose between 1 and ${this.currentTcgCards.length}.` };
        }
        
        const card = this.currentTcgCards[index];
        
        // Optional: Validate pokemon name matches (case-insensitive)
        if (pokemonName && card.name) {
            const cardPokemonName = card.name.split(' ')[0].toLowerCase();
            const requestedName = pokemonName.toLowerCase();
            if (!cardPokemonName.includes(requestedName) && !requestedName.includes(cardPokemonName)) {
                console.warn('⚠️ Pokemon name mismatch:', { requested: pokemonName, card: card.name });
                return { 
                    error: `Card #${cardIndex} is "${card.name}", not ${pokemonName}. The gallery may have changed.`,
                    suggestion: `Try searching for ${pokemonName} cards first.`
                };
            }
        }
        
        console.log('✅ Showing card:', card.name);
        this.tcgDetail.show(card);
        
        return { 
            success: true, 
            card: card.name,
            pokemon_name: pokemonName,
            card_index: cardIndex
        };
    }
    
    // Deprecated: kept for backwards compatibility, delegates to detailView
    async loadPokemonData(id) {
        await this.detailView.loadPokemon(id);
    }

    // Deprecated: kept for backwards compatibility, delegates to detailView
    displayPokemonDetails(pokemon, species) {
        this.detailView.display(pokemon, species);
    }

    /**
     * Execute a frontend action received from text chat tool calls.
     * Maps _action names to the same window functions used by realtime voice.
     */
    async executeFrontendAction(action) {
        const name = action?._action;
        if (!name) return;
        console.log('🔧 Executing frontend action from chat:', name, action);

        switch (name) {
            case 'navigate_back':
                this.navigateBack();
                break;
            case 'navigate_forward':
                this.navigateForward();
                break;
            case 'show_tcg_card_by_index':
                this.showTcgCardByIndex(action.card_index, action.pokemon_name);
                break;
            case 'show_pokemon_index':
                this.showPokemonIndexInCanvas();
                break;
            case 'show_tcg_database':
                window.showTcgDatabaseCanvas?.();
                break;
            case 'show_my_collection':
                await window.showMyCollectionCanvas?.();
                break;
            case 'compare_pokemon':
                await window.comparePokemonCanvas?.(action.pokemon_name || null, action.compare_pokemon_name || null);
                break;
            case 'filter_pokemon_by_type':
                window.filterPokemonByType?.(action.types || []);
                break;
            case 'filter_pokemon_by_generation':
                window.filterPokemonByGeneration?.(action.generations || []);
                break;
            case 'filter_pokemon_by_classification':
                await window.filterPokemonByClassification?.(action.classifications || []);
                break;
            case 'sort_tcg_cards':
                window.sortTcgCardsCanvas?.(action.sort_by || 'default');
                break;
            case 'sort_tcg_database':
                window.sortTcgDatabaseCanvas?.(action.sort_by || 'release-desc');
                break;
            default:
                console.warn('Unknown frontend action:', name);
        }
    }
    
    // Deprecated: kept for backwards compatibility, delegates to detailView
    async loadPokemonDataWithoutHistory(id) {
        await this.detailView.loadPokemonWithoutHistory(id);
    }

    // Delegate to gridView
    showPokemonGrid() {
        this.gridView.show();
    }
    
    /**
     * Public API: Show the Pokemon grid/index page in canvas
     * Displays all Pokemon from the Kanto region
     */
    showPokemonIndexInCanvas() {
        console.log('📋 showPokemonIndexInCanvas called - displaying all Pokemon');
        this.gridView.show();
        return {
            success: true,
            view: 'grid'
        };
    }
    
    async navigateForward() {
        if (this.currentViewIndex < this.viewHistory.length - 1) {
            this.currentViewIndex++;
            const view = this.viewHistory[this.currentViewIndex];
            
            if (view === 'grid') {
                this.gridView.showWithoutHistory();
                history.replaceState({ viewKey: view }, '', '/');
            } else if (view === 'tcg-database') {
                this.tcgDatabase.showWithoutHistory();
                history.replaceState({ viewKey: view }, '', '/tcg/database');
            } else if (view === 'tcg') {
                if (this.currentTcgData) {
                    this.tcgGallery.displayWithoutHistory(this.currentTcgData);
                    const pokemonName = this.currentTcgData.search_query || this.currentTcgData.pokemon_name || this.currentPokemonName;
                    if (pokemonName) history.replaceState({ viewKey: view }, '', `/pokemon/${pokemonName.toLowerCase()}/cards`);
                }
            } else if (view.startsWith('tcg-detail-')) {
                // For TCG detail, find and show the specific card
                const cardId = view.replace('tcg-detail-', '');
                if (this.currentTcgData && this.currentTcgData.cards) {
                    const card = this.currentTcgData.cards.find(c => c.id === cardId);
                    if (card) {
                        await this.tcgDetail.showWithoutHistory(card);
                        history.replaceState({ viewKey: view }, '', `/tcg/${cardId}`);
                    } else {
                        console.log('Card not found in current TCG data:', cardId);
                    }
                } else {
                    console.log('No TCG data available for navigation');
                }
            } else if (view.startsWith('pokemon-')) {
                const pokemonId = parseInt(view.split('-')[1]);
                this.detailView.loadPokemonWithoutHistory(pokemonId);
                const pokemon = this.allPokemons?.find(p => p.id === pokemonId);
                history.replaceState({ viewKey: view }, '', `/pokemon/${pokemon?.name || pokemonId}`);
            }
            this.updateNavigationButtons();
        }
    }
    
    updateNavigationButtons() {
        const backBtn = document.getElementById('backBtnFooter');
        const forwardBtn = document.getElementById('forwardBtnFooter');
        
        if (backBtn) {
            const canGoBack = this.currentViewIndex > 0;
            backBtn.disabled = !canGoBack;
            backBtn.classList.toggle('footer-btn-active', canGoBack);
            backBtn.classList.toggle('footer-btn-disabled', !canGoBack);
        }
        
        if (forwardBtn) {
            const canGoForward = this.currentViewIndex < this.viewHistory.length - 1;
            forwardBtn.disabled = !canGoForward;
            forwardBtn.classList.toggle('footer-btn-active', canGoForward);
            forwardBtn.classList.toggle('footer-btn-disabled', !canGoForward);
        }
    }
    
    // Deprecated: delegates to gridView
    showPokemonGridWithoutHistory() {
        this.gridView.showWithoutHistory();
    }

    // Delegate to tcgGallery view
    displayTcgCardsInCanvas(tcgData) {
        console.log('🃏 displayTcgCardsInCanvas called with:', tcgData);
        
        if (!tcgData || !tcgData.cards || !Array.isArray(tcgData.cards) || tcgData.cards.length === 0) {
            console.error('❌ Invalid TCG data:', tcgData);
            return;
        }
        
        console.log('✅ Valid TCG data with', tcgData.cards.length, 'cards');
        
        // Store for forward navigation
        this.currentTcgData = tcgData;
        
        // Delegate to view class
        this.tcgGallery.display(tcgData);

        // Stale-while-revalidate: if data was from expired cache, refresh in background
        if (tcgData._cache_stale && tcgData.search_query) {
            this._revalidateTcgSearch(tcgData);
        }
    }
    
    // Delegate to tcgGallery view
    displayTcgCardsInCanvasWithoutHistory(tcgData) {
        console.log('🃏 displayTcgCardsInCanvasWithoutHistory called');
        
        if (!tcgData || !tcgData.cards || !Array.isArray(tcgData.cards) || tcgData.cards.length === 0) {
            return;
        }
        
        this.tcgGallery.displayWithoutHistory(tcgData);
    }

    /**
     * Background revalidation for stale TCG search data.
     * Re-fetches with force_refresh, re-renders gallery only if data changed.
     */
    async _revalidateTcgSearch(staleTcgData) {
        console.log('🔄 Revalidating stale TCG data for:', staleTcgData.search_query);
        try {
            // Use original search params if available, otherwise fall back to search_query
            const args = staleTcgData._search_params
                ? { ...staleTcgData._search_params, force_refresh: true }
                : { pokemon_name: staleTcgData.search_query, force_refresh: true };

            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'search_pokemon_cards',
                    arguments: args
                })
            });
            if (!response.ok) return;
            const data = await response.json();
            const freshData = data.result;

            if (!freshData || !freshData.cards || freshData.cards.length === 0) return;

            // Compare: only re-render if content actually changed
            const oldJson = JSON.stringify(staleTcgData.cards);
            const newJson = JSON.stringify(freshData.cards);
            if (oldJson === newJson) {
                console.log('✅ TCG revalidation: data unchanged');
                return;
            }

            console.log('🔄 TCG revalidation: data changed, re-rendering gallery');
            this.currentTcgData = freshData;
            // Re-render without adding a new history entry
            this.tcgGallery.displayWithoutHistory(freshData);
        } catch (err) {
            console.warn('⚠️ TCG revalidation failed:', err);
        }
    }

    async initializeCameraControls() {
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

        if (this.cameraSwitchButton) {
            this.cameraSwitchButton.addEventListener('click', () => this.toggleCameraFacingMode());
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                this.setCameraSwitchEnabled(false);
            }
        }

        this.cameraIdentifyButton?.addEventListener('click', () => this.identifyCurrentCard());
        this.cameraInsightsModeBtn?.addEventListener('click', () => this.setCameraMode('insights'));
        this.cameraCollectionModeBtn?.addEventListener('click', () => this.setCameraMode('collection'));
        this.cameraAcceptCardBtn?.addEventListener('click', () => this.acceptCurrentScannerMatch());
        this.cameraRejectCardBtn?.addEventListener('click', () => this.retryScannerMatch());
        this.cameraHintSubmitBtn?.addEventListener('click', () => this.identifyCurrentCard({ useHints: true }));
        this.cameraSaveCollectionBtn?.addEventListener('click', () => {
            this.cardCollection?._persist?.();
            this.showToast('Card Collection', 'Collection saved locally in this browser.', 'success', 2500);
        });

        this.cameraHistoryList?.addEventListener('click', (event) => {
            const removeButton = event.target.closest('[data-history-id]');
            if (!removeButton) return;
            this.cardCollection?.removeHistoryEntry(removeButton.dataset.historyId);
        });

        this.cameraSummaryList?.addEventListener('click', (event) => {
            const counterButton = event.target.closest('[data-card-id][data-action]');
            if (!counterButton) return;
            const cardId = counterButton.dataset.cardId;
            const currentCount = this.cardCollection?.getCardCount(cardId) || 0;
            const nextCount = counterButton.dataset.action === 'increment' ? currentCount + 1 : currentCount - 1;
            const card = this.cardCollection?.state?.cards?.[cardId]?.card;
            if (card) this.cardCollection?.setCardCount(card, nextCount);
        });

        this.cameraSummaryList?.addEventListener('change', (event) => {
            const input = event.target.closest('input[data-card-id]');
            if (!input) return;
            const card = this.cardCollection?.state?.cards?.[input.dataset.cardId]?.card;
            if (card) this.cardCollection?.setCardCount(card, input.value);
        });

        this.setCameraMode(this.cameraMode, { force: true });
        this.resetScannerPreview();
    }

    setCameraMode(mode, { force = false } = {}) {
        if (!force && mode === this.cameraMode) return;
        this.cameraMode = mode === 'collection' ? 'collection' : 'insights';
        const isCollection = this.cameraMode === 'collection';

        this.cameraModal?.classList.toggle('is-collection-mode', isCollection);
        this.cameraCollectionPanel && (this.cameraCollectionPanel.hidden = !isCollection);
        this.cameraInsightsModeBtn?.classList.toggle('active', !isCollection);
        this.cameraCollectionModeBtn?.classList.toggle('active', isCollection);
        if (this.cameraModalSubtitle) {
            this.cameraModalSubtitle.textContent = isCollection
                ? 'Identify cards with the camera, confirm the match, and save them to My Collection.'
                : 'Share a card or poster and get real-time insights.';
        }
        if (this.cameraIdentifyButton) {
            this.cameraIdentifyButton.textContent = isCollection ? 'Identify Card' : 'Send Camera Frame';
        }

        if (isCollection) {
            this.renderScannerCollectionPanels();
        } else {
            this.hideScannerHints();
        }
    }

    hideScannerHints() {
        if (this.cameraHintSection) this.cameraHintSection.hidden = true;
    }

    showScannerHints(message = null) {
        if (this.cameraHintSection) this.cameraHintSection.hidden = false;
        if (message) {
            this.updateCameraStatus(message);
        }
    }

    getCameraFacingDescription(mode = this.cameraFacingMode) {
        return mode === 'environment' ? 'rear' : 'front';
    }

    updateCameraSwitchButton() {
        if (!this.cameraSwitchText) return;
        const nextMode = this.cameraFacingMode === 'environment' ? 'Front' : 'Rear';
        this.cameraSwitchText.textContent = `Use ${nextMode} Camera`;
        if (this.cameraSwitchButton) {
            this.cameraSwitchButton.setAttribute('aria-label', `Switch to ${nextMode.toLowerCase()} camera`);
        }
    }

    setCameraSwitchEnabled(isEnabled) {
        if (!this.cameraSwitchButton) return;
        this.cameraSwitchButton.disabled = !isEnabled;
    }

    async toggleCameraFacingMode() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            return;
        }

        this.cameraFacingMode = this.cameraFacingMode === 'environment' ? 'user' : 'environment';
        this.updateCameraSwitchButton();
        this.updateCameraStatus(`Switching to ${this.getCameraFacingDescription()} camera...`);
        await this.restartCameraPreview();
    }

    async restartCameraPreview() {
        this.stopCameraStream();
        await this.startCameraPreview();
    }

    async openCameraModal() {
        if (!this.cameraModalOverlay) return;
        this.cameraModalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';

        this.setCameraMode(this.cameraMode, { force: true });
        this.updateCameraSwitchButton();
        this.renderScannerCollectionPanels();
        await this.startCameraPreview();
        await this.startCameraScanningSession();
    }

    closeCameraModal() {
        if (!this.cameraModalOverlay) return;
        this.cameraModalOverlay.classList.remove('active');
        document.body.style.overflow = '';
        this.pendingCardScan = null;
        this.stopCameraScanning();
        this.stopCameraStream();
        this.resetScannerPreview();
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
            this.setCameraSwitchEnabled(false);
            return;
        }

        try {
            const videoConstraints = {
                facingMode: this.cameraFacingMode === 'environment' ? { ideal: 'environment' } : { ideal: 'user' }
            };

            this.cameraStream = await navigator.mediaDevices.getUserMedia({
                video: videoConstraints,
                audio: false
            });

            this.cameraPreview.srcObject = this.cameraStream;
            await this.cameraPreview.play().catch(() => {});
            const label = this.getCameraFacingDescription();
            this.updateCameraStatus(`Camera ready (${label} camera). Capture or scan when you are ready.`);
            this.setCameraSwitchEnabled(true);
        } catch (error) {
            console.error('Camera preview failed:', error);
            if (this.cameraFacingMode === 'environment') {
                console.warn('Rear camera unavailable, falling back to front camera.');
                this.cameraFacingMode = 'user';
                this.updateCameraSwitchButton();
                await this.startCameraPreview();
                return;
            }
            this.updateCameraStatus('Camera access denied or unavailable.');
            this.setCameraSwitchEnabled(false);
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

    captureCurrentCameraFrame() {
        if (!this.cameraPreview || this.cameraPreview.readyState < 2) {
            return null;
        }
        const canvas = document.createElement('canvas');
        canvas.width = this.cameraPreview.videoWidth;
        canvas.height = this.cameraPreview.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(this.cameraPreview, 0, 0);
        return canvas.toDataURL('image/jpeg', 0.92);
    }

    async identifyCurrentCard({ useHints = false } = {}) {
        if (this.cameraMode !== 'collection') {
            return this.sendCameraSnapshot('manual');
        }

        const imageDataUrl = this.captureCurrentCameraFrame();
        if (!imageDataUrl) {
            this.updateCameraStatus('Waiting for a clear camera frame before identifying the card.');
            return false;
        }

        this.lastScannerFrame = imageDataUrl;
        this.updateCameraStatus('Identifying the card...');
        this.cameraIdentifyButton && (this.cameraIdentifyButton.disabled = true);
        this.hideScannerHints();

        try {
            const prompt = this.buildCardIdentificationPrompt({
                attempt: useHints ? Math.max(3, this.scannerAttemptCount + 1) : this.scannerAttemptCount + 1,
                previousGuess: this.currentScannerMatch?.guess,
                hints: useHints ? this.cameraHintInput?.value?.trim() : ''
            });
            const responseText = await this.requestScannerResponse(imageDataUrl, prompt);
            const guess = this.parseScannerGuess(responseText);
            const matchedCard = await this.findBestMatchingCard(guess);
            this.currentScannerMatch = {
                guess,
                matchedCard,
                responseText,
                imageDataUrl
            };
            this.scannerAttemptCount = useHints ? 3 : this.scannerAttemptCount + 1;
            this.renderScannerMatch();
            this.updateCameraStatus(matchedCard
                ? `Best match: ${matchedCard.name}${matchedCard.set?.name ? ` from ${matchedCard.set.name}` : ''}`
                : 'I found a guess, but I could not confidently match it in the card database.');
            return true;
        } catch (error) {
            console.error('Card identification failed:', error);
            this.updateCameraStatus('Could not identify the card right now.');
            this.showToast('Card Scanner', 'Unable to identify the current card.', 'error', 3500);
            return false;
        } finally {
            this.cameraIdentifyButton && (this.cameraIdentifyButton.disabled = false);
        }
    }

    buildCardIdentificationPrompt({ attempt = 1, previousGuess = null, hints = '' } = {}) {
        const promptParts = [
            'Identify the most visible Pokémon TCG card in this image.',
            'Reply with exactly six lines in this format:',
            'Card: <best full card name>',
            'Pokemon: <pokemon name or unknown>',
            'Set: <set name or unknown>',
            'Number: <printed card number or unknown>',
            'HP: <hp or unknown>',
            'Confidence: <high|medium|low>',
        ];

        if (attempt >= 2 && previousGuess) {
            promptParts.push(`The previous guess was wrong: ${previousGuess.cardName || previousGuess.pokemonName || 'unknown card'}${previousGuess.setName ? ` from ${previousGuess.setName}` : ''}. Suggest a different card.`);
        }

        if (hints) {
            promptParts.push(`User hints: ${hints}`);
        }

        promptParts.push('Keep the answer short and do not add any extra commentary.');
        return promptParts.join(' ');
    }

    requestScannerResponse(imageDataUrl, prompt) {
        return new Promise(async (resolve, reject) => {
            if (!this.realtimeVoice || !this.useRealtimeApi) {
                reject(new Error('Realtime voice is not available'));
                return;
            }

            this.pendingCardScan = { resolve, reject };

            try {
                await this.activateRealtimeConversation({ announce: false });
                const sent = await this.realtimeVoice.sendImage(imageDataUrl, prompt);
                if (!sent) {
                    this.pendingCardScan = null;
                    reject(new Error('Image was not sent'));
                }
            } catch (error) {
                this.pendingCardScan = null;
                reject(error);
            }
        });
    }

    parseScannerGuess(text = '') {
        const lines = text.split(/\n+/).map(line => line.trim()).filter(Boolean);
        const readField = (label) => {
            const match = lines.find(line => line.toLowerCase().startsWith(`${label.toLowerCase()}:`));
            return match ? match.split(':').slice(1).join(':').trim() : '';
        };
        return {
            cardName: readField('Card'),
            pokemonName: readField('Pokemon'),
            setName: readField('Set'),
            number: readField('Number'),
            hp: readField('HP'),
            confidence: readField('Confidence') || 'medium'
        };
    }

    async findBestMatchingCard(guess) {
        const terms = [...new Set([guess.cardName, guess.pokemonName].filter(Boolean))];
        if (terms.length === 0) return null;

        const candidates = [];
        for (const term of terms) {
            try {
                const response = await fetch('/api/realtime/tool', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tool_name: 'search_pokemon_cards',
                        arguments: { pokemon_name: term }
                    })
                });
                if (!response.ok) continue;
                const data = await response.json();
                const cards = data?.result?.cards || [];
                cards.forEach(card => {
                    if (!candidates.some(existing => existing.id === card.id)) {
                        candidates.push(card);
                    }
                });
            } catch (error) {
                console.warn('Candidate lookup failed:', error);
            }
        }

        if (candidates.length === 0) return null;

        const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
        const wantedName = normalize(guess.cardName);
        const wantedSet = normalize(guess.setName);
        const wantedNumber = normalize(guess.number);
        const wantedHp = normalize(guess.hp);

        const scored = candidates.map(card => {
            let score = 0;
            const cardName = normalize(card.name);
            const setName = normalize(card.set?.name);
            if (wantedName && cardName === wantedName) score += 70;
            else if (wantedName && (cardName.includes(wantedName) || wantedName.includes(cardName))) score += 35;
            if (wantedSet && setName === wantedSet) score += 35;
            else if (wantedSet && (setName.includes(wantedSet) || wantedSet.includes(setName))) score += 15;
            if (wantedNumber && normalize(card.number) === wantedNumber) score += 30;
            if (wantedHp && normalize(card.hp) === wantedHp) score += 10;
            return { card, score };
        }).sort((a, b) => b.score - a.score);

        return scored[0]?.card || candidates[0];
    }

    renderScannerMatch() {
        const match = this.currentScannerMatch;
        const card = match?.matchedCard;
        const guess = match?.guess;
        const imageUrl = card?.images?.small || card?.imageSmall || '';
        if (this.cameraIdentifiedCardImage) {
            this.cameraIdentifiedCardImage.hidden = !imageUrl;
            this.cameraIdentifiedCardImage.src = imageUrl || '';
        }
        if (this.cameraPreviewPlaceholder) {
            this.cameraPreviewPlaceholder.hidden = Boolean(imageUrl);
        }
        if (this.cameraIdentifiedCardTitle) {
            this.cameraIdentifiedCardTitle.textContent = card?.name || guess?.cardName || 'Best guess ready for review';
        }
        if (this.cameraIdentifiedCardMeta) {
            const pieces = [
                card?.set?.name || guess?.setName || 'Set unknown',
                card?.number || guess?.number || 'Number unknown',
                guess?.confidence ? `Confidence: ${guess.confidence}` : ''
            ].filter(Boolean);
            this.cameraIdentifiedCardMeta.textContent = pieces.join(' · ');
        }
        if (this.cameraPreviewTags) {
            const tags = [
                guess?.pokemonName && guess.pokemonName.toLowerCase() !== 'unknown' ? guess.pokemonName : '',
                guess?.hp && guess.hp.toLowerCase() !== 'unknown' ? `${guess.hp} HP` : '',
                card?.rarity || ''
            ].filter(Boolean);
            this.cameraPreviewTags.innerHTML = tags.map(tag => `<span class="camera-preview-tag">${tag}</span>`).join('');
        }
        if (this.cameraAcceptCardBtn) this.cameraAcceptCardBtn.disabled = !card;
        if (this.cameraRejectCardBtn) this.cameraRejectCardBtn.disabled = !match;
    }

    resetScannerPreview() {
        this.currentScannerMatch = null;
        this.scannerAttemptCount = 0;
        if (this.cameraHintInput) this.cameraHintInput.value = '';
        if (this.cameraIdentifiedCardImage) {
            this.cameraIdentifiedCardImage.hidden = true;
            this.cameraIdentifiedCardImage.src = '';
        }
        if (this.cameraPreviewPlaceholder) this.cameraPreviewPlaceholder.hidden = false;
        if (this.cameraIdentifiedCardTitle) this.cameraIdentifiedCardTitle.textContent = 'No card identified yet';
        if (this.cameraIdentifiedCardMeta) this.cameraIdentifiedCardMeta.textContent = 'Use the live preview and tap Identify Card to start logging cards you own.';
        if (this.cameraPreviewTags) this.cameraPreviewTags.innerHTML = '';
        if (this.cameraAcceptCardBtn) this.cameraAcceptCardBtn.disabled = true;
        if (this.cameraRejectCardBtn) this.cameraRejectCardBtn.disabled = true;
        this.hideScannerHints();
    }

    async acceptCurrentScannerMatch() {
        const card = this.currentScannerMatch?.matchedCard;
        if (!card) return;
        this.cardCollection?.recordScan(card, { source: 'scanner' });
        this.animateScannerCardToHistory();
        window.setTimeout(() => this.resetScannerPreview(), 220);
        this.updateCameraStatus(`Saved ${card.name} to your collection.`);
        this.showToast('Card Scanner', `${card.name} saved to My Collection.`, 'success', 2500);
    }

    async retryScannerMatch() {
        if (!this.currentScannerMatch) return;
        if (this.scannerAttemptCount >= 2) {
            this.showScannerHints('Still not right? Add a clue like Pokémon name, HP, attack, or expansion and try again.');
            return;
        }
        await this.identifyCurrentCard();
    }

    renderScannerCollectionPanels() {
        if (!this.cardCollection) return;
        const history = this.cardCollection.getHistory();
        const summary = this.cardCollection.getOwnedCards().sort((a, b) => (a.name || '').localeCompare(b.name || ''));

        if (this.cameraHistoryList) {
            this.cameraHistoryList.innerHTML = history.length > 0
                ? history.map(entry => `
                    <div class="camera-history-item">
                        ${entry.image ? `<img class="camera-history-thumb" src="${entry.image}" alt="${entry.cardName}">` : '<div class="camera-history-thumb"></div>'}
                        <div class="camera-history-details">
                            <strong>${entry.cardName}</strong>
                            <span>${entry.setName || 'Set unknown'} · +${entry.countChange}</span>
                        </div>
                        <button class="camera-history-remove" type="button" data-history-id="${entry.id}" aria-label="Remove ${entry.cardName} from history">✕</button>
                    </div>
                `).join('')
                : '<div class="camera-empty-state">Accepted cards will appear here.</div>';
        }

        if (this.cameraSummaryList) {
            this.cameraSummaryList.innerHTML = summary.length > 0
                ? summary.map(card => `
                    <div class="camera-summary-item">
                        <div class="camera-summary-details">
                            <strong>${card.name}</strong>
                            <span>${card.set?.name || 'Set unknown'}${card.number ? ` · #${card.number}` : ''}</span>
                        </div>
                        <div class="tcg-collection-counter camera-summary-counter">
                            <button class="tcg-collection-counter-btn" type="button" data-card-id="${card.id}" data-action="decrement" aria-label="Decrease ${card.name} count">−</button>
                            <input class="tcg-collection-counter-input" type="number" min="0" value="${card._collectionCount || 0}" data-card-id="${card.id}" aria-label="${card.name} count">
                            <button class="tcg-collection-counter-btn" type="button" data-card-id="${card.id}" data-action="increment" aria-label="Increase ${card.name} count">+</button>
                        </div>
                    </div>
                `).join('')
                : '<div class="camera-empty-state">Your saved card counts will appear here.</div>';
        }
    }

    handleCardCollectionUpdated() {
        this.renderScannerCollectionPanels();
        this.tcgDatabase?.refreshCollectionState?.();
    }

    animateScannerCardToHistory() {
        if (!this.cameraPreviewCard) return;
        this.cameraPreviewCard.classList.remove('is-saving');
        void this.cameraPreviewCard.offsetWidth;
        this.cameraPreviewCard.classList.add('is-saving');
        window.setTimeout(() => {
            this.cameraPreviewCard?.classList.remove('is-saving');
        }, 520);
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

    loadFaceIdOverlayPreference() {
        try {
            const stored = localStorage.getItem('faceIdOverlayEnabled');
            if (stored === null) {
                return true;
            }
            return stored === 'true';
        } catch (error) {
            console.warn('Unable to read face overlay preference, defaulting to enabled', error);
            return true;
        }
    }

    saveFaceIdOverlayPreference(enabled) {
        this.faceIdOverlayEnabled = Boolean(enabled);
        try {
            localStorage.setItem('faceIdOverlayEnabled', String(this.faceIdOverlayEnabled));
        } catch (error) {
            console.warn('Unable to persist face overlay preference', error);
        }
    }

    shouldShowFaceIdOverlay() {
        return this.faceIdOverlayEnabled !== false;
    }

    loadSpriteStyle() {
        try {
            return localStorage.getItem('pokedex_sprite_style') || 'official-artwork';
        } catch {
            return 'official-artwork';
        }
    }

    saveSpriteStyle(style) {
        this.spriteStyle = style || 'official-artwork';
        try {
            localStorage.setItem('pokedex_sprite_style', this.spriteStyle);
        } catch { /* ignore */ }
        this.gridView.refreshSprites();
    }

    loadCryPreference() {
        try {
            const raw = localStorage.getItem('pokedex_cry_enabled');
            if (raw === null) return true;
            return raw === 'true';
        } catch {
            return true;
        }
    }

    saveCryPreference(enabled) {
        this.criesEnabled = Boolean(enabled);
        try {
            localStorage.setItem('pokedex_cry_enabled', String(this.criesEnabled));
        } catch { /* ignore */ }
        if (!this.criesEnabled && this.detailView && typeof this.detailView.stopPokemonCry === 'function') {
            this.detailView.stopPokemonCry();
        }
    }

    loadScrollResetPreference() {
        try {
            const raw = localStorage.getItem('pokedex_scroll_reset');
            if (raw === null) return true;
            return raw === 'true';
        } catch {
            return true;
        }
    }

    saveScrollResetPreference(enabled) {
        this.scrollResetEnabled = Boolean(enabled);
        try {
            localStorage.setItem('pokedex_scroll_reset', String(this.scrollResetEnabled));
        } catch { /* ignore */ }
    }

    setupScrollResetControls() {
        const toggle = document.getElementById('scrollResetToggle');
        if (!toggle) return;
        toggle.checked = this.scrollResetEnabled;
        if (toggle.dataset.listenerAttached === 'true') return;
        toggle.addEventListener('change', (event) => {
            this.saveScrollResetPreference(event.target.checked);
        });
        toggle.dataset.listenerAttached = 'true';
    }

    setupCurrencyControls() {
        const cc = typeof CurrencyConverter !== 'undefined' ? CurrencyConverter : null;
        if (!cc) return;

        // ── Currency selector ────────────────────────────────────────
        const select = document.getElementById('currencySelect');
        if (select) {
            const currencies = cc.getAvailableCurrencies();
            const current = cc.getCurrency();
            select.innerHTML = currencies.map(c =>
                `<option value="${c.code}" ${c.code === current ? 'selected' : ''}>${c.flag} ${c.code} — ${c.name} (${c.symbol})</option>`
            ).join('');
            this._updatePriceUnitLabel();
            if (select.dataset.listenerAttached !== 'true') {
                select.addEventListener('change', () => {
                    cc.setCurrency(select.value);
                    this.currency = select.value;
                    this._updatePriceUnitLabel();
                    this._renderBucketEditor();
                    this._refreshPriceDisplays();
                });
                select.dataset.listenerAttached = 'true';
            }
        }

        // ── Number locale selector ───────────────────────────────────
        const localeSelect = document.getElementById('numberLocaleSelect');
        if (localeSelect) {
            const presets = cc.getLocalePresets();
            const currentLocale = cc.getLocale();
            localeSelect.innerHTML = presets.map(p =>
                `<option value="${p.key}" ${p.key === currentLocale ? 'selected' : ''}>${p.name}</option>`
            ).join('');
            if (localeSelect.dataset.listenerAttached !== 'true') {
                localeSelect.addEventListener('change', () => {
                    cc.setLocale(localeSelect.value);
                    this._renderBucketEditor();
                    this._refreshPriceDisplays();
                });
                localeSelect.dataset.listenerAttached = 'true';
            }
        }

        // ── Price bucket editor ──────────────────────────────────────
        this._renderBucketEditor();

        const addBtn = document.getElementById('addBucketBtn');
        if (addBtn && addBtn.dataset.listenerAttached !== 'true') {
            addBtn.addEventListener('click', () => {
                const buckets = cc.getBuckets();
                if (buckets.length >= 8) return; // max 8 buckets
                // Insert a new bucket before the last one
                const last = buckets[buckets.length - 1];
                const prevMax = buckets.length >= 2 ? (buckets[buckets.length - 2].max === Infinity ? 500 : buckets[buckets.length - 2].max) : 50;
                const newMax = prevMax + Math.round((500 - prevMax) / 2);
                const colors = ['#17a2b8', '#6f42c1', '#e83e8c', '#20c997', '#6610f2'];
                const color = colors[buckets.length % colors.length];
                buckets.splice(buckets.length - 1, 0, { max: newMax, color, label: 'New' });
                cc.setBuckets(buckets);
                this._renderBucketEditor();
                this._refreshPriceDisplays();
            });
            addBtn.dataset.listenerAttached = 'true';
        }

        const resetBtn = document.getElementById('resetBucketsBtn');
        if (resetBtn && resetBtn.dataset.listenerAttached !== 'true') {
            resetBtn.addEventListener('click', () => {
                cc.resetBuckets();
                this._renderBucketEditor();
                this._refreshPriceDisplays();
            });
            resetBtn.dataset.listenerAttached = 'true';
        }
    }

    setupCollectionImportExportControls() {
        if (this.collectionExportBtn && this.collectionExportBtn.dataset.listenerAttached !== 'true') {
            this.collectionExportBtn.addEventListener('click', () => this.exportCardCollection());
            this.collectionExportBtn.dataset.listenerAttached = 'true';
        }

        if (this.collectionImportBtn && this.collectionImportBtn.dataset.listenerAttached !== 'true') {
            this.collectionImportBtn.addEventListener('click', () => this.collectionImportInput?.click());
            this.collectionImportBtn.dataset.listenerAttached = 'true';
        }

        if (this.collectionImportInput && this.collectionImportInput.dataset.listenerAttached !== 'true') {
            this.collectionImportInput.addEventListener('change', async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                try {
                    const text = await file.text();
                    this.cardCollection?.importState(text);
                    this.updateCollectionImportStatus(`Imported ${file.name} successfully.`, 'success');
                    this.showToast('Card Collection', 'Collection imported successfully.', 'success', 2500);
                } catch (error) {
                    console.error('Collection import failed:', error);
                    this.updateCollectionImportStatus('Import failed. Please choose a valid JSON export.', 'error');
                    this.showToast('Card Collection', 'Unable to import that file.', 'error', 3500);
                } finally {
                    event.target.value = '';
                }
            });
            this.collectionImportInput.dataset.listenerAttached = 'true';
        }
    }

    updateCollectionImportStatus(message, type = 'info') {
        if (!this.collectionImportStatus) return;
        this.collectionImportStatus.textContent = message;
        this.collectionImportStatus.dataset.state = type;
    }

    exportCardCollection() {
        if (!this.cardCollection) return;
        const json = this.cardCollection.exportState();
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        const stamp = new Date().toISOString().slice(0, 10);
        link.href = url;
        link.download = `pokedex-card-collection-${stamp}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        this.updateCollectionImportStatus('Collection exported from this browser.', 'success');
        this.showToast('Card Collection', 'Collection exported to JSON.', 'success', 2500);
    }

    _renderBucketEditor() {
        const container = document.getElementById('priceBucketsEditor');
        const cc = typeof CurrencyConverter !== 'undefined' ? CurrencyConverter : null;
        if (!container || !cc) return;

        const buckets = cc.getBuckets();
        const info = cc.getInfo();

        // Build the color bar + handles
        let html = '<div class="price-bucket-bar">';
        // Determine scale max for display (last finite threshold * 2, min 200)
        const finiteMaxes = buckets.filter(b => b.max !== Infinity).map(b => b.max);
        const scaleMax = finiteMaxes.length > 0 ? Math.max(finiteMaxes[finiteMaxes.length - 1] * 1.5, 200) : 500;

        buckets.forEach((bucket, i) => {
            const prevMax = i > 0 ? buckets[i - 1].max : 0;
            const bMax = bucket.max === Infinity ? scaleMax : bucket.max;
            const left = (prevMax / scaleMax) * 100;
            const width = ((bMax - prevMax) / scaleMax) * 100;
            const label = bucket.max === Infinity ? `${info.symbol}${this._formatBucketVal(prevMax)}+` :
                `${info.symbol}${this._formatBucketVal(prevMax)} – ${info.symbol}${this._formatBucketVal(bucket.max)}`;
            html += `<div class="price-bucket-segment" style="left:${left}%;width:${width}%;background:${bucket.color}" title="${label}">
                <span class="price-bucket-label">${label}</span>
            </div>`;
        });

        // Handles between buckets (not for the last bucket)
        for (let i = 0; i < buckets.length - 1; i++) {
            const pos = (buckets[i].max / scaleMax) * 100;
            html += `<div class="price-bucket-handle" data-index="${i}" style="left:${pos}%" title="${info.symbol}${this._formatBucketVal(buckets[i].max)}">
                <span class="handle-value">${info.symbol}${this._formatBucketVal(buckets[i].max)}</span>
            </div>`;
        }
        html += '</div>';

        // Bucket list with color pickers, editable thresholds, and remove buttons
        html += '<div class="price-bucket-list">';
        buckets.forEach((bucket, i) => {
            const prevMax = i > 0 ? buckets[i - 1].max : 0;
            const canRemove = buckets.length > 2 && i < buckets.length - 1;
            let rangeHtml;
            if (bucket.max === Infinity) {
                rangeHtml = `<span class="price-bucket-range">${info.symbol}${this._formatBucketVal(prevMax)}+</span>`;
            } else {
                rangeHtml = `<span class="price-bucket-range">${info.symbol}${this._formatBucketVal(prevMax)} – ${info.symbol}<input type="number" class="price-bucket-max-input" data-index="${i}" value="${bucket.max}" min="1" step="1"></span>`;
            }
            html += `<div class="price-bucket-row">
                <input type="color" class="price-bucket-color" data-index="${i}" value="${bucket.color}">
                ${rangeHtml}
                <input type="text" class="price-bucket-label-input" data-index="${i}" value="${bucket.label}" maxlength="15" placeholder="Label">
                ${canRemove ? `<button class="price-bucket-remove-btn" data-index="${i}" title="Remove bucket">✕</button>` : '<span class="price-bucket-remove-spacer"></span>'}
            </div>`;
        });
        html += '</div>';

        container.innerHTML = html;

        // Wire drag handles
        container.querySelectorAll('.price-bucket-handle').forEach(handle => {
            this._setupBucketHandleDrag(handle, container, buckets, scaleMax);
        });

        // Wire color pickers
        container.querySelectorAll('.price-bucket-color').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                buckets[idx].color = input.value;
                cc.setBuckets(buckets);
                this._renderBucketEditor();
                this._refreshPriceDisplays();
            });
        });

        // Wire label inputs
        container.querySelectorAll('.price-bucket-label-input').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                buckets[idx].label = input.value.trim() || 'Unlabeled';
                cc.setBuckets(buckets);
            });
        });

        // Wire max-value inputs (typed thresholds)
        container.querySelectorAll('.price-bucket-max-input').forEach(input => {
            input.addEventListener('change', () => {
                const idx = parseInt(input.dataset.index);
                let newVal = parseInt(input.value);
                if (isNaN(newVal) || newVal < 1) newVal = 1;
                const minVal = idx > 0 ? buckets[idx - 1].max + 1 : 1;
                const maxVal = idx < buckets.length - 2 ? buckets[idx + 1].max - 1 : 99999;
                newVal = Math.max(minVal, Math.min(maxVal, newVal));
                buckets[idx].max = newVal;
                cc.setBuckets(buckets);
                this._renderBucketEditor();
                this._refreshPriceDisplays();
            });
        });

        // Wire remove buttons
        container.querySelectorAll('.price-bucket-remove-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.dataset.index);
                buckets.splice(idx, 1);
                cc.setBuckets(buckets);
                this._renderBucketEditor();
                this._refreshPriceDisplays();
            });
        });
    }

    _setupBucketHandleDrag(handle, container, buckets, scaleMax) {
        const cc = CurrencyConverter;
        const idx = parseInt(handle.dataset.index);
        const bar = container.querySelector('.price-bucket-bar');
        const segments = bar.querySelectorAll('.price-bucket-segment');
        const handles = bar.querySelectorAll('.price-bucket-handle');
        const info = cc.getInfo();

        const updateBarVisual = () => {
            // Update segment positions and labels
            segments.forEach((seg, i) => {
                const prevMax = i > 0 ? buckets[i - 1].max : 0;
                const bMax = buckets[i].max === Infinity ? scaleMax : buckets[i].max;
                const left = (prevMax / scaleMax) * 100;
                const width = ((bMax - prevMax) / scaleMax) * 100;
                seg.style.left = left + '%';
                seg.style.width = width + '%';
                const label = buckets[i].max === Infinity
                    ? `${info.symbol}${this._formatBucketVal(prevMax)}+`
                    : `${info.symbol}${this._formatBucketVal(prevMax)} – ${info.symbol}${this._formatBucketVal(buckets[i].max)}`;
                seg.title = label;
                const labelEl = seg.querySelector('.price-bucket-label');
                if (labelEl) labelEl.textContent = label;
            });
            // Update handle positions and labels
            handles.forEach((h, i) => {
                const pos = (buckets[i].max / scaleMax) * 100;
                h.style.left = pos + '%';
                h.title = `${info.symbol}${this._formatBucketVal(buckets[i].max)}`;
                const valEl = h.querySelector('.handle-value');
                if (valEl) valEl.textContent = `${info.symbol}${this._formatBucketVal(buckets[i].max)}`;
            });
        };

        const onMove = (clientX) => {
            const rect = bar.getBoundingClientRect();
            let pct = (clientX - rect.left) / rect.width;
            pct = Math.max(0.01, Math.min(0.99, pct));
            let newVal = Math.round(pct * scaleMax);
            const minVal = idx > 0 ? buckets[idx - 1].max + 1 : 1;
            const maxVal = idx < buckets.length - 2 ? buckets[idx + 1].max - 1 : scaleMax - 1;
            newVal = Math.max(minVal, Math.min(maxVal, newVal));
            buckets[idx].max = newVal;
            updateBarVisual();
        };

        const onMouseMove = (e) => onMove(e.clientX);
        const onTouchMove = (e) => { e.preventDefault(); onMove(e.touches[0].clientX); };
        const onEnd = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onEnd);
            document.removeEventListener('touchmove', onTouchMove);
            document.removeEventListener('touchend', onEnd);
            cc.setBuckets(buckets);
            this._renderBucketEditor();
            this._refreshPriceDisplays();
        };

        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onEnd);
        });
        handle.addEventListener('touchstart', (e) => {
            e.preventDefault();
            document.addEventListener('touchmove', onTouchMove, { passive: false });
            document.addEventListener('touchend', onEnd);
        });
    }

    _formatBucketVal(val) {
        if (val >= 1000) return Math.round(val).toLocaleString('en');
        if (val >= 100) return Math.round(val).toString();
        return val.toString();
    }

    _updatePriceUnitLabel() {
        const el = document.getElementById('tcgPriceUnit');
        if (!el || typeof CurrencyConverter === 'undefined') return;
        const cur = CurrencyConverter.getCurrency();
        el.textContent = `(${cur})`;
    }

    _refreshPriceDisplays() {
        // Re-render the currently visible TCG view so prices update
        if (this.currentCanvasState?.type === 'tcg-detail' && this.tcgDetail) {
            // Re-render just the price section
            const card = this.currentTcgCard;
            if (card) {
                const pricesEl = this.tcgDetail.detailView?.querySelector('.tcg-card-prices');
                if (pricesEl) {
                    pricesEl.innerHTML = this.tcgDetail.buildPricesHTML(card);
                }
            }
        } else if (this.currentCanvasState?.type === 'tcg-database' && this.tcgDatabase) {
            this.tcgDatabase._renderCardGrid();
        } else if (this.currentCanvasState?.type === 'tcg-gallery' && this.tcgGallery) {
            // Gallery needs full re-render
            const galleryData = this.currentCanvasState.data;
            if (galleryData?.cards) {
                this.tcgGallery.displayCards(galleryData.cards, galleryData.pokemon_name);
            }
        }
    }

    setupCryControls() {
        const toggle = document.getElementById('cryToggle');
        if (!toggle) return;
        toggle.checked = this.criesEnabled;

        if (toggle.dataset.listenerAttached === 'true') {
            return;
        }

        toggle.addEventListener('change', (event) => {
            this.saveCryPreference(event.target.checked);
        });

        toggle.dataset.listenerAttached = 'true';
    }

    setupSpriteStyleControls() {
        const grid = document.getElementById('spriteStyleGrid');
        if (!grid) return;

        // Mark the current selection
        grid.querySelectorAll('.sprite-style-option').forEach(opt => {
            opt.classList.toggle('selected', opt.dataset.style === this.spriteStyle);
        });

        if (grid.dataset.listenerAttached === 'true') return;
        grid.addEventListener('click', (e) => {
            const opt = e.target.closest('.sprite-style-option');
            if (!opt) return;
            grid.querySelectorAll('.sprite-style-option').forEach(o => o.classList.remove('selected'));
            opt.classList.add('selected');
            this.saveSpriteStyle(opt.dataset.style);
        });
        grid.dataset.listenerAttached = 'true';
    }

    loadVoiceActorPreference() {
        try {
            return localStorage.getItem('voiceActorPreference') || 'alloy';
        } catch (error) {
            console.warn('Unable to read voice preference, defaulting to Alloy', error);
            return 'alloy';
        }
    }

    saveVoiceActorPreference(voice) {
        const normalized = voice || 'alloy';
        this.voicePreference = normalized;
        try {
            localStorage.setItem('voiceActorPreference', normalized);
        } catch (error) {
            console.warn('Unable to persist voice preference', error);
        }
        this.applyVoicePreference();
    }

    applyVoicePreference() {
        if (this.realtimeVoice && typeof this.realtimeVoice.setVoicePreference === 'function') {
            this.realtimeVoice.setVoicePreference(this.voicePreference);
        }
    }

    initializeSpeechVoices() {
        if (!this.synthesis) {
            return;
        }

        const updateVoices = () => {
            this.availableSpeechVoices = this.synthesis.getVoices() || [];
        };

        updateVoices();

        if (typeof this.synthesis.onvoiceschanged !== 'undefined') {
            this.synthesis.onvoiceschanged = updateVoices;
        }
    }

    getSpeechVoiceProfile(preference = this.voicePreference) {
        const defaults = { voice: null, rate: 1, pitch: 1 };
        if (!this.synthesis) {
            return defaults;
        }

        const voices = (this.availableSpeechVoices && this.availableSpeechVoices.length > 0)
            ? this.availableSpeechVoices
            : this.synthesis.getVoices();

        if (!voices || voices.length === 0) {
            return defaults;
        }

        const profiles = {
            alloy: { tokens: ['guy', 'david', 'mark', 'daniel', 'ryan'], rate: 1.0, pitch: 1.0 },
            ash: { tokens: ['aria', 'zira', 'ash', 'female'], rate: 1.0, pitch: 1.05 },
            ballad: { tokens: ['guy', 'brian', 'mark', 'male'], rate: 0.96, pitch: 0.95 },
            cedar: { tokens: ['jenny', 'linda', 'female'], rate: 0.97, pitch: 1.0 },
            coral: { tokens: ['ava', 'allison', 'bright', 'female'], rate: 1.05, pitch: 1.08 },
            echo: { tokens: ['guy', 'davis', 'roger', 'male'], rate: 1.02, pitch: 0.98 },
            ember: { tokens: ['aria', 'zira', 'jessa', 'susan', 'female'], rate: 0.98, pitch: 1.08 },
            marin: { tokens: ['emma', 'serena', 'sofia', 'female'], rate: 0.95, pitch: 1.02 },
            luna: { tokens: ['luna', 'sofia', 'midnight', 'female'], rate: 0.96, pitch: 1.12 },
            pearl: { tokens: ['pearl', 'clara', 'olivia', 'female'], rate: 0.99, pitch: 0.97 },
            sage: { tokens: ['george', 'brian', 'roger', 'bass', 'baritone'], rate: 0.9, pitch: 0.85 },
            shimmer: { tokens: ['jenny', 'ava', 'bright', 'youth'], rate: 1.08, pitch: 1.15 },
            sol: { tokens: ['ava', 'allison', 'hero', 'male'], rate: 1.1, pitch: 1.05 },
            verse: { tokens: ['emma', 'serena', 'eva', 'olivia', 'neural'], rate: 0.94, pitch: 0.92 }
        };

        const profile = profiles[preference] || profiles.alloy;
        const match = voices.find((voice) => profile.tokens.some((token) => voice.name.toLowerCase().includes(token)));

        return {
            voice: match || voices[0],
            rate: profile.rate,
            pitch: profile.pitch
        };
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
        
        // Don't interrupt if realtime voice is actively responding
        if (this.realtimeVoice && this.realtimeVoice.isResponseActive) {
            console.log('Face identification skipped - voice response in progress');
            return;
        }

        // Rate limiting: Check cooldown period
        const now = Date.now();
        if (now - this.lastFaceIdentificationTime < this.faceIdentificationCooldown) {
            const remainingCooldown = Math.ceil((this.faceIdentificationCooldown - (now - this.lastFaceIdentificationTime)) / 1000);
            console.log(`Face identification on cooldown (${remainingCooldown}s remaining)`);
            return;
        }

        let stream = null;
        let timeoutId = null;
        let faceIdModal = null;
        let statusText = null;
        let videoElement = null;
        const showOverlay = this.shouldShowFaceIdOverlay();

        try {
            this.isFaceIdentifying = true;
            this.lastFaceIdentificationTime = now;

            if (showOverlay) {
                // Create face identification modal to show camera preview
                faceIdModal = this.createFaceIdModal();
                document.body.appendChild(faceIdModal);
                videoElement = faceIdModal.querySelector('video');
                statusText = faceIdModal.querySelector('.face-id-status');
            } else {
                videoElement = this.createFaceIdVideoElement();
            }

            // Set timeout for camera access (10 seconds)
            const timeoutPromise = new Promise((_, reject) => {
                timeoutId = setTimeout(() => reject(new Error('Camera access timeout')), 10000);
            });

            // Get user media (camera) with timeout
            const streamPromise = navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'user',  // Use front camera
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                } 
            });

            stream = await Promise.race([streamPromise, timeoutPromise]);

            // Clear timeout if successful
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }

            // Show camera preview in modal
            const video = videoElement;
            video.srcObject = stream;
            video.autoplay = true;

            // Wait for video to be ready with timeout
            const videoReadyPromise = new Promise((resolve, reject) => {
                const videoTimeout = setTimeout(() => reject(new Error('Video load timeout')), 5000);
                video.onloadedmetadata = () => {
                    clearTimeout(videoTimeout);
                    video.play();
                    resolve();
                };
            });

            await videoReadyPromise;

            // Update modal status
            if (statusText) {
                statusText.textContent = 'Identifying...';
            }

            // Wait a bit for camera to adjust
            await new Promise(resolve => setTimeout(resolve, 500));

            // Capture frame from video
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);

            // Convert to base64 with reduced quality (0.6 is sufficient for face recognition)
            const base64Image = canvas.toDataURL('image/jpeg', 0.6);

            // Send to backend for identification with timeout using AbortController
            const controller = new AbortController();
            timeoutId = setTimeout(() => controller.abort(), 15000);

            const response = await fetch('/api/face/identify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    image: base64Image
                }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }

            const result = await response.json();

            console.log('Face identification result:', result);

            // Update modal with result
            if (statusText) {
                statusText.textContent = result.name ? `Hello, ${result.name}!` : 'Identifying...';
            }

            // Handle the result
            if (result.name) {
                this.handleIdentifiedUserResult(result.name, {
                    isNewUser: Boolean(result.is_new_user),
                    greetingMessage: result.is_new_user ? result.greeting_message : null
                });
            } else if (result.error) {
                // Error occurred
                console.log('Face identification error:', result.error);
            } else {
                // No face detected or not recognized
                console.log('No user identified');
            }

        } catch (error) {
            console.error('Error during face identification:', error.message || error);

            // Handle specific error cases
            if (error.name === 'AbortError') {
                console.log('Face identification timed out after 15 seconds');
            } else if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                console.log('Camera permission denied by user');
            } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                console.log('No camera found on device');
            } else if (error.message && error.message.includes('timeout')) {
                console.log('Camera access or processing timed out');
            }

        } finally {
            // Clean up: Stop all video streams
            if (stream) {
                stream.getTracks().forEach(track => {
                    track.stop();
                    console.log('Camera track stopped');
                });
            }

            // Remove face ID modal after a brief delay
            if (faceIdModal) {
                setTimeout(() => {
                    faceIdModal.classList.add('fade-out');
                    setTimeout(() => {
                        if (faceIdModal.parentNode) {
                            document.body.removeChild(faceIdModal);
                        }
                    }, 300);
                }, 1500);
            }

            this.isFaceIdentifying = false;
        }
    }

    handleIdentifiedUserResult(name, { isNewUser = false, greetingMessage = null } = {}) {
        if (!name) {
            return;
        }

        this.currentIdentifiedUser = name;
        this.cacheFaceCapture({ name });

        if (this.faceProfileNameInput && this.faceProfileNameInput.value !== name) {
            this.faceProfileNameInput.value = name;
        }

        if (isNewUser && greetingMessage) {
            this.addMessage('assistant', greetingMessage);
            console.log(`Greeting new user: ${name}`);
        } else if (!isNewUser) {
            console.log(`Same user detected: ${name} (no greeting)`);
        }

        this.syncIdentifiedUserToRealtime({ force: isNewUser });
    }

    syncIdentifiedUserToRealtime({ force = false } = {}) {
        const name = this.currentIdentifiedUser;
        if (!name) {
            return;
        }

        this.pendingRealtimeUserName = name;

        if (!this.realtimeVoice || typeof this.realtimeVoice.updateUserContext !== 'function') {
            console.log('⚠️ Realtime voice not initialized or updateUserContext method not available');
            return;
        }

        if (!this.realtimeVoice.isConnected) {
            console.log('⏳ Realtime voice not connected yet, user context queued');
            return;
        }

        if (!force && this.lastAppliedRealtimeUserName === name) {
            this.pendingRealtimeUserName = null;
            return;
        }

        const success = this.realtimeVoice.updateUserContext(name);
        if (success) {
            this.lastAppliedRealtimeUserName = name;
            this.pendingRealtimeUserName = null;
        } else {
            console.log('⚠️ Unable to update realtime user context immediately, will retry when idle');
        }
    }

    flushPendingRealtimeUserContext({ force = false } = {}) {
        if (!this.pendingRealtimeUserName) {
            return;
        }

        if (this.currentIdentifiedUser !== this.pendingRealtimeUserName) {
            this.currentIdentifiedUser = this.pendingRealtimeUserName;
        }

        this.syncIdentifiedUserToRealtime({ force });
    }

    /**
     * Create face identification modal with camera preview
     */
    createFaceIdModal() {
        const modal = document.createElement('div');
        modal.className = 'face-id-modal';
        modal.innerHTML = `
            <div class="face-id-container">
                <div class="face-id-header">
                    <span class="face-id-icon">👤</span>
                    <h3>Face Identification</h3>
                </div>
                <div class="face-id-video-container">
                    <video autoplay playsinline muted></video>
                    <div class="face-id-overlay"></div>
                </div>
                <div class="face-id-status">Accessing camera...</div>
            </div>
        `;
        return modal;
    }

    createFaceIdVideoElement() {
        const video = document.createElement('video');
        video.autoplay = true;
        video.playsInline = true;
        video.muted = true;
        video.setAttribute('playsinline', '');
        video.setAttribute('muted', '');
        return video;
    }

    async openToolsModal() {
        if (!this.toolsModalOverlay) return;
        
        this.toolsModalOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        this.pendingToolChanges = {};
        
        // Load cache config and tools
        await Promise.all([
            this.loadCacheConfig(),
            this.loadTools()
        ]);
        this.renderToolsModal();
        this.setupCacheControls();
        this.setupFaceIdentificationControls();
        this.setupVoiceControls();
        this.setupSpriteStyleControls();
        this.setupCryControls();
        this.setupScrollResetControls();
        this.setupCurrencyControls();
        this.setupCollectionImportExportControls();
    }
    
    async loadCacheConfig() {
        try {
            const response = await fetch('/api/cache/config');
            if (response.ok) {
                this.cacheConfig = await response.json();
            }
        } catch (error) {
            console.error('Error loading cache config:', error);
        }
    }
    
    setupCacheControls() {
        // Cache toggle
        const cacheToggle = document.getElementById('cacheToggle');
        if (cacheToggle) {
            cacheToggle.checked = this.cacheConfig?.enabled ?? true;
            cacheToggle.addEventListener('change', async (e) => {
                const enabled = Boolean(e.target.checked);
                this.cacheConfig = { ...(this.cacheConfig || {}), enabled };
                this.applyCacheDependencies(enabled);
                await this.updateCacheEnabled(enabled);
            });
        }

        // PokeAPI cache toggle
        const pokeapiCacheToggle = document.getElementById('pokeapiCacheToggle');
        if (pokeapiCacheToggle) {
            pokeapiCacheToggle.checked = this.cacheConfig?.pokeapi_cache_enabled ?? true;
            pokeapiCacheToggle.disabled = !(this.cacheConfig?.enabled ?? true);
            pokeapiCacheToggle.addEventListener('change', async (e) => {
                await this.updatePokeapiCacheEnabled(e.target.checked);
            });
        }

        // TCG cache toggle
        const tcgCacheToggle = document.getElementById('tcgCacheToggle');
        if (tcgCacheToggle) {
            tcgCacheToggle.checked = this.cacheConfig?.tcg_cache_enabled ?? true;
            tcgCacheToggle.disabled = true;
            tcgCacheToggle.dataset.forceDisabled = tcgCacheToggle.dataset.forceDisabled || 'true';
            const row = tcgCacheToggle.closest('.control-row');
            if (row) {
                row.classList.add('disabled');
            }
        }
        
        // Cache expiry slider
        const cacheExpiry = document.getElementById('cacheExpiry');
        if (cacheExpiry) {
            this.updateCacheExpiryUI(this.cacheConfig?.expiry_days ?? Number(cacheExpiry.value));

            cacheExpiry.addEventListener('input', (e) => {
                this.updateCacheExpiryUI(Number(e.target.value));
            });
            
            cacheExpiry.addEventListener('change', async (e) => {
                await this.updateCacheExpiry(parseInt(e.target.value, 10));
            });
        }
        
        // Clear cache button
        const cacheClearBtn = document.getElementById('cacheClearBtn');
        if (cacheClearBtn) {
            cacheClearBtn.addEventListener('click', () => this.clearCache());
        }
        
        // Update cache stats
        this.updateCacheStats();
        this.applyCacheDependencies(this.cacheConfig?.enabled ?? true);
    }

    setupFaceIdentificationControls() {
        const overlayToggle = document.getElementById('faceIdOverlayToggle');
        if (overlayToggle) {
            overlayToggle.checked = this.shouldShowFaceIdOverlay();

            if (overlayToggle.dataset.listenerAttached !== 'true') {
                overlayToggle.addEventListener('change', (event) => {
                    const enabled = Boolean(event.target.checked);
                    this.saveFaceIdOverlayPreference(enabled);
                    console.log(`Face ID overlay ${enabled ? 'enabled' : 'disabled'}`);
                });

                overlayToggle.dataset.listenerAttached = 'true';
            }
        }

        this.initializeFaceProfileCaptureControls();
        this.ensureFaceProfileCameraActive();
    }

    setupVoiceControls() {
        const voiceSelect = document.getElementById('voiceActorSelect');
        if (!voiceSelect) {
            return;
        }

        const currentPreference = this.voicePreference || 'alloy';
        const optionExists = Array.from(voiceSelect.options).some(option => option.value === currentPreference);
        voiceSelect.value = optionExists ? currentPreference : voiceSelect.options[0]?.value;

        if (voiceSelect.dataset.listenerAttached === 'true') {
            return;
        }

        voiceSelect.addEventListener('change', async (event) => {
            const nextVoice = event.target.value || 'alloy';
            const resumeVoice = this.isVoiceActive;
            this.saveVoiceActorPreference(nextVoice);
            console.log(`Voice preference set to ${nextVoice}`);

            if (this.useRealtimeApi) {
                await this.restartRealtimeVoiceClient({ resumeVoice, voiceName: nextVoice });
            }
        });

        voiceSelect.dataset.listenerAttached = 'true';
    }

    async ensureRealtimeVoiceConnection() {
        if (!this.useRealtimeApi || !this.realtimeVoice) {
            throw new Error('Realtime voice is not available');
        }

        if (!this.realtimeVoice.isConnected) {
            await this.realtimeVoice.connect();
            this.syncCurrentViewContext();
            this.flushPendingRealtimeUserContext({ force: true });
        }
    }

    async previewVoiceChange(voiceName) {
        if (!voiceName || !this.useRealtimeApi || !this.realtimeVoice) {
            return;
        }

        const displayName = voiceName.charAt(0).toUpperCase() + voiceName.slice(1);

        try {
            await this.ensureRealtimeVoiceConnection();

            if (this.realtimeVoice.isResponseActive) {
                this.realtimeVoice.cancelCurrentResponse();
            }

            this.voicePreviewPending = true;
            const started = await this.realtimeVoice.playVoicePreview(voiceName);
            if (!started) {
                this.voicePreviewPending = false;
                return;
            }

            this.showToast('Voice Settings', `${displayName} voice selected. Preview playing...`, 'info', 2000);
        } catch (error) {
            this.voicePreviewPending = false;
            console.error('Voice preview failed:', error);
            this.showToast('Voice Settings', 'Unable to play the voice preview right now.', 'error', 4000);
        }
    }

    async restartRealtimeVoiceClient({ resumeVoice = false, voiceName = this.voicePreference } = {}) {
        if (!this.useRealtimeApi) {
            return;
        }

        if (this.restartingRealtimeVoice) {
            await this.restartingRealtimeVoice;
            return;
        }

        const shouldResumeVoice = resumeVoice && this.isVoiceActive;
        const displayName = voiceName ? voiceName.charAt(0).toUpperCase() + voiceName.slice(1) : 'Alloy';

        const restartRoutine = (async () => {
            if (this.realtimeVoice) {
                try { this.realtimeVoice.cancelCurrentResponse(); } catch (error) { console.warn('Unable to cancel response before restart', error); }
                try { this.realtimeVoice.stopRecording(); } catch (error) { console.warn('Unable to stop recording before restart', error); }
                try { this.realtimeVoice.disconnect(); } catch (error) { console.warn('Unable to disconnect realtime voice before restart', error); }
            }

            this.initializeRealtimeVoice();

            if (!shouldResumeVoice) {
                try {
                    await this.previewVoiceChange(voiceName);
                } catch (error) {
                    console.warn('Voice preview failed during restart', error);
                }
            } else {
                try {
                    await this.ensureRealtimeVoiceConnection();
                    this.showToast('Voice Settings', `${displayName} voice applied.`, 'success', 2000);
                } catch (error) {
                    console.warn('Unable to reconnect realtime voice before resuming:', error);
                }
            }

            if (shouldResumeVoice) {
                try {
                    await this.activateRealtimeConversation({ announce: false });
                } catch (error) {
                    console.error('Failed to resume realtime conversation after voice change:', error);
                    this.showToast('Voice Settings', 'Voice session restarted, tap Voice to resume listening.', 'info', 5000);
                    this.isVoiceActive = false;
                    this.voiceButton?.classList.remove('active');
                }
            }
        })();

        this.restartingRealtimeVoice = restartRoutine;
        await restartRoutine;
        this.restartingRealtimeVoice = null;
    }
    
    updateCacheStats() {
        if (!this.cacheConfig) return;
        
        const cacheStatus = document.getElementById('cacheStatus');
        const cacheFiles = document.getElementById('cacheFiles');
        const cacheSize = document.getElementById('cacheSize');
        
        if (cacheStatus) {
            cacheStatus.textContent = this.cacheConfig.enabled ? '✅ Enabled' : '❌ Disabled';
            cacheStatus.style.color = this.cacheConfig.enabled ? '#28a745' : '#dc3545';
        }
        if (cacheFiles) {
            cacheFiles.textContent = this.cacheConfig.total_files ?? 0;
        }
        if (cacheSize) {
            cacheSize.textContent = `${this.cacheConfig.total_size_mb ?? 0} MB`;
        }

        this.updateCacheExpiryUI(this.cacheConfig?.expiry_days);
        this.syncCacheControlAvailability();
        this.applyCacheDependencies(this.cacheConfig?.enabled ?? true);
    }

    syncCacheControlAvailability() {
        const pokeapiCacheToggle = document.getElementById('pokeapiCacheToggle');
        const tcgCacheToggle = document.getElementById('tcgCacheToggle');
        const toggles = [
            { element: pokeapiCacheToggle, key: 'pokeapi_cache_enabled' },
            { element: tcgCacheToggle, key: 'tcg_cache_enabled' }
        ];
        const globalEnabled = this.cacheConfig?.enabled ?? true;
        toggles.forEach(({ element, key }) => {
            if (!element) return;
            const forceDisabled = element.dataset.forceDisabled === 'true';
            element.disabled = forceDisabled || !globalEnabled;
            if (typeof this.cacheConfig?.[key] !== 'undefined') {
                element.checked = this.cacheConfig[key];
            }
            const row = element.closest('.control-row');
            if (row) {
                row.classList.toggle('disabled', element.disabled);
            }
        });
    }

    applyCacheDependencies(isEnabled) {
        const dependentToggles = [
            document.getElementById('pokeapiCacheToggle'),
            document.getElementById('tcgCacheToggle')
        ];

        dependentToggles.forEach((toggle) => {
            if (!toggle) {
                return;
            }
            const forceDisabled = toggle.dataset.forceDisabled === 'true';
            toggle.disabled = forceDisabled || !isEnabled;
            const row = toggle.closest('.control-row');
            if (row) {
                row.classList.toggle('disabled', toggle.disabled);
            }
        });

        const cacheExpiryInput = document.getElementById('cacheExpiry');
        if (cacheExpiryInput) {
            cacheExpiryInput.disabled = !isEnabled;
            const row = cacheExpiryInput.closest('.control-row');
            if (row) {
                row.classList.toggle('disabled', !isEnabled);
            }
        }

        const cacheClearBtn = document.getElementById('cacheClearBtn');
        if (cacheClearBtn) {
            cacheClearBtn.disabled = !isEnabled;
            cacheClearBtn.classList.toggle('disabled', !isEnabled);
        }
    }

    formatCacheExpiryLabel(days) {
        const value = Number(days);
        if (!Number.isFinite(value) || value <= 0) {
            return 'Unlimited';
        }
        return value === 1 ? '1 day' : `${value} days`;
    }

    updateCacheExpiryUI(value) {
        const cacheExpiry = document.getElementById('cacheExpiry');
        const cacheExpiryTitle = document.getElementById('cacheExpiryTitle');
        const cacheExpiryDescription = document.getElementById('cacheExpiryDescription');
        if (!cacheExpiry) {
            return;
        }
        const sliderMin = Number(cacheExpiry.min ?? 0);
        const sliderMax = Number(cacheExpiry.max ?? 90);
        const numericValue = value === undefined || value === null ? Number(cacheExpiry.value) : Number(value);
        cacheExpiry.value = numericValue;
        const titleText = this.formatCacheExpiryLabel(numericValue);
        if (cacheExpiryTitle) {
            cacheExpiryTitle.textContent = `Cache Expiry: ${titleText}`;
        }
        if (cacheExpiryDescription) {
            cacheExpiryDescription.textContent = numericValue <= 0
                ? 'Cache never expires until you clear it'
                : 'Cached data will refresh after this time';
        }
        const range = sliderMax - sliderMin || 1;
        const percentRaw = ((numericValue - sliderMin) / range) * 100;
        const percent = Math.min(100, Math.max(0, percentRaw));
        cacheExpiry.style.background = `linear-gradient(to right, var(--pokedex-red) 0%, var(--pokedex-red) ${percent}%, #e0e0e0 ${percent}%, #e0e0e0 100%)`;
    }

    shouldUsePokemonProxy() {
        if (!this.cacheConfig) {
            return true;
        }
        return this.cacheConfig.pokeapi_cache_enabled !== false;
    }

    normalizePokemonIdentifier(identifier, { preserveCase = false } = {}) {
        if (identifier === undefined || identifier === null) {
            return '';
        }
        const text = String(identifier).trim();
        if (!text) {
            return '';
        }
        if (/^\d+$/.test(text)) {
            return text;
        }
        return preserveCase ? text : text.toLowerCase();
    }

    buildPokemonApiUrl(resource, identifier, options = {}) {
        const mode = options.mode || (this.shouldUsePokemonProxy() ? 'proxy' : 'direct');
        const useProxy = mode === 'proxy';
        const preserveCase = resource === 'evolution';
        const normalized = this.normalizePokemonIdentifier(identifier, { preserveCase });
        const encoded = encodeURIComponent(normalized);
        const directBase = this.pokeapiBaseUrl.replace(/\/$/, '');

        const proxyPaths = {
            pokemon: `/api/pokemon/${encoded}`,
            species: `/api/pokemon/species/${encoded}`,
            type: `/api/pokemon/type/${encoded}`,
            evolution: `/api/pokemon/evolution-chain/${encoded}`
        };

        const directPaths = {
            pokemon: `${directBase}/pokemon/${encoded}`,
            species: `${directBase}/pokemon-species/${encoded}`,
            type: `${directBase}/type/${encoded}`,
            evolution: `${directBase}/evolution-chain/${encoded}`
        };

        if (useProxy) {
            if (!proxyPaths[resource]) {
                throw new Error(`Unknown PokéAPI proxy resource: ${resource}`);
            }
            return proxyPaths[resource];
        }

        if (!directPaths[resource]) {
            throw new Error(`Unknown PokéAPI direct resource: ${resource}`);
        }
        return directPaths[resource];
    }
    
    async updateCacheEnabled(enabled) {
        try {
            const response = await fetch('/api/cache/enable', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.cacheConfig = { ...this.cacheConfig, ...data.config };
                this.updateCacheStats();
                this.applyCacheDependencies(this.cacheConfig?.enabled ?? true);
                console.log('✅ Cache', enabled ? 'enabled' : 'disabled');
            }
        } catch (error) {
            console.error('Error updating cache:', error);
        }
    }

    async updatePokeapiCacheEnabled(enabled) {
        try {
            const response = await fetch('/api/cache/pokeapi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });

            if (response.ok) {
                const data = await response.json();
                this.cacheConfig = { ...this.cacheConfig, ...data.config };
                this.updateCacheStats();
                console.log('✅ PokeAPI cache', enabled ? 'enabled' : 'disabled');
            }
        } catch (error) {
            console.error('Error updating PokeAPI cache:', error);
        }
    }

    async updateTcgCacheEnabled(enabled) {
        try {
            const response = await fetch('/api/cache/tcg', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });

            if (response.ok) {
                const data = await response.json();
                this.cacheConfig = { ...this.cacheConfig, ...data.config };
                this.updateCacheStats();
                console.log('✅ TCG cache', enabled ? 'enabled' : 'disabled');
            }
        } catch (error) {
            console.error('Error updating TCG cache:', error);
        }
    }
    
    async updateCacheExpiry(days) {
        try {
            const response = await fetch('/api/cache/expiry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ days })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.cacheConfig = { ...this.cacheConfig, ...data.config };
                this.updateCacheStats();
                const label = days === 0 ? 'unlimited' : `${days} day${days === 1 ? '' : 's'}`;
                console.log(`✅ Cache expiry set to ${label}`);
            }
        } catch (error) {
            console.error('Error updating cache expiry:', error);
        }
    }
    
    async clearCache() {
        if (!confirm('Are you sure you want to clear all cached data? This will make the next API calls slower until data is cached again.')) {
            return;
        }
        
        try {
            const response = await fetch('/api/cache/clear', {
                method: 'POST'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.cacheConfig = { ...this.cacheConfig, ...data.stats };
                this.updateCacheStats();
                alert(`✅ ${data.message}`);
            }
        } catch (error) {
            console.error('Error clearing cache:', error);
            alert('❌ Error clearing cache');
        }
    }
    
    renderToolsModal() {
        const toolsList = document.getElementById('toolsList');
        if (!toolsList) return;
        
        if (this.tools.length === 0) {
            toolsList.innerHTML = '<div class="tools-empty">No tools available</div>';
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
        
        toolsList.innerHTML = toolsHTML;
        
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

        if (this.faceProfileCameraStream) {
            this.stopFaceProfileCamera();
        }

        if (!this.faceProfileCameraStream) {
            this.updateFaceProfileStatus('Camera idle. Tap Start Camera to begin.');
        }

        this.updateFaceProfileUIState();
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
                
                // Update face recognition enabled state
                this.faceRecognitionEnabled = this.isToolEnabled('face_identification');
                console.log('Face recognition enabled:', this.faceRecognitionEnabled);
                
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
                
                // Update face recognition enabled state
                this.faceRecognitionEnabled = this.isToolEnabled('face_identification');
                console.log('Face recognition enabled:', this.faceRecognitionEnabled);
                
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
    
    // Help Modal Methods
    showHelpModal() {
        const helpModalOverlay = document.getElementById('helpModalOverlay');
        if (helpModalOverlay) {
            helpModalOverlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }
    
    closeHelpModal() {
        const helpModalOverlay = document.getElementById('helpModalOverlay');
        if (helpModalOverlay) {
            helpModalOverlay.classList.remove('active');
            document.body.style.overflow = '';
        }
    }
    
    // Random Pokemon
    async getRandomPokemon() {
        try {
            console.log('🎲 Getting random Pokemon...');
            this.setLoading(true);
            
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'get_random_pokemon',
                    arguments: {}
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get random Pokemon');
            }
            
            const data = await response.json();
            console.log('✅ Random Pokemon response:', data);
            
            this.setLoading(false);
            
            if (data.result) {
                const pokemon = data.result;
                // Show in canvas
                if (pokemon.id) {
                    this.showPokemonInCanvas(pokemon.id);
                } else if (pokemon.name) {
                    this.showPokemonInCanvas(pokemon.name);
                }
                
                // Add to chat
                this.addAssistantMessage(`Here's a random Pokemon: ${pokemon.name}! 🎲`);
            }
        } catch (error) {
            console.error('Error getting random Pokemon:', error);
            this.setLoading(false);
            this.addAssistantMessage('Sorry, I had trouble getting a random Pokemon. Please try again.');
        }
    }
    
    // Navigation Methods
    async navigateBack() {
        if (this.currentViewIndex > 0) {
            this.currentViewIndex--;
            const view = this.viewHistory[this.currentViewIndex];
            
            if (view === 'grid') {
                this.gridView.showWithoutHistory();
                history.replaceState({ viewKey: view }, '', '/');
            } else if (view === 'tcg-database') {
                this.tcgDatabase.showWithoutHistory();
                history.replaceState({ viewKey: view }, '', '/tcg/database');
            } else if (view === 'tcg' && this.currentTcgData) {
                this.tcgGallery.displayWithoutHistory(this.currentTcgData);
                const pokemonName = this.currentTcgData.search_query || this.currentTcgData.pokemon_name || this.currentPokemonName;
                if (pokemonName) history.replaceState({ viewKey: view }, '', `/pokemon/${pokemonName.toLowerCase()}/cards`);
            } else if (view.startsWith('tcg-detail-')) {
                // For TCG detail, find and show the specific card
                const cardId = view.replace('tcg-detail-', '');
                if (this.currentTcgData && this.currentTcgData.cards) {
                    const card = this.currentTcgData.cards.find(c => c.id === cardId);
                    if (card) {
                        await this.tcgDetail.showWithoutHistory(card);
                        history.replaceState({ viewKey: view }, '', `/tcg/${cardId}`);
                    } else {
                        console.log('Card not found in current TCG data:', cardId);
                    }
                } else {
                    console.log('No TCG data available for navigation');
                }
            } else if (view.startsWith('pokemon-')) {
                const pokemonId = parseInt(view.split('-')[1]);
                this.detailView.loadPokemonWithoutHistory(pokemonId);
                const pokemon = this.allPokemons?.find(p => p.id === pokemonId);
                history.replaceState({ viewKey: view }, '', `/pokemon/${pokemon?.name || pokemonId}`);
            }
            this.updateNavigationButtons();
        }
    }
    
    // View Pokemon Cards
    async viewPokemonCards() {
        // Use species name for card searches (forms like megas share the base species name)
        const searchName = this.currentSpeciesName || this.currentPokemonName;
        if (!searchName) {
            console.error('No Pokemon selected');
            return;
        }
        
        try {
            console.log('🃏 Searching cards for:', searchName);
            this.setLoading(true);
            
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'search_pokemon_cards',
                    arguments: { pokemon_name: searchName }
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to search cards');
            }
            
            const data = await response.json();
            console.log('✅ Cards response:', data);
            
            this.setLoading(false);
            
            if (data.result && data.result.cards && data.result.cards.length > 0) {
                // Display cards in canvas
                this.displayTcgCardsInCanvas(data.result);
            } else {
                this.addMessage('assistant', `No trading cards found for ${searchName}.`);
            }
        } catch (error) {
            console.error('Error searching cards:', error);
            this.setLoading(false);
            this.addMessage('assistant', 'Sorry, I had trouble searching for cards. Please try again.');
        }
    }
    
    // Delegate to tcgDetail view
    async showTcgCardDetail(card) {
        await this.tcgDetail.show(card);
    }

    /**
     * Initialize voice - try Realtime API first, fall back to browser Speech Recognition
     */
    async initializeVoice() {
        this.setVoiceBackendState({
            mode: 'checking',
            label: 'Checking...',
            detail: 'Checking whether GPT Realtime voice is available for this browser and API configuration.'
        });

        // First, check if Azure OpenAI Realtime API is available
        if (window.RealtimeVoiceClient && RealtimeVoiceClient.isSupported()) {
            const realtimeSettings = this.buildApiSettingsPayload('realtime');
            if (realtimeSettings) {
                try {
                    const statusOptions = {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            api_settings: realtimeSettings,
                            language: this.getRealtimeLanguagePreference()
                        })
                    };
                    const statusResponse = await fetch('/api/realtime/status', statusOptions);
                    if (!statusResponse.ok) {
                        const errorBody = await statusResponse.json().catch(() => ({}));
                        console.log('Realtime status error:', errorBody.message || statusResponse.statusText);
                        throw new Error(errorBody.message || 'Realtime API unavailable');
                    }
                    const status = await statusResponse.json();
                    
                    if (status.available) {
                        this.setVoiceBackendState({
                            mode: 'realtime',
                            label: 'GPT Realtime',
                            detail: this.describeRealtimeStatusDetails(status.details || {})
                        });
                        console.log('Azure OpenAI Realtime API available, initializing...');
                        this.initializeRealtimeVoice();
                        return;
                    }
                    this.setVoiceBackendState({
                        mode: 'browser',
                        label: 'Browser Fallback',
                        detail: status.message || 'Realtime voice is unavailable, so browser speech recognition will be used.'
                    });
                    console.log('Realtime API not available:', status.message || 'Unknown reason');
                } catch (error) {
                    this.setVoiceBackendState({
                        mode: 'browser',
                        label: 'Browser Fallback',
                        detail: `Realtime check failed: ${error.message || error}. Using browser speech recognition instead.`
                    });
                    console.log('Could not check Realtime API status:', error);
                }
            } else {
                this.setVoiceBackendState({
                    mode: 'browser',
                    label: 'Browser Fallback',
                    detail: 'Realtime credentials are not configured, so browser speech recognition will be used.'
                });
                console.log('Realtime API locked until credentials are configured.');
            }
        } else {
            this.setVoiceBackendState({
                mode: 'browser',
                label: 'Browser Fallback',
                detail: 'This browser does not support the media and WebSocket APIs required for GPT Realtime voice.'
            });
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
            preferredVoice: this.voicePreference,
            apiSettingsProvider: () => this.buildApiSettingsPayload('realtime', { notifyOnError: true }),
            languagePreferenceProvider: () => this.getRealtimeLanguagePreference(),
            onConfigLoaded: (meta) => {
                this.setVoiceBackendState({
                    mode: 'realtime',
                    label: 'GPT Realtime',
                    detail: this.describeRealtimeConfigMeta(meta)
                });
            },
            
            onStatusChange: (status, message) => {
                console.log('Realtime status:', status, message);
                this.updateVoiceStatus(status, message);

                if (status === 'connected') {
                    this.flushPendingRealtimeUserContext();
                }

                // Trigger face identification when session becomes ready
                // Use a longer delay to avoid interrupting user's initial interaction
                if (status === 'session_ready') {
                    this.flushPendingRealtimeUserContext({ force: true });
                    if (this.faceRecognitionEnabled) {
                        console.log('Session ready - scheduling face identification (2s delay)');
                        setTimeout(() => {
                            this.identifyUserFromCamera();
                        }, 2000);
                    }
                }
            },
            
            onTranscript: (text, role) => {
                if (role === 'user') {
                    // Check for navigation voice commands before processing normally
                    const lowerText = text.toLowerCase().trim();
                    
                    // Voice command: Go back / Navigate back / Back
                    if (lowerText.match(/^(go back|navigate back|back|previous)$/)) {
                        console.log('🔙 Voice command: Go back');
                        this.showPokemonGrid();
                        this.addMessage('user', text);
                        this.addMessage('assistant', 'Going back to the Pokemon grid.');
                        this.syncVoiceMessageToBackend('user', text);
                        this.syncVoiceMessageToBackend('assistant', 'Going back to the Pokemon grid.');
                        return;
                    }
                    
                    // Voice command: Go forward / Navigate forward / Forward
                    if (lowerText.match(/^(go forward|navigate forward|forward|next)$/)) {
                        console.log('⏭️ Voice command: Go forward');
                        this.navigateForward();
                        this.addMessage('user', text);
                        this.addMessage('assistant', 'Moving forward in history.');
                        this.syncVoiceMessageToBackend('user', text);
                        this.syncVoiceMessageToBackend('assistant', 'Moving forward in history.');
                        return;
                    }
                    
                    // Voice command: Show index / Show all Pokemon / Go home
                    if (lowerText.match(/^(show index|show all pokemon|go home|home|index)$/)) {
                        console.log('🏠 Voice command: Show index');
                        this.showPokemonIndexInCanvas();
                        this.addMessage('user', text);
                        this.addMessage('assistant', 'Showing all Pokemon in the index.');
                        this.syncVoiceMessageToBackend('user', text);
                        this.syncVoiceMessageToBackend('assistant', 'Showing all Pokemon in the index.');
                        return;
                    }
                    
                    // Normal processing for other messages
                    this.addMessage('user', text);
                    this.syncVoiceMessageToBackend('user', text);
                    this.hideWelcomeMessage();
                        void this.maybeSendScanSnapshotForQuestion();
                    // Clear tool calls for new conversation turn
                    this.currentToolCalls = [];
                }
            },
            
            onResponse: (text, isPartial) => {
                if (this.pendingCardScan) {
                    if (!isPartial && text) {
                        this.pendingCardScan.resolve(text);
                        this.pendingCardScan = null;
                    }
                    return;
                }

                if (this.voicePreviewPending) {
                    if (!isPartial) {
                        this.voicePreviewPending = false;
                    }
                    return;
                }

                if (!isPartial && text) {
                    
                    // Full response received - extract any pokemon/tcg data from tool results
                    let pokemonData = null;
                    let tcgData = null;
                    
                    console.log('🔍 Processing response, checking tool calls:', this.currentToolCalls.length);
                    
                    // Check tool results for displayable data
                    for (const toolCall of this.currentToolCalls) {
                        if (toolCall.result && toolCall.success) {
                            console.log('✅ Tool call result:', toolCall.toolName, toolCall.result);
                            
                            // Check for Pokemon data and auto-display
                            if (toolCall.result.name && toolCall.result.types) {
                                pokemonData = toolCall.result;
                                console.log('🎮 Pokemon data found:', pokemonData.name, 'Full data:', toolCall.result);
                                
                                // Auto-display Pokemon using the public API
                                const pokemonId = toolCall.result.id || toolCall.result.pokemon_id;
                                const pokemonName = toolCall.result.name;
                                const identifier = pokemonId || pokemonName;
                                
                                if (identifier) {
                                    console.log('🎯 Auto-displaying Pokemon:', identifier);
                                    this.showPokemonInCanvas(identifier);
                                }
                            }
                            
                            // Check for TCG card data - support multiple formats
                            if (toolCall.result.cards && Array.isArray(toolCall.result.cards) && toolCall.result.cards.length > 0) {
                                tcgData = toolCall.result;
                                console.log('🃏 TCG data found:', tcgData.cards.length, 'cards');
                            }
                            // Check if result itself is an array of cards
                            else if (Array.isArray(toolCall.result) && toolCall.result.length > 0 && toolCall.result[0].name) {
                                tcgData = { cards: toolCall.result, count: toolCall.result.length, total_count: toolCall.result.length };
                                console.log('🃏 TCG data found (array format):', tcgData.cards.length, 'cards');
                            }
                            // Check if there's a data property containing cards
                            else if (toolCall.result.data && Array.isArray(toolCall.result.data) && toolCall.result.data.length > 0) {
                                tcgData = { cards: toolCall.result.data, count: toolCall.result.data.length, total_count: toolCall.result.totalCount || toolCall.result.data.length };
                                console.log('🃏 TCG data found (data property):', tcgData.cards.length, 'cards');
                            }
                        }
                    }
                    
                    console.log('📤 Adding message with Pokemon:', !!pokemonData, 'TCG:', !!tcgData);
                    this.addMessage('assistant', text, pokemonData, tcgData);
                    this.syncVoiceMessageToBackend('assistant', text, pokemonData, tcgData);
                }
            },
            
            onError: (error) => {
                if (this.pendingCardScan) {
                    this.pendingCardScan.reject(new Error(error));
                    this.pendingCardScan = null;
                }
                console.error('Realtime voice error:', error);
                this.setVoiceBackendState({
                    mode: 'error',
                    label: 'Realtime Error',
                    detail: `GPT Realtime reported an error: ${error}`
                });
                this.addMessage('assistant', `⚠️ Voice error: ${error}`);
            },
            
            onAudioStart: () => {
                this.updateVoiceStatus('speaking', 'Speaking...');
            },
            
            onAudioEnd: () => {
                if (this.isVoiceActive) {
                    this.updateVoiceStatus('listening', 'Listening...');
                }
                this.handleRealtimePlaybackLevel(0);
            },

            onPlaybackLevel: (level) => {
                this.handleRealtimePlaybackLevel(level);
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
                // Also track for context viewer (keep last 50)
                this._contextViewerToolCalls.push(toolCallEntry);
                if (this._contextViewerToolCalls.length > 50) this._contextViewerToolCalls.shift();
                
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
                
                // Check if tool result contains data that should be displayed immediately
                if (success && result) {
                    // Check for Pokemon data and auto-display
                    if (result.name && result.types && (result.id || result.pokemon_id)) {
                        const identifier = result.id || result.pokemon_id || result.name;
                        console.log('🎮 Pokemon detected in tool result, displaying in canvas:', result.name, 'ID:', identifier);
                        this.showPokemonInCanvas(identifier);
                    }
                    
                    // Check for TCG card data in various formats
                    let tcgData = null;
                    if (result.cards && Array.isArray(result.cards) && result.cards.length > 0) {
                        tcgData = result;
                        console.log('🃏 TCG cards detected in tool result, displaying in canvas:', tcgData.cards.length, 'cards');
                        this.displayTcgCardsInCanvas(tcgData);
                    } else if (Array.isArray(result) && result.length > 0 && result[0].name) {
                        tcgData = { cards: result, count: result.length, total_count: result.length };
                        console.log('🃏 TCG cards detected (array), displaying in canvas:', tcgData.cards.length, 'cards');
                        this.displayTcgCardsInCanvas(tcgData);
                    } else if (result.data && Array.isArray(result.data) && result.data.length > 0) {
                        tcgData = { cards: result.data, count: result.data.length, total_count: result.totalCount || result.data.length };
                        console.log('🃏 TCG cards detected (data property), displaying in canvas:', tcgData.cards.length, 'cards');
                        this.displayTcgCardsInCanvas(tcgData);
                    }
                    
                    // Check for single TCG card detail (from get_card_details)
                    if (!tcgData && result.name && result.set && (result.number || result.hp)) {
                        console.log('🎴 Single TCG card detected in tool result, displaying detail:', result.name);
                        this.showTcgCardDetail(result);
                    }
                    
                    // Handle legacy assistant_text format
                    if (result.assistant_text) {
                        const displayData = result.pokemon_data || result;
                        this.addMessage('assistant', result.assistant_text, displayData, result.tcg_data);
                    }
                }
                // Note: Tool results are also checked in onResponse callback for display
            },

            onSpeechStarted: () => {
                // Trigger face identification when user starts speaking
                console.log('Speech started - triggering face identification');
                this.identifyUserFromCamera();
            }
        });
        
        this.lastAppliedRealtimeUserName = null;
        if (this.currentIdentifiedUser) {
            this.pendingRealtimeUserName = this.currentIdentifiedUser;
        }

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

        const activeStatuses = new Set(['recording', 'listening', 'speaking', 'processing']);
        this.setPowerLightVoiceMode(this.isVoiceActive || activeStatuses.has(status));
    }

    setVoiceBackendState({ mode = 'checking', label = 'Checking...', detail = '' } = {}) {
        this.voiceBackendState = { mode, label, detail };

        if (this.voiceBackendValue) {
            this.voiceBackendValue.textContent = label;
        }

        if (this.voiceBackendIndicator) {
            this.voiceBackendIndicator.classList.remove('is-realtime', 'is-browser', 'is-checking', 'is-error');
            this.voiceBackendIndicator.classList.add(`is-${mode}`);
            const tooltip = detail || label;
            this.voiceBackendIndicator.setAttribute('title', tooltip);
            this.voiceBackendIndicator.setAttribute('aria-label', `Voice backend: ${label}. ${tooltip}`);
        }
    }

    describeRealtimeStatusDetails(details = {}) {
        const parts = ['GPT Realtime is available for voice mode.'];
        if (details.deployment) {
            parts.push(`Deployment: ${details.deployment}.`);
        }
        if (details.auth_mode) {
            parts.push(`Auth: ${details.auth_mode.replace(/_/g, ' ')}.`);
        }
        if (details.api_version) {
            parts.push(`API version: ${details.api_version}.`);
        }
        parts.push('The app will open a WebSocket session when you press Voice.');
        return parts.join(' ');
    }

    describeRealtimeConfigMeta(meta = {}) {
        const parts = [meta.transport === 'relay'
            ? 'Using GPT Realtime through the backend relay.'
            : 'Using GPT Realtime over WebSocket.'];
        if (meta.deployment) {
            parts.push(`Deployment: ${meta.deployment}.`);
        }
        if (meta.authMode) {
            parts.push(`Auth: ${meta.authMode.replace(/_/g, ' ')}.`);
        }
        if (meta.transport) {
            parts.push(`Transport: ${meta.transport}.`);
        }
        if (meta.apiVersion) {
            parts.push(`API version: ${meta.apiVersion}.`);
        }
        if (meta.relayUrl) {
            parts.push('Browser audio is relayed through this app because Entra-authenticated Azure Realtime requires server-side authorization headers.');
        }
        if (meta.wsUrl) {
            try {
                const parsed = new URL(meta.wsUrl);
                parts.push(`Host: ${parsed.host}.`);
            } catch (error) {
                // Ignore malformed tooltip metadata.
            }
        }
        return parts.join(' ');
    }

    initializeVoiceRecognition() {
        // Check if browser supports Speech Recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            console.warn('Speech Recognition not supported in this browser');
            this.setVoiceBackendState({
                mode: 'error',
                label: 'Voice Unsupported',
                detail: 'Neither GPT Realtime nor browser speech recognition is available in this browser.'
            });
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
        const requiredPayload = this.useRealtimeApi
            ? this.buildApiSettingsPayload('realtime', { notifyOnError: true })
            : this.buildApiSettingsPayload('chat', { notifyOnError: true });

        if (!requiredPayload) {
            return;
        }

        // Use Realtime API if available
        if (this.useRealtimeApi && this.realtimeVoice) {
            try {
                await this.activateRealtimeConversation({ announce: true });
                return;
            } catch (error) {
                console.error('Error starting realtime voice:', error);
                this.setVoiceBackendState({
                    mode: 'browser',
                    label: 'Browser Fallback',
                    detail: `Realtime voice failed to start: ${error.message}. Browser speech recognition is active instead.`
                });
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
        this.setPowerLightVoiceMode(true);
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
            
            // Set the current view context when connection is established
            console.log('🎯 Setting initial canvas context after connection');
            this.syncCurrentViewContext();
            this.flushPendingRealtimeUserContext({ force: true });
        }

        if (!this.realtimeVoice.isRecording) {
            await this.realtimeVoice.startRecording();
        }

        const becameActive = !this.isVoiceActive;
        if (becameActive) {
            this.isVoiceActive = true;
            this.voiceButton?.classList.add('active');
            this.setPowerLightVoiceMode(true);
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
        this.setPowerLightVoiceMode(false);
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
        const apiSettingsPayload = this.buildApiSettingsPayload('chat', { notifyOnError: true });
        if (!apiSettingsPayload) {
            this.setLoading(false);
            return;
        }
        
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    user_id: this.userId,
                    card_context: this.getCardContextPayload(),
                    api_settings: apiSettingsPayload
                })
            });
            
            if (!response.ok) {
                const errorDetail = await this.extractApiError(response, 'Failed to get response');
                throw new Error(errorDetail);
            }
            
            const data = await response.json();
            
            // Add assistant message to chat
            this.addMessage('assistant', data.message, data.pokemon_data, data.tcg_data);
            
            // Speak the response
            this.speakText(data.message);
            
        } catch (error) {
            console.error('Error processing voice message:', error);
            const detail = error?.message || 'Unexpected error while processing your voice query.';
            const assistantMessage = `Sorry, I ran into a problem: ${detail}`;
            this.addMessage('assistant', assistantMessage);
            this.speakText(assistantMessage);
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
        const profile = this.getSpeechVoiceProfile();
        if (profile.voice) {
            utterance.voice = profile.voice;
        }
        utterance.rate = profile.rate;
        utterance.pitch = profile.pitch;
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
    
    // ====================
    // Viewing Status Tracking
    // ====================
    
    loadViewingStatus() {
        try {
            const stored = document.cookie
                .split('; ')
                .find(row => row.startsWith('pokemon_viewing_status='));
            
            if (stored) {
                const value = stored.split('=')[1];
                return JSON.parse(decodeURIComponent(value));
            }
        } catch (e) {
            console.error('Error loading viewing status:', e);
        }
        return {};
    }
    
    saveViewingStatus() {
        try {
            const value = encodeURIComponent(JSON.stringify(this.viewingStatus));
            // Store for 365 days
            const expires = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toUTCString();
            document.cookie = `pokemon_viewing_status=${value}; expires=${expires}; path=/; SameSite=Lax`;
        } catch (e) {
            console.error('Error saving viewing status:', e);
        }
    }
    
    markPokemonViewed(pokemonId, viewType) {
        // viewType: 'detail', 'tcg-gallery', 'tcg-detail'
        const id = String(pokemonId);
        
        if (!this.viewingStatus[id]) {
            this.viewingStatus[id] = { detail: false, tcgGallery: false, tcgDetail: false, cardsViewed: 0 };
        }
        
        if (viewType === 'detail') {
            this.viewingStatus[id].detail = true;
        } else if (viewType === 'tcg-gallery') {
            this.viewingStatus[id].tcgGallery = true;
        } else if (viewType === 'tcg-detail') {
            this.viewingStatus[id].tcgDetail = true;
            // Increment card view count
            this.viewingStatus[id].cardsViewed = (this.viewingStatus[id].cardsViewed || 0) + 1;
        }
        
        this.saveViewingStatus();
        
        // Re-render the grid to update badges
        if (this.allPokemons.length > 0) {
            this.gridView.renderPokemonGrid();
        }
    }
    
    getViewingBadge(pokemonId) {
        const status = this.viewingStatus[String(pokemonId)];
        if (!status) return null;
        
        // Priority: masterball (2+ cards) > ultraball (1 card) > greatball (gallery) > pokeball (detail)
        const cardsViewed = status.cardsViewed || 0;
        
        if (cardsViewed >= 2) return '<img src="/static/images/pokeballs/masterball.png" alt="Master Ball">'; // Master Ball - viewed 2+ cards
        if (status.tcgDetail) return '<img src="/static/images/pokeballs/ultraball.png" alt="Ultra Ball">'; // Ultra Ball - viewed 1 card
        if (status.tcgGallery) return '<img src="/static/images/pokeballs/greatball.png" alt="Great Ball">'; // Great Ball - viewed TCG gallery
        if (status.detail) return '<img src="/static/images/pokeballs/pokeball.png" alt="Pokeball">'; // Pokeball - viewed Pokemon detail
        
        return null;
    }
    
    clearViewingStatus() {
        this.viewingStatus = {};
        this.saveViewingStatus();
        
        // Re-render grid to remove badges
        if (this.allPokemons.length > 0) {
            this.gridView.renderPokemonGrid();
        }
    }
    
    // ====================
    // Force Refresh Pokemon
    // ====================
    
    async forceRefreshCurrentPokemon() {
        if (!this.currentPokemonName) {
            console.error('No current Pokemon to refresh');
            return;
        }
        
        console.log('🔄 Force refreshing Pokemon:', this.currentPokemonName);
        
        try {
            // Clear cache for this Pokemon
            const response = await fetch('/api/cache/invalidate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool: 'get_pokemon',
                    params: { pokemon_name: this.currentPokemonName.toLowerCase() }
                })
            });
            
            if (response.ok) {
                console.log('✅ Cache cleared, reloading Pokemon...');
                
                // Find Pokemon ID
                const pokemon = this.allPokemons.find(p => p.name === this.currentPokemonName);
                if (pokemon) {
                    await this.detailView.loadPokemon(pokemon.id);
                }
            } else {
                console.error('Failed to clear cache');
            }
        } catch (error) {
            console.error('Error force refreshing:', error);
        }
    }
    
    async forceRefreshTcgCards() {
        const searchName = this.currentSpeciesName || this.currentPokemonName;
        if (!searchName) {
            console.error('No current Pokemon to refresh cards for');
            return;
        }
        
        console.log('🔄 Force refreshing TCG cards for:', searchName);
        
        try {
            // Clear cache for TCG cards
            console.log('🗑️ Calling cache invalidation API...');
            const response = await fetch('/api/cache/invalidate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool: 'search_pokemon_cards',
                    params: { pokemon_name: searchName.toLowerCase() }
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ TCG cache invalidation response:', result);
                
                if (result.deleted) {
                    console.log('✅ Cache file deleted successfully, reloading cards...');
                } else {
                    console.warn('⚠️ No cache file was deleted - it may not have existed');
                }
                
                // Reload cards
                await this.viewPokemonCards();
            } else {
                console.error('Failed to clear TCG cache, status:', response.status);
            }
        } catch (error) {
            console.error('Error force refreshing TCG cards:', error);
        }
    }
    
    async handleQuickAction(action) {
        if (action === 'random') {
            await this.triggerRandomQuickAction();
            return;
        }

        if (action === 'context') {
            this.toggleContextViewer();
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

            // Auto-display in canvas
            const identifier = toolResult.id || toolResult.name;
            if (identifier) {
                console.log('🎯 Auto-displaying random Pokemon:', identifier);
                this.showPokemonInCanvas(identifier);
            }
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
        
        // Open chat sidebar if not already open
        this.openChatSidebar();
        
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
        const apiSettingsPayload = this.buildApiSettingsPayload('chat', { notifyOnError: true });
        if (!apiSettingsPayload) {
            this.setLoading(false);
            return;
        }
        
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
                    card_context: this.getCardContextPayload(),
                    api_settings: apiSettingsPayload
                })
            });
            
            if (!response.ok) {
                const errorDetail = await this.extractApiError(response, 'Failed to get response');
                throw new Error(errorDetail);
            }
            
            const data = await response.json();
            
            // Add assistant message
            this.addMessage('assistant', data.message, data.pokemon_data, data.tcg_data);
            
            // Handle frontend actions from tool calls
            if (data.frontend_actions && Array.isArray(data.frontend_actions)) {
                for (const action of data.frontend_actions) {
                    await this.executeFrontendAction(action);
                }
            }
            // Auto-display Pokemon in canvas if pokemon_data returned
            else if (data.pokemon_data && !data.pokemon_data.error) {
                const identifier = data.pokemon_data.id || data.pokemon_data.name;
                if (identifier) {
                    console.log('🎯 Auto-displaying Pokemon from chat:', identifier);
                    this.showPokemonInCanvas(identifier);
                }
            } else if (data.tcg_data) {
                // Auto-display TCG cards in canvas
                const tcg = data.tcg_data;
                if (tcg.cards && Array.isArray(tcg.cards) && tcg.cards.length > 0) {
                    console.log('🃏 Auto-displaying TCG cards from chat:', tcg.cards.length, 'cards');
                    this.displayTcgCardsInCanvas(tcg);
                }
            } else {
                // No pokemon_data or tcg_data from backend — detect Pokemon name in the user message
                const detected = this.detectPokemonInMessage(message);
                if (detected) {
                    console.log('🎯 Detected Pokemon in message, showing:', detected.name);
                    this.showPokemonInCanvas(detected.id || detected.name);
                }
            }
            
        } catch (error) {
            console.error('Error sending message:', error);
            const detail = error?.message || 'Unexpected error while sending your message.';
            this.addMessage('assistant', `Sorry, I couldn’t answer that: ${detail}`);
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
    /**
     * Add a tool call message bubble to the chat
     * @param {string} toolName - Name of the tool being called
     * @param {object} args - Arguments passed to the tool
     * @param {string} status - Status: 'calling', 'success', 'error'
     * @param {object} result - Tool result (optional, for success/error)
     * @param {number} duration - Execution time in ms (optional)
     */
    addToolCallMessage(toolName, args, status, result = null, duration = null) {
        // Find existing tool call message to update, or create new one
        const existingId = `tool-call-${toolName}-${Date.now()}`;
        let messageDiv = document.getElementById(existingId);

        if (!messageDiv) {
            // Create new tool call bubble
            messageDiv = document.createElement('div');
            messageDiv.id = existingId;
            messageDiv.className = `tool-call-bubble ${status}`;

            const icon = status === 'calling' ? '🔧' : status === 'success' ? '✅' : '❌';
            const displayName = toolName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

            // Header
            const headerDiv = document.createElement('div');
            headerDiv.className = 'tool-call-header';
            const nameSpan = document.createElement('span');
            nameSpan.className = 'tool-call-name';
            nameSpan.textContent = `${icon} ${displayName}`;
            headerDiv.appendChild(nameSpan);
            
            if (duration) {
                const durationSpan = document.createElement('span');
                durationSpan.className = 'tool-call-duration';
                durationSpan.innerHTML = `⏱️ ${(duration / 1000).toFixed(2)}s`;
                headerDiv.appendChild(durationSpan);
            }
            messageDiv.appendChild(headerDiv);

            // Arguments section (summary + collapsible JSON)
            if (args && Object.keys(args).length > 0) {
                const argsDiv = document.createElement('div');
                argsDiv.className = 'tool-call-args';
                
                // Summary view
                const argsSummary = Object.entries(args)
                    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
                    .join(', ');
                argsDiv.innerHTML = `<strong>Arguments:</strong> ${argsSummary}`;
                
                // Collapsible JSON toggle
                const toggleBtn = document.createElement('button');
                toggleBtn.className = 'tool-call-json-toggle';
                toggleBtn.textContent = 'Show JSON';
                toggleBtn.onclick = () => {
                    const jsonDiv = argsDiv.querySelector('.tool-call-json');
                    jsonDiv.classList.toggle('expanded');
                    toggleBtn.textContent = jsonDiv.classList.contains('expanded') ? 'Hide JSON' : 'Show JSON';
                };
                argsDiv.appendChild(toggleBtn);
                
                // JSON view (hidden by default)
                const jsonDiv = document.createElement('div');
                jsonDiv.className = 'tool-call-json';
                jsonDiv.innerHTML = `<pre>${JSON.stringify(args, null, 2)}</pre>`;
                argsDiv.appendChild(jsonDiv);
                
                messageDiv.appendChild(argsDiv);
            }

            // Result section (added when result arrives)
            if (result) {
                this.addToolCallResult(messageDiv, result);
            }

            this.chatContainer.appendChild(messageDiv);
        } else {
            // Update existing message with result
            messageDiv.className = `tool-call-bubble ${status}`;

            const icon = status === 'success' ? '✅' : '❌';
            const displayName = toolName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const nameSpan = messageDiv.querySelector('.tool-call-name');
            if (nameSpan) {
                nameSpan.textContent = `${icon} ${displayName}`;
            }

            // Update duration
            if (duration) {
                const durationSpan = messageDiv.querySelector('.tool-call-duration');
                if (durationSpan) {
                    durationSpan.innerHTML = `⏱️ ${(duration / 1000).toFixed(2)}s`;
                } else {
                    const headerDiv = messageDiv.querySelector('.tool-call-header');
                    if (headerDiv) {
                        const newDurationSpan = document.createElement('span');
                        newDurationSpan.className = 'tool-call-duration';
                        newDurationSpan.innerHTML = `⏱️ ${(duration / 1000).toFixed(2)}s`;
                        headerDiv.appendChild(newDurationSpan);
                    }
                }
            }

            // Add result if not already present
            if (result && !messageDiv.querySelector('.tool-call-response')) {
                this.addToolCallResult(messageDiv, result);
            }
        }

        this.scrollToBottom();
    }

    addToolCallResult(messageDiv, result) {
        const responseDiv = document.createElement('div');
        responseDiv.className = 'tool-call-response';
        
        // Summary
        const summary = typeof result === 'object' && result !== null 
            ? `Received ${Object.keys(result).length} properties`
            : 'Response received';
        responseDiv.innerHTML = `<strong>Response:</strong> ${summary}`;
        
        // Collapsible JSON toggle
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'tool-call-json-toggle';
        toggleBtn.textContent = 'Show Response JSON';
        toggleBtn.onclick = () => {
            const jsonDiv = responseDiv.querySelector('.tool-call-json');
            jsonDiv.classList.toggle('expanded');
            toggleBtn.textContent = jsonDiv.classList.contains('expanded') ? 'Hide Response JSON' : 'Show Response JSON';
        };
        responseDiv.appendChild(toggleBtn);
        
        // JSON view (hidden by default)
        const jsonDiv = document.createElement('div');
        jsonDiv.className = 'tool-call-json';
        jsonDiv.innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
        responseDiv.appendChild(jsonDiv);
        
        messageDiv.appendChild(responseDiv);
    }

    addMessage(role, content, pokemonData = null, tcgData = null) {
        console.log('💬 Adding message - Role:', role, 'Pokemon:', !!pokemonData, 'TCG:', !!tcgData);
        if (tcgData) {
            console.log('🃏 TCG Data details:', tcgData);
        }
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
            // Display cards in the main canvas
            this.displayTcgCardsInCanvas(tcgData);
            
            // Also add a small preview in the chat
            const tcgPreview = document.createElement('div');
            tcgPreview.className = 'tcg-chat-preview';
            tcgPreview.innerHTML = `<span class="tcg-icon">🃏</span> ${tcgData.cards.length} trading cards displayed in canvas`;
            messageDiv.appendChild(tcgPreview);
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
                // if (resultText.length > 2000) {
                //     resultText = resultText.substring(0, 2000) + '\n... (truncated)';
                // }
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
            console.log('🎯 Setting card context in system prompt');
            void this.realtimeVoice.updateCanvasContext(summary);
        }
    }

    setPokemonContext(pokemon, species) {
        const summary = this.buildPokemonContextSummary(pokemon, species);
        if (!summary) {
            return;
        }

        if (this.currentCardContext?.summary === summary) {
            this.currentCardContext.data = { pokemon, species };
            return;
        }

        this.currentCardContext = {
            summary: summary,
            data: { pokemon, species }
        };

        console.log('🎯 Setting Pokemon context:', pokemon.name);
        if (this.useRealtimeApi && this.realtimeVoice?.isConnected) {
            void this.realtimeVoice.updateCanvasContext(summary);
        }
    }

    buildPokemonContextSummary(pokemon, species, comparePokemon = null, compareSpecies = null) {
        if (!pokemon) return null;

        const name = pokemon.name.charAt(0).toUpperCase() + pokemon.name.slice(1);
        const id = pokemon.id;
        const header = `${name} #${String(id).padStart(3, '0')}`;
        const descriptors = [];

        // Types
        if (pokemon.types && pokemon.types.length) {
            const typeNames = pokemon.types.map(t => t.type.name.charAt(0).toUpperCase() + t.type.name.slice(1));
            descriptors.push(`Type${pokemon.types.length > 1 ? 's' : ''}: ${typeNames.join('/')}`);
        }

        // Height and Weight
        if (pokemon.height) {
            descriptors.push(`Height: ${(pokemon.height / 10).toFixed(1)}m`);
        }
        if (pokemon.weight) {
            descriptors.push(`Weight: ${(pokemon.weight / 10).toFixed(1)}kg`);
        }

        // Abilities
        if (pokemon.abilities && pokemon.abilities.length) {
            const abilityNames = pokemon.abilities.map(a => 
                a.ability.name.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
            );
            descriptors.push(`Abilities: ${abilityNames.join(', ')}`);
        }

        // Stats
        if (pokemon.stats && pokemon.stats.length) {
            const statSummary = pokemon.stats.map(s => {
                const statName = s.stat.name.split('-').map(word => word.toUpperCase()).join('');
                return `${statName}:${s.base_stat}`;
            }).join(' ');
            descriptors.push(`Base Stats: ${statSummary}`);
        }

        // Description from species
        if (species && species.flavor_text_entries) {
            const flavorText = species.flavor_text_entries.find(entry => entry.language.name === 'en');
            if (flavorText) {
                const description = flavorText.flavor_text.replace(/\f/g, ' ').replace(/\s+/g, ' ').trim();
                descriptors.push(`Description: ${description}`);
            }
        }

        if (comparePokemon) {
            const compareName = comparePokemon.name.charAt(0).toUpperCase() + comparePokemon.name.slice(1);
            const compareHeader = `${compareName} #${String(comparePokemon.id).padStart(3, '0')}`;
            const compareTypes = comparePokemon.types && comparePokemon.types.length
                ? comparePokemon.types.map(t => t.type.name.charAt(0).toUpperCase() + t.type.name.slice(1)).join('/')
                : 'Unknown';
            const compareFlavorText = compareSpecies?.flavor_text_entries?.find(entry => entry.language.name === 'en');
            const compareDescription = compareFlavorText?.flavor_text
                ? compareFlavorText.flavor_text.replace(/\f/g, ' ').replace(/\s+/g, ' ').trim()
                : '';

            descriptors.push(`Currently comparing against ${compareHeader} (Types: ${compareTypes})${compareDescription ? ` | Compare Description: ${compareDescription}` : ''}`);
        }

        const summaryParts = [`User is viewing the Pokemon ${header}.`];
        if (descriptors.length) {
            summaryParts.push(descriptors.join(' | '));
        }

        return summaryParts.join(' ');
    }

    /**
     * Centralized canvas state management - automatically updates GPT context
     * @param {string} type - Type of content: 'grid', 'pokemon', 'tcg-gallery', 'tcg-detail'
     * @param {Object} data - Associated data for the view
     */
    updateCanvasState(type, data, addToHistory = true) {
        this.currentCanvasState = { type, data };
        
        // Automatically manage navigation history
        if (addToHistory) {
            const viewKey = this.buildViewKey(type, data);
            
            // Only add to history if it's different from current
            if (this.viewHistory[this.currentViewIndex] !== viewKey) {
                this.currentViewIndex++;
                this.viewHistory = this.viewHistory.slice(0, this.currentViewIndex);
                this.viewHistory.push(viewKey);
                console.log(`📚 History updated: [${this.viewHistory.join(' → ')}] (index: ${this.currentViewIndex})`);
            }
            
            // Update navigation buttons
            this.updateNavigationButtons();
            
            // Update browser URL
            if (!this._suppressPushState) {
                const url = this.buildUrl(type, data);
                if (url !== null) {
                    history.pushState({ viewKey }, '', url);
                }
            }
        }
        
        // Generate context description based on canvas state
        const contextDescription = this.buildCanvasContextDescription();
        
        // Update realtime voice context
        if (this.realtimeVoice && this.realtimeVoice.isConnected) {
            console.log(`🎯 Canvas state changed to: ${type}`);
            this.realtimeVoice.updateCanvasContext(contextDescription);
        }
        
        // Also update legacy context variables for backward compatibility
        if (type === 'pokemon' && data) {
            this.currentPokemonContext = data;
            this.currentCardContext = null;
        } else if (type === 'tcg-detail' && data) {
            this.currentCardContext = { summary: contextDescription, data: data };
            this.currentPokemonContext = null;
        } else {
            this.currentCardContext = null;
            this.currentPokemonContext = null;
        }
    }
    
    /**
     * Build a URL path for the given canvas state
     */
    buildUrl(type, data) {
        switch (type) {
            case 'grid':
                return '/';
            case 'tcg-database':
                return '/tcg/database';
            case 'pokemon':
                if (data?.pokemon?.id) {
                    const name = data.pokemon.name || data.pokemon.id;
                    return `/pokemon/${name}`;
                }
                return '/';
            case 'tcg-gallery': {
                // Expansion browsing uses /tcg/set/<setId>
                if (data?.set_id) {
                    return `/tcg/set/${encodeURIComponent(data.set_id)}`;
                }
                const pokemonName = data?.pokemon_name || this.currentPokemonName;
                if (pokemonName) {
                    return `/pokemon/${pokemonName.toLowerCase()}/cards`;
                }
                return '/';
            }
            case 'tcg-detail':
                if (data?.id) {
                    return `/tcg/${data.id}`;
                }
                return '/';
            default:
                return null;
        }
    }
    
    /**
     * Build a unique view key for history tracking
     */
    buildViewKey(type, data) {
        switch (type) {
            case 'grid':
                return 'grid';
            case 'tcg-database':
                return 'tcg-database';
            case 'pokemon':
                return data?.pokemon?.id ? `pokemon-${data.pokemon.id}` : 'pokemon';
            case 'tcg-gallery':
                return 'tcg';
            case 'tcg-detail':
                return data?.id ? `tcg-detail-${data.id}` : 'tcg-detail';
            default:
                return type;
        }
    }
    
    /**
     * Build context description based on current canvas state
     */
    _getCurrencyContextNote() {
        if (typeof CurrencyConverter === 'undefined') return '';
        const cur = CurrencyConverter.getCurrency();
        if (cur === 'USD') return '';
        const info = CurrencyConverter.getInfo();
        const rate = CurrencyConverter.fromUSD(1);
        return ` Prices on screen are displayed in ${info.name} (${cur}, symbol: ${info.symbol}). IMPORTANT: All tool responses (get_card_details, get_card_price, search_pokemon_cards) return prices in USD. You MUST multiply USD values by ${rate} to convert to ${cur} before presenting them to the user. For example, $1.00 USD = ${info.symbol}${rate.toFixed(2)} ${cur}. Never show raw USD values when the user's currency is ${cur}.`;
    }

    buildCanvasContextDescription() {
        const { type, data } = this.currentCanvasState;
        const currNote = this._getCurrencyContextNote();
        
        switch (type) {
            case 'grid':
                return "User is currently viewing the Pokemon index page (grid view) showing all Pokemon. They can select any Pokemon to view details, or ask about specific Pokemon.";
            
            case 'tcg-database':
                if (data?.viewMode === 'all-cards') {
                    const cardCount = this.currentTcgCards?.length || 0;
                    const setCount = data?.selectedSets || 0;
                    return `User is viewing the TCG Card Database in All Cards mode with ${cardCount} cards loaded from ${setCount} expansion(s). Cards are numbered #1 through #${cardCount}. User can say "show card 5" or "open card number 12" to view a specific card's details.${currNote}`;
                }
                if (data?.viewMode === 'collection') {
                    const cardCount = this.currentTcgCards?.length || 0;
                    return `User is viewing My Collection in the TCG Card Database with ${cardCount} owned card(s) saved locally in this browser. They can adjust counts or open any saved card.${currNote}`;
                }
                return `User is currently viewing the TCG Card Database page showing all Pokemon TCG sets/expansions. They can browse and explore any expansion to see its cards.${currNote}`;
            
            case 'pokemon':
                if (!data || !data.pokemon) return null;
                return this.buildPokemonContextSummary(data.pokemon, data.species, data.comparePokemon, data.compareSpecies);
            
            case 'tcg-gallery':
                if (!data || !data.pokemon_name) return null;
                const cardCount = data.total_count || (data.cards ? data.cards.length : 0);
                return `User is viewing a gallery of ${cardCount} Pokemon TCG trading cards for ${data.pokemon_name}. Cards are numbered #1 through #${cardCount} in the gallery grid. When the user says "show card 4" or "open #4", they mean the 4th card in this gallery (not a card's printed set number). Use show_tcg_card_by_index with card_index=4 to open it. Do NOT search for cards again - just navigate to the card by its gallery position number.${currNote}`;
            
            case 'tcg-detail':
                if (!data) return null;
                return this.buildCardContextSummary(data) + currNote;
            
            default:
                return null;
        }
    }

    /**
     * Update hover context when user mouses over interactive elements.
     * Debounced to avoid spamming the voice API with rapid hover changes.
     */
    updateHoverContext(type, summary, id) {
        this.hoveredItem = { type, summary, id: id || null };
        // Debounce voice context update (300ms)
        clearTimeout(this._hoverContextTimer);
        this._hoverContextTimer = setTimeout(() => {
            if (this.hoveredItem) {
                this._pushHoverContextToVoice();
            }
        }, 300);
        // Refresh debug panel immediately so hover is visible
        if (this._contextViewerInterval) this.refreshContextViewer();
    }

    clearHoverContext() {
        this.hoveredItem = null;
        clearTimeout(this._hoverContextTimer);
        this._hoverContextTimer = setTimeout(() => {
            if (!this.hoveredItem) {
                this._pushHoverContextToVoice();
            }
        }, 300);
        // Refresh debug panel immediately
        if (this._contextViewerInterval) this.refreshContextViewer();
    }

    _buildHoverContextText() {
        if (!this.hoveredItem) return '';
        let text = `\n\nHOVER CONTEXT: The user's mouse is currently hovering over: ${this.hoveredItem.summary}.`;
        if (this.hoveredItem.id) {
            text += ` Card ID: "${this.hoveredItem.id}". Use get_card_details with card_id="${this.hoveredItem.id}" to get full info, or get_card_price with card_id="${this.hoveredItem.id}" for pricing.`;
        }
        text += ` If the user says "this one", "tell me about this", "what's this?", or asks about value/price, they mean this specific hovered item.`;
        return text;
    }

    _pushHoverContextToVoice() {
        if (!this.realtimeVoice || !this.realtimeVoice.isConnected) return;
        const base = this.buildCanvasContextDescription();
        let full = base || '';
        full += this._buildHoverContextText();
        this.realtimeVoice.updateCanvasContext(full);
    }

    clearCardContext() {
        this.updateCanvasState('grid', null);
    }

    syncCurrentViewContext() {
        // Determine which view is currently active and sync with current canvas state
        if (!this.realtimeVoice || !this.realtimeVoice.isConnected) {
            return;
        }

        const gridVisible = this.pokemonGridView && this.pokemonGridView.style.display !== 'none';
        const detailVisible = this.pokemonDetailView && this.pokemonDetailView.style.display !== 'none';
        const tcgVisible = this.tcgCardsView && this.tcgCardsView.style.display !== 'none';

        // Re-apply the current canvas state
        const contextDescription = this.buildCanvasContextDescription();
        if (contextDescription) {
            console.log('🎯 Syncing canvas context:', this.currentCanvasState.type);
            this.realtimeVoice.updateCanvasContext(contextDescription);
        }
    }

    getCardContextPayload() {
        // Build base context
        let context;
        if (this.currentCanvasState?.type === 'tcg-gallery' || this.currentCanvasState?.type === 'tcg-database') {
            context = this.buildCanvasContextDescription();
        } else {
            context = this.currentCardContext?.summary || this.buildCanvasContextDescription();
        }
        // Append hover context if available
        if (this.hoveredItem) {
            context = (context || '') + this._buildHoverContextText();
        }
        return context || null;
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

    installFetchInterceptor() {
        if (this.fetchInterceptorInstalled || typeof window === 'undefined' || typeof window.fetch !== 'function') {
            return;
        }

        const originalFetch = window.fetch.bind(window);
        window.fetch = async (...args) => {
            const shouldTrack = this.shouldTrackLoadingRequest(args[0]);
            const loadingToken = shouldTrack ? this.beginGlobalLoading(this.buildLoadingDescriptor(args[0], args[1])) : null;

            try {
                return await originalFetch(...args);
            } finally {
                if (shouldTrack) {
                    this.endGlobalLoading(loadingToken);
                }
            }
        };

        this.fetchInterceptorInstalled = true;
    }

    shouldTrackLoadingRequest(resource) {
        if (!resource) {
            return false;
        }

        const url = this.extractRequestUrl(resource);
        if (!url) {
            return false;
        }

        try {
            const parsed = new URL(url, window.location.origin);
            if (parsed.protocol === 'data:') {
                return false;
            }

            const pathname = parsed.pathname || '';
            const hostname = parsed.hostname || '';
            if (pathname.startsWith('/static/')) {
                return false;
            }

            const includesApiSegment = pathname.startsWith('/api/') || pathname.includes('/api/');
            const knownHosts = ['pokeapi.co', 'pokemontcg', 'pokemon-tcg', 'tcgplayer', 'cardmarket'];
            const matchesKnownHost = knownHosts.some(host => hostname.includes(host));
            return includesApiSegment || matchesKnownHost;
        } catch (error) {
            return false;
        }
    }

    extractRequestUrl(resource) {
        if (typeof resource === 'string') {
            return resource;
        }
        if (resource instanceof URL) {
            return resource.toString();
        }
        if (resource && typeof resource.url === 'string') {
            return resource.url;
        }
        return null;
    }

    buildLoadingDescriptor(resource, init = null) {
        const fallback = {
            label: 'Working...',
            detail: 'Rotom is waiting for the current request to finish.'
        };

        const url = this.extractRequestUrl(resource);
        if (!url) {
            return fallback;
        }

        try {
            const parsed = new URL(url, window.location.origin);
            const pathname = parsed.pathname || '';

            if (pathname === '/api/pokemon/list') {
                return {
                    label: 'Loading Pokedex...',
                    detail: 'Rotom is fetching the Pokemon index for the first screen.'
                };
            }

            if (pathname === '/api/tools') {
                return {
                    label: 'Loading tools...',
                    detail: 'Rotom is checking which assistant tools are enabled for this session.'
                };
            }

            if (pathname === '/api/cache/config') {
                return {
                    label: 'Loading cache settings...',
                    detail: 'Rotom is reading cache settings before opening the app controls.'
                };
            }

            if (pathname === '/api/chat') {
                return {
                    label: 'Answering...',
                    detail: 'Rotom is sending your message to the assistant and waiting for a reply.'
                };
            }

            if (pathname === '/api/chat/record') {
                return {
                    label: 'Saving context...',
                    detail: 'Rotom is saving the latest chat turn so text and voice stay in sync.'
                };
            }

            if (pathname === '/api/random-pokemon') {
                return {
                    label: 'Picking a random Pokemon...',
                    detail: 'Rotom is choosing a random entry from the Pokedex for you.'
                };
            }

            if (pathname === '/api/realtime/status') {
                return {
                    label: 'Checking voice status...',
                    detail: 'Rotom is checking the realtime voice connection state.'
                };
            }

            if (pathname === '/api/face/identify') {
                return {
                    label: 'Identifying...',
                    detail: 'Rotom is matching the camera snapshot against saved face profiles.'
                };
            }

            if (pathname === '/api/cache/invalidate') {
                return {
                    label: 'Refreshing cache...',
                    detail: 'Rotom is clearing cached data so the next result is freshly loaded.'
                };
            }

            if (pathname === '/api/realtime/tool') {
                const payload = this.parseLoadingRequestBody(init?.body);
                return this.describeRealtimeToolLoading(payload?.tool_name, payload?.arguments);
            }

            if (pathname.startsWith('/api/pokemon/')) {
                return {
                    label: 'Loading Pokemon data...',
                    detail: 'Rotom is fetching Pokemon details through the cached PokeAPI proxy.'
                };
            }
        } catch (error) {
            return fallback;
        }

        return fallback;
    }

    parseLoadingRequestBody(body) {
        if (!body || typeof body !== 'string') {
            return null;
        }

        try {
            return JSON.parse(body);
        } catch (error) {
            return null;
        }
    }

    describeRealtimeToolLoading(toolName, toolArgs = {}) {
        if (!toolName) {
            return {
                label: 'Running tool...',
                detail: 'Rotom is waiting for an assistant tool to finish.'
            };
        }

        const name = this.humanizeLoadingToolName(toolName);

        if (toolName === 'get_tcg_sets') {
            return {
                label: toolArgs?.force_refresh ? 'Refreshing TCG sets...' : 'Loading TCG sets...',
                detail: toolArgs?.force_refresh
                    ? 'Rotom is refreshing the trading card set list in the background.'
                    : 'Rotom is loading trading card expansions so the TCG views open faster.'
            };
        }

        if (toolName === 'search_pokemon_cards') {
            const pokemonName = toolArgs?.pokemon_name || toolArgs?.pokemon || 'this Pokemon';
            return {
                label: 'Loading card gallery...',
                detail: `Rotom is searching trading cards for ${pokemonName}.`
            };
        }

        if (toolName === 'search_cards_by_set') {
            const setId = toolArgs?.set_id || 'the selected set';
            return {
                label: 'Loading expansion cards...',
                detail: `Rotom is fetching cards from ${setId}.`
            };
        }

        if (toolName === 'get_card_details') {
            return {
                label: 'Loading card details...',
                detail: 'Rotom is fetching the full details and pricing for the selected card.'
            };
        }

        if (toolName === 'get_random_pokemon') {
            return {
                label: 'Picking a random Pokemon...',
                detail: 'Rotom is choosing a random Pokemon to show on the canvas.'
            };
        }

        if (toolName === 'get_pokemon_info') {
            const pokemonName = toolArgs?.name || toolArgs?.pokemon || toolArgs?.pokemon_name || 'that Pokemon';
            return {
                label: 'Loading Pokemon...',
                detail: `Rotom is looking up details for ${pokemonName}.`
            };
        }

        return {
            label: `${name}...`,
            detail: `Rotom is waiting for ${name.toLowerCase()} to finish.`
        };
    }

    humanizeLoadingToolName(toolName) {
        return toolName
            .replace(/_/g, ' ')
            .replace(/\b\w/g, char => char.toUpperCase());
    }

    beginGlobalLoading(descriptor = null) {
        const token = `loading-${++this.loadingRequestSequence}`;
        this.activeLoadingRequests.set(token, descriptor || {
            label: 'Working...',
            detail: 'Rotom is waiting for the current request to finish.'
        });
        this.activeLoadingCount = this.activeLoadingRequests.size;
        this.updateLoadingIndicator();
        return token;
    }

    endGlobalLoading(token = null) {
        if (token && this.activeLoadingRequests.has(token)) {
            this.activeLoadingRequests.delete(token);
        } else if (this.activeLoadingRequests.size > 0) {
            const lastToken = Array.from(this.activeLoadingRequests.keys()).pop();
            this.activeLoadingRequests.delete(lastToken);
        }

        this.activeLoadingCount = this.activeLoadingRequests.size;
        this.updateLoadingIndicator();
    }

    getActiveLoadingDescriptor() {
        const descriptors = Array.from(this.activeLoadingRequests.values());
        if (descriptors.length === 0) {
            return {
                label: 'Thinking...',
                detail: 'Rotom is waiting for the next request to finish.'
            };
        }

        const primary = descriptors[descriptors.length - 1];
        const extraCount = descriptors.length - 1;
        if (extraCount <= 0) {
            return primary;
        }

        return {
            label: primary.label,
            detail: `${primary.detail} ${extraCount} other ${extraCount === 1 ? 'task is' : 'tasks are'} still running in the background.`
        };
    }

    syncLoadingIndicatorContent() {
        const descriptor = this.getActiveLoadingDescriptor();

        if (this.loadingIndicatorLabel) {
            this.loadingIndicatorLabel.textContent = descriptor.label;
        }

        if (this.loadingRotomTooltipTarget) {
            this.loadingRotomTooltipTarget.dataset.tooltip = descriptor.detail;
            this.loadingRotomTooltipTarget.setAttribute('title', descriptor.detail);
            this.loadingRotomTooltipTarget.setAttribute('aria-label', `${descriptor.label} ${descriptor.detail}`);
        }
    }

    updateLoadingIndicator() {
        if (!this.loadingIndicator) {
            return;
        }
        this.syncLoadingIndicatorContent();
        if (this.activeLoadingCount > 0) {
            this.loadingIndicator.classList.add('active');
            this.startIndicatorLoadingEffects();
        } else {
            this.loadingIndicator.classList.remove('active');
            this.stopIndicatorLoadingEffects();
        }
    }

    handleRealtimePlaybackLevel(level) {
        if (!this.powerLightElement) {
            return;
        }
        const clamped = Math.max(0, Math.min(1, Number(level) || 0));
        const amplified = Math.max(0, Math.min(1, Math.pow(clamped, 0.6)));
        this.powerLightTargetLevel = amplified;

        if (!this.powerLightAnimationFrame) {
            this.powerLightAnimationFrame = requestAnimationFrame(() => this.animatePowerLightGlow());
        }
    }

    animatePowerLightGlow() {
        if (!this.powerLightElement) {
            this.powerLightAnimationFrame = null;
            return;
        }

        const smoothing = 0.35;
        this.powerLightLevel += (this.powerLightTargetLevel - this.powerLightLevel) * smoothing;
        this.powerLightElement.style.setProperty('--power-light-level', this.powerLightLevel.toFixed(3));

        const shouldContinue = this.powerLightTargetLevel > 0.01 || this.powerLightLevel > 0.01;
        if (!shouldContinue) {
            this.powerLightLevel = 0;
            this.powerLightElement.style.setProperty('--power-light-level', '0');
            this.powerLightAnimationFrame = null;
            return;
        }

        this.powerLightAnimationFrame = requestAnimationFrame(() => this.animatePowerLightGlow());
    }

    setPowerLightVoiceMode(isActive) {
        if (!this.powerLightElement) {
            return;
        }
        const normalized = Boolean(isActive);
        if (this.powerLightVoiceActive === normalized) {
            return;
        }
        this.powerLightVoiceActive = normalized;
        this.powerLightElement.classList.toggle('voice-active', normalized);
    }

    startIndicatorLoadingEffects() {
        if (!this.indicatorLights || this.indicatorLights.length === 0 || this.indicatorLoadingActive) {
            return;
        }
        this.indicatorLoadingActive = true;
        this.scheduleIndicatorPulse();
    }

    scheduleIndicatorPulse() {
        if (!this.indicatorLoadingActive) {
            return;
        }

        this.flashIndicatorLights();
        const delay = 130 + Math.random() * 220;
        this.indicatorPulseTimeout = setTimeout(() => this.scheduleIndicatorPulse(), delay);
    }

    flashIndicatorLights() {
        if (!this.indicatorLights || this.indicatorLights.length === 0) {
            return;
        }

        this.indicatorLights.forEach(light => light.classList.remove('flash'));
        const activeCount = Math.max(1, Math.floor(Math.random() * this.indicatorLights.length));
        const shuffled = [...this.indicatorLights].sort(() => Math.random() - 0.5);
        const selected = shuffled.slice(0, activeCount);

        selected.forEach(light => {
            const brightness = 0.35 + Math.random() * 0.65;
            light.style.setProperty('--indicator-brightness', brightness.toFixed(2));
            light.classList.add('flash');
            const timeoutId = setTimeout(() => {
                light.classList.remove('flash');
                const idx = this.indicatorFlashTimeouts.indexOf(timeoutId);
                if (idx > -1) {
                    this.indicatorFlashTimeouts.splice(idx, 1);
                }
            }, 120 + Math.random() * 180);
            this.indicatorFlashTimeouts.push(timeoutId);
        });
    }

    stopIndicatorLoadingEffects() {
        if (this.indicatorPulseTimeout) {
            clearTimeout(this.indicatorPulseTimeout);
            this.indicatorPulseTimeout = null;
        }
        if (this.indicatorFlashTimeouts && this.indicatorFlashTimeouts.length > 0) {
            this.indicatorFlashTimeouts.forEach(timeoutId => clearTimeout(timeoutId));
            this.indicatorFlashTimeouts = [];
        }
        this.indicatorLoadingActive = false;

        if (this.indicatorLights) {
            this.indicatorLights.forEach(light => {
                light.classList.remove('flash');
                light.style.removeProperty('--indicator-brightness');
            });
        }
    }
    
    hideWelcomeMessage() {
        const welcomeMessage = this.chatContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
    }

    /**
     * Sync a voice message to the backend so text chat LLM has full history.
     */
    syncVoiceMessageToBackend(role, text, pokemonData = null, tcgData = null) {
        const body = { user_id: this.userId };
        if (role === 'user') {
            body.user_message = text;
        } else {
            body.assistant_text = text;
            if (pokemonData) body.pokemon_data = pokemonData;
            if (tcgData) body.tcg_data = tcgData;
        }
        fetch('/api/chat/record', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        }).catch(err => console.warn('Failed to sync voice message:', err));
    }

    clearChatHistory() {
        // Remove all message bubbles from the chat container
        const messages = this.chatContainer.querySelectorAll('.message-bubble');
        messages.forEach(msg => msg.remove());

        // Show the welcome message again
        const welcomeMessage = this.chatContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = '';
        }

        // Clear server-side conversation history
        fetch(`/api/chat/clear/${encodeURIComponent(this.userId)}`, { method: 'DELETE' })
            .catch(err => console.warn('Failed to clear server history:', err));
    }
    
    setLoading(loading) {
        const previousState = this.isLoading;
        this.isLoading = loading;
        if (this.sendButton) {
            this.sendButton.disabled = loading;
        }
        if (this.messageInput) {
            this.messageInput.disabled = loading;
        }

        if (loading && !previousState) {
            this.manualLoadingToken = this.beginGlobalLoading({
                label: 'Working...',
                detail: 'Rotom is waiting for the current action to finish.'
            });
        } else if (!loading && previousState) {
            this.endGlobalLoading(this.manualLoadingToken);
            this.manualLoadingToken = null;
        }
    }
    
    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }

    // ─── AI Context Viewer ─────────────────────────────────────────────

    toggleContextViewer() {
        const panel = document.getElementById('contextViewerPanel');
        if (!panel) return;
        const isVisible = panel.style.display !== 'none';
        if (isVisible) {
            this.closeContextViewer();
        } else {
            this.openContextViewer();
        }
    }

    openContextViewer() {
        const panel = document.getElementById('contextViewerPanel');
        if (!panel) return;
        panel.style.display = 'flex';
        this.refreshContextViewer();
        // Start live refresh
        this._contextViewerInterval = setInterval(() => this.refreshContextViewer(), 1500);
        // Wire close button
        const closeBtn = document.getElementById('contextViewerClose');
        if (closeBtn && !closeBtn.dataset.bound) {
            closeBtn.addEventListener('click', () => this.closeContextViewer());
            closeBtn.dataset.bound = 'true';
        }
    }

    closeContextViewer() {
        const panel = document.getElementById('contextViewerPanel');
        if (panel) panel.style.display = 'none';
        if (this._contextViewerInterval) {
            clearInterval(this._contextViewerInterval);
            this._contextViewerInterval = null;
        }
    }

    refreshContextViewer() {
        const body = document.getElementById('contextViewerBody');
        if (!body) return;

        const sections = [];

        // 1. Connection status
        const voiceConnected = this.realtimeVoice?.isConnected || false;
        const voiceStatus = voiceConnected ? '🟢 Connected' : '🔴 Disconnected';
        sections.push(this._ctxSection('Voice Connection', voiceStatus));

        // 2. System prompt (realtime)
        const instructions = this.realtimeVoice?.sessionConfig?.session?.instructions;
        if (instructions) {
            sections.push(this._ctxSection('System Prompt (Realtime)', this._ctxCode(instructions)));
        } else {
            sections.push(this._ctxSection('System Prompt (Realtime)', '<em>Not loaded — connect voice to see</em>'));
        }

        // 3. Canvas context (what AI sees right now)
        const canvasCtx = this.buildCanvasContextDescription();
        let canvasDisplay = canvasCtx ? this._ctxCode(canvasCtx) : '<em>No context</em>';
        if (this.hoveredItem) {
            canvasDisplay += `<br><br><strong>🎯 Hover:</strong> ${this.hoveredItem.summary}`;
            if (this.hoveredItem.id) {
                canvasDisplay += `<br><code>card_id: ${this.hoveredItem.id}</code>`;
            }
        }
        sections.push(this._ctxSection('Current Canvas Context', canvasDisplay));

        // 4. Canvas state
        const state = this.currentCanvasState;
        sections.push(this._ctxSection('Canvas State',
            `<code>type:</code> ${state?.type || 'none'}<br><code>viewHistory:</code> [${(this.viewHistory || []).join(' → ')}] (idx: ${this.currentViewIndex ?? 0})`));

        // 5. Registered tools
        const tools = this.realtimeVoice?.tools || [];
        if (tools.length > 0) {
            const toolList = tools.map(t => {
                const name = t.name || '?';
                const desc = t.description || '';
                return `<div class="ctx-tool-item"><code>${name}</code><span class="ctx-tool-desc">${desc}</span></div>`;
            }).join('');
            sections.push(this._ctxSection(`Registered Tools (${tools.length})`, `<div class="ctx-tool-list">${toolList}</div>`));
        } else {
            sections.push(this._ctxSection('Registered Tools', '<em>None loaded</em>'));
        }

        // 6. Recent tool calls
        const toolCalls = this._contextViewerToolCalls || [];
        if (toolCalls.length > 0) {
            const callsHtml = toolCalls.map(tc => {
                const status = tc.success === true ? '✅' : tc.success === false ? '❌' : '⏳';
                const dur = tc.duration ? ` (${tc.duration}ms)` : '';
                const args = tc.args ? JSON.stringify(tc.args) : '{}';
                let resultSnippet = '';
                if (tc.result) {
                    const str = JSON.stringify(tc.result);
                    resultSnippet = str.length > 200 ? str.substring(0, 200) + '…' : str;
                }
                return `<div class="ctx-toolcall-item">
                    <div>${status} <code>${tc.toolName}</code>${dur}</div>
                    <div class="ctx-toolcall-args">Args: ${this._escapeHtml(args)}</div>
                    ${resultSnippet ? `<div class="ctx-toolcall-result">Result: ${this._escapeHtml(resultSnippet)}</div>` : ''}
                </div>`;
            }).join('');
            sections.push(this._ctxSection(`Recent Tool Calls (${toolCalls.length})`, callsHtml));
        } else {
            sections.push(this._ctxSection('Recent Tool Calls', '<em>None yet</em>'));
        }

        // 7. Text chat conversation history (server-side)
        const chatHistory = this._contextViewerChatHistory;
        if (chatHistory && chatHistory.length > 0) {
            const histHtml = chatHistory.map(msg => {
                const role = msg.role || '?';
                const content = (msg.content || '').substring(0, 300);
                const badge = role === 'system' ? '🔧' : role === 'user' ? '👤' : role === 'assistant' ? '🤖' : '📎';
                return `<div class="ctx-hist-item"><span class="ctx-hist-role">${badge} ${role}</span><div class="ctx-hist-content">${this._escapeHtml(content)}${msg.content && msg.content.length > 300 ? '…' : ''}</div></div>`;
            }).join('');
            sections.push(this._ctxSection(`Chat History (${chatHistory.length} messages)`, histHtml));
        } else {
            sections.push(this._ctxSection('Chat History', '<em>Empty</em>'));
        }

        // 8. Session info
        const sessionInfo = [];
        sessionInfo.push(`<code>userId:</code> ${this.userId || 'unknown'}`);
        sessionInfo.push(`<code>voice:</code> ${this.realtimeVoice?.preferredVoice || this.voicePreference || 'alloy'}`);
        sessionInfo.push(`<code>identifiedUser:</code> ${this.currentIdentifiedUser || 'none'}`);
        sessionInfo.push(`<code>currentPokemon:</code> ${this.currentPokemonName || 'none'}`);
        sessionInfo.push(`<code>spriteStyle:</code> ${this.spriteStyle || 'official-artwork'}`);
        sections.push(this._ctxSection('Session Info', sessionInfo.join('<br>')));

        body.innerHTML = sections.join('');

        // Fetch chat history in background (don't block render)
        this._fetchChatHistoryForViewer();
    }

    async _fetchChatHistoryForViewer() {
        try {
            const resp = await fetch(`/api/chat/history/${encodeURIComponent(this.userId)}`);
            if (resp.ok) {
                const data = await resp.json();
                this._contextViewerChatHistory = data.history || [];
            }
        } catch { /* ignore */ }
    }

    _ctxSection(title, content) {
        return `<details class="ctx-section" open><summary class="ctx-section-title">${title}</summary><div class="ctx-section-body">${content}</div></details>`;
    }

    _ctxCode(text) {
        return `<pre class="ctx-code">${this._escapeHtml(text)}</pre>`;
    }

    _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.pokemonChatApp = new PokemonChatApp();
    
    // Expose functions for realtime API to call
    window.showTcgCardByIndex = (cardIndex, pokemonName = null) => {
        if (window.pokemonChatApp) {
            return window.pokemonChatApp.showTcgCardByIndex(cardIndex, pokemonName);
        }
        return { error: 'App not initialized' };
    };
    
    window.showPokemonIndexCanvas = () => {
        if (window.pokemonChatApp) {
            return window.pokemonChatApp.showPokemonIndexInCanvas();
        }
        return { error: 'App not initialized' };
    };

    window.showTcgDatabaseCanvas = () => {
        if (window.pokemonChatApp?.tcgDatabase) {
            window.pokemonChatApp.tcgDatabase.show();
            return { success: true };
        }
        return { error: 'TCG Database not available' };
    };

    window.showMyCollectionCanvas = async () => {
        if (window.pokemonChatApp?.tcgDatabase) {
            await window.pokemonChatApp.tcgDatabase.show();
            await window.pokemonChatApp.tcgDatabase.showMyCollection();
            return { success: true };
        }
        return { error: 'My Collection view is not available' };
    };

    window.navigateBackCanvas = () => {
        if (window.pokemonChatApp) {
            if (window.pokemonChatApp.currentViewIndex <= 0) {
                return { error: 'Already at the earliest page in history' };
            }
            window.pokemonChatApp.navigateBack();
            return { success: true };
        }
        return { error: 'App not initialized' };
    };

    window.navigateForwardCanvas = () => {
        if (window.pokemonChatApp) {
            if (window.pokemonChatApp.currentViewIndex >= window.pokemonChatApp.viewHistory.length - 1) {
                return { error: 'Already at the latest page in history' };
            }
            window.pokemonChatApp.navigateForward();
            return { success: true };
        }
        return { error: 'App not initialized' };
    };

    window.comparePokemonCanvas = async (pokemonName = null, comparePokemonName = null) => {
        const app = window.pokemonChatApp;
        if (!app?.detailView) {
            return { error: 'Pokemon detail view is not available' };
        }
        return app.detailView.showCompareSection(pokemonName, comparePokemonName);
    };

    window.filterPokemonByType = (types) => {
        const app = window.pokemonChatApp;
        if (!app) return { error: 'App not initialized' };
        // Navigate to grid first
        app.showPokemonIndexInCanvas();
        // Clear existing filters and set new type filters
        const sv = app.searchView;
        if (!sv) return { error: 'Search view not available' };
        sv.selectedTypes.clear();
        sv.selectedGens.clear();
        sv.selectedClasses?.clear();
        if (sv.nameInput) sv.nameInput.value = '';
        // Deselect all type chips visually
        sv.typeGrid?.querySelectorAll('.search-type-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
        sv.genGrid?.querySelectorAll('.search-gen-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
        sv.classGrid?.querySelectorAll('.search-class-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
        // Select requested types
        (types || []).forEach(t => {
            const typeLower = t.toLowerCase();
            sv.selectedTypes.add(typeLower);
            const chip = sv.typeGrid?.querySelector(`[data-type="${typeLower}"]`);
            if (chip) chip.classList.add('selected');
        });
        sv.applyFilters();
        const matchCount = document.querySelectorAll('#pokemonList .list-item[style*="display: flex"], #pokemonList .list-item:not([style*="display"])').length;
        return { success: true, matchCount };
    };

    window.filterPokemonByGeneration = (generations) => {
        const app = window.pokemonChatApp;
        if (!app) return { error: 'App not initialized' };
        // Navigate to grid first
        app.showPokemonIndexInCanvas();
        const sv = app.searchView;
        if (!sv) return { error: 'Search view not available' };
        sv.selectedTypes.clear();
        sv.selectedGens.clear();
        sv.selectedClasses?.clear();
        if (sv.nameInput) sv.nameInput.value = '';
        // Deselect all chips visually
        sv.typeGrid?.querySelectorAll('.search-type-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
        sv.genGrid?.querySelectorAll('.search-gen-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
        sv.classGrid?.querySelectorAll('.search-class-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
        // Select requested generations (convert 1-based to 0-based index)
        (generations || []).forEach(g => {
            const idx = String(parseInt(g) - 1);
            sv.selectedGens.add(idx);
            const chip = sv.genGrid?.querySelector(`[data-gen="${idx}"]`);
            if (chip) chip.classList.add('selected');
        });
        sv.applyFilters();
        const matchCount = document.querySelectorAll('#pokemonList .list-item[style*="display: flex"], #pokemonList .list-item:not([style*="display"])').length;
        return { success: true, matchCount };
    };

    window.filterPokemonByClassification = async (classifications) => {
        const app = window.pokemonChatApp;
        if (!app) return { error: 'App not initialized' };
        app.showPokemonIndexInCanvas();
        const sv = app.searchView;
        if (!sv) return { error: 'Search view not available' };

        if (!sv.metadata) {
            await sv._loadMetadata();
        }

        sv.selectedTypes.clear();
        sv.selectedGens.clear();
        sv.selectedClasses.clear();
        if (sv.nameInput) sv.nameInput.value = '';
        sv.typeGrid?.querySelectorAll('.search-type-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
        sv.genGrid?.querySelectorAll('.search-gen-chip').forEach(chip => {
            chip.classList.remove('selected');
        });
        sv.classGrid?.querySelectorAll('.search-class-chip').forEach(chip => {
            chip.classList.remove('selected');
        });

        (classifications || []).forEach(classification => {
            const normalized = String(classification).toLowerCase();
            if (!['legendary', 'mythical'].includes(normalized)) return;
            sv.selectedClasses.add(normalized);
            const chip = sv.classGrid?.querySelector(`[data-class="${normalized}"]`);
            if (chip) chip.classList.add('selected');
        });
        sv.applyFilters();
        const matchCount = document.querySelectorAll('#pokemonList .list-item[style*="display: flex"], #pokemonList .list-item:not([style*="display"])').length;
        return { success: true, matchCount };
    };

    window.sortTcgCardsCanvas = (sortBy) => {
        const app = window.pokemonChatApp;
        if (!app) return { error: 'App not initialized' };
        // Check if TCG gallery is visible
        if (!app.tcgCardsView || app.tcgCardsView.style.display === 'none') {
            return { error: 'No TCG card gallery is currently displayed. Search for a Pokemon\'s cards first.' };
        }
        if (!app.tcgGallery) return { error: 'TCG gallery not available' };
        // Update sort and re-render
        app.tcgGallery.currentSort = sortBy;
        const sortSelect = app.tcgCardsView.querySelector('#tcg-sort-select');
        if (sortSelect) sortSelect.value = sortBy;
        if (app.currentTcgData) {
            app.tcgGallery.display(app.currentTcgData);
        }
        return { success: true };
    };

    window.sortTcgDatabaseCanvas = (sortBy) => {
        const app = window.pokemonChatApp;
        if (!app) return { error: 'App not initialized' };
        if (!app.tcgDatabaseViewEl || app.tcgDatabaseViewEl.style.display === 'none') {
            return { error: 'TCG Database is not currently displayed. Navigate there first.' };
        }
        if (!app.tcgDatabase) return { error: 'TCG Database not available' };
        // Update sort select UI and re-sort
        const sortSelect = app.tcgDatabaseViewEl.querySelector('#tcg-db-sort-select');
        if (sortSelect) sortSelect.value = sortBy;
        app.tcgDatabase.changeSort(sortBy);
        return { success: true };
    };
    
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
