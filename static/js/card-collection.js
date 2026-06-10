class CardCollectionStore {
    constructor(storageKey = 'pokedex_card_collection_v1') {
        this.storageKey = storageKey;
        this.listeners = new Set();
        this.state = this._loadState();
    }

    _createDefaultState() {
        return {
            version: 1,
            cards: {},
            history: [],
            updatedAt: new Date().toISOString()
        };
    }

    _loadState() {
        if (typeof localStorage === 'undefined') {
            return this._createDefaultState();
        }

        try {
            const raw = localStorage.getItem(this.storageKey);
            if (!raw) return this._createDefaultState();
            const parsed = JSON.parse(raw);
            return this._normalizeState(parsed);
        } catch (error) {
            console.warn('Unable to load stored card collection:', error);
            return this._createDefaultState();
        }
    }

    _normalizeState(state) {
        const normalized = this._createDefaultState();
        const sourceCards = state?.cards && typeof state.cards === 'object' ? state.cards : {};
        for (const [cardId, entry] of Object.entries(sourceCards)) {
            const count = Number(entry?.count || 0);
            if (count <= 0) continue;
            normalized.cards[cardId] = {
                card: this._normalizeCard(entry.card || {}),
                count,
                updatedAt: entry.updatedAt || new Date().toISOString()
            };
        }

        const sourceHistory = Array.isArray(state?.history) ? state.history : [];
        normalized.history = sourceHistory
            .filter(entry => entry?.id && entry?.cardId)
            .map(entry => ({
                id: entry.id,
                cardId: entry.cardId,
                countChange: Number(entry.countChange || 1),
                label: entry.label || entry.cardName || 'Unknown card',
                cardName: entry.cardName || 'Unknown card',
                setName: entry.setName || '',
                image: entry.image || '',
                source: entry.source || 'scanner',
                createdAt: entry.createdAt || new Date().toISOString()
            }))
            .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));

        normalized.updatedAt = state?.updatedAt || new Date().toISOString();
        return normalized;
    }

    _normalizeCard(card) {
        const set = card?.set || {};
        const images = card?.images || {};
        return {
            id: card?.id || '',
            name: card?.name || 'Unknown',
            number: card?.number || '',
            hp: card?.hp || '',
            rarity: card?.rarity || '',
            supertype: card?.supertype || '',
            subtypes: Array.isArray(card?.subtypes) ? [...card.subtypes] : [],
            types: Array.isArray(card?.types) ? [...card.types] : [],
            nationalPokedexNumbers: Array.isArray(card?.nationalPokedexNumbers) ? [...card.nationalPokedexNumbers] : [],
            set: {
                id: set?.id || '',
                name: set?.name || '',
                series: set?.series || '',
                releaseDate: set?.releaseDate || '',
                total: set?.total || null,
                images: set?.images || {},
                logo: set?.logo || set?.images?.logo || '',
                symbol: set?.symbol || set?.images?.symbol || ''
            },
            images: {
                small: images?.small || card?.imageSmall || '',
                large: images?.large || ''
            },
            imageSmall: card?.imageSmall || images?.small || '',
            tcgplayer: card?.tcgplayer || {},
            prices: card?.prices || {}
        };
    }

    _persist() {
        this.state.updatedAt = new Date().toISOString();
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem(this.storageKey, JSON.stringify(this.state));
        }
        this._emit();
    }

    _emit() {
        const snapshot = this.getState();
        this.listeners.forEach(listener => {
            try {
                listener(snapshot);
            } catch (error) {
                console.warn('Card collection listener failed:', error);
            }
        });
    }

    subscribe(listener) {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    }

    getState() {
        return JSON.parse(JSON.stringify(this.state));
    }

    getCardCount(cardId) {
        return Number(this.state.cards?.[cardId]?.count || 0);
    }

    getOwnedCards() {
        return Object.values(this.state.cards)
            .filter(entry => Number(entry.count) > 0)
            .map(entry => ({
                ...JSON.parse(JSON.stringify(entry.card)),
                _collectionCount: Number(entry.count)
            }));
    }

    getHistory() {
        return this.state.history.map(entry => ({ ...entry }));
    }

    setCardCount(card, count) {
        const normalizedCount = Math.max(0, Number(count) || 0);
        const cardId = card?.id;
        if (!cardId) return 0;

        if (normalizedCount <= 0) {
            delete this.state.cards[cardId];
        } else {
            this.state.cards[cardId] = {
                card: this._normalizeCard(card),
                count: normalizedCount,
                updatedAt: new Date().toISOString()
            };
        }

        this._persist();
        return normalizedCount;
    }

    recordScan(card, { countChange = 1, source = 'scanner' } = {}) {
        const cardId = card?.id;
        if (!cardId) return 0;

        const nextCount = this.getCardCount(cardId) + Math.max(1, Number(countChange) || 1);
        this.state.cards[cardId] = {
            card: this._normalizeCard(card),
            count: nextCount,
            updatedAt: new Date().toISOString()
        };

        this.state.history.unshift({
            id: `scan-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            cardId,
            countChange: Math.max(1, Number(countChange) || 1),
            label: this.buildCardLabel(card),
            cardName: card?.name || 'Unknown',
            setName: card?.set?.name || '',
            image: card?.images?.small || card?.imageSmall || '',
            source,
            createdAt: new Date().toISOString()
        });

        this.state.history = this.state.history.slice(0, 100);
        this._persist();
        return nextCount;
    }

    removeHistoryEntry(entryId) {
        const index = this.state.history.findIndex(entry => entry.id === entryId);
        if (index === -1) return false;

        const [entry] = this.state.history.splice(index, 1);
        const currentCount = this.getCardCount(entry.cardId);
        const nextCount = Math.max(0, currentCount - Math.max(1, Number(entry.countChange) || 1));

        if (nextCount <= 0) {
            delete this.state.cards[entry.cardId];
        } else if (this.state.cards[entry.cardId]) {
            this.state.cards[entry.cardId].count = nextCount;
            this.state.cards[entry.cardId].updatedAt = new Date().toISOString();
        }

        this._persist();
        return true;
    }

    clear() {
        this.state = this._createDefaultState();
        this._persist();
    }

    exportState() {
        return JSON.stringify(this.getState(), null, 2);
    }

    importState(raw) {
        const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
        this.state = this._normalizeState(parsed);
        this._persist();
        return this.getState();
    }

    buildCardLabel(card) {
        if (!card) return 'Unknown card';
        const pieces = [card.name || 'Unknown'];
        if (card.set?.name) pieces.push(card.set.name);
        if (card.number) pieces.push(`#${card.number}`);
        return pieces.join(' · ');
    }
}

window.CardCollectionStore = CardCollectionStore;
