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
        this.lastFaceIdentificationTime = 0;
        this.faceIdentificationCooldown = 10000; // 10 seconds cooldown between identifications
        this.faceIdOverlayEnabled = this.loadFaceIdOverlayPreference();
        this.voicePreference = this.loadVoiceActorPreference();
        this.apiSettings = this.loadApiSettings();

        // Pokemon viewing status tracking (stored in cookies)
        this.viewingStatus = this.loadViewingStatus();

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
        this.activeLoadingCount = 0;
        this.fetchInterceptorInstalled = false;
        this.initializeHeaderLights();

        // Camera scanner elements
        this.cameraButton = document.getElementById('cameraButton');
        this.cameraModalOverlay = document.getElementById('cameraModalOverlay');
        this.cameraModalClose = document.getElementById('cameraModalClose');
        this.cameraPreview = document.getElementById('cameraPreview');
        this.cameraStatusText = document.getElementById('cameraStatusText');
        this.cameraSwitchButton = document.getElementById('cameraSwitchButton');
        this.cameraSwitchText = document.getElementById('cameraSwitchText');
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

        // TCG card modal elements
        this.tcgCardModalOverlay = document.getElementById('tcgCardModalOverlay');
        this.tcgCardModalContent = document.getElementById('tcgCardModalContent');
        this.tcgCardModalClose = document.getElementById('tcgCardModalClose');

        // New layout elements
        this.chatSidebar = document.getElementById('chatSidebar');
        this.chatToggleBtn = document.getElementById('chatToggleBtn');
        this.chatCloseBtn = document.getElementById('chatCloseBtn');
        this.mainCanvas = document.getElementById('mainCanvas');
        this.pokemonGridView = document.getElementById('pokemonGridView');
        this.pokemonList = document.getElementById('pokemonList');
        this.pokemonDetailView = document.getElementById('pokemonDetailView');
        this.tcgCardsView = document.getElementById('tcgCardsView');
        this.tcgCardDetailView = document.getElementById('tcgCardDetailView');

        // Initialize view classes
        this.gridView = new PokemonGridView(this);
        this.detailView = new PokemonDetailView(this);
        this.tcgGallery = new TcgCardsGalleryView(this);
        this.tcgDetail = new TcgCardDetailView(this);

        // Pokemon data
        this.allPokemons = [];
        this.MAX_POKEMON = 1025; // All Pokemon up to Gen 9
        this.currentPokemonName = null; // Store current Pokemon name for card searches

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
        this.adjustTextareaHeight();
        this.loadTools();
        this.loadCacheConfig();
        this.gridView.show(); // Use gridView instead of loadPokemonGrid
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
            } else if (view === 'tcg') {
                if (this.currentTcgData) {
                    this.tcgGallery.displayWithoutHistory(this.currentTcgData);
                }
            } else if (view.startsWith('tcg-detail-')) {
                // For TCG detail, find and show the specific card
                const cardId = view.replace('tcg-detail-', '');
                if (this.currentTcgData && this.currentTcgData.cards) {
                    const card = this.currentTcgData.cards.find(c => c.id === cardId);
                    if (card) {
                        await this.tcgDetail.showWithoutHistory(card);
                    } else {
                        console.log('Card not found in current TCG data:', cardId);
                    }
                } else {
                    console.log('No TCG data available for navigation');
                }
            } else if (view.startsWith('pokemon-')) {
                const pokemonId = parseInt(view.split('-')[1]);
                this.detailView.loadPokemonWithoutHistory(pokemonId);
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
            backBtn.style.opacity = canGoBack ? '1' : '0.4';
            backBtn.classList.toggle('footer-btn-active', canGoBack);
        }
        
        if (forwardBtn) {
            const canGoForward = this.currentViewIndex < this.viewHistory.length - 1;
            forwardBtn.disabled = !canGoForward;
            forwardBtn.style.opacity = canGoForward ? '1' : '0.4';
            forwardBtn.classList.toggle('footer-btn-active', canGoForward);
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
    }
    
    // Delegate to tcgGallery view
    displayTcgCardsInCanvasWithoutHistory(tcgData) {
        console.log('🃏 displayTcgCardsInCanvasWithoutHistory called');
        
        if (!tcgData || !tcgData.cards || !Array.isArray(tcgData.cards) || tcgData.cards.length === 0) {
            return;
        }
        
        this.tcgGallery.displayWithoutHistory(tcgData);
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

        this.updateCameraSwitchButton();
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
            if (result.name && result.is_new_user && result.greeting_message) {
                // New user detected - greet them
                this.currentIdentifiedUser = result.name;
                this.addMessage('assistant', result.greeting_message);
                console.log(`Greeting new user: ${result.name}`);

                // Update realtime voice context with user's name
                if (this.realtimeVoice && typeof this.realtimeVoice.updateUserContext === 'function') {
                    if (this.realtimeVoice.isConnected) {
                        this.realtimeVoice.updateUserContext(result.name);
                    } else {
                        console.log('⏳ Realtime voice not connected yet, will update context when connected');
                    }
                } else {
                    console.log('⚠️ Realtime voice not initialized or updateUserContext method not available');
                }
            } else if (result.name && !result.is_new_user) {
                // Same user as before - update tracking but don't greet
                this.currentIdentifiedUser = result.name;
                console.log(`Same user detected: ${result.name}, no greeting`);

                // Update realtime voice context with user's name (even if same user)
                if (this.realtimeVoice && typeof this.realtimeVoice.updateUserContext === 'function') {
                    if (this.realtimeVoice.isConnected) {
                        this.realtimeVoice.updateUserContext(result.name);
                    } else {
                        console.log('⏳ Realtime voice not connected yet, will update context when connected');
                    }
                } else {
                    console.log('⚠️ Realtime voice not initialized or updateUserContext method not available');
                }
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
            } else if (view === 'tcg' && this.currentTcgData) {
                this.tcgGallery.displayWithoutHistory(this.currentTcgData);
            } else if (view.startsWith('tcg-detail-')) {
                // For TCG detail, find and show the specific card
                const cardId = view.replace('tcg-detail-', '');
                if (this.currentTcgData && this.currentTcgData.cards) {
                    const card = this.currentTcgData.cards.find(c => c.id === cardId);
                    if (card) {
                        await this.tcgDetail.showWithoutHistory(card);
                    } else {
                        console.log('Card not found in current TCG data:', cardId);
                    }
                } else {
                    console.log('No TCG data available for navigation');
                }
            } else if (view.startsWith('pokemon-')) {
                const pokemonId = parseInt(view.split('-')[1]);
                this.detailView.loadPokemonWithoutHistory(pokemonId);
            }
            this.updateNavigationButtons();
        }
    }
    
    // View Pokemon Cards
    async viewPokemonCards() {
        if (!this.currentPokemonName) {
            console.error('No Pokemon selected');
            return;
        }
        
        try {
            console.log('🃏 Searching cards for:', this.currentPokemonName);
            this.setLoading(true);
            
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'search_pokemon_cards',
                    arguments: { pokemon_name: this.currentPokemonName }
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
                this.addMessage('assistant', `No trading cards found for ${this.currentPokemonName}.`);
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
                        console.log('Azure OpenAI Realtime API available, initializing...');
                        this.initializeRealtimeVoice();
                        return;
                    }
                    console.log('Realtime API not available:', status.message || 'Unknown reason');
                } catch (error) {
                    console.log('Could not check Realtime API status:', error);
                }
            } else {
                console.log('Realtime API locked until credentials are configured.');
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
            preferredVoice: this.voicePreference,
            apiSettingsProvider: () => this.buildApiSettingsPayload('realtime', { notifyOnError: true }),
            languagePreferenceProvider: () => this.getRealtimeLanguagePreference(),
            
            onStatusChange: (status, message) => {
                console.log('Realtime status:', status, message);
                this.updateVoiceStatus(status, message);

                // Trigger face identification when session becomes ready
                // Use a longer delay to avoid interrupting user's initial interaction
                if (status === 'session_ready' && this.faceRecognitionEnabled) {
                    console.log('Session ready - scheduling face identification (2s delay)');
                    setTimeout(() => {
                        this.identifyUserFromCamera();
                    }, 2000);
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
                        return;
                    }
                    
                    // Voice command: Go forward / Navigate forward / Forward
                    if (lowerText.match(/^(go forward|navigate forward|forward|next)$/)) {
                        console.log('⏭️ Voice command: Go forward');
                        this.navigateForward();
                        this.addMessage('user', text);
                        this.addMessage('assistant', 'Moving forward in history.');
                        return;
                    }
                    
                    // Voice command: Show index / Show all Pokemon / Go home
                    if (lowerText.match(/^(show index|show all pokemon|go home|home|index)$/)) {
                        console.log('🏠 Voice command: Show index');
                        this.showPokemonIndexInCanvas();
                        this.addMessage('user', text);
                        this.addMessage('assistant', 'Showing all Pokemon in the index.');
                        return;
                    }
                    
                    // Normal processing for other messages
                    this.addMessage('user', text);
                    this.hideWelcomeMessage();
                        void this.maybeSendScanSnapshotForQuestion();
                    // Clear tool calls for new conversation turn
                    this.currentToolCalls = [];
                }
            },
            
            onResponse: (text, isPartial) => {
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
        if (!this.currentPokemonName) {
            console.error('No current Pokemon to refresh cards for');
            return;
        }
        
        console.log('🔄 Force refreshing TCG cards for:', this.currentPokemonName);
        
        try {
            // Clear cache for TCG cards
            console.log('🗑️ Calling cache invalidation API...');
            const response = await fetch('/api/cache/invalidate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool: 'search_pokemon_cards',
                    params: { pokemon_name: this.currentPokemonName.toLowerCase() }
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

    buildPokemonContextSummary(pokemon, species) {
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
     * Build a unique view key for history tracking
     */
    buildViewKey(type, data) {
        switch (type) {
            case 'grid':
                return 'grid';
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
    buildCanvasContextDescription() {
        const { type, data } = this.currentCanvasState;
        
        switch (type) {
            case 'grid':
                return "User is currently viewing the Pokemon index page (grid view) showing all Pokemon. They can select any Pokemon to view details, or ask about specific Pokemon.";
            
            case 'pokemon':
                if (!data || !data.pokemon) return null;
                return this.buildPokemonContextSummary(data.pokemon, data.species);
            
            case 'tcg-gallery':
                if (!data || !data.pokemon_name) return null;
                const cardCount = data.total_count || (data.cards ? data.cards.length : 0);
                return `User is viewing a gallery of ${cardCount} Pokemon TCG trading cards for ${data.pokemon_name}. They can click any card to see details and pricing information.`;
            
            case 'tcg-detail':
                if (!data) return null;
                return this.buildCardContextSummary(data);
            
            default:
                return null;
        }
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

    installFetchInterceptor() {
        if (this.fetchInterceptorInstalled || typeof window === 'undefined' || typeof window.fetch !== 'function') {
            return;
        }

        const originalFetch = window.fetch.bind(window);
        window.fetch = async (...args) => {
            const shouldTrack = this.shouldTrackLoadingRequest(args[0]);
            if (shouldTrack) {
                this.beginGlobalLoading();
            }

            try {
                return await originalFetch(...args);
            } finally {
                if (shouldTrack) {
                    this.endGlobalLoading();
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

    beginGlobalLoading() {
        this.activeLoadingCount += 1;
        this.updateLoadingIndicator();
    }

    endGlobalLoading() {
        this.activeLoadingCount = Math.max(0, this.activeLoadingCount - 1);
        this.updateLoadingIndicator();
    }

    updateLoadingIndicator() {
        if (!this.loadingIndicator) {
            return;
        }
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
            this.beginGlobalLoading();
        } else if (!loading && previousState) {
            this.endGlobalLoading();
        }
    }
    
    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
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
