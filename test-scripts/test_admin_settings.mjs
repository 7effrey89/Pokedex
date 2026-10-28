import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../static/js/app.js', import.meta.url), 'utf8');

function createView(overrides = {}) {
    const elements = new Map([
        ['adminDataRoot', {}],
        ['adminCatalogStatus', {}],
        ['adminUsersStatus', {}],
        ['adminAssetComponents', {}],
        ['adminBackupComponents', {}],
    ]);
    const context = vm.createContext({
        document: {
            addEventListener() {},
            getElementById: id => elements.get(id),
        },
        navigator: {},
        ...overrides,
    });
    vm.runInContext(source, context);
    return {
        view: vm.runInContext('PokemonChatApp.prototype', context),
        elements,
    };
}

test('settings displays browsable catalog totals before artwork is downloaded', () => {
    const { view, elements } = createView();
    view.renderAdminStorage({
        storage: { data_root: 'local-data', persistent: false },
        catalog: {
            available: false,
            schema_version: 2,
            species_count: 1025,
            pokemon_count: 1350,
            card_count: 20314,
            set_count: 173,
            reason: 'Database needs Pokemon data and official artwork',
        },
        users: { available: false },
    });
    const summary = elements.get('adminCatalogStatus').textContent;
    for (const [count, label] of [[1025, 'species'], [1350, 'forms'], [20314, 'cards'], [173, 'sets']]) {
        assert.ok(summary.includes(`${count.toLocaleString()} ${label}`), summary);
    }
    assert.ok(!summary.includes('needs'));
});

test('backup categories include TCG image embeddings using the shared service label', () => {
    const { view, elements } = createView();
    view.renderAdminBackupComponents([{
        key: 'tcg_embeddings', label: 'TCG image embeddings', available: true, size_bytes: 4096,
    }]);
    const html = elements.get('adminBackupComponents').innerHTML;
    assert.ok(html.includes('value="tcg_embeddings"'));
    assert.ok(html.includes('TCG image embeddings'));
    assert.ok(html.includes('checked'));
});

test('restore imports ZIP categories instead of restricting them to locally available export selections', async () => {
    const appended = [];
    const messages = [];
    let refreshed = false;
    const { view } = createView({
        FormData: class {
            append(...entry) { appended.push(entry); }
        },
        fetch: async (url, options) => {
            assert.equal(url, '/api/admin/restore');
            assert.equal(options.method, 'POST');
            return { ok: true, json: async () => ({
                restored_components: ['tcg_embeddings'], restored_labels: ['TCG image embeddings'], file_count: 3,
            }) };
        },
    });
    const app = Object.create(view);
    app.getAdminSelection = () => { throw new Error('Export checkboxes must not restrict a restore'); };
    app.setAdminStatusText = message => messages.push(message);
    app.loadAdminStatus = async () => { refreshed = true; };
    const input = { files: [{ name: 'tcg-image-embeddings.zip' }], value: 'selected' };
    await app.restoreAdminBackup(input);
    assert.equal(appended.length, 1);
    assert.equal(appended[0][0], 'bundle');
    assert.ok(messages.at(-1).includes('TCG image embeddings'));
    assert.equal(input.value, '');
    assert.equal(refreshed, true);
});

test('catalog import reports added, updated, and preserved records', async () => {
    const messages = [];
    const { view } = createView({
        FormData: class { append() {} },
        fetch: async () => ({ ok: true, json: async () => ({
            restored_labels: ['Catalog database'], file_count: 1,
            catalog_merge: { inserted: 3, updated: 2, preserved: 7 },
        }) }),
    });
    const app = Object.create(view);
    app.setAdminStatusText = message => messages.push(message);
    app.loadAdminStatus = async () => {};
    await app.restoreAdminBackup({ files: [{ name: 'catalog.zip' }], value: 'selected' });
    assert.ok(messages.at(-1).includes('3 added, 2 updated, 7 preserved'), messages.at(-1));
});

test('an empty catalog still displays its unavailable reason', () => {
    const { view, elements } = createView();
    view.renderAdminStorage({
        storage: { data_root: 'local-data', persistent: false },
        catalog: { pokemon_count: 0, reason: 'Database has not been built' },
        users: { available: false },
    });
    assert.equal(elements.get('adminCatalogStatus').textContent, 'Database has not been built');
});

test('asset availability stays constant as files are cached and download selection still works', () => {
    const { view, elements } = createView();
    for (const stored of [0, 64, 100]) {
        view.renderAdminAssetComponents({
            available: true,
            components: [{
                key: 'pokemon_images', label: 'Pokemon artwork and sprites',
                available_count: 100, stored, missing: 100 - stored,
            }],
        });

        const html = elements.get('adminAssetComponents').innerHTML;
        assert.ok(html.includes('<strong>100 catalog assets</strong>'));
        assert.ok(html.includes(`${stored} stored locally`));
        assert.ok(html.includes(`${100 - stored} remote sources registered`));
        assert.equal(html.includes('checked'), stored < 100);
        assert.ok(!html.includes(' missing'));
    }
});

test('Pokemon refresh fetches and displays fresh form, species, and evolution data', async () => {
            const calls = [];
            const pokemon = { id: 10034, species: { url: 'https://pokeapi.co/api/v2/pokemon-species/6/' } };
            const species = { evolution_chain: { url: 'https://pokeapi.co/api/v2/evolution-chain/2/' } };
            const evolution = { id: 2 };
            const payloads = [pokemon, species, evolution];
            const { view } = createView({
                fetch: async url => {
                    calls.push(url);
                    return { ok: true, json: async () => payloads[calls.length - 1] };
                },
            });
            const app = Object.create(view);
            const displayed = [];
            const loading = [];
            app.currentPokemonName = 'charizard-mega-x';
            app.detailView = { display: (...data) => displayed.push(data) };
            app.setLoading = value => loading.push(value);
            app.showToast = () => {};
            await app.forceRefreshCurrentPokemon();
            assert.deepEqual(calls, [
                '/api/pokemon/charizard-mega-x?refresh=1',
                '/api/pokemon/species/6?refresh=1',
                '/api/pokemon/evolution-chain/2?refresh=1',
            ]);
            assert.deepEqual(displayed, [[pokemon, species, evolution]]);
            assert.deepEqual(loading, [true, false]);
            assert.equal((source.match(/async forceRefreshCurrentPokemon\(/g) || []).length, 1);
            assert.equal(typeof view.clearCache, 'undefined');
            assert.ok(!source.includes('/api/cache/invalidate'));
        });

        test('a failed refresh reports the error and does not display success', async () => {
            const { view } = createView({
                console: { error() {} },
                fetch: async () => ({ ok: false, json: async () => ({ error: 'Persistence failed' }) }),
            });
            const app = Object.create(view);
            const notifications = [];
            app.currentPokemonName = 'pikachu';
            app.detailView = { display: () => assert.fail('Failed refresh must not replace the view') };
            app.setLoading = () => {};
            app.showToast = (...args) => notifications.push(args);
            await app.forceRefreshCurrentPokemon();
            assert.deepEqual(notifications, [['Refresh Failed', 'Persistence failed', 'error']]);
        });

        test('footer TCG refresh preserves set selection even without a current Pokemon', async () => {
            const { view } = createView();
            const app = Object.create(view);
            app.currentTcgData = { set_id: 'base1' };
            const calls = [];
            app.tcgGallery = { forceRefresh: async data => calls.push(data) };
            await app.forceRefreshTcgCards();
            assert.deepEqual(calls, [app.currentTcgData]);
        });

        test('gallery refresh forwards all filters and force_refresh without JSON invalidation', async () => {
            const gallerySource = readFileSync(new URL('../static/js/views/TcgCardsGalleryView.js', import.meta.url), 'utf8');
            const calls = [];
            const result = { cards: [{ id: 'base1-1' }] };
            const context = vm.createContext({
                console: { log() {} },
                fetch: async (url, options) => {
                    calls.push({ url, body: JSON.parse(options.body) });
                    return { ok: true, json: async () => ({ result }) };
                },
            });
            vm.runInContext(gallerySource, context);
            const gallery = Object.create(vm.runInContext('TcgCardsGalleryView.prototype', context));
            const displayed = [];
            gallery.app = { setLoading() {}, addMessage: () => assert.fail('Unexpected error') };
            gallery.display = data => displayed.push(data);
            await gallery.forceRefresh({ _search_params: { card_type: 'Water', hp_min: 100 } });
            assert.deepEqual(calls, [{
                url: '/api/realtime/tool',
                body: { tool_name: 'search_pokemon_cards', arguments: { card_type: 'Water', hp_min: 100, force_refresh: true } },
            }]);
            assert.deepEqual(displayed, [result]);
        });
