/**
 * TCG Card Detail View - Displays detailed information about a single trading card
 */
class TcgCardDetailView {
    constructor(app) {
        this.app = app;
        this.detailView = document.getElementById('tcgCardDetailView');
    }

    async show(card) {
        if (!this.detailView) return;
        
        // Store current card for navigation
        this.app.currentTcgCard = card;
        
        // Hide other views
        this.app.pokemonGridView.style.display = 'none';
        this.app.pokemonDetailView.style.display = 'none';
        this.app.tcgCardsView.style.display = 'none';
        this.detailView.style.display = 'block';
        
        // Update canvas state - automatic context injection and history management!
        this.app.updateCanvasState('tcg-detail', card);
        
        this.render(card);
    }
    
    async showWithoutHistory(card) {
        if (!this.detailView) return;
        
        // Store current card for navigation
        this.app.currentTcgCard = card;
        
        // Hide other views
        this.app.pokemonGridView.style.display = 'none';
        this.app.pokemonDetailView.style.display = 'none';
        this.app.tcgCardsView.style.display = 'none';
        this.detailView.style.display = 'block';
        
        // Update canvas state without adding to history
        this.app.updateCanvasState('tcg-detail', card, false);
        
        this.render(card);
    }

    render(card) {
        // Support both formats: card.images.large (raw API) and card.imageLarge/card.image (formatted)
        const largeImage = card.images?.large || card.imageLarge || card.images?.small || card.image;
        const setName = card.set?.name || card.set || 'Unknown Set';
        
        // Generate prices HTML
        const pricesHTML = this.buildPricesHTML(card);
        
        const cardHTML = `
            <div class="tcg-card-detail-content">
                <div class="tcg-card-image">
                    <img src="${largeImage}" alt="${card.name}">
                </div>
                <div class="tcg-card-info">
                    <h2>${card.name}</h2>
                    <p class="tcg-card-set">${setName} - ${card.number || ''}</p>
                    
                    ${this.buildTypesHTML(card)}
                    ${this.buildHPHTML(card)}
                    ${this.buildSubtypesHTML(card)}
                    ${this.buildAbilitiesHTML(card)}
                    ${this.buildAttacksHTML(card)}
                    ${this.buildRarityHTML(card)}
                    ${this.buildArtistHTML(card)}
                    ${this.buildLegalitiesHTML(card)}
                    
                    <div class="tcg-card-prices">
                        ${pricesHTML}
                    </div>
                </div>
            </div>
        `;
        
        this.detailView.innerHTML = cardHTML;
        this.detailView.scrollTop = 0;
    }

    buildTypesHTML(card) {
        if (!card.types) return '';
        return `
            <div class="tcg-card-types">
                ${card.types.map(t => `<span class="type-badge type-${t.toLowerCase()}">${t}</span>`).join('')}
            </div>
        `;
    }

    buildHPHTML(card) {
        return card.hp ? `<p class="tcg-card-hp">HP: ${card.hp}</p>` : '';
    }

    buildSubtypesHTML(card) {
        return card.subtypes?.length ? `<p class="tcg-card-subtypes">Subtypes: ${card.subtypes.join(', ')}</p>` : '';
    }

    buildAbilitiesHTML(card) {
        if (!card.abilities?.length) return '';
        return `
            <div class="tcg-card-abilities">
                <h3>Abilities</h3>
                ${card.abilities.map(a => `
                    <div class="tcg-ability">
                        <strong>${a.name}</strong>: ${a.text}
                    </div>
                `).join('')}
            </div>
        `;
    }

    buildAttacksHTML(card) {
        if (!card.attacks?.length) return '';
        return `
            <div class="tcg-card-attacks">
                <h3>Attacks</h3>
                ${card.attacks.map(a => `
                    <div class="tcg-attack">
                        <strong>${a.name}</strong> ${a.damage ? `- ${a.damage}` : ''}
                        ${a.text ? `<p>${a.text}</p>` : ''}
                    </div>
                `).join('')}
            </div>
        `;
    }

    buildRarityHTML(card) {
        return card.rarity ? `<p class="tcg-card-rarity">Rarity: ${card.rarity}</p>` : '';
    }

    buildArtistHTML(card) {
        return card.artist ? `<p class="tcg-card-artist">Artist: ${card.artist}</p>` : '';
    }

    buildLegalitiesHTML(card) {
        if (!card.legalities) return '';
        return `
            <div class="tcg-card-legalities">
                <h3>Format Legality</h3>
                <div class="legality-badges">
                    ${Object.entries(card.legalities).map(([format, status]) => `
                        <span class="legality-badge ${status.toLowerCase()}">${format}: ${status}</span>
                    `).join('')}
                </div>
            </div>
        `;
    }

    buildPricesHTML(card) {
        let pricesHTML = '<h3>Market Prices</h3>';
        
        // TCGPlayer prices
        if (card.tcgplayer?.prices) {
            pricesHTML += '<div class="price-section"><h4>💳 TCGPlayer</h4>';
            for (const [variant, prices] of Object.entries(card.tcgplayer.prices)) {
                if (typeof prices === 'object' && prices !== null) {
                    pricesHTML += `<div class="price-variant"><strong>${variant}:</strong><div class="price-list">`;
                    if (prices.low) pricesHTML += `<span class="price-item">Low: $${prices.low.toFixed(2)}</span>`;
                    if (prices.mid) pricesHTML += `<span class="price-item">Mid: $${prices.mid.toFixed(2)}</span>`;
                    if (prices.high) pricesHTML += `<span class="price-item">High: $${prices.high.toFixed(2)}</span>`;
                    if (prices.market) pricesHTML += `<span class="price-item price-market">Market: $${prices.market.toFixed(2)}</span>`;
                    pricesHTML += '</div></div>';
                }
            }
            pricesHTML += '</div>';
        }
        
        // Cardmarket prices
        if (card.cardmarket?.prices) {
            pricesHTML += '<div class="price-section"><h4>🇪🇺 Cardmarket</h4><div class="price-list">';
            const cm = card.cardmarket.prices;
            if (cm.averageSellPrice) pricesHTML += `<span class="price-item">Avg: €${cm.averageSellPrice.toFixed(2)}</span>`;
            if (cm.lowPrice) pricesHTML += `<span class="price-item">Low: €${cm.lowPrice.toFixed(2)}</span>`;
            if (cm.trendPrice) pricesHTML += `<span class="price-item price-market">Trend: €${cm.trendPrice.toFixed(2)}</span>`;
            pricesHTML += '</div></div>';
        }
        
        // If no prices available
        if (!card.tcgplayer?.prices && !card.cardmarket?.prices) {
            pricesHTML += '<p class="price-error">No price data available for this card</p>';
        }
        
        // Last updated
        if (card.tcgplayer?.updatedAt) {
            const date = new Date(card.tcgplayer.updatedAt);
            pricesHTML += `<p class="price-updated">Updated: ${date.toLocaleDateString()}</p>`;
        }
        
        return pricesHTML;
    }
}
