import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function view(name) {
    const context = vm.createContext({});
    vm.runInContext(readFileSync(new URL(`../static/js/views/${name}.js`, import.meta.url), 'utf8'), context);
    return vm.runInContext(`${name}.prototype`, context);
}

test('gallery averages TCGdex variants and does not confuse zero or missing prices', () => {
    const gallery = view('TcgCardsGalleryView');
    assert.ok(Math.abs(gallery.getCardAvgPrice({ tcgplayer: { prices: {
        normal: { market: 0.07 }, reverseHolofoil: { market: 0.17 },
    } } }) - 0.12) < 1e-12);
    assert.equal(gallery.getCardAvgPrice({ tcgplayer: { prices: { normal: { market: 0, mid: 5 } } } }), 0);
    assert.equal(gallery.getCardAvgPrice({ tcgplayer: { prices: { normal: { market: null } } } }), null);
});

test('card detail shows valid zero amounts and an explicit unavailable message', () => {
    const detail = view('TcgCardDetailView');
    const priced = detail.buildPricesHTML({ tcgplayer: { prices: { normal: { market: 0, low: 0 } } } });
    assert.ok(priced.includes('Market: $0.00'));
    assert.ok(priced.includes('Low: $0.00'));
    const unavailable = detail.buildPricesHTML({ tcgplayer: { prices: {} }, cardmarket: { prices: {} } });
    assert.ok(unavailable.includes('No price data available'));
    assert.ok(!unavailable.includes('price-section'));
});
