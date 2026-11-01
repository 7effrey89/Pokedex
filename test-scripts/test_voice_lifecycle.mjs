import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const appSource = readFileSync(new URL('../static/js/app.js', import.meta.url), 'utf8');
const voiceSource = readFileSync(new URL('../static/js/realtime-voice.js', import.meta.url), 'utf8');

function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}

function setup(overrides = {}) {
    const sockets = [];
    const messages = [];
    class Socket {
        static OPEN = 1;
        constructor() {
            this.readyState = Socket.OPEN;
            sockets.push(this);
        }
        send(message) { messages.push(JSON.parse(message)); }
        close() { this.closed = true; this.readyState = 3; this.onclose?.({ code: 1000 }); }
    }
    const context = vm.createContext({
        console,
        document: { addEventListener() {} },
        window: {},
        navigator: {},
        WebSocket: Socket,
        setTimeout,
        clearTimeout,
        ...overrides,
    });
    vm.runInContext(voiceSource, context);
    vm.runInContext(appSource, context);
    const client = vm.runInContext('new RealtimeVoiceClient()', context);
    const app = Object.create(vm.runInContext('PokemonChatApp.prototype', context));
    const classes = new Set(['active']);
    Object.assign(app, {
        realtimeVoice: client,
        useRealtimeApi: true,
        isVoiceActive: true,
        isVoiceStarting: false,
        voiceActivationVersion: 0,
        voiceButton: {
            classList: { add: value => classes.add(value), remove: value => classes.delete(value) },
            querySelector: () => null,
        },
        statusText: {},
        setPowerLightVoiceMode() {},
        addMessage() {},
        hideWelcomeMessage() {},
        syncCurrentViewContext() {},
        flushPendingRealtimeUserContext() {},
        buildApiSettingsPayload: () => ({}),
    });
    return { app, client, context, sockets, messages, classes, Socket };
}

function microphone() {
    const track = { stopped: false, stop() { this.stopped = true; } };
    return { track, stream: { getTracks: () => [track] } };
}

test('disabling voice discards buffered audio instead of requesting another response', () => {
    const { app, client, messages, classes, Socket } = setup();
    client.ws = new Socket();
    client.isConnected = true;
    client.isRecording = true;
    client.isResponseActive = true;
    client.audioBytesSent = 6400;
    const { stream, track } = microphone();
    client.mediaStream = stream;
    const source = { stopped: false, stop() { this.stopped = true; } };
    client.currentAudioSources = [source];
    app.stopVoiceConversation();
    assert.equal(messages.some(message => message.type === 'response.create'), false);
    assert.equal(messages.some(message => message.type === 'input_audio_buffer.commit'), false);
    assert.equal(client.isConnected, false);
    assert.equal(client.isRecording, false);
    assert.equal(track.stopped, true);
    assert.equal(source.stopped, true);
    assert.equal(app.isVoiceActive, false);
    assert.equal(classes.has('active'), false);
});

test('ordinary stopRecording still submits the recorded turn', () => {
    const { client, messages, Socket } = setup();
    client.ws = new Socket();
    client.isRecording = true;
    client.audioBytesSent = 6400;
    client.stopRecording();
    assert.equal(messages.filter(message => message.type === 'input_audio_buffer.commit').length, 1);
    assert.equal(messages.filter(message => message.type === 'response.create').length, 1);
});

test('disabling during connection prevents the pending activation from starting the microphone', async () => {
    const { app, client } = setup();
    const connection = deferred();
    let recordings = 0;
    app.isVoiceActive = false;
    client.connect = () => connection.promise;
    client.startRecording = async () => { recordings++; };
    client.disconnect = () => {};
    const start = app.startVoiceConversation();
    app.toggleVoiceConversation();
    connection.resolve(true);
    await start;
    assert.equal(recordings, 0);
    assert.equal(app.isVoiceActive, false);
    assert.equal(app.isVoiceStarting, false);
});

test('a cancelled startup failure does not enable browser fallback', async () => {
    const { app, client } = setup();
    const connection = deferred();
    app.isVoiceActive = false;
    client.connect = () => connection.promise;
    client.disconnect = () => {};
    app.setVoiceBackendState = () => assert.fail('Cancelled activation must not switch backends');
    app.initializeVoiceRecognition = () => assert.fail('Cancelled activation must not start recognition');
    const start = app.startVoiceConversation();
    app.stopVoiceConversation();
    connection.reject(new Error('Connection failed after disabling'));
    await start;
    assert.equal(app.isVoiceActive, false);
});

test('disconnect during configuration prevents a late WebSocket connection', async () => {
    const { client, sockets } = setup();
    const configuration = deferred();
    client.initialize = () => configuration.promise;
    const connecting = client.connect();
    client.disconnect();
    configuration.resolve(true);
    assert.equal(await connecting, false);
    assert.equal(sockets.length, 0);
});

test('events from a disconnected socket cannot reactivate playback or status', async () => {
    const { client, sockets } = setup();
    client.wsUrl = 'wss://example.test';
    client.apiKey = 'test';
    const connecting = client.connect();
    const socket = sockets[0];
    const lateOpen = socket.onopen;
    const lateMessage = socket.onmessage;
    client.disconnect();
    assert.equal(await connecting, false);
    client.onStatusChange = () => assert.fail('Stale socket changed voice status');
    client.onResponse = () => assert.fail('Stale socket delivered a response');
    client.handleAudioChunk = () => assert.fail('Stale socket restarted audio');
    lateOpen();
    lateMessage({ data: JSON.stringify({ type: 'response.output_audio.delta', delta: 'AAAA' }) });
    lateMessage({ data: JSON.stringify({ type: 'response.output_audio_transcript.done', transcript: 'late speech' }) });
    assert.equal(client.isConnected, false);
});

test('microphone permission completing after disconnect releases the stream', async () => {
    const permission = deferred();
    const { client } = setup({ navigator: { mediaDevices: { getUserMedia: () => permission.promise } } });
    const { stream, track } = microphone();
    const recording = client.startRecording();
    client.disconnect();
    permission.resolve(stream);
    await recording;
    assert.equal(track.stopped, true);
    assert.equal(client.isRecording, false);
    assert.equal(client.mediaStream, null);
});

test('browser speech results completing after disabling do not speak', async () => {
    const response = deferred();
    const { app } = setup({ fetch: () => response.promise });
    app.useRealtimeApi = false;
    app.setLoading = () => {};
    app.getCardContextPayload = () => null;
    app.speakText = () => assert.fail('Disabled voice must not speak a late reply');
    const processing = app.processVoiceMessage('show Pikachu');
    app.stopVoiceConversation();
    response.resolve({ ok: true, json: async () => ({ message: 'Here is Pikachu.' }) });
    await processing;
});

test('late browser recognition start and results cannot reactivate voice', () => {
    const { app } = setup({
        window: {
            SpeechRecognition: class {
                stop() { this.stopped = true; }
            },
        },
    });
    app.initializeVoiceRecognition();
    app.useRealtimeApi = false;
    app.stopVoiceConversation();
    app.processVoiceMessage = () => assert.fail('Disabled recognition processed a result');
    app.recognition.onstart();
    app.recognition.onresult({ results: [[{ transcript: 'late input' }]] });
    assert.equal(app.isVoiceActive, false);
    assert.equal(app.recognition.stopped, true);
});

test('stopping while the audio context resumes prevents microphone startup', async () => {
    const resumed = deferred();
    const { stream, track } = microphone();
    const { client } = setup({ navigator: { mediaDevices: { getUserMedia: async () => stream } } });
    client.audioContext = {
        state: 'suspended',
        resume: () => resumed.promise,
        close() {},
        createMediaStreamSource: () => assert.fail('Cancelled microphone was connected'),
    };
    const recording = client.startRecording();
    await Promise.resolve();
    client.disconnect();
    resumed.resolve();
    await recording;
    assert.equal(track.stopped, true);
    assert.equal(client.isRecording, false);
});

test('cancelled playback cannot resume after disconnect', async () => {
    for (const reject of [false, true]) {
        const resumed = deferred();
        const { client } = setup();
        client.audioQueue = [new Int16Array([1, 2])];
        client.playbackContext = {
            state: 'suspended',
            resume: () => resumed.promise,
            close() {},
            createBuffer: () => assert.fail('Cancelled playback restarted'),
        };
        const playback = client.playAudioQueueSmooth();
        client.disconnect();
        client.onError = () => assert.fail('Cancellation was reported as a playback error');
        if (reject) resumed.reject(new Error('Context closed'));
        else resumed.resolve();
        await playback;
        assert.equal(client.isPlaying, false);
    }
});

test('a tool result from the closed session cannot request speech on a new socket', async () => {
    const response = deferred();
    const { client, messages, Socket } = setup({ fetch: () => response.promise });
    client.ws = new Socket();
    const tool = client.handleToolCall({ name: 'get_pokemon', call_id: 'old-call', arguments: '{}' });
    client.disconnect();
    client.ws = new Socket();
    client.onToolResult = () => assert.fail('Old tool result was delivered to the new session');
    response.resolve({ ok: true, json: async () => ({ result: { name: 'Pikachu' } }) });
    await tool;
    assert.equal(messages.some(message => message.type === 'response.create'), false);
});

test('voice preference restart does not resume voice after the user disables it', async () => {
    const connection = deferred();
    const { app } = setup();
    app.initializeRealtimeVoice = () => {};
    app.ensureRealtimeVoiceConnection = () => connection.promise;
    app.showToast = () => {};
    app.activateRealtimeConversation = () => assert.fail('Voice preference change reactivated disabled voice');
    const restart = app.restartRealtimeVoiceClient({ resumeVoice: true, voiceName: 'alloy' });
    app.stopVoiceConversation();
    connection.resolve();
    await restart;
    assert.equal(app.isVoiceActive, false);
});

test('an explicit new activation reconnects and starts recording after disabling', async () => {
    const { app, client, sockets } = setup();
    client.wsUrl = 'wss://example.test';
    client.apiKey = 'test';
    client.startRecording = async () => { client.isRecording = true; return true; };
    app.stopVoiceConversation();
    const activation = app.startVoiceConversation();
    sockets[0].onopen();
    await activation;
    assert.equal(app.isVoiceActive, true);
    assert.equal(client.isRecording, true);
    assert.equal(app.isVoiceStarting, false);
    app.stopVoiceConversation();
});
