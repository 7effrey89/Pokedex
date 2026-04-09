/**
 * Pokemon Detail View - Displays detailed information about a specific Pokemon
 */
class PokemonDetailView {
    constructor(app) {
        this.app = app;
        this.detailView = document.getElementById('pokemonDetailView');
        this.lastCryPokemonId = null;
        this.currentCryAudio = null;
        this.setupNavigationArrows();
    }

    getSpriteUrl(pokemon) {
        const style = this.app.spriteStyle || 'official-artwork';
        const sprites = pokemon.sprites;
        if (!sprites) return this.app.gridView.getArtworkUrl(pokemon.id);
        switch (style) {
            case 'home':
                return sprites.other?.home?.front_default || sprites.other?.['official-artwork']?.front_default || sprites.front_default;
            case 'dream-world':
                return sprites.other?.dream_world?.front_default || sprites.other?.['official-artwork']?.front_default || sprites.front_default;
            case 'showdown':
                return sprites.other?.showdown?.front_default || sprites.front_default;
            case 'default':
                return sprites.front_default;
            default:
                return sprites.other?.['official-artwork']?.front_default || sprites.front_default;
        }
    }

    stopPokemonCry() {
        if (this.currentCryAudio) {
            this.currentCryAudio.pause();
            this.currentCryAudio.currentTime = 0;
        }
    }

    playPokemonCry(pokemon) {
        if (!this.app.criesEnabled) return;
        if (!pokemon || !pokemon.cries) return;
        if (pokemon.id === this.lastCryPokemonId) return;

        const cryUrl = pokemon.cries.latest || pokemon.cries.legacy;
        if (!cryUrl) return;

        this.lastCryPokemonId = pokemon.id;
        this.stopPokemonCry();

        const audio = new Audio(cryUrl);
        audio.volume = 0.6;
        audio.play().catch(() => {});
        this.currentCryAudio = audio;
    }

    async fetchPokemonResource(resource, identifier, mode = 'auto') {
        const options = mode === 'auto' ? {} : { mode };
        const url = this.app.buildPokemonApiUrl(resource, identifier, options);
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to load ${resource} (${response.status})`);
        }
        const data = await response.json();
        const isStale = response.headers.get('X-PokeAPI-Stale') === 'true';
        return { data, isStale };
    }

    async fetchResourceWithFallback(resource, identifier) {
        if (!this.app.cacheConfig) {
            await this.app.loadCacheConfig();
        }

        if (this.app.shouldUsePokemonProxy()) {
            return this.fetchPokemonResource(resource, identifier, 'proxy');
        }
        try {
            return await this.fetchPokemonResource(resource, identifier, 'direct');
        } catch (error) {
            console.warn(`Direct ${resource} fetch failed, falling back to proxy`, error);
            return this.fetchPokemonResource(resource, identifier, 'proxy');
        }
    }

    /**
     * Revalidate a stale resource in the background.
     * Fetches with ?refresh=1 and returns the fresh data.
     */
    async _revalidateResource(resource, identifier) {
        const options = { mode: 'proxy' };
        const url = this.app.buildPokemonApiUrl(resource, identifier, options) + '?refresh=1';
        const response = await fetch(url);
        if (!response.ok) return null;
        return response.json();
    }

    setupNavigationArrows() {
        const prevBtn = document.getElementById('pokemonNavPrev');
        const nextBtn = document.getElementById('pokemonNavNext');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.navigateToPreviousPokemon());
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.navigateToNextPokemon());
        }
    }

    updateNavigationPreviews(currentId) {
        const prevBtn = document.getElementById('pokemonNavPrev');
        const nextBtn = document.getElementById('pokemonNavNext');
        
        // Update previous Pokemon preview
        if (prevBtn && currentId > 1) {
            const prevPokemon = this.app.allPokemons.find(p => p.id === currentId - 1);
            if (prevPokemon) {
                prevBtn.style.display = 'block';
                const img = prevBtn.querySelector('.nav-preview-image');
                const name = prevBtn.querySelector('.nav-preview-name');
                const number = prevBtn.querySelector('.nav-preview-number');
                img.src = this.app.gridView.getArtworkUrl(prevPokemon.id);
                name.textContent = prevPokemon.name;
                number.textContent = `#${String(prevPokemon.id).padStart(3, '0')}`;
            }
        } else if (prevBtn) {
            prevBtn.style.display = 'none';
        }
        
        // Update next Pokemon preview
        if (nextBtn && currentId < this.app.allPokemons.length) {
            const nextPokemon = this.app.allPokemons.find(p => p.id === currentId + 1);
            if (nextPokemon) {
                nextBtn.style.display = 'block';
                const img = nextBtn.querySelector('.nav-preview-image');
                const name = nextBtn.querySelector('.nav-preview-name');
                const number = nextBtn.querySelector('.nav-preview-number');
                img.src = this.app.gridView.getArtworkUrl(nextPokemon.id);
                name.textContent = nextPokemon.name;
                number.textContent = `#${String(nextPokemon.id).padStart(3, '0')}`;
            }
        } else if (nextBtn) {
            nextBtn.style.display = 'none';
        }
    }

    async navigateToPreviousPokemon() {
        const currentId = this.app.currentPokemonName ? 
            this.app.allPokemons.find(p => p.name === this.app.currentPokemonName)?.id : null;
        
        if (currentId && currentId > 1) {
            await this.loadPokemon(currentId - 1);
        }
    }

    async navigateToNextPokemon() {
        const currentId = this.app.currentPokemonName ? 
            this.app.allPokemons.find(p => p.name === this.app.currentPokemonName)?.id : null;
        
        if (currentId && currentId < this.app.allPokemons.length) {
            await this.loadPokemon(currentId + 1);
        }
    }

    async loadPokemon(identifier) {
        try {
            const [pokemonResult, speciesResult] = await Promise.all([
                this.fetchResourceWithFallback('pokemon', identifier),
                this.fetchResourceWithFallback('species', identifier)
            ]);

            const pokemon = pokemonResult.data;
            const species = speciesResult.data;
            const anyStale = pokemonResult.isStale || speciesResult.isStale;

            // Fetch evolution chain if available
            let evolutionChain = null;
            let evolutionStale = false;
            if (species.evolution_chain && species.evolution_chain.url) {
                const chainId = species.evolution_chain.url.split('/').filter(Boolean).pop();
                const evoResult = await this.fetchResourceWithFallback('evolution', chainId);
                evolutionChain = evoResult.data;
                evolutionStale = evoResult.isStale;
            }

            this.display(pokemon, species, evolutionChain);

            // Stale-while-revalidate: refresh in background, re-render if data changed
            if (anyStale || evolutionStale) {
                this._revalidateAndRerender(identifier, pokemon, species, evolutionChain,
                    pokemonResult.isStale, speciesResult.isStale, evolutionStale);
            }
        } catch (error) {
            console.error('Error loading Pokemon:', error);
        }
    }

    async _revalidateAndRerender(identifier, oldPokemon, oldSpecies, oldEvolution,
                                  pokemonStale, speciesStale, evolutionStale) {
        console.log(`🔄 Revalidating stale cache for: ${identifier}`);
        try {
            const promises = [];
            promises.push(pokemonStale
                ? this._revalidateResource('pokemon', identifier)
                : Promise.resolve(null));
            promises.push(speciesStale
                ? this._revalidateResource('species', identifier)
                : Promise.resolve(null));

            const [freshPokemon, freshSpecies] = await Promise.all(promises);

            let freshEvolution = null;
            const species = freshSpecies || oldSpecies;
            if (evolutionStale && species.evolution_chain?.url) {
                const chainId = species.evolution_chain.url.split('/').filter(Boolean).pop();
                freshEvolution = await this._revalidateResource('evolution', chainId);
            }

            const newPokemon = freshPokemon || oldPokemon;
            const newSpecies = freshSpecies || oldSpecies;
            const newEvolution = freshEvolution || oldEvolution;

            // Only re-render if data actually changed
            const changed = (freshPokemon && JSON.stringify(freshPokemon) !== JSON.stringify(oldPokemon))
                || (freshSpecies && JSON.stringify(freshSpecies) !== JSON.stringify(oldSpecies))
                || (freshEvolution && JSON.stringify(freshEvolution) !== JSON.stringify(oldEvolution));

            if (changed) {
                console.log(`✨ Fresh data differs from stale — re-rendering ${identifier}`);
                this.updateDisplay(newPokemon, newSpecies, newEvolution);
                // Update canvas context so realtime voice knows about fresh data
                this.app.updateCanvasState('pokemon', {
                    pokemon: newPokemon,
                    species: newSpecies,
                    evolutionChain: newEvolution
                }, false);
            } else {
                console.log(`✅ Revalidated ${identifier} — data unchanged, no re-render needed`);
            }
        } catch (err) {
            console.warn('Background revalidation failed (stale data still shown):', err);
        }
    }

    async loadPokemonWithoutHistory(identifier) {
        try {
            const [pokemonResult, speciesResult] = await Promise.all([
                this.fetchResourceWithFallback('pokemon', identifier),
                this.fetchResourceWithFallback('species', identifier)
            ]);

            const pokemon = pokemonResult.data;
            const species = speciesResult.data;
            const anyStale = pokemonResult.isStale || speciesResult.isStale;

            // Fetch evolution chain if available
            let evolutionChain = null;
            let evolutionStale = false;
            if (species.evolution_chain && species.evolution_chain.url) {
                const chainId = species.evolution_chain.url.split('/').filter(Boolean).pop();
                const evoResult = await this.fetchResourceWithFallback('evolution', chainId);
                evolutionChain = evoResult.data;
                evolutionStale = evoResult.isStale;
            }

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
            this.app.gridView.saveScrollPosition();
            this.app.pokemonGridView.style.display = 'none';
            this.detailView.style.display = 'block';
            
            // Update canvas state with Pokemon data (without adding to history)
            this.app.updateCanvasState('pokemon', { pokemon, species, evolutionChain }, false);
            
            // Update the display
            this.updateDisplay(pokemon, species, evolutionChain);

            // Stale-while-revalidate
            if (anyStale || evolutionStale) {
                this._revalidateAndRerender(identifier, pokemon, species, evolutionChain,
                    pokemonResult.isStale, speciesResult.isStale, evolutionStale);
            }
        } catch (error) {
            console.error('Error loading Pokemon:', error);
        }
    }

    display(pokemon, species, evolutionChain = null) {
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
        this.app.gridView.saveScrollPosition();
        this.app.pokemonGridView.style.display = 'none';
        this.detailView.style.display = 'block';
        
        // Store current Pokemon name for card searches
        this.app.currentPokemonName = pokemon.name;
        
        // Mark Pokemon as viewed
        this.app.markPokemonViewed(pokemon.id, 'detail');

        // Update canvas state with Pokemon data (automatically adds to history)
        this.app.updateCanvasState('pokemon', { pokemon, species, evolutionChain });

        this.updateDisplay(pokemon, species, evolutionChain);
        
        // Update navigation previews
        this.updateNavigationPreviews(pokemon.id);
    }

    updateDisplay(pokemon, species, evolutionChain = null) {
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
        const imageUrl = this.getSpriteUrl(pokemon) || '';
        if (imageUrl) {
            imageEl.src = imageUrl;
            imageEl.alt = pokemon.name;
        }

        this.playPokemonCry(pokemon);

        // Update types
        const typesContainer = this.detailView.querySelector('.pokemon-types');
        if (typesContainer) {
            typesContainer.innerHTML = pokemon.types.map(t => 
                `<span class="type-badge type-${t.type.name}">${t.type.name}</span>`
            ).join('');
        }

        // Update about section with enhanced details
        this.updateAboutSection(pokemon, species);
        
        // Update base stats
        this.updateBaseStats(pokemon);
        
        // Update evolution chain
        if (evolutionChain) {
            this.updateEvolutionChain(evolutionChain, pokemon.name);
        }
    }

    updateAboutSection(pokemon, species) {
        const weightEl = this.detailView.querySelector('.pokemon-weight');
        const heightEl = this.detailView.querySelector('.pokemon-height');
        const abilitiesEl = this.detailView.querySelector('.pokemon-abilities');
        
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
        
        // Add enhanced details
        this.addEnhancedDetails(pokemon, species);
        
        // Add weaknesses
        this.addWeaknesses(pokemon);
    }

    addEnhancedDetails(pokemon, species) {
        // Check if enhanced details section already exists
        let enhancedSection = this.detailView.querySelector('.enhanced-pokemon-details');
        if (!enhancedSection) {
            enhancedSection = document.createElement('div');
            enhancedSection.className = 'enhanced-pokemon-details';
            
            // Insert after description
            const descEl = this.detailView.querySelector('.pokemon-description');
            if (descEl && descEl.parentNode) {
                descEl.parentNode.insertBefore(enhancedSection, descEl.nextSibling);
            }
        }
        
        // Build enhanced details HTML
        let detailsHTML = '<div class="detail-grid">';
        
        // Gender Ratio
        if (species.gender_rate !== undefined) {
            if (species.gender_rate === -1) {
                detailsHTML += `
                    <div class="detail-item">
                        <span class="detail-label">Gender</span>
                        <span class="detail-value">Genderless</span>
                    </div>
                `;
            } else {
                const femalePercent = (species.gender_rate / 8) * 100;
                const malePercent = 100 - femalePercent;
                detailsHTML += `
                    <div class="detail-item">
                        <span class="detail-label">Gender</span>
                        <span class="detail-value">
                            <span class="gender-icon male">♂</span> ${malePercent}%
                            <span class="gender-icon female">♀</span> ${femalePercent}%
                        </span>
                    </div>
                `;
            }
        }
        
        // Egg Groups
        if (species.egg_groups && species.egg_groups.length > 0) {
            const eggGroups = species.egg_groups.map(g => 
                g.name.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
            ).join(', ');
            detailsHTML += `
                <div class="detail-item">
                    <span class="detail-label">Egg Groups</span>
                    <span class="detail-value">${eggGroups}</span>
                </div>
            `;
        }
        
        // Capture Rate
        if (species.capture_rate !== undefined) {
            detailsHTML += `
                <div class="detail-item">
                    <span class="detail-label">Capture Rate</span>
                    <span class="detail-value">${species.capture_rate}</span>
                </div>
            `;
        }
        
        // Base Happiness
        if (species.base_happiness !== undefined) {
            detailsHTML += `
                <div class="detail-item">
                    <span class="detail-label">Base Happiness</span>
                    <span class="detail-value">${species.base_happiness}</span>
                </div>
            `;
        }
        
        // Growth Rate
        if (species.growth_rate && species.growth_rate.name) {
            const growthRate = species.growth_rate.name.split('-').map(w => 
                w.charAt(0).toUpperCase() + w.slice(1)
            ).join(' ');
            detailsHTML += `
                <div class="detail-item">
                    <span class="detail-label">Growth Rate</span>
                    <span class="detail-value">${growthRate}</span>
                </div>
            `;
        }
        
        // Habitat
        if (species.habitat && species.habitat.name) {
            const habitat = species.habitat.name.split('-').map(w => 
                w.charAt(0).toUpperCase() + w.slice(1)
            ).join(' ');
            detailsHTML += `
                <div class="detail-item">
                    <span class="detail-label">Habitat</span>
                    <span class="detail-value">${habitat}</span>
                </div>
            `;
        }
        
        detailsHTML += '</div>';
        enhancedSection.innerHTML = detailsHTML;
    }

    async addWeaknesses(pokemon) {
        // Check if weaknesses section already exists
        let weaknessSection = this.detailView.querySelector('.pokemon-weaknesses-section');
        if (!weaknessSection) {
            weaknessSection = document.createElement('div');
            weaknessSection.className = 'pokemon-weaknesses-section';
            
            // Insert after enhanced details
            const enhancedSection = this.detailView.querySelector('.enhanced-pokemon-details');
            if (enhancedSection && enhancedSection.parentNode) {
                enhancedSection.parentNode.insertBefore(weaknessSection, enhancedSection.nextSibling);
            }
        }
        
        // Fetch type data for all Pokemon types
        let typeData = [];
        try {
            const typeResults = await Promise.all(
                pokemon.types.map(t => this.fetchResourceWithFallback('type', t.type.name))
            );
            typeData = typeResults.map(r => r.data);
        } catch (error) {
            console.error('Error loading type data for weaknesses:', error);
            return;
        }
        
        // Calculate weaknesses (damage multipliers)
        const weaknessMap = {};
        
        typeData.forEach(type => {
            // Double damage from these types
            type.damage_relations.double_damage_from.forEach(damageType => {
                const typeName = damageType.name;
                weaknessMap[typeName] = (weaknessMap[typeName] || 1) * 2;
            });
            
            // Half damage from these types
            type.damage_relations.half_damage_from.forEach(damageType => {
                const typeName = damageType.name;
                weaknessMap[typeName] = (weaknessMap[typeName] || 1) * 0.5;
            });
            
            // No damage from these types
            type.damage_relations.no_damage_from.forEach(damageType => {
                const typeName = damageType.name;
                weaknessMap[typeName] = 0;
            });
        });
        
        // Filter for actual weaknesses (2x or 4x damage)
        const weaknesses = Object.entries(weaknessMap)
            .filter(([type, multiplier]) => multiplier > 1)
            .sort((a, b) => b[1] - a[1]); // Sort by multiplier (4x first, then 2x)
        
        if (weaknesses.length === 0) {
            weaknessSection.innerHTML = '';
            return;
        }
        
        // Build weaknesses HTML
        let weaknessHTML = '<h4 class="weakness-title">Weaknesses</h4><div class="weakness-types">';
        
        weaknesses.forEach(([type, multiplier]) => {
            const displayMultiplier = multiplier === 4 ? '4×' : '2×';
            weaknessHTML += `
                <div class="weakness-item">
                    <span class="type-badge type-${type}">${type}</span>
                    <span class="weakness-multiplier">${displayMultiplier}</span>
                </div>
            `;
        });
        
        weaknessHTML += '</div>';
        weaknessSection.innerHTML = weaknessHTML;
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
        
        // Stat color mapping
        const statColors = {
            'hp': '#90EE90',
            'attack': '#FFD700',
            'defense': '#FF8C00',
            'special-attack': '#87CEEB',
            'special-defense': '#9370DB',
            'speed': '#FF69B4'
        };
        
        let totalStats = 0;
        
        pokemon.stats.forEach(stat => {
            const statName = stat.stat.name;
            const statValue = stat.base_stat;
            const displayName = statNames[statName] || statName;
            const color = statColors[statName] || '#90EE90';
            
            totalStats += statValue;
            
            const statRow = document.createElement('div');
            statRow.className = 'stat-row';
            
            const percentage = Math.min((statValue / 255) * 100, 100);
            
            statRow.innerHTML = `
                <div class="stat-name">${displayName}</div>
                <div class="stat-value">${statValue}</div>
                <div class="stat-bar-container">
                    <div class="stat-bar" style="width: ${percentage}%; background: ${color};"></div>
                </div>
            `;
            
            statsContainer.appendChild(statRow);
        });
        
        // Add total stats row
        const totalRow = document.createElement('div');
        totalRow.className = 'stat-row stat-total';
        totalRow.innerHTML = `
            <div class="stat-name">Total</div>
            <div class="stat-value">${totalStats}</div>
            <div class="stat-bar-container" style="visibility: hidden;"></div>
        `;
        statsContainer.appendChild(totalRow);
    }

    async updateEvolutionChain(evolutionChain, currentPokemonName) {
        // Check if evolution section already exists, otherwise create it
        let evolutionSection = this.detailView.querySelector('.pokemon-evolution-section');
        if (!evolutionSection) {
            evolutionSection = document.createElement('div');
            evolutionSection.className = 'pokemon-evolution-section';
            
            // Insert before base stats section
            const statsTitle = Array.from(this.detailView.querySelectorAll('.section-title'))
                .find(el => el.textContent === 'Base Stats');
            if (statsTitle) {
                statsTitle.parentNode.insertBefore(evolutionSection, statsTitle);
            } else {
                // Fallback: append to info card
                const infoCard = this.detailView.querySelector('.pokemon-info-card');
                if (infoCard) {
                    infoCard.appendChild(evolutionSection);
                }
            }
        }
        
        // Build evolution chain HTML
        const evolutionHTML = await this.buildEvolutionChainHTML(evolutionChain.chain, currentPokemonName);
        evolutionSection.innerHTML = `
            <h3 class="section-title">Evolutions</h3>
            <div class="evolution-chain">
                ${evolutionHTML}
            </div>
        `;
        
        // Add click handlers for evolution Pokemon
        const evolutionLinks = evolutionSection.querySelectorAll('[data-pokemon-id]');
        evolutionLinks.forEach(link => {
            link.addEventListener('click', async (e) => {
                e.preventDefault();
                const pokemonId = link.dataset.pokemonId;
                if (pokemonId) {
                    await this.loadPokemon(pokemonId);
                }
            });
        });
    }

    async buildEvolutionChainHTML(chain, currentName) {
        if (!chain) return '';
        
        const evolutions = [];
        await this.extractEvolutions(chain, evolutions);
        
        if (evolutions.length === 0) return '<p class="no-evolutions">This Pokémon does not evolve.</p>';
        
        return evolutions.map((evo, index) => {
            const isCurrent = evo.name === currentName;
            
            // Build type badges HTML
            const typeBadges = evo.types ? evo.types.map(type => 
                `<span class="type-badge type-${type.toLowerCase()}">${type}</span>`
            ).join('') : '';
            
            let html = `
                <div class="evolution-item ${isCurrent ? 'current' : ''}" data-pokemon-id="${evo.id}">
                    <div class="evolution-image-wrapper">
                        <img src="${evo.image}" alt="${evo.name}" class="evolution-image">
                        ${isCurrent ? '<span class="current-badge">Current</span>' : ''}
                    </div>
                    <p class="evolution-name">${evo.name}</p>
                    <p class="evolution-id">#${String(evo.id).padStart(3, '0')}</p>
                    <div class="evolution-types">${typeBadges}</div>
                </div>
            `;
            
            // Show arrow with NEXT evolution's details (not current one's)
            if (index < evolutions.length - 1) {
                const nextEvo = evolutions[index + 1];
                const evolutionDetails = nextEvo.details ? this.formatEvolutionDetails(nextEvo.details) : '';
                
                html += `
                    <div class="evolution-arrow">
                        <svg class="arrow-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M5 12H19M19 12L12 5M19 12L12 19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                        ${evolutionDetails ? `<span class="evolution-method">${evolutionDetails}</span>` : ''}
                    </div>
                `;
            }
            
            return html;
        }).join('');
    }

    async extractEvolutions(chain, evolutions, details = null) {
        if (!chain) return;
        
        // Extract Pokemon ID from species URL
        const speciesUrl = chain.species.url;
        const pokemonId = speciesUrl.split('/').filter(Boolean).pop();
        
        // Fetch Pokemon data for image and types
        try {
            const { data: pokemon } = await this.fetchResourceWithFallback('pokemon', pokemonId);
            
            evolutions.push({
                name: chain.species.name,
                id: pokemonId,
                image: this.getSpriteUrl(pokemon),
                types: pokemon.types ? pokemon.types.map(t => t.type.name) : [],
                details: details
            });
        } catch (error) {
            console.error('Error fetching evolution Pokemon:', error);
        }
        
        // Process evolutions recursively
        if (chain.evolves_to && chain.evolves_to.length > 0) {
            for (const evolution of chain.evolves_to) {
                const evolutionDetails = evolution.evolution_details && evolution.evolution_details[0];
                await this.extractEvolutions(evolution, evolutions, evolutionDetails);
            }
        }
    }

    formatEvolutionDetails(details) {
        if (!details) return '';
        
        const parts = [];
        
        if (details.min_level) {
            parts.push(`Level ${details.min_level}`);
        }
        
        if (details.item) {
            const itemName = details.item.name.split('-').map(w => 
                w.charAt(0).toUpperCase() + w.slice(1)
            ).join(' ');
            parts.push(itemName);
        }
        
        if (details.trigger && details.trigger.name === 'trade') {
            parts.push('Trade');
        }
        
        if (details.min_happiness) {
            parts.push(`Happiness ${details.min_happiness}`);
        }
        
        if (details.min_affection) {
            parts.push(`Affection ${details.min_affection}`);
        }
        
        if (details.held_item) {
            const itemName = details.held_item.name.split('-').map(w => 
                w.charAt(0).toUpperCase() + w.slice(1)
            ).join(' ');
            parts.push(`Holding ${itemName}`);
        }
        
        if (details.known_move) {
            const moveName = details.known_move.name.split('-').map(w => 
                w.charAt(0).toUpperCase() + w.slice(1)
            ).join(' ');
            parts.push(`Knows ${moveName}`);
        }
        
        if (details.location) {
            const locationName = details.location.name.split('-').map(w => 
                w.charAt(0).toUpperCase() + w.slice(1)
            ).join(' ');
            parts.push(`At ${locationName}`);
        }
        
        if (details.time_of_day) {
            parts.push(details.time_of_day.charAt(0).toUpperCase() + details.time_of_day.slice(1));
        }
        
        return parts.join(', ');
    }
}
