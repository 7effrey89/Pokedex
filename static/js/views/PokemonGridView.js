/**
 * Pokemon Grid View - Displays the index page with all Pokemon
 */
class PokemonGridView {
    constructor(app) {
        this.app = app;
        this.gridView = document.getElementById('pokemonGridView');
        this.pokemonList = document.getElementById('pokemonList');
        this._savedScrollTop = 0;
    }

    /** Save scroll position of main canvas before leaving grid */
    saveScrollPosition() {
        const canvas = document.getElementById('mainCanvas');
        if (canvas) {
            this._savedScrollTop = canvas.scrollTop;
        }
    }

    /** Restore saved scroll position on main canvas */
    restoreScrollPosition() {
        const canvas = document.getElementById('mainCanvas');
        if (canvas && this._savedScrollTop > 0) {
            // Use requestAnimationFrame to ensure DOM has updated
            requestAnimationFrame(() => { canvas.scrollTop = this._savedScrollTop; });
        }
    }

    async show() {
        this.app.pokemonDetailView.style.display = 'none';
        this.app.tcgCardsView.style.display = 'none';
        if (this.app.tcgCardDetailView) {
            this.app.tcgCardDetailView.style.display = 'none';
        }
        this.gridView.style.display = 'block';
        
        // Load Pokemon if not already loaded
        await this.loadPokemonGrid();
        
        // Restore scroll position
        this.restoreScrollPosition();
        
        // Update canvas state
        this.app.updateCanvasState('grid', null);
        
        // Add to history if not already there
        if (this.app.viewHistory[this.app.currentViewIndex] !== 'grid') {
            this.app.currentViewIndex++;
            this.app.viewHistory = this.app.viewHistory.slice(0, this.app.currentViewIndex);
            this.app.viewHistory.push('grid');
        }
    }
    
    showWithoutHistory() {
        this.app.pokemonDetailView.style.display = 'none';
        this.app.tcgCardsView.style.display = 'none';
        if (this.app.tcgCardDetailView) {
            this.app.tcgCardDetailView.style.display = 'none';
        }
        this.gridView.style.display = 'block';
        
        // Restore scroll position
        this.restoreScrollPosition();
        
        this.app.updateCanvasState('grid', null, false);
    }

    async loadPokemonGrid() {
        if (this.app.allPokemons.length > 0) {
            return; // Already loaded
        }

        console.log('Loading Pokemon grid...');
        try {
            const response = await fetch('/api/pokemon/list');
            if (!response.ok) {
                throw new Error('Failed to load Pokemon list');
            }
            const list = await response.json();
            this.app.allPokemons = list.map(entry => ({
                id: entry.number,
                name: entry.name,
            }));
            this.renderPokemonGrid();
        } catch (error) {
            console.error('Failed to load Pokemon list:', error);
            if (this.pokemonList) {
                this.pokemonList.innerHTML = '<div class="error-state">Unable to load Pokémon. Please refresh.</div>';
            }
        }
    }

    renderPokemonGrid() {
        if (!this.pokemonList) return;

        this.pokemonList.innerHTML = '';
        
        let currentGen = 0;
        
        this.app.allPokemons.forEach(pokemon => {
            // Check if we need to add a generation separator
            const genIndex = this.app.generations.findIndex(gen => 
                pokemon.id >= gen.start && pokemon.id <= gen.end
            );
            
            if (genIndex !== -1 && genIndex !== currentGen) {
                currentGen = genIndex;
                const separator = this.createGenerationSeparator(this.app.generations[genIndex]);
                this.pokemonList.appendChild(separator);
            }
            
            const card = this.createPokemonCard(pokemon);
            this.pokemonList.appendChild(card);
        });
    }
    
    createGenerationSeparator(generation) {
        const separator = document.createElement('div');
        separator.className = 'generation-separator';
        separator.innerHTML = `
            <div class="generation-line"></div>
            <div class="generation-label">${generation.name}</div>
            <div class="generation-line"></div>
        `;
        return separator;
    }

    createPokemonCard(pokemon) {
        const card = document.createElement('div');
        card.className = 'list-item';
        card.onclick = () => this.app.detailView.loadPokemon(pokemon.id);
        card.style.position = 'relative';

        const imageUrl = this.getArtworkUrl(pokemon.id);
        
        // Get viewing badge
        const badge = this.app.getViewingBadge(pokemon.id);
        const badgeHtml = badge ? `<div class="viewing-status-badge">${badge}</div>` : '';

        card.innerHTML = `
            ${badgeHtml}
            <div class="number-wrap">#${String(pokemon.id).padStart(3, '0')}</div>
            <div class="img-wrap">
                <img src="${imageUrl}" alt="${pokemon.name}" loading="lazy">
            </div>
            <div class="name-wrap">${pokemon.name}</div>
        `;

        return card;
    }

    getArtworkUrl(pokemonId) {
        return `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${pokemonId}.png`;
    }
}
