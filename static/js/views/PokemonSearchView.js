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

        // TCG filter elements
        this.pokemonFiltersEl = document.getElementById('pokemonFilters');
        this.tcgFiltersEl = document.getElementById('tcgFilters');
        this.tcgNameInput = document.getElementById('tcgSearchNameInput');
        this.tcgTypeGrid = document.getElementById('tcgSearchTypeGrid');
        this.tcgCategoryGrid = document.getElementById('tcgCategoryGrid');
        this.tcgExpansionSection = document.getElementById('tcgExpansionSection');
        this.tcgExpansionList = document.getElementById('tcgExpansionList');
        this.tcgExpansionToggle = document.getElementById('tcgExpansionToggle');
        this.tcgPriceMin = document.getElementById('tcgPriceMin');
        this.tcgPriceMax = document.getElementById('tcgPriceMax');
        this.tcgRaritySelect = document.getElementById('tcgSearchRarity');
        this.tcgSelectedTypes = new Set();
        this.tcgSelectedCategories = new Set();
        this.tcgSelectedSets = new Set();
        this._tcgExpansionListBuilt = false;
        this._currentContext = 'pokemon'; // 'pokemon' or 'tcg'

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
        this._buildTcgTypeChips();
        this._buildTcgCategoryChips();
        this._bindEvents();
    }

    _buildTypeChips() {
        if (!this.typeGrid) return;
        this.typeGrid.innerHTML = this.allTypes.map(type =>
            `<span class="search-type-chip type-${type}" data-type="${type}">${type}</span>`
        ).join('');
    }

    _buildTcgTypeChips() {
        if (!this.tcgTypeGrid) return;
        // TCG energy types
        const tcgTypes = ['Colorless', 'Darkness', 'Dragon', 'Fairy', 'Fighting', 'Fire', 'Grass', 'Lightning', 'Metal', 'Psychic', 'Water'];
        this.tcgTypeGrid.innerHTML = tcgTypes.map(type =>
            `<span class="search-type-chip tcg-type-${type.toLowerCase()}" data-type="${type}">${type}</span>`
        ).join('');
    }

    _buildTcgCategoryChips() {
        if (!this.tcgCategoryGrid) return;
        const categories = [
            { label: 'Pokémon', value: 'Pokémon' },
            { label: 'Trainer', value: 'Trainer' },
            { label: 'Energy', value: 'Energy' },
            { label: 'Supporter', value: 'Supporter' },
            { label: 'Item', value: 'Item' },
            { label: 'Stadium', value: 'Stadium' },
            { label: 'Tool', value: 'Pokémon Tool' },
            { label: 'ACE SPEC', value: 'ACE SPEC' },
            { label: 'Tech Machine', value: 'Technical Machine' },
        ];
        this.tcgCategoryGrid.innerHTML = categories.map(cat =>
            `<span class="search-type-chip tcg-cat-chip" data-category="${cat.value}">${cat.label}</span>`
        ).join('');
    }

    _buildTcgExpansionList() {
        if (!this.tcgExpansionList || this._tcgExpansionListBuilt) return;
        const db = this.app.tcgDatabase;
        if (!db || !db.allSets.length) return;

        this._tcgExpansionListBuilt = true;
        // Sort sets newest first
        const sorted = [...db.allSets].sort((a, b) =>
            (b.releaseDate || '').localeCompare(a.releaseDate || '')
        );

        this.tcgExpansionList.innerHTML = sorted.map(set => {
            const year = set.releaseDate ? set.releaseDate.substring(0, 4) : '';
            const symbolUrl = set.images?.symbol || '';
            return `<label class="tcg-expansion-item" data-set-id="${set.id}">
                <input type="checkbox" value="${set.id}">
                ${symbolUrl ? `<img src="${symbolUrl}" alt="" class="tcg-expansion-symbol" loading="lazy">` : ''}
                <span class="tcg-expansion-name">${set.name}</span>
                <span class="tcg-expansion-year">${year}</span>
            </label>`;
        }).join('');
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

        // TCG filter live bindings
        if (this.tcgNameInput) {
            this.tcgNameInput.addEventListener('input', () => this._applyTcgFilters());
        }
        if (this.tcgTypeGrid) {
            this.tcgTypeGrid.addEventListener('click', (e) => {
                const chip = e.target.closest('.search-type-chip');
                if (!chip) return;
                const type = chip.dataset.type;
                if (this.tcgSelectedTypes.has(type)) {
                    this.tcgSelectedTypes.delete(type);
                    chip.classList.remove('selected');
                } else {
                    this.tcgSelectedTypes.add(type);
                    chip.classList.add('selected');
                }
                this._applyTcgFilters();
            });
        }
        if (this.tcgCategoryGrid) {
            this.tcgCategoryGrid.addEventListener('click', (e) => {
                const chip = e.target.closest('.tcg-cat-chip');
                if (!chip) return;
                const cat = chip.dataset.category;
                if (this.tcgSelectedCategories.has(cat)) {
                    this.tcgSelectedCategories.delete(cat);
                    chip.classList.remove('selected');
                } else {
                    this.tcgSelectedCategories.add(cat);
                    chip.classList.add('selected');
                }
                this._applyTcgFilters();
            });
        }
        if (this.tcgExpansionToggle) {
            this.tcgExpansionToggle.addEventListener('click', () => {
                const list = this.tcgExpansionList;
                if (!list) return;
                const visible = list.style.display !== 'none';
                list.style.display = visible ? 'none' : '';
                this.tcgExpansionToggle.textContent = visible ? '▸ show list' : '▾ hide list';
                if (!visible) this._buildTcgExpansionList();
            });
        }
        if (this.tcgExpansionList) {
            this.tcgExpansionList.addEventListener('change', (e) => {
                if (e.target.type !== 'checkbox') return;
                const setId = e.target.value;
                if (e.target.checked) {
                    this.tcgSelectedSets.add(setId);
                } else {
                    this.tcgSelectedSets.delete(setId);
                }
                // Sync with database view expansion picker
                const db = this.app.tcgDatabase;
                if (db && db.viewMode === 'all-cards') {
                    db.syncFromFilterPanel(new Set(this.tcgSelectedSets));
                }
                this._applyTcgFilters();
            });
        }
        for (const el of [this.tcgPriceMin, this.tcgPriceMax]) {
            if (el) el.addEventListener('input', () => this._applyTcgFilters());
        }
        if (this.tcgRaritySelect) {
            this.tcgRaritySelect.addEventListener('change', () => this._applyTcgFilters());
        }
    }

    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    async open() {
        if (!this.panel) return;
        // Detect context based on visible view
        this._detectContext();
        // Fetch metadata on first open (for Pokemon context)
        if (this._currentContext === 'pokemon' && !this.metadata) {
            await this._loadMetadata();
        }
        if (this._currentContext === 'tcg') {
            this._buildTcgExpansionList();
        }
        this.panel.classList.add('open');
        this.isOpen = true;
        if (this._currentContext === 'tcg') {
            if (this.tcgNameInput) this.tcgNameInput.focus();
        } else {
            if (this.nameInput) this.nameInput.focus();
        }
    }

    close() {
        if (!this.panel) return;
        this.panel.classList.remove('open');
        this.isOpen = false;
    }

    _detectContext() {
        const tcgDbVisible = this.app.tcgDatabaseViewEl && this.app.tcgDatabaseViewEl.style.display !== 'none';
        const tcgGalleryVisible = this.app.tcgCardsView && this.app.tcgCardsView.style.display !== 'none';
        this._currentContext = (tcgDbVisible || tcgGalleryVisible) ? 'tcg' : 'pokemon';
        this._isTcgGallery = tcgGalleryVisible && !tcgDbVisible;

        const headerEl = this.panel?.querySelector('.search-panel-header h3');
        if (this._currentContext === 'tcg') {
            if (this.pokemonFiltersEl) this.pokemonFiltersEl.style.display = 'none';
            if (this.tcgFiltersEl) this.tcgFiltersEl.style.display = '';
            if (headerEl) headerEl.textContent = 'TCG Search & Filter';
            // Hide expansion section in gallery mode (cards are already scoped)
            if (this.tcgExpansionSection) {
                this.tcgExpansionSection.style.display = this._isTcgGallery ? 'none' : '';
            }
        } else {
            if (this.pokemonFiltersEl) this.pokemonFiltersEl.style.display = '';
            if (this.tcgFiltersEl) this.tcgFiltersEl.style.display = 'none';
            if (headerEl) headerEl.textContent = 'Search & Filter';
        }
    }

    _buildTcgFilterCriteria() {
        const filters = {};
        const nameQuery = (this.tcgNameInput?.value || '').trim().toLowerCase();
        if (nameQuery) filters.name = nameQuery;
        if (this.tcgSelectedTypes.size > 0) filters.types = new Set(this.tcgSelectedTypes);
        if (this.tcgSelectedCategories.size > 0) filters.categories = new Set(this.tcgSelectedCategories);
        const priceMin = this.tcgPriceMin?.value?.trim();
        const priceMax = this.tcgPriceMax?.value?.trim();
        if (priceMin) filters.priceMin = priceMin;
        if (priceMax) filters.priceMax = priceMax;
        const rarity = this.tcgRaritySelect?.value;
        if (rarity) filters.rarity = rarity;
        return Object.keys(filters).length > 0 ? filters : null;
    }

    _applyTcgFilters() {
        // Gallery view: filter cards in the gallery DOM
        if (this._isTcgGallery) {
            this._applyGalleryFilters();
            this.hasActiveFilter = !!this._buildTcgFilterCriteria();
            this._updateSearchIndicator();
            return;
        }

        const nameQuery = (this.tcgNameInput?.value || '').trim().toLowerCase();
        const db = this.app.tcgDatabase;
        if (!db) return;

        if (db.viewMode === 'all-cards') {
            db.filterCards(this._buildTcgFilterCriteria());
        } else {
            // Expansions mode: filter sets by name + selected sets
            db.filterSets(nameQuery, this.tcgSelectedSets);
        }

        this.hasActiveFilter = !!this._buildTcgFilterCriteria();
        this._updateSearchIndicator();
    }

    _applyGalleryFilters() {
        const gallery = this.app.tcgCardsView;
        if (!gallery) return;
        const filters = this._buildTcgFilterCriteria();
        const cards = gallery.querySelectorAll('.tcg-card-item');
        const allCards = this.app.currentTcgCards || [];
        let visibleCount = 0;

        cards.forEach((cardEl, i) => {
            const card = allCards[i];
            if (!card) { cardEl.style.display = ''; visibleCount++; return; }

            let show = true;
            if (filters) {
                // Name filter
                if (filters.name && !(card.name || '').toLowerCase().includes(filters.name)) {
                    show = false;
                }
                // Energy type filter
                if (show && filters.types) {
                    const cardTypes = card.types || [];
                    const match = [...filters.types].some(t => cardTypes.includes(t));
                    if (!match) show = false;
                }
                // Category filter (supertype + subtypes)
                if (show && filters.categories) {
                    const supertypeMatch = filters.categories.has(card.supertype);
                    const subtypeMatch = (card.subtypes || []).some(s => filters.categories.has(s));
                    if (!supertypeMatch && !subtypeMatch) show = false;
                }
                // Price filter
                if (show && (filters.priceMin || filters.priceMax)) {
                    const avg = this.app.tcgGallery?.getCardAvgPrice(card) ?? null;
                    const min = filters.priceMin ? parseFloat(filters.priceMin) : 0;
                    const max = filters.priceMax ? parseFloat(filters.priceMax) : Infinity;
                    if (avg === null || avg < min || avg > max) show = false;
                }
                // Rarity filter
                if (show && filters.rarity) {
                    if ((card.rarity || '') !== filters.rarity) show = false;
                }
            }

            cardEl.style.display = show ? '' : 'none';
            if (show) visibleCount++;
        });

        // Update the header count
        const countEl = gallery.querySelector('.tcg-canvas-title p:last-child');
        if (countEl) {
            const total = allCards.length;
            countEl.textContent = filters ? `${visibleCount} of ${total} cards` : `${total} cards found`;
        }
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

    applyFilters({ silent = false } = {}) {
        // TCG context uses its own filter logic
        if (this._currentContext === 'tcg') {
            this._applyTcgFilters();
            return;
        }
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

            // Type filter – AND logic: must have ALL selected types (requires metadata)
            if (visible && hasTypeFilter && this.metadata) {
                const meta = this.metadata[String(id)];
                if (meta && meta.types) {
                    const hasAllTypes = [...this.selectedTypes].every(t => meta.types.includes(t));
                    if (!hasAllTypes) visible = false;
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

        if (!silent) {
            // Scroll to top of grid
            const canvas = document.getElementById('mainCanvas');
            if (canvas) canvas.scrollTop = 0;

            // Make sure we're on the grid view
            if (this.app.pokemonDetailView.style.display !== 'none' ||
                this.app.tcgCardsView.style.display !== 'none') {
                this.app.gridView.showWithoutHistory();
            }
        }
    }

    resetFilters() {
        if (this._currentContext === 'tcg') {
            this._resetTcgFilters();
            return;
        }
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

    _resetTcgFilters() {
        if (this.tcgNameInput) this.tcgNameInput.value = '';
        if (this.tcgPriceMin) this.tcgPriceMin.value = '';
        if (this.tcgPriceMax) this.tcgPriceMax.value = '';
        if (this.tcgRaritySelect) this.tcgRaritySelect.value = '';
        this.tcgSelectedTypes.clear();
        this.tcgSelectedCategories.clear();
        this.tcgTypeGrid?.querySelectorAll('.search-type-chip.selected').forEach(c => c.classList.remove('selected'));
        this.tcgCategoryGrid?.querySelectorAll('.tcg-cat-chip.selected').forEach(c => c.classList.remove('selected'));
        this.hasActiveFilter = false;
        this._updateSearchIndicator();
        if (this._isTcgGallery) {
            this._applyGalleryFilters();
            return;
        }
        if (this.app.tcgDatabase) this.app.tcgDatabase.filterSets('');
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
