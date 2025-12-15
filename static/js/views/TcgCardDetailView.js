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
        
        // Mark TCG card detail as viewed for current Pokemon
        if (this.app.currentPokemonName) {
            const pokemonId = this.app.allPokemons.find(p => p.name === this.app.currentPokemonName)?.id;
            if (pokemonId) {
                this.app.markPokemonViewed(pokemonId, 'tcg-detail');
            }
        }
        
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
                    
                    ${this.buildSubtypeHeaderHTML(card)}
                    ${this.buildEvolvesFromHTML(card)}
                    ${this.buildHPTypesHTML(card)}
                    ${this.buildAbilitiesHTML(card)}
                    ${this.buildAttacksHTML(card)}
                    ${this.buildWeaknessResistanceRetreatHTML(card)}
                    ${this.buildRulesHTML(card)}
                    
                    <div class="tcg-card-metadata">
                        ${this.buildSetInfoHTML(card)}
                        ${this.buildArtistHTML(card)}
                        ${this.buildRegulationMarkHTML(card)}
                    </div>
                    
                    ${this.buildLegalitiesHTML(card)}
                    
                    <div class="tcg-card-prices">
                        ${pricesHTML}
                    </div>
                </div>
            </div>
        `;
        
        this.detailView.innerHTML = cardHTML;
        this.detailView.scrollTop = 0;
        
        // Attach event listener to evolves from link
        this.attachEvolvesFromListener();
    }

    attachEvolvesFromListener() {
        const evolvesLink = this.detailView.querySelector('.tcg-evolves-link');
        if (evolvesLink) {
            evolvesLink.addEventListener('click', async (e) => {
                e.preventDefault();
                const pokemonName = e.target.dataset.pokemon;
                if (pokemonName) {
                    await this.app.searchPokemon(pokemonName);
                }
            });
        }
    }

    buildSubtypeHeaderHTML(card) {
        if (!card.subtypes?.length) return '';
        return `
            <div class="tcg-card-subtype-header">
                <h3>${card.subtypes.join(' ')}</h3>
            </div>
        `;
    }

    buildEvolvesFromHTML(card) {
        if (!card.evolvesFrom) return '';
        return `
            <div class="tcg-card-evolves">
                <strong>Evolves From:</strong>
                <a href="#" class="tcg-evolves-link" data-pokemon="${card.evolvesFrom}">${card.evolvesFrom}</a>
            </div>
        `;
    }

    buildHPTypesHTML(card) {
        if (!card.hp && !card.types?.length) return '';
        return `
            <div class="tcg-card-hp-types">
                ${card.hp ? `<span class="tcg-hp">HP${card.hp}</span>` : ''}
                ${card.types ? card.types.map(t => this.getTypeIcon(t)).join('') : ''}
            </div>
        `;
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
                ${card.attacks.map(a => `
                    <div class="tcg-attack">
                        <div class="tcg-attack-header">
                            <div class="tcg-attack-cost">
                                ${this.buildAttackCostHTML(a.cost)}
                            </div>
                            <div class="tcg-attack-name-damage">
                                <strong>${a.name}</strong>
                                ${a.damage ? `<span class="tcg-attack-damage">${a.damage}</span>` : ''}
                            </div>
                        </div>
                        ${a.text ? `<p class="tcg-attack-text">${a.text}</p>` : ''}
                    </div>
                `).join('')}
            </div>
        `;
    }

    buildAttackCostHTML(cost) {
        if (!cost?.length) return '';
        return cost.map(type => this.getTypeIcon(type)).join('');
    }

    buildWeaknessResistanceRetreatHTML(card) {
        const hasWeakness = card.weaknesses?.length;
        const hasResistance = card.resistances?.length;
        const hasRetreat = card.retreatCost?.length;
        
        if (!hasWeakness && !hasResistance && !hasRetreat) return '';
        
        return `
            <div class="tcg-card-wr-retreat">
                ${hasWeakness ? `
                    <div class="tcg-wr-section">
                        <h4>Weakness</h4>
                        <div class="tcg-wr-values">
                            ${card.weaknesses.map(w => `
                                ${this.getTypeIcon(w.type)}<span class="tcg-multiplier">${w.value}</span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${hasResistance ? `
                    <div class="tcg-wr-section">
                        <h4>Resistance</h4>
                        <div class="tcg-wr-values">
                            ${card.resistances.map(r => `
                                ${this.getTypeIcon(r.type)}<span class="tcg-multiplier">${r.value}</span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${hasRetreat ? `
                    <div class="tcg-wr-section">
                        <h4>Retreat Cost</h4>
                        <div class="tcg-retreat-cost">
                            ${card.retreatCost.map(() => this.getTypeIcon('Colorless')).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    buildRulesHTML(card) {
        if (!card.rules?.length) return '';
        return `
            <div class="tcg-card-rules">
                ${card.rules.map(rule => `<p>${rule}</p>`).join('')}
            </div>
        `;
    }

    buildSetInfoHTML(card) {
        const setName = card.set?.name || card.set || 'Unknown Set';
        const setLogo = card.set?.images?.logo;
        return `
            <div class="tcg-card-set-info">
                <strong>${setName}</strong>
                <span class="tcg-card-number">${card.number}/${card.set?.total || '?'}</span>
                ${card.rarity ? `<span class="tcg-rarity-badge">${card.rarity}</span>` : ''}
                ${setLogo ? `<img src="${setLogo}" alt="${setName}" class="tcg-set-logo">` : ''}
            </div>
        `;
    }

    buildArtistHTML(card) {
        return card.artist ? `
            <p class="tcg-card-artist"><strong>Illustrator:</strong> ${card.artist}</p>
        ` : '';
    }

    buildRegulationMarkHTML(card) {
        return card.regulationMark ? `
            <p class="tcg-regulation-mark">Regulation Mark: ${card.regulationMark}</p>
        ` : '';
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

    getTypeIcon(type) {
        const typeIcons = {
            'Grass': 'grass_280.png',
            'Fire': 'fire_280.png',
            'Water': 'water_280.png',
            'Lightning': 'lightning_280.png',
            'Psychic': 'psychic_280.png',
            'Fighting': 'fighting_280.png',
            'Darkness': 'darkness_280.png',
            'Metal': 'metal_280.png',
            'Dragon': 'dragon_280.png',
            'Fairy': 'fairy_280.png',
            'Colorless': 'colorless_280.png'
        };
        const iconFile = typeIcons[type] || 'colorless_280.png';
        const iconPath = `/static/images/energy/${iconFile}`;
        return `<img src="${iconPath}" alt="${type}" class="energy-icon type-${type?.toLowerCase() || 'colorless'}" title="${type}">`;
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
