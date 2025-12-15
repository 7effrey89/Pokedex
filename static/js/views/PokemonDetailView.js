/**
 * Pokemon Detail View - Displays detailed information about a specific Pokemon
 */
class PokemonDetailView {
    constructor(app) {
        this.app = app;
        this.detailView = document.getElementById('pokemonDetailView');
    }

    async loadPokemon(id) {
        try {
            const [pokemonResponse, speciesResponse] = await Promise.all([
                fetch(`https://pokeapi.co/api/v2/pokemon/${id}`),
                fetch(`https://pokeapi.co/api/v2/pokemon-species/${id}`)
            ]);

            const pokemon = await pokemonResponse.json();
            const species = await speciesResponse.json();

            this.display(pokemon, species);
        } catch (error) {
            console.error('Error loading Pokemon:', error);
        }
    }

    async loadPokemonWithoutHistory(id) {
        try {
            const [pokemonResponse, speciesResponse] = await Promise.all([
                fetch(`https://pokeapi.co/api/v2/pokemon/${id}`),
                fetch(`https://pokeapi.co/api/v2/pokemon-species/${id}`)
            ]);

            const pokemon = await pokemonResponse.json();
            const species = await speciesResponse.json();

            // Defensive checks
            if (!this.detailView || !this.app.pokemonGridView) {
                console.error('Pokemon detail view or grid view not found');
                return;
            }
            
            if (!pokemon || !pokemon.types || !pokemon.types[0]) {
                console.error('Invalid pokemon data:', pokemon);
                return;
            }

            // Hide grid, show detail view (without adding to history)
            this.app.pokemonGridView.style.display = 'none';
            this.detailView.style.display = 'block';
            
            // Update canvas state with Pokemon data (without adding to history)
            this.app.updateCanvasState('pokemon', { pokemon, species }, false);
            
            // Update the display
            this.updateDisplay(pokemon, species);
        } catch (error) {
            console.error('Error loading Pokemon:', error);
        }
    }

    display(pokemon, species) {
        // Defensive checks
        if (!this.detailView || !this.app.pokemonGridView) {
            console.error('Pokemon detail view or grid view not found');
            return;
        }
        
        if (!pokemon || !pokemon.types || !pokemon.types[0]) {
            console.error('Invalid pokemon data:', pokemon);
            return;
        }
        
        // Hide grid, show detail view
        this.app.pokemonGridView.style.display = 'none';
        this.detailView.style.display = 'block';
        
        // Store current Pokemon name for card searches
        this.app.currentPokemonName = pokemon.name;
        
        // Mark Pokemon as viewed
        this.app.markPokemonViewed(pokemon.id, 'detail');

        // Update canvas state with Pokemon data (automatically adds to history)
        this.app.updateCanvasState('pokemon', { pokemon, species });

        this.updateDisplay(pokemon, species);
    }

    updateDisplay(pokemon, species) {
        // Set background color based on primary type
        const primaryType = pokemon.types[0].type.name;
        this.detailView.className = 'pokemon-detail-view';
        this.detailView.classList.add(`bg-${primaryType}`);

        // Update name and ID
        const nameEl = this.detailView.querySelector('.pokemon-name');
        const idEl = this.detailView.querySelector('.pokemon-id');
        nameEl.textContent = pokemon.name;
        idEl.textContent = `#${String(pokemon.id).padStart(3, '0')}`;

        // Update image
        const imageEl = this.detailView.querySelector('.pokemon-main-image');
        const imageUrl = pokemon.sprites?.other?.['official-artwork']?.front_default || 
                        pokemon.sprites?.front_default || 
                        '';
        if (imageUrl) {
            imageEl.src = imageUrl;
            imageEl.alt = pokemon.name;
        }

        // Update types
        const typesContainer = this.detailView.querySelector('.pokemon-types');
        if (typesContainer) {
            typesContainer.innerHTML = pokemon.types.map(t => 
                `<span class="type-badge type-${t.type.name}">${t.type.name}</span>`
            ).join('');
        }

        // Update about section
        this.updateAboutSection(pokemon, species);
        
        // Update base stats
        this.updateBaseStats(pokemon);
    }

    updateAboutSection(pokemon, species) {
        const weightEl = this.detailView.querySelector('.pokemon-weight');
        const heightEl = this.detailView.querySelector('.pokemon-height');
        const abilitiesEl = this.detailView.querySelector('.pokemon-abilities-list');
        
        if (weightEl) {
            weightEl.textContent = `${(pokemon.weight / 10).toFixed(1)} kg`;
        }
        
        if (heightEl) {
            heightEl.textContent = `${(pokemon.height / 10).toFixed(1)} m`;
        }
        
        if (abilitiesEl && pokemon.abilities) {
            const abilities = pokemon.abilities.map(a => {
                const name = a.ability.name.split('-').map(word => 
                    word.charAt(0).toUpperCase() + word.slice(1)
                ).join(' ');
                return `<span class="ability-badge">${name}</span>`;
            }).join('');
            abilitiesEl.innerHTML = abilities;
        }
        
        // Update description
        const descEl = this.detailView.querySelector('.pokemon-description');
        if (descEl && species && species.flavor_text_entries) {
            const flavorText = species.flavor_text_entries.find(entry => entry.language.name === 'en');
            if (flavorText) {
                descEl.textContent = flavorText.flavor_text.replace(/\f/g, ' ').replace(/\s+/g, ' ').trim();
            }
        }
    }

    updateBaseStats(pokemon) {
        if (!pokemon.stats) return;
        
        const statsContainer = this.detailView.querySelector('.pokemon-stats');
        if (!statsContainer) return;
        
        // Clear existing stats
        statsContainer.innerHTML = '';
        
        // Stat name mapping for better display
        const statNames = {
            'hp': 'HP',
            'attack': 'Attack',
            'defense': 'Defense',
            'special-attack': 'Sp. Atk',
            'special-defense': 'Sp. Def',
            'speed': 'Speed'
        };
        
        pokemon.stats.forEach(stat => {
            const statName = stat.stat.name;
            const statValue = stat.base_stat;
            const displayName = statNames[statName] || statName;
            
            const statRow = document.createElement('div');
            statRow.className = 'stat-row';
            
            const percentage = Math.min((statValue / 255) * 100, 100);
            
            statRow.innerHTML = `
                <div class="stat-name">${displayName}</div>
                <div class="stat-value">${statValue}</div>
                <div class="stat-bar-container">
                    <div class="stat-bar" style="width: ${percentage}%; background: linear-gradient(to right, #ff6b6b, #4ecdc4);"></div>
                </div>
            `;
            
            statsContainer.appendChild(statRow);
        });
    }
}
