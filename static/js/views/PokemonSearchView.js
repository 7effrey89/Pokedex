/**
 * Pokemon Search View - Handles the search/filter panel for the Pokemon grid
 */
class PokemonSearchView {
    constructor(app) {
        this.app = app;
        this.panel = document.getElementById('searchPanel');
        this.closeBtn = document.getElementById('searchPanelClose');
        this.nameInput = document.getElementById('searchNameInput');
        this.typeGrid = document.getElementById('searchTypeGrid');
        this.genGrid = document.getElementById('searchGenGrid');
        this.numMin = document.getElementById('searchNumMin');
        this.numMax = document.getElementById('searchNumMax');
        this.heightMin = document.getElementById('searchHeightMin');
        this.heightMax = document.getElementById('searchHeightMax');
        this.weightMin = document.getElementById('searchWeightMin');
        this.weightMax = document.getElementById('searchWeightMax');
        this.abilityInput = document.getElementById('searchAbilityInput');
        this.abilityDatalist = document.getElementById('abilityDatalist');
        this.applyBtn = document.getElementById('searchApplyBtn');
        this.resetBtn = document.getElementById('searchResetBtn');
        this.resultBar = document.getElementById('searchResultBar');
        this.searchBtn = document.getElementById('searchBtnFooter');

        this.metadata = null; // { "25": { name, types, ... } }
        this.selectedTypes = new Set();
        this.selectedGens = new Set();
        this.isOpen = false;
        this.hasActiveFilter = false;

        this.allTypes = [
            'normal', 'grass', 'fire', 'water', 'electric', 'ice',
            'fighting', 'poison', 'ground', 'flying', 'psychic', 'bug',
            'rock', 'ghost', 'dark', 'dragon', 'steel', 'fairy'
        ];

        this._buildTypeChips();
        this._buildGenChips();
        this._bindEvents();
    }

    _buildTypeChips() {
        if (!this.typeGrid) return;
        this.typeGrid.innerHTML = this.allTypes.map(type =>
            `<span class="search-type-chip type-${type}" data-type="${type}">${type}</span>`
        ).join('');
    }

    _buildGenChips() {
        if (!this.genGrid) return;
        this.genGrid.innerHTML = this.app.generations.map((gen, i) =>
            `<span class="search-gen-chip" data-gen="${i}">${gen.name.replace('Generation ', 'Gen ')}</span>`
        ).join('');
    }

    _bindEvents() {
        // Toggle panel
        if (this.searchBtn) {
            this.searchBtn.addEventListener('click', () => this.toggle());
        }
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }

        // Type chip selection — apply immediately
        if (this.typeGrid) {
            this.typeGrid.addEventListener('click', (e) => {
                const chip = e.target.closest('.search-type-chip');
                if (!chip) return;
                const type = chip.dataset.type;
                if (this.selectedTypes.has(type)) {
                    this.selectedTypes.delete(type);
                    chip.classList.remove('selected');
                } else {
                    this.selectedTypes.add(type);
                    chip.classList.add('selected');
                }
                this.applyFilters();
            });
        }

        // Generation chip selection — apply immediately
        if (this.genGrid) {
            this.genGrid.addEventListener('click', (e) => {
                const chip = e.target.closest('.search-gen-chip');
                if (!chip) return;
                const gen = chip.dataset.gen;
                if (this.selectedGens.has(gen)) {
                    this.selectedGens.delete(gen);
                    chip.classList.remove('selected');
                } else {
                    this.selectedGens.add(gen);
                    chip.classList.add('selected');
                }
                this.applyFilters();
            });
        }

        // Apply / Reset
        if (this.applyBtn) {
            this.applyBtn.addEventListener('click', () => {
                this.applyFilters();
                this.close();
            });
        }
        if (this.resetBtn) {
            this.resetBtn.addEventListener('click', () => this.resetFilters());
        }

        // Live filtering on name input
        if (this.nameInput) {
            this.nameInput.addEventListener('input', () => this.applyFilters());
        }

        // Live filtering on number range inputs
        if (this.numMin) {
            this.numMin.addEventListener('input', () => this.applyFilters());
        }
        if (this.numMax) {
            this.numMax.addEventListener('input', () => this.applyFilters());
        }

        // Live filtering on height/weight/ability inputs
        for (const el of [this.heightMin, this.heightMax, this.weightMin, this.weightMax]) {
            if (el) el.addEventListener('input', () => this.applyFilters());
        }
        if (this.abilityInput) {
            this.abilityInput.addEventListener('input', () => this.applyFilters());
        }
    }

    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    async open() {
        if (!this.panel) return;
        // Fetch metadata on first open
        if (!this.metadata) {
            await this._loadMetadata();
        }
        this.panel.classList.add('open');
        this.isOpen = true;
        if (this.nameInput) this.nameInput.focus();
    }

    close() {
        if (!this.panel) return;
        this.panel.classList.remove('open');
        this.isOpen = false;
    }

    async _loadMetadata() {
        try {
            const resp = await fetch('/api/pokemon/metadata');
            if (resp.ok) {
                this.metadata = await resp.json();
                console.log(`🔍 Loaded metadata for ${Object.keys(this.metadata).length} cached Pokemon`);
                this._buildAbilityDatalist();
            } else {
                this.metadata = {};
            }
        } catch (err) {
            console.warn('Failed to load Pokemon metadata:', err);
            this.metadata = {};
        }
    }

    _buildAbilityDatalist() {
        if (!this.abilityDatalist || !this.metadata) return;
        const abilities = new Set();
        for (const meta of Object.values(this.metadata)) {
            if (meta.abilities) meta.abilities.forEach(a => abilities.add(a));
        }
        const sorted = [...abilities].sort();
        this.abilityDatalist.innerHTML = sorted.map(a =>
            `<option value="${a}">`
        ).join('');
    }

    applyFilters() {
        const nameQuery = (this.nameInput?.value || '').trim().toLowerCase();
        const minNum = parseInt(this.numMin?.value) || 1;
        const maxNum = parseInt(this.numMax?.value) || 1025;
        const hasTypeFilter = this.selectedTypes.size > 0;
        const hasGenFilter = this.selectedGens.size > 0;
        const hasNameFilter = nameQuery.length > 0;
        const hasRangeFilter = minNum > 1 || maxNum < 1025;

        // Height filter (user enters metres, API stores decimetres)
        const heightMinVal = parseFloat(this.heightMin?.value);
        const heightMaxVal = parseFloat(this.heightMax?.value);
        const hasHeightFilter = !isNaN(heightMinVal) || !isNaN(heightMaxVal);
        const heightMinDm = !isNaN(heightMinVal) ? Math.round(heightMinVal * 10) : 0;
        const heightMaxDm = !isNaN(heightMaxVal) ? Math.round(heightMaxVal * 10) : Infinity;

        // Weight filter (user enters kg, API stores hectograms)
        const weightMinVal = parseFloat(this.weightMin?.value);
        const weightMaxVal = parseFloat(this.weightMax?.value);
        const hasWeightFilter = !isNaN(weightMinVal) || !isNaN(weightMaxVal);
        const weightMinHg = !isNaN(weightMinVal) ? Math.round(weightMinVal * 10) : 0;
        const weightMaxHg = !isNaN(weightMaxVal) ? Math.round(weightMaxVal * 10) : Infinity;

        // Ability filter
        const abilityQuery = (this.abilityInput?.value || '').trim().toLowerCase();
        const hasAbilityFilter = abilityQuery.length > 0;

        this.hasActiveFilter = hasTypeFilter || hasGenFilter || hasNameFilter || hasRangeFilter
            || hasHeightFilter || hasWeightFilter || hasAbilityFilter;

        // Build allowed generation ranges
        let genRanges = [];
        if (hasGenFilter) {
            for (const genIdx of this.selectedGens) {
                genRanges.push(this.app.generations[parseInt(genIdx)]);
            }
        }

        const pokemonList = this.app.pokemonList || document.getElementById('pokemonList');
        if (!pokemonList) return;

        const cards = pokemonList.querySelectorAll('.list-item');
        const separators = pokemonList.querySelectorAll('.generation-separator');
        let matchCount = 0;

        cards.forEach(card => {
            const numberEl = card.querySelector('.number-wrap');
            const nameEl = card.querySelector('.name-wrap');
            if (!numberEl || !nameEl) return;

            const id = parseInt(numberEl.textContent.replace('#', ''));
            const name = nameEl.textContent.toLowerCase();
            let visible = true;

            // Name filter
            if (hasNameFilter && !name.includes(nameQuery)) {
                visible = false;
            }

            // Number range filter
            if (visible && (id < minNum || id > maxNum)) {
                visible = false;
            }

            // Generation filter
            if (visible && hasGenFilter) {
                const inGen = genRanges.some(g => id >= g.start && id <= g.end);
                if (!inGen) visible = false;
            }

            // Type filter (requires metadata)
            if (visible && hasTypeFilter && this.metadata) {
                const meta = this.metadata[String(id)];
                if (meta && meta.types) {
                    const hasMatchingType = meta.types.some(t => this.selectedTypes.has(t));
                    if (!hasMatchingType) visible = false;
                } else {
                    // No cached data — keep visible if only type filter is active
                    // (don't hide Pokemon we have no data for)
                }
            }

            // Height filter (requires metadata)
            if (visible && hasHeightFilter && this.metadata) {
                const meta = this.metadata[String(id)];
                if (meta && meta.height != null) {
                    if (meta.height < heightMinDm || meta.height > heightMaxDm) visible = false;
                }
            }

            // Weight filter (requires metadata)
            if (visible && hasWeightFilter && this.metadata) {
                const meta = this.metadata[String(id)];
                if (meta && meta.weight != null) {
                    if (meta.weight < weightMinHg || meta.weight > weightMaxHg) visible = false;
                }
            }

            // Ability filter (requires metadata)
            if (visible && hasAbilityFilter && this.metadata) {
                const meta = this.metadata[String(id)];
                if (meta && meta.abilities) {
                    const hasMatchingAbility = meta.abilities.some(a => a.includes(abilityQuery));
                    if (!hasMatchingAbility) visible = false;
                }
            }

            card.style.display = visible ? '' : 'none';
            if (visible) matchCount++;
        });

        // Show/hide generation separators based on visible cards in that gen
        separators.forEach(sep => {
            const label = sep.querySelector('.generation-label')?.textContent || '';
            // Find the generation
            const gen = this.app.generations.find(g => label.includes(g.name.replace('Generation ', 'Gen ')) || label.includes(g.name));
            if (!gen) return;

            // Check if any card in this gen range is visible
            let hasVisible = false;
            cards.forEach(card => {
                if (card.style.display === 'none') return;
                const numEl = card.querySelector('.number-wrap');
                if (!numEl) return;
                const cid = parseInt(numEl.textContent.replace('#', ''));
                if (cid >= gen.start && cid <= gen.end) hasVisible = true;
            });
            sep.style.display = hasVisible ? '' : 'none';
        });

        // Update result bar
        this._updateResultBar(matchCount);
        this._updateSearchIndicator();

        // Scroll to top of grid
        const canvas = document.getElementById('mainCanvas');
        if (canvas) canvas.scrollTop = 0;

        // Make sure we're on the grid view
        if (this.app.pokemonDetailView.style.display !== 'none' ||
            this.app.tcgCardsView.style.display !== 'none') {
            this.app.gridView.showWithoutHistory();
        }
    }

    resetFilters() {
        // Clear inputs
        if (this.nameInput) this.nameInput.value = '';
        if (this.numMin) this.numMin.value = '';
        if (this.numMax) this.numMax.value = '';
        if (this.heightMin) this.heightMin.value = '';
        if (this.heightMax) this.heightMax.value = '';
        if (this.weightMin) this.weightMin.value = '';
        if (this.weightMax) this.weightMax.value = '';
        if (this.abilityInput) this.abilityInput.value = '';

        // Clear type selections
        this.selectedTypes.clear();
        this.typeGrid?.querySelectorAll('.search-type-chip.selected').forEach(c => c.classList.remove('selected'));

        // Clear gen selections
        this.selectedGens.clear();
        this.genGrid?.querySelectorAll('.search-gen-chip.selected').forEach(c => c.classList.remove('selected'));

        this.hasActiveFilter = false;

        // Show all cards and separators
        const pokemonList = this.app.pokemonList || document.getElementById('pokemonList');
        if (pokemonList) {
            pokemonList.querySelectorAll('.list-item').forEach(c => c.style.display = '');
            pokemonList.querySelectorAll('.generation-separator').forEach(s => s.style.display = '');
        }

        this._updateResultBar(0);
        this._updateSearchIndicator();
    }

    _updateResultBar(count) {
        if (!this.resultBar) return;
        if (this.hasActiveFilter) {
            this.resultBar.textContent = `${count} Pokémon found`;
            this.resultBar.classList.add('active');
        } else {
            this.resultBar.classList.remove('active');
        }
    }

    _updateSearchIndicator() {
        if (!this.searchBtn) return;
        let dot = this.searchBtn.querySelector('.search-active-dot');
        if (this.hasActiveFilter) {
            if (!dot) {
                dot = document.createElement('span');
                dot.className = 'search-active-dot';
                this.searchBtn.style.position = 'relative';
                this.searchBtn.appendChild(dot);
            }
        } else {
            if (dot) dot.remove();
        }
    }
}
