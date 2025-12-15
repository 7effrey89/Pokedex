/**
 * Pokemon Grid View - Displays the index page with all Pokemon
 */
class PokemonGridView {
    constructor(app) {
        this.app = app;
        this.gridView = document.getElementById('pokemonGridView');
        this.pokemonList = document.getElementById('pokemonList');
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
        this.app.updateCanvasState('grid', null, false);
    }

    async loadPokemonGrid() {
        if (this.app.allPokemons.length > 0) {
            return; // Already loaded
        }

        console.log('Loading Pokemon grid...');
        const promises = [];
        
        for (let i = 1; i <= this.app.MAX_POKEMON; i++) {
            promises.push(
                fetch(`https://pokeapi.co/api/v2/pokemon/${i}`)
                    .then(res => res.json())
                    .catch(err => {
                        console.error(`Failed to load Pokemon #${i}:`, err);
                        return null;
                    })
            );
        }

        const results = await Promise.all(promises);
        this.app.allPokemons = results.filter(p => p !== null);
        
        this.renderPokemonGrid();
    }

    renderPokemonGrid() {
        if (!this.pokemonList) return;

        this.pokemonList.innerHTML = '';
        
        this.app.allPokemons.forEach(pokemon => {
            const card = this.createPokemonCard(pokemon);
            this.pokemonList.appendChild(card);
        });
    }

    createPokemonCard(pokemon) {
        const card = document.createElement('div');
        card.className = 'list-item';
        card.onclick = () => this.app.detailView.loadPokemon(pokemon.id);

        const imageUrl = pokemon.sprites?.other?.['official-artwork']?.front_default || 
                        pokemon.sprites?.front_default || 
                        '';

        card.innerHTML = `
            <div class="number-wrap">#${String(pokemon.id).padStart(3, '0')}</div>
            <div class="img-wrap">
                <img src="${imageUrl}" alt="${pokemon.name}" loading="lazy">
            </div>
            <div class="name-wrap">${pokemon.name}</div>
        `;

        return card;
    }
}
