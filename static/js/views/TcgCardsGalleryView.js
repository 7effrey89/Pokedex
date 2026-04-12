/**
 * TCG Cards Gallery View - Displays a grid of Pokemon trading cards
 */
class TcgCardsGalleryView {
    constructor(app) {
        this.app = app;
        this.galleryView = document.getElementById('tcgCardsView');
        this._dexLookup = null;
    }

    display(tcgData) {
        console.log('🃏 displayTcgCardsInCanvas called with:', tcgData);
        
        if (!tcgData || !tcgData.cards || !Array.isArray(tcgData.cards) || tcgData.cards.length === 0) {
            console.error('❌ Invalid TCG data:', tcgData);
            return;
        }
        
        console.log('✅ Valid TCG data with', tcgData.cards.length, 'cards');
        
        // Store for forward navigation
        this.app.currentTcgData = tcgData;
        
        // Hide other views
        this.app.gridView.saveScrollPosition();
        if (this.app.tcgDatabase) this.app.tcgDatabase.saveScrollPosition();
        this.app.pokemonGridView.style.display = 'none';
        this.app.pokemonDetailView.style.display = 'none';
        if (this.app.tcgCardDetailView) this.app.tcgCardDetailView.style.display = 'none';
        if (this.app.tcgDatabaseViewEl) this.app.tcgDatabaseViewEl.style.display = 'none';
        
        // Show TCG cards view
        this.galleryView.style.display = 'block';
        
        this.renderCards(tcgData);
        
        // Update canvas state for TCG gallery
        const stateData = {
            pokemon_name: tcgData.search_query || tcgData.pokemon_name || 'Pokemon',
            cards: tcgData.cards,
            total_count: tcgData.total_count
        };
        if (tcgData.set_id) stateData.set_id = tcgData.set_id;
        this.app.updateCanvasState('tcg-gallery', stateData);
        
        // Scroll to top
        this.galleryView.scrollTop = 0;
        console.log('✅ TCG cards view updated and displayed');
    }

    displayWithoutHistory(tcgData) {
        console.log('🃏 displayTcgCardsInCanvasWithoutHistory called');
        
        if (!tcgData || !tcgData.cards || !Array.isArray(tcgData.cards) || tcgData.cards.length === 0) {
            return;
        }
        
        // Update canvas state for TCG gallery (without adding to history)
        const stateData = {
            pokemon_name: tcgData.search_query || tcgData.pokemon_name || 'Pokemon',
            cards: tcgData.cards,
            total_count: tcgData.total_count
        };
        if (tcgData.set_id) stateData.set_id = tcgData.set_id;
        this.app.updateCanvasState('tcg-gallery', stateData, false);
        
        // Hide other views
        this.app.gridView.saveScrollPosition();
        if (this.app.tcgDatabase) this.app.tcgDatabase.saveScrollPosition();
        this.app.pokemonGridView.style.display = 'none';
        this.app.pokemonDetailView.style.display = 'none';
        if (this.app.tcgCardDetailView) this.app.tcgCardDetailView.style.display = 'none';
        if (this.app.tcgDatabaseViewEl) this.app.tcgDatabaseViewEl.style.display = 'none';
        this.galleryView.style.display = 'block';
        
        this.renderCards(tcgData);
    }

    renderCards(tcgData) {
        // Clear existing content
        this.galleryView.innerHTML = '';
        
        // Store cards array for indexed access
        this.app.currentTcgCards = tcgData.cards;
        
        // Track current sort
        this.currentSort = this.currentSort || 'default';
        
        // Create header with sort controls
        const header = document.createElement('div');
        header.className = 'tcg-canvas-header';
        
        // Build subtitle for expansion browsing
        let subtitleHTML = '';
        if (tcgData.set_id && tcgData.cards.length > 0) {
            const setName = tcgData.search_query || tcgData.cards[0]?.set?.name || '';
            const releaseYear = this.getCardReleaseYear(tcgData.cards[0]);
            const yearStr = releaseYear ? ` (${releaseYear})` : '';
            subtitleHTML = `<p class="tcg-canvas-subtitle">${setName}${yearStr}</p>`;
        }
        
        header.innerHTML = `
            <div class="tcg-canvas-title">
                <h1>🃏 Trading Card Gallery</h1>
                ${subtitleHTML}
                <p>${tcgData.total_count || tcgData.cards.length} cards found</p>
            </div>
            <div class="tcg-sort-controls">
                <label for="tcg-sort-select">Sort by:</label>
                <select id="tcg-sort-select">
                    <option value="default"${this.currentSort === 'default' ? ' selected' : ''}>Default</option>
                    <option value="number"${this.currentSort === 'number' ? ' selected' : ''}>Card #</option>
                    <option value="dex-asc"${this.currentSort === 'dex-asc' ? ' selected' : ''}>Pokédex #</option>
                    <option value="name-asc"${this.currentSort === 'name-asc' ? ' selected' : ''}>Name: A → Z</option>
                    <option value="name-desc"${this.currentSort === 'name-desc' ? ' selected' : ''}>Name: Z → A</option>
                    <option value="rarity-desc"${this.currentSort === 'rarity-desc' ? ' selected' : ''}>Rarity: Rare First</option>
                    <option value="rarity-asc"${this.currentSort === 'rarity-asc' ? ' selected' : ''}>Rarity: Common First</option>
                    <option value="price-desc"${this.currentSort === 'price-desc' ? ' selected' : ''}>Price: High → Low</option>
                    <option value="price-asc"${this.currentSort === 'price-asc' ? ' selected' : ''}>Price: Low → High</option>
                    <option value="year-desc"${this.currentSort === 'year-desc' ? ' selected' : ''}>Year: Newest</option>
                    <option value="year-asc"${this.currentSort === 'year-asc' ? ' selected' : ''}>Year: Oldest</option>
                    <option value="set-asc"${this.currentSort === 'set-asc' ? ' selected' : ''}>Expansion: A → Z</option>
                    <option value="set-desc"${this.currentSort === 'set-desc' ? ' selected' : ''}>Expansion: Z → A</option>
                </select>
                <button id="tcg-refresh-btn" class="tcg-refresh-btn" title="Refresh cards from API">🔄</button>
            </div>
        `;
        this.galleryView.appendChild(header);
        
        // Attach sort listener
        const sortSelect = header.querySelector('#tcg-sort-select');
        sortSelect.addEventListener('change', () => {
            this.currentSort = sortSelect.value;
            this.renderCards(tcgData);
        });

        // Attach refresh listener
        const refreshBtn = header.querySelector('#tcg-refresh-btn');
        refreshBtn.addEventListener('click', () => {
            this.forceRefresh(tcgData);
        });
        
        // Sort cards
        const sortedCards = this.sortCards(tcgData.cards, this.currentSort);
        
        // Create cards grid
        const cardsGrid = document.createElement('div');
        cardsGrid.className = 'tcg-cards-grid';
        
        sortedCards.forEach((card, index) => {
            const cardDiv = this.createCardElement(card, index);
            cardsGrid.appendChild(cardDiv);
        });
        
        console.log('✅ Created', cardsGrid.children.length, 'card elements');
        this.galleryView.appendChild(cardsGrid);
        
        // Mark TCG gallery as viewed for current Pokemon
        if (this.app.currentPokemonName) {
            const pokemonId = this.app.allPokemons.find(p => p.name === this.app.currentPokemonName)?.id;
            if (pokemonId) {
                this.app.markPokemonViewed(pokemonId, 'tcg-gallery');
            }
        }
    }

    getCardAvgPrice(card) {
        const prices = card.tcgplayer?.prices;
        if (!prices) return null;
        // Collect all market prices across variants
        const markets = [];
        for (const variant of Object.values(prices)) {
            if (variant && typeof variant === 'object') {
                if (variant.market) markets.push(variant.market);
                else if (variant.mid) markets.push(variant.mid);
            }
        }
        if (markets.length === 0) return null;
        return markets.reduce((a, b) => a + b, 0) / markets.length;
    }

    getCardReleaseYear(card) {
        const dateStr = card.set?.releaseDate;
        if (!dateStr) return null;
        const year = parseInt(dateStr.substring(0, 4), 10);
        return isNaN(year) ? null : year;
    }

    sortCards(cards, sortBy) {
        const sorted = [...cards];
        switch (sortBy) {
            case 'number':
                sorted.sort((a, b) => (a.number || '').localeCompare(b.number || '', undefined, { numeric: true }));
                break;
            case 'dex-asc':
                sorted.sort((a, b) => {
                    const aPoke = a.supertype === 'Pokémon';
                    const bPoke = b.supertype === 'Pokémon';
                    if (aPoke && bPoke) return this._getCardDexNumber(a) - this._getCardDexNumber(b);
                    if (aPoke && !bPoke) return -1;
                    if (!aPoke && bPoke) return 1;
                    return (a.name || '').localeCompare(b.name || '');
                });
                break;
            case 'name-asc':
                sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
                break;
            case 'name-desc':
                sorted.sort((a, b) => (b.name || '').localeCompare(a.name || ''));
                break;
            case 'rarity-desc':
                sorted.sort((a, b) => this._getRarityRank(b.rarity) - this._getRarityRank(a.rarity));
                break;
            case 'rarity-asc':
                sorted.sort((a, b) => this._getRarityRank(a.rarity) - this._getRarityRank(b.rarity));
                break;
            case 'price-desc':
                sorted.sort((a, b) => (this.getCardAvgPrice(b) || 0) - (this.getCardAvgPrice(a) || 0));
                break;
            case 'price-asc':
                sorted.sort((a, b) => (this.getCardAvgPrice(a) || 0) - (this.getCardAvgPrice(b) || 0));
                break;
            case 'year-desc':
                sorted.sort((a, b) => (this.getCardReleaseYear(b) || 0) - (this.getCardReleaseYear(a) || 0));
                break;
            case 'year-asc':
                sorted.sort((a, b) => (this.getCardReleaseYear(a) || 0) - (this.getCardReleaseYear(b) || 0));
                break;
            case 'set-asc':
                sorted.sort((a, b) => (a.set?.name || '').localeCompare(b.set?.name || ''));
                break;
            case 'set-desc':
                sorted.sort((a, b) => (b.set?.name || '').localeCompare(a.set?.name || ''));
                break;
            default: // 'default' — original order
                break;
        }
        return sorted;
    }

    _getCardDexNumber(card) {
        const dex = card.nationalPokedexNumbers;
        if (dex && dex.length > 0) return dex[0];
        // Fallback: reuse database view's lookup or load our own
        const lookup = this._dexLookup || this.app.tcgDatabase?._dexLookup;
        if (lookup && card.supertype === 'Pokémon') {
            const baseName = (card.name || '').toLowerCase()
                .replace(/\s+(ex|gx|vmax|vstar|v|lv\.\s*x|prime|break|δ)$/i, '')
                .replace(/[\s-]+/g, '-').trim();
            const dexNum = lookup.get(baseName);
            if (dexNum) return dexNum;
        }
        return card.supertype === 'Pokémon' ? 99999 : Infinity;
    }

    _getRarityRank(rarity) {
        const order = {
            'Common': 1, 'Uncommon': 2, 'Rare': 3, 'Rare Holo': 4,
            'Promo': 5, 'Double Rare': 6, 'Rare Holo EX': 7, 'Rare Holo GX': 8,
            'Rare Holo V': 9, 'Rare Holo VMAX': 10, 'Rare Holo VSTAR': 11,
            'Ultra Rare': 12, 'Rare Ultra': 12, 'Illustration Rare': 13,
            'Special Illustration Rare': 14, 'Rare Rainbow': 15,
            'Rare Secret': 16, 'Hyper Rare': 17, 'Shiny Rare': 18,
            'Shiny Ultra Rare': 19, 'Rare Shiny': 18, 'Rare Shiny GX': 19,
            'ACE SPEC Rare': 15, 'Rare ACE': 15, 'Radiant Rare': 13,
            'Amazing Rare': 13, 'Rare BREAK': 7, 'Rare Holo LV.X': 8,
            'Rare Prime': 8, 'Rare Prism Star': 9, 'Rare Holo Star': 16,
            'Rare Shining': 16, 'LEGEND': 17, 'Classic Collection': 14,
        };
        return order[rarity] || 10;
    }

    getSetId(card) {
        // Direct set.id (new format)
        if (card.set?.id) return card.set.id;
        // Extract from card ID (format: "setid-number", e.g. "det1-10")
        if (card.id && card.id.includes('-')) {
            return card.id.substring(0, card.id.lastIndexOf('-'));
        }
        // Extract from logo/symbol URL (e.g. "https://images.pokemontcg.io/det1/logo.png")
        const url = card.set?.logo || card.set?.symbol || '';
        const match = url.match(/pokemontcg\.io\/([^/]+)\//);
        if (match) return match[1];
        return '';
    }

    createCardElement(card, index) {
        const cardDiv = document.createElement('div');
        cardDiv.className = 'tcg-card-item';
        cardDiv.style.position = 'relative';
        
        const imageUrl = card.images?.small || card.imageSmall || card.images?.large || card.image;
        const cardName = card.name || 'Unknown';
        const setInfo = card.set?.name || card.set || '';
        const setId = this.getSetId(card);
        const releaseYear = this.getCardReleaseYear(card);
        const avgPrice = this.getCardAvgPrice(card);

        const cc = typeof CurrencyConverter !== 'undefined' ? CurrencyConverter : null;
        const priceDisplay = avgPrice !== null
            ? (cc ? cc.formatUSD(avgPrice) : `$${avgPrice.toFixed(2)}`)
            : 'N/A';
        const priceColor = avgPrice !== null && cc ? cc.getPriceColor(avgPrice) : '';
        const priceStyle = priceColor ? ` style="color:${priceColor}"` : '';

        const setLink = setId
            ? `<a href="#" class="tcg-set-link" data-set-id="${setId}" data-set-name="${setInfo}">${setInfo}</a>`
            : setInfo;
        
        cardDiv.innerHTML = `
            <div class="card-index-badge">#${index + 1}</div>
            <img src="${imageUrl}" alt="${cardName}" loading="lazy">
            <div class="tcg-card-info">
                <h3>${cardName}</h3>
                ${setInfo ? `<p class="tcg-card-set">${setLink}${releaseYear ? ` (${releaseYear})` : ''}</p>` : ''}
                <p class="tcg-card-price-tag">Avg: <span class="${avgPrice !== null ? 'has-price' : 'no-price'}"${priceStyle}>${priceDisplay}</span></p>
            </div>
        `;
        
        // Card image click → detail view
        const img = cardDiv.querySelector('img');
        img.addEventListener('click', () => {
            this.app.tcgDetail.show(card);
        });

        // Set link click → browse expansion
        const setLinkEl = cardDiv.querySelector('.tcg-set-link');
        if (setLinkEl) {
            setLinkEl.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.searchBySet(setLinkEl.dataset.setId, setLinkEl.dataset.setName);
            });
        }

        // Hover tracking for AI context
        const cardId = card.id || '';
        const hoverPriceStr = avgPrice !== null ? `, avg price ${priceDisplay}` : '';
        const hoverSummary = `TCG card #${index + 1}: "${cardName}" from ${setInfo || 'unknown set'}${hoverPriceStr} (card_id: ${cardId})`;
        cardDiv.addEventListener('mouseenter', () => {
            this.app.updateHoverContext('tcg-card', hoverSummary, cardId);
        });
        cardDiv.addEventListener('mouseleave', () => {
            this.app.clearHoverContext();
        });
        
        return cardDiv;
    }

    async searchBySet(setId, setName) {
        console.log(`🃏 Searching cards for set: ${setName} (${setId})`);
        this.app.setLoading(true);
        try {
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'search_cards_by_set',
                    arguments: { set_id: setId }
                })
            });

            if (!response.ok) throw new Error('Failed to search set cards');

            const data = await response.json();
            this.app.setLoading(false);

            if (data.result && data.result.cards && data.result.cards.length > 0) {
                this.currentSort = 'default';
                this.display(data.result);
            } else {
                this.app.addMessage('assistant', `No cards found for expansion "${setName}".`);
            }
        } catch (error) {
            console.error('❌ Error searching set:', error);
            this.app.setLoading(false);
            this.app.addMessage('assistant', `Error searching expansion "${setName}".`);
        }
    }

    async forceRefresh(tcgData) {
        console.log('🔄 Force refreshing TCG gallery');
        this.app.setLoading(true);
        try {
            // Determine tool + args based on whether this is a set browse or pokemon search
            const toolName = tcgData.set_id ? 'search_cards_by_set' : 'search_pokemon_cards';
            const args = tcgData.set_id
                ? { set_id: tcgData.set_id, force_refresh: true }
                : { pokemon_name: tcgData.search_query || tcgData.pokemon_name, force_refresh: true };

            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_name: toolName, arguments: args })
            });

            if (!response.ok) throw new Error('Failed to refresh cards');

            const data = await response.json();
            this.app.setLoading(false);

            if (data.result && data.result.cards && data.result.cards.length > 0) {
                this.currentSort = 'default';
                this.display(data.result);
                console.log('✅ Gallery refreshed with', data.result.cards.length, 'cards');
            } else {
                this.app.addMessage('assistant', 'Refresh returned no cards.');
            }
        } catch (error) {
            console.error('❌ Error refreshing gallery:', error);
            this.app.setLoading(false);
            this.app.addMessage('assistant', 'Error refreshing cards.');
        }
    }
}
