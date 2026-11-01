import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const appSource = readFileSync(new URL('../static/js/app.js', import.meta.url), 'utf8');
const voiceSource = readFileSync(new URL('../static/js/realtime-voice.js', import.meta.url), 'utf8');

function setup(overrides = {}) {
    const elements = new Map([
        ['adminEmbeddingEncoder', { value: 'clip' }],
        ['adminEmbeddingInventory', {}],
        ['adminEmbeddingGenerateBtn', {}],
        ['adminEmbeddingProgress', {}],
        ['adminEmbeddingProgressFill', { style: {} }],
        ['adminEmbeddingProgressText', {}],
    ]);
    const stored = new Map();
    const context = vm.createContext({
        console,
        document: { addEventListener() {}, getElementById: id => elements.get(id) },
        window: {},
        navigator: {},
        localStorage: { getItem: key => stored.get(key), setItem: (key, value) => stored.set(key, value) },
        clearTimeout() {},
        ...overrides,
    });
    vm.runInContext(appSource, context);
    vm.runInContext(voiceSource, context);
    const app = Object.create(vm.runInContext('PokemonChatApp.prototype', context));
    return { app, context, elements, stored };
}

test('CLIP selection persists and opens through the shared text action', async () => {
    const { app, stored } = setup();
    const calls = [];
    Object.assign(app, {
        syncScannerPipelineControls() {},
        setScannerSettingsOpen() {},
        updateCameraStatus() {},
        setCameraMode: mode => calls.push(mode),
        openCameraModal: async () => calls.push('open'),
    });
    await app.executeFrontendAction({ _action: 'set_scanner_pipeline', mode: 'clip' });
    assert.equal(app.scannerPipelineMode, 'clip');
    assert.equal(stored.get('pokedex_scanner_pipeline_v1'), 'clip');
    assert.deepEqual(calls, ['collection', 'open']);
    assert.equal(app.loadScannerPipelineMode(), 'clip');
});

test('CLIP camera scans do not require starting a voice session', async () => {
    const { app } = setup();
    app.cameraMode = 'collection';
    app.scannerPipelineMode = 'clip';
    app.updateCameraStatus = () => {};
    app.activateRealtimeConversation = () => { throw new Error('CLIP must remain local'); };
    assert.equal(await app.startCameraScanningSession(), true);
});

test('CLIP request compares the exact same capture and stores crop diagnostics', async () => {
    const { app } = setup({
        fetch: async (url, options) => {
            assert.equal(url, '/api/tcg/clip-image-match');
            const payload = JSON.parse(options.body);
            assert.equal(payload.image_data_url, 'data:image/jpeg;base64,capture');
            assert.equal(payload.compare, true);
            return { ok: true, json: async () => ({
                matches: [{
                    score: 0.75, ocr_print_boost: 0.12,
                    ocr_print_evidence: { attacks: ['Leaf Step'], collector_number: '003/088' },
                    card: { id: 'me3-3', name: 'Shaymin' },
                }],
                comparison: { legacy: [{ id: 'wrong' }], legacy_crop: [{ id: 'me3-3' }] },
                crop: { detected: true, method: 'perspective' },
                ocr: {
                    enabled: true, recognized_text: 'Shaymin', confidence: 0.94, matched_names: ['Shaymin'],
                    print_lines: [{ region: 'body', text: 'Leaf Step', confidence: 0.99 }],
                },
                cropped_image_data_url: 'data:image/jpeg;base64,crop',
                index_metadata: { vector_size: 512 },
            }) };
        },
    });
    app.scannerPipelineMode = 'clip';
    app.scannerDebugTrace = {};
    const matches = await app.findNumpyMatchingCards('data:image/jpeg;base64,capture');
    assert.equal(matches[0].card.id, 'me3-3');
    assert.equal(matches[0].visualBreakdown.calibrated_confidence, false);
    assert.equal(matches[0].visualBreakdown.ocr_print_boost, 0.12);
    assert.equal(matches[0].visualBreakdown.matched_print_text.collector_number, '003/088');
    assert.equal(app.scannerDebugTrace.comparison.legacy[0].id, 'wrong');
    assert.equal(app.scannerDebugTrace.crop.method, 'perspective');
    assert.equal(app.scannerDebugTrace.cropImage, 'data:image/jpeg;base64,crop');
    assert.equal(app.scannerDebugTrace.ocr.recognized_text, 'Shaymin');
});

test('scanner debug shows escaped print evidence and explicit OCR failures', () => {
    const { app } = setup();
    app._escapeHtml = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    app.cameraDebugSteps = {};
    app.cameraDebugEvidence = {};
    app.scannerDebugTrace = {
        mode: 'clip', steps: [], rankings: [], imageDataUrl: 'capture',
        ocr: {
            enabled: true, recognized_text: 'Shaymin',
            print_lines: [{ region: 'body', text: 'Leaf <Step>', confidence: 0.99 }],
            metadata_error: 'catalog unavailable',
        },
    };
    app.renderScannerDebugTrace();
    assert.match(app.cameraDebugEvidence.innerHTML, /Attack and footer text/);
    assert.match(app.cameraDebugEvidence.innerHTML, /Leaf &lt;Step&gt;/);
    assert.match(app.cameraDebugEvidence.innerHTML, /Print metadata error: catalog unavailable/);
    app.scannerDebugTrace.ocr = { enabled: false, skipped_reason: 'No reliable card boundary was detected.' };
    app.renderScannerDebugTrace();
    assert.match(app.cameraDebugEvidence.innerHTML, /OCR skipped: No reliable card boundary/);
});

test('Settings routes CLIP generation and polling to a separate encoder job', async () => {
    const urls = [];
    const { app, elements } = setup({
        fetch: async url => {
            urls.push(url);
            return { ok: true, json: async () => ({ job: {
                status: 'completed', percent: 100, completed: 1, total: 1, message: 'Done',
            } }) };
        },
    });
    app.setAdminStatusText = () => {};
    app.loadAdminStatus = async () => {};
    await app.startAdminEmbeddingGeneration();
    assert.equal(urls[0], '/api/admin/embeddings/generate?encoder=clip');
    assert.equal(urls[1], '/api/admin/embeddings/job?encoder=clip');
    assert.equal(elements.get('adminEmbeddingGenerateBtn').disabled, true);
});

test('realtime voice dispatches the scanner tool through the same frontend method', async () => {
    const { context } = setup();
    let chosen;
    context.window.app = { openScannerPipeline: async mode => { chosen = mode; return { success: true, mode }; } };
    const client = vm.runInContext('new RealtimeVoiceClient()', context);
    let result;
    client._sendFrontendToolResult = (id, name, args, value, success) => { result = { name, value, success }; };
    await client.handleToolCall({ name: 'set_scanner_pipeline', call_id: 'clip-call', arguments: '{"mode":"clip"}' });
    assert.equal(chosen, 'clip');
    assert.equal(result.name, 'set_scanner_pipeline');
    assert.equal(result.success, true);
});
