/**
 * TCG Database View - Displays all TCG cards grouped by expansion/set
 * Modeled after PokemonGridView's generation grouping pattern
 */
class TcgDatabaseView {
    constructor(app) {
        this.app = app;
        this.databaseView = document.getElementById('tcgDatabaseView');
        this.cardList = document.getElementById('tcgDatabaseList');
        this._savedScrollTop = 0;
        this.allSets = [];
        this.loadedSets = new Set();
        this.currentSort = 'release-desc';
        this.observer = null;

        // All Cards flat view state
        this.viewMode = 'expansions'; // 'expansions' | 'all-cards' | 'collection'
        this.allCards = [];
        this.loadedSetIds = new Set(); // track which sets have been fetched
        this.filteredCards = null; // null = no filter active
        this._activeFilters = null; // remember last applied filters
        this.isLoadingCards = false;
        this.cardSort = 'set-desc';
        this._dexLookup = null; // name → dex number map (fetched lazily)
        this._selectedSetIds = new Set(); // sets user has chosen to load

        this._setupLazyObserver();
    }

    /** IntersectionObserver to lazy-load set cards when set section scrolls into view */
    _setupLazyObserver() {
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const setId = entry.target.dataset.setId;
                    if (setId && !this.loadedSets.has(setId)) {
                        this._queuePreviewLoad(setId, entry.target);
                    }
                    this.observer.unobserve(entry.target);
                }
            });
        }, { rootMargin: '400px' });
    }

    /** Throttled preview loading — max 3 concurrent requests */
    _queuePreviewLoad(setId, placeholderEl) {
        if (!this._previewQueue) this._previewQueue = [];
        if (!this._previewInFlight) this._previewInFlight = 0;
        this._previewQueue.push({ setId, placeholderEl });
        this._drainPreviewQueue();
    }

    async _drainPreviewQueue() {
        const MAX_CONCURRENT = 3;
        while (this._previewQueue.length > 0 && this._previewInFlight < MAX_CONCURRENT) {
            const { setId, placeholderEl } = this._previewQueue.shift();
            this._previewInFlight++;
            this._loadSetCards(setId, placeholderEl).finally(() => {
                this._previewInFlight--;
                this._drainPreviewQueue();
            });
        }
    }

    async toggleViewMode(mode) {
        if (mode === this.viewMode) return;
        this.viewMode = mode;

        // Update toggle button states
        const toggleBtns = this.databaseView?.querySelectorAll('.tcg-view-toggle-btn');
        toggleBtns?.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        // Update sort select options
        this._updateSortOptions();

        if (mode === 'all-cards' || mode === 'collection') {
            await this._renderAllCardsView();
        } else {
            this.app.currentTcgCards = null;
            this._renderDatabase();
            this.app.updateCanvasState('tcg-database', {
                total_sets: this.allSets.length
            }, false);
        }
    }

    _updateSortOptions() {
        const sortSelect = this.databaseView?.querySelector('#tcg-db-sort-select');
        if (!sortSelect) return;

        if (this.viewMode === 'all-cards' || this.viewMode === 'collection') {
            sortSelect.innerHTML = `
                <option value="set-desc" selected>Newest Set First</option>
                <option value="set-asc">Oldest Set First</option>
                <option value="number">Card #</option>
                <option value="dex-asc">Pokédex #</option>
                <option value="name-asc">Name: A → Z</option>
                <option value="name-desc">Name: Z → A</option>
                <option value="rarity-desc">Rarity: Rare First</option>
                <option value="rarity-asc">Rarity: Common First</option>
                <option value="price-desc">Price: High → Low</option>
                <option value="price-asc">Price: Low → High</option>
            `;
            sortSelect.value = this.cardSort;
        } else {
            sortSelect.innerHTML = `
                <option value="release-desc" selected>Newest First</option>
                <option value="release-asc">Oldest First</option>
                <option value="name-asc">Name: A → Z</option>
                <option value="name-desc">Name: Z → A</option>
                <option value="cards-desc">Most Cards</option>
            `;
            sortSelect.value = this.currentSort;
        }
    }

    saveScrollPosition() {
        const canvas = document.getElementById('mainCanvas');
        if (canvas) this._savedScrollTop = canvas.scrollTop;
    }

    restoreScrollPosition() {
        const canvas = document.getElementById('mainCanvas');
        if (canvas && this._savedScrollTop > 0) {
            requestAnimationFrame(() => { canvas.scrollTop = this._savedScrollTop; });
        }
    }

    /**
     * Preload sets and dex data in the background so they're ready
     * when the user navigates to the TCG Database page.
     */
    preload() {
        // Fire-and-forget: don't await, just start loading in background
        this._preloadPromise = Promise.all([
            this._loadSetsData(),
            this._loadDexLookup()
        ]).catch(err => console.warn('TCG preload failed:', err));
    }

    /** Fetch sets data only (no DOM rendering) */
    async _loadSetsData() {
        if (this.allSets.length > 0) return;
        try {
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_name: 'get_tcg_sets', arguments: {} })
            });
            if (!response.ok) return;
            const data = await response.json();
            if (data.result?.sets) {
                this.allSets = data.result.sets;
                if (data.result._cache_stale) {
                    this._revalidateSets();
                }
            }
        } catch (err) {
            console.warn('TCG sets preload failed:', err);
        }
    }

    async show() {
        this._hideOtherViews();
        this.databaseView.style.display = 'block';

        // Wait for preload if it's still running, otherwise load now
        if (this._preloadPromise) {
            await this._preloadPromise;
        }
        await this._loadSets();
        this.restoreScrollPosition();

        this.app.updateCanvasState('tcg-database', {
            total_sets: this.allSets.length
        });
    }

    showWithoutHistory() {
        this._hideOtherViews();
        this.databaseView.style.display = 'block';
        this.restoreScrollPosition();

        this.app.updateCanvasState('tcg-database', {
            total_sets: this.allSets.length
        }, false);
    }

    _hideOtherViews() {
        if (this.app.gridView) this.app.gridView.saveScrollPosition();
        this.app.pokemonGridView.style.display = 'none';
        this.app.pokemonDetailView.style.display = 'none';
        this.app.tcgCardsView.style.display = 'none';
        if (this.app.tcgCardDetailView) this.app.tcgCardDetailView.style.display = 'none';
    }

    async _loadSets() {
        if (this.allSets.length > 0) {
            this._updateSetCount();
            this._wireControls();
            this._renderDatabase();
            return; // Already loaded from preload
        }

        console.log('🃏 Loading TCG sets...');
        this.app.setLoading(true);
        try {
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'get_tcg_sets',
                    arguments: {}
                })
            });
            if (!response.ok) throw new Error('Failed to load TCG sets');

            const data = await response.json();
            if (data.result && data.result.sets) {
                this.allSets = data.result.sets;
                this._updateSetCount();
                this._wireControls();
                this._renderDatabase();

                // Stale-while-revalidate: refresh sets list in background if stale
                if (data.result._cache_stale) {
                    this._revalidateSets();
                }
            } else {
                this.cardList.innerHTML = '<div class="error-state">Unable to load TCG sets.</div>';
            }
        } catch (error) {
            console.error('Failed to load TCG sets:', error);
            this.cardList.innerHTML = '<div class="error-state">Unable to load TCG sets. Please refresh.</div>';
        } finally {
            this.app.setLoading(false);
        }
    }

    /** Background revalidation for stale TCG sets list */
    async _revalidateSets() {
        console.log('🔄 Revalidating stale TCG sets list...');
        try {
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'get_tcg_sets',
                    arguments: { force_refresh: true }
                })
            });
            if (!response.ok) return;
            const data = await response.json();
            if (data?.result?.sets) {
                const oldCount = this.allSets.length;
                if (data.result.sets.length !== oldCount) {
                    this.allSets = data.result.sets;
                    this._updateSetCount();
                    this._renderDatabase();
                    console.log(`✅ Sets revalidated: ${oldCount} → ${data.result.sets.length} sets`);
                } else {
                    this.allSets = data.result.sets; // Update data silently
                    console.log('✅ Sets revalidated: count unchanged');
                }
            }
        } catch (err) {
            console.warn('⚠️ Sets revalidation failed:', err);
        }
    }

    _updateSetCount() {
        const countEl = document.getElementById('tcgDbSetCount');
        if (countEl) countEl.textContent = `${this.allSets.length} expansions`;
    }

    _wireControls() {
        const sortSelect = document.getElementById('tcg-db-sort-select');
        if (sortSelect) {
            sortSelect.addEventListener('change', () => {
                this.changeSort(sortSelect.value);
            });
        }

        // View toggle buttons
        const toggleBtns = this.databaseView?.querySelectorAll('.tcg-view-toggle-btn');
        toggleBtns?.forEach(btn => {
            btn.addEventListener('click', () => {
                this.toggleViewMode(btn.dataset.mode);
            });
        });
    }

    _renderDatabase() {
        if (!this.cardList) return;
        this.cardList.innerHTML = '';
        this.loadedSets.clear();

        const sortedSets = this._sortSets(this.allSets, this.currentSort);

        // Group by series
        let currentSeries = '';
        sortedSets.forEach(set => {
            const series = set.series || 'Other';
            if (series !== currentSeries) {
                currentSeries = series;
                const separator = this._createSeriesSeparator(series);
                this.cardList.appendChild(separator);
            }

            const setSection = this._createSetSection(set);
            this.cardList.appendChild(setSection);
        });
    }

    _createSeriesSeparator(series) {
        const separator = document.createElement('div');
        separator.className = 'tcg-series-separator';
        separator.innerHTML = `
            <div class="generation-line"></div>
            <div class="generation-label">${series}</div>
            <div class="generation-line"></div>
        `;
        return separator;
    }

    _createSetSection(set) {
        const section = document.createElement('div');
        section.className = 'tcg-set-section';
        section.dataset.setId = set.id;

        const year = set.releaseDate ? set.releaseDate.substring(0, 4) : '';
        const logoUrl = set.images?.logo || '';
        const symbolUrl = set.images?.symbol || '';

        section.innerHTML = `
            <div class="tcg-set-header" data-set-id="${set.id}">
                <div class="tcg-set-header-info">
                    ${logoUrl ? `<img src="${logoUrl}" alt="${set.name}" class="tcg-set-logo" loading="lazy">` : ''}
                    <div class="tcg-set-header-text">
                        <h2 class="tcg-set-name">${set.name}</h2>
                        <span class="tcg-set-meta">${year} · ${set.total} cards${symbolUrl ? ` <img src="${symbolUrl}" alt="" class="tcg-set-symbol">` : ''}</span>
                    </div>
                </div>
            </div>
            <div class="tcg-set-cards-placeholder" data-set-id="${set.id}">
                <div class="tcg-set-loading">Loading cards...</div>
            </div>
        `;

        // Lazy-load cards when section enters viewport
        const placeholder = section.querySelector('.tcg-set-cards-placeholder');
        this.observer.observe(placeholder);

        return section;
    }

    async _loadSetCards(setId, placeholderEl) {
        this.loadedSets.add(setId);
        try {
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'search_cards_by_set',
                    arguments: { set_id: setId, slim: true, limit: 8 }
                })
            });

            if (!response.ok) throw new Error('Failed');

            const data = await response.json();
            if (data.result && data.result.cards && data.result.cards.length > 0) {
                this._renderSetCards(placeholderEl, data.result.cards);

                // Stale-while-revalidate: refresh in background if stale
                if (data.result._cache_stale) {
                    this._revalidateSetCards(setId, placeholderEl);
                }
            } else {
                placeholderEl.innerHTML = '<div class="tcg-set-loading">No cards found</div>';
            }
        } catch (err) {
            console.warn(`Failed to load cards for set ${setId}:`, err);
            placeholderEl.innerHTML = '<div class="tcg-set-loading">Failed to load cards</div>';
        }
    }

    /** Background revalidation for stale expansion preview cards */
    async _revalidateSetCards(setId, placeholderEl) {
        console.log(`🔄 Revalidating stale set cards: ${setId}`);
        try {
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'search_cards_by_set',
                    arguments: { set_id: setId, slim: true, limit: 8, force_refresh: true }
                })
            });
            if (!response.ok) return;
            const data = await response.json();
            if (data?.result?.cards?.length > 0) {
                this._renderSetCards(placeholderEl, data.result.cards);
                console.log(`✅ Revalidated set ${setId}`);
            }
        } catch (err) {
            console.warn(`⚠️ Set revalidation failed for ${setId}:`, err);
        }
    }

    _renderSetCards(placeholderEl, cards) {
        // Show a preview row of cards (max 8), rest accessible via the more tile
        const previewCards = cards.slice(0, 8);
        const grid = document.createElement('div');
        grid.className = 'tcg-set-cards-row';

        // Resolve set info once for hover context and "+N more" count
        const setId = placeholderEl.dataset.setId;
        const setInfo = this.allSets.find(s => s.id === setId);
        const hoverSetName = setInfo?.name || setId || 'unknown set';

        previewCards.forEach((card, i) => {
            const cardEl = document.createElement('div');
            cardEl.className = 'tcg-db-card-item';
            cardEl.style.position = 'relative';
            const imageUrl = card.images?.small || card.imageSmall || '';
            const cardName = card.name || 'Unknown';

            cardEl.innerHTML = `
                <div class="card-index-badge">#${i + 1}</div>
                <img src="${imageUrl}" alt="${cardName}" loading="lazy">
                <span class="tcg-db-card-name">${cardName}</span>
            `;
            cardEl.addEventListener('click', () => {
                this.app.tcgDetail.show(card);
            });

            // Hover tracking for AI context
            cardEl.addEventListener('mouseenter', () => {
                this.app.updateHoverContext('tcg-card', `TCG card "${cardName}" from ${hoverSetName} (card_id: ${card.id})`, card.id);
            });
            cardEl.addEventListener('mouseleave', () => {
                this.app.clearHoverContext();
            });

            grid.appendChild(cardEl);
        });

        // Use set total from allSets for accurate "+N more" count
        const totalCards = setInfo?.total || cards.length;
        if (totalCards > 8) {
            const moreEl = document.createElement('div');
            moreEl.className = 'tcg-db-card-more';
            moreEl.textContent = `+${totalCards - 8} more`;
            moreEl.addEventListener('click', () => {
                const setId = placeholderEl.dataset.setId;
                const setSection = placeholderEl.closest('.tcg-set-section');
                const setName = setSection?.querySelector('.tcg-set-name')?.textContent || setId;
                this.app.tcgGallery.searchBySet(setId, setName);
            });
            grid.appendChild(moreEl);
        }

        placeholderEl.innerHTML = '';
        placeholderEl.appendChild(grid);
    }

    _sortSets(sets, sortBy) {
        const sorted = [...sets];
        switch (sortBy) {
            case 'release-asc':
                sorted.sort((a, b) => (a.releaseDate || '').localeCompare(b.releaseDate || ''));
                break;
            case 'name-asc':
                sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
                break;
            case 'name-desc':
                sorted.sort((a, b) => (b.name || '').localeCompare(a.name || ''));
                break;
            case 'cards-desc':
                sorted.sort((a, b) => (b.total || 0) - (a.total || 0));
                break;
            case 'release-desc':
            default:
                sorted.sort((a, b) => (b.releaseDate || '').localeCompare(a.releaseDate || ''));
                break;
        }
        return sorted;
    }

    /** Called from the TCG search panel to filter sets by name and/or selection */
    filterSets(query, selectedSets) {
        if (!this.cardList) return;
        const lcQuery = query.toLowerCase();
        const hasSetFilter = selectedSets && selectedSets.size > 0;
        const sections = this.cardList.querySelectorAll('.tcg-set-section');
        const separators = this.cardList.querySelectorAll('.tcg-series-separator');

        let visibleCount = 0;
        sections.forEach(section => {
            const setId = section.dataset.setId || '';
            const setName = section.querySelector('.tcg-set-name')?.textContent?.toLowerCase() || '';
            const series = section.dataset?.series || '';
            const matchesQuery = !lcQuery || setName.includes(lcQuery) || series.toLowerCase().includes(lcQuery);
            const matchesSet = !hasSetFilter || selectedSets.has(setId);
            const visible = matchesQuery && matchesSet;
            section.style.display = visible ? '' : 'none';
            if (visible) visibleCount++;
        });

        // Hide series separators if no visible sets in them
        separators.forEach(sep => {
            const label = sep.querySelector('.generation-label')?.textContent || '';
            let hasVisible = false;
            let next = sep.nextElementSibling;
            while (next && !next.classList.contains('tcg-series-separator')) {
                if (next.classList.contains('tcg-set-section') && next.style.display !== 'none') {
                    hasVisible = true;
                }
                next = next.nextElementSibling;
            }
            sep.style.display = hasVisible ? '' : 'none';
        });
    }

    /** Re-sort and re-render */
    changeSort(sortValue) {
        if (this.viewMode === 'all-cards') {
            this.cardSort = sortValue;
            this._renderCardGrid();
        } else {
            this.currentSort = sortValue;
            this._renderDatabase();
        }
    }

    // ========================================
    // All Cards Flat View
    // ========================================

    async _renderAllCardsView() {
        if (!this.cardList) return;
        this.cardList.innerHTML = '';

        if (this.viewMode === 'all-cards') {
            // Build expansion picker and grid container immediately (no await)
            this._buildExpansionPicker();
        }

        const grid = document.createElement('div');
        grid.className = 'tcg-all-cards-grid';
        grid.id = 'tcgAllCardsGrid';
        this.cardList.appendChild(grid);

        if (this.viewMode === 'collection') {
            this._loadDexLookup();
            this._renderCardGrid();
        } else if (this.allCards.length > 0) {
            // Already have cards — just load dex lookup in background for sorting
            this._loadDexLookup();
            this._renderCardGrid();
        } else {
            // First visit: load dex lookup + first expansion in parallel
            const newest = this._sortSets(this.allSets, 'release-desc')[0];
            const promises = [this._loadDexLookup()];
            if (newest) {
                promises.push(this._toggleSetSelection(newest.id, true));
            }
            await Promise.all(promises);
        }

        this._updateCardCount();
    }

    showMyCollection() {
        return this.toggleViewMode('collection');
    }

    /** Build the expansion picker checklist below the header */
    _buildExpansionPicker() {
        let picker = document.getElementById('tcgExpansionPicker');
        if (picker) picker.remove();

        picker = document.createElement('div');
        picker.className = 'tcg-expansion-picker';
        picker.id = 'tcgExpansionPicker';

        // Header row with toggle - entire header is clickable
        const header = document.createElement('div');
        header.className = 'tcg-expansion-picker-header';
        header.innerHTML = `
            <span class="tcg-expansion-picker-arrow" id="tcgPickerArrow">▸</span>
            <span class="tcg-expansion-picker-title">Expansions to load</span>
            <span class="tcg-expansion-picker-count" id="tcgPickerCount">${this._selectedSetIds.size} of ${this.allSets.length} selected</span>
        `;
        picker.appendChild(header);

        // Checklist (hidden by default)
        const list = document.createElement('div');
        list.className = 'tcg-expansion-picker-list';
        list.id = 'tcgPickerList';
        list.style.display = 'none';

        // Select All / Deselect All controls
        const bulkBar = document.createElement('div');
        bulkBar.className = 'tcg-picker-bulk-bar';
        bulkBar.innerHTML = `
            <button class="tcg-picker-bulk-btn" id="tcgPickerSelectAll">Select All</button>
            <button class="tcg-picker-bulk-btn" id="tcgPickerDeselectAll">Deselect All</button>
        `;
        list.appendChild(bulkBar);

        const sorted = this._sortSets(this.allSets, 'release-desc');
        list.innerHTML += sorted.map(set => {
            const year = set.releaseDate ? set.releaseDate.substring(0, 4) : '';
            const symbolUrl = set.images?.symbol || '';
            const checked = this._selectedSetIds.has(set.id) ? 'checked' : '';
            const loading = '';
            return `<label class="tcg-picker-item" data-set-id="${set.id}">
                <input type="checkbox" value="${set.id}" ${checked}>
                ${symbolUrl ? `<img src="${symbolUrl}" alt="" class="tcg-picker-symbol" loading="lazy">` : ''}
                <span class="tcg-picker-name">${set.name}</span>
                <span class="tcg-picker-year">${year}</span>
                <span class="tcg-picker-status" id="tcgPickerStatus-${set.id}"></span>
            </label>`;
        }).join('');
        picker.appendChild(list);

        // Insert before the card grid
        this.cardList.insertBefore(picker, this.cardList.firstChild);

        // Wire toggle - clicking anywhere on header toggles list
        header.addEventListener('click', () => {
            const visible = list.style.display !== 'none';
            list.style.display = visible ? 'none' : '';
            document.getElementById('tcgPickerArrow').textContent = visible ? '▸' : '▾';
            header.classList.toggle('expanded', !visible);
        });

        // Wire checkboxes
        list.addEventListener('change', async (e) => {
            if (e.target.type !== 'checkbox') return;
            const setId = e.target.value;
            const checked = e.target.checked;
            await this._toggleSetSelection(setId, checked);
        });

        // Wire Select All / Deselect All
        document.getElementById('tcgPickerSelectAll').addEventListener('click', async () => {
            const allSetIds = sorted.map(s => s.id);
            const toSelect = allSetIds.filter(id => !this._selectedSetIds.has(id));
            // Add ALL set IDs to _selectedSetIds first so _updatePickerCount keeps them checked
            allSetIds.forEach(id => this._selectedSetIds.add(id));
            list.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
            this._updatePickerCount();
            if (toSelect.length > 0) {
                await this._loadMultipleSets(toSelect);
            }
        });

        document.getElementById('tcgPickerDeselectAll').addEventListener('click', () => {
            list.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
            this._selectedSetIds.clear();
            this.allCards = [];
            this.loadedSetIds.clear();
            this.filteredCards = null;
            this._updateCardCount();
            this._renderCardGrid();
            this._updatePickerCount();
        });
    }

    /** Toggle a set on/off: load or unload its cards */
    async _toggleSetSelection(setId, selected) {
        if (selected) {
            this._selectedSetIds.add(setId);
            if (!this.loadedSetIds.has(setId)) {
                await this._loadSetCardsForAllCards(setId);
            }
        } else {
            this._selectedSetIds.delete(setId);
            // Remove cards from this set
            this.allCards = this.allCards.filter(c => (c.set?.id || '') !== setId);
            this.loadedSetIds.delete(setId);
        }

        this._reapplyActiveFilters();
        this._updateCardCount();
        this._renderCardGrid();
        this._updatePickerCount();
        this._syncFilterPanelExpansions();
    }

    /** Load cards for a single set into allCards */
    async _loadSetCardsForAllCards(setId) {
        // Show loading status
        const statusEl = document.getElementById(`tcgPickerStatus-${setId}`);
        if (statusEl) statusEl.textContent = '⏳';

        try {
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'search_cards_by_set',
                    arguments: { set_id: setId, slim: true }
                })
            });
            if (!response.ok) throw new Error('Failed');
            const data = await response.json();
            if (data?.result?.cards) {
                this.allCards = this.allCards.concat(data.result.cards);
                this.loadedSetIds.add(setId);

                // Stale-while-revalidate: refresh in background if stale
                if (data.result._cache_stale) {
                    this._revalidateAllCardsSet(setId, data.result.cards.length);
                }
            }
            if (statusEl) statusEl.textContent = '✓';
        } catch (err) {
            console.warn(`Failed to load cards for set ${setId}:`, err);
            if (statusEl) statusEl.textContent = '✗';
        }
    }

    /** Background revalidation for stale All Cards set data */
    async _revalidateAllCardsSet(setId, oldCount) {
        console.log(`🔄 Revalidating stale All Cards set: ${setId}`);
        try {
            const response = await fetch('/api/realtime/tool', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tool_name: 'search_cards_by_set',
                    arguments: { set_id: setId, slim: true, force_refresh: true }
                })
            });
            if (!response.ok) return;
            const data = await response.json();
            if (data?.result?.cards) {
                // Replace old cards for this set with fresh ones
                this.allCards = this.allCards.filter(c => (c.set?.id || '') !== setId);
                this.allCards = this.allCards.concat(data.result.cards);
                this._reapplyActiveFilters();
                this._updateCardCount();
                this._renderCardGrid();
                console.log(`✅ Revalidated All Cards set ${setId} (${oldCount} → ${data.result.cards.length} cards)`);
            }
        } catch (err) {
            console.warn(`⚠️ All Cards set revalidation failed for ${setId}:`, err);
        }
    }

    /** Load multiple sets at once (for batch selection) */
    async _loadMultipleSets(setIds) {
        this.isLoadingCards = true;
        const toLoad = setIds.filter(id => !this.loadedSetIds.has(id));

        for (let i = 0; i < toLoad.length; i += 5) {
            const batch = toLoad.slice(i, i + 5);
            const promises = batch.map(id => this._loadSetCardsForAllCards(id));
            await Promise.all(promises);
            this._reapplyActiveFilters();
            this._updateCardCount();
            this._renderCardGrid();
        }

        this.isLoadingCards = false;
        this._reapplyActiveFilters();
        this._updateCardCount();
        this._renderCardGrid();
        this._updatePickerCount();
    }

    /** Update the picker count label */
    _updatePickerCount() {
        const el = document.getElementById('tcgPickerCount');
        if (el) el.textContent = `${this._selectedSetIds.size} of ${this.allSets.length} selected`;

        // Update checkbox states in picker
        const list = document.getElementById('tcgPickerList');
        if (list) {
            list.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.checked = this._selectedSetIds.has(cb.value);
            });
        }
    }

    /** Sync the expansion checkboxes in the filter panel with our selection */
    _syncFilterPanelExpansions() {
        const searchView = this.app.searchView;
        if (!searchView) return;

        // Update PokemonSearchView's tcgSelectedSets
        searchView.tcgSelectedSets = new Set(this._selectedSetIds);

        // Update checkbox DOM in the filter panel
        const filterList = searchView.tcgExpansionList;
        if (filterList) {
            filterList.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.checked = this._selectedSetIds.has(cb.value);
            });
        }
    }

    /** Called from PokemonSearchView when user changes expansion checkboxes in the filter panel */
    syncFromFilterPanel(selectedSets) {
        const added = [...selectedSets].filter(id => !this._selectedSetIds.has(id));
        const removed = [...this._selectedSetIds].filter(id => !selectedSets.has(id));

        // Remove unselected sets
        removed.forEach(id => {
            this._selectedSetIds.delete(id);
            this.allCards = this.allCards.filter(c => (c.set?.id || '') !== id);
            this.loadedSetIds.delete(id);
        });

        // Add newly selected sets
        this._selectedSetIds = new Set(selectedSets);

        if (added.length > 0) {
            this._loadMultipleSets(added);
        } else {
            this._reapplyActiveFilters();
            this._updateCardCount();
            this._renderCardGrid();
            this._updatePickerCount();
        }
    }

    _updateCardCount() {
        const countEl = document.getElementById('tcgDbSetCount');
        if (!countEl) return;
        const display = this._getDisplayCards();
        if (this.viewMode === 'collection') {
            countEl.textContent = `${display.length} owned cards`;
        } else if (this.filteredCards !== null) {
            countEl.textContent = `${display.length} of ${this.allCards.length} cards`;
        } else {
            countEl.textContent = `${this.allCards.length} cards · ${this._selectedSetIds.size} expansions`;
        }

        // Keep AI context up to date when in All Cards mode
        if (this.viewMode === 'all-cards' || this.viewMode === 'collection') {
            this.app.updateCanvasState('tcg-database', {
                total_sets: this.allSets.length,
                viewMode: this.viewMode,
                selectedSets: this._selectedSetIds.size
            }, false);
        }
    }

    _getDisplayCards() {
        if (this.viewMode === 'collection') {
            const owned = this.app.cardCollection?.getOwnedCards?.() || [];
            return this.filteredCards !== null ? this.filteredCards : owned;
        }
        return this.filteredCards !== null ? this.filteredCards : this.allCards;
    }

    _getCardPrice(card) {
        const prices = card.tcgplayer?.prices || card.prices;
        if (!prices) return 0;
        for (const variant of Object.values(prices)) {
            if (variant?.market) return variant.market;
            if (variant?.mid) return variant.mid;
        }
        return 0;
    }

    /** Get the national dex number for a Pokemon card, or Infinity for non-Pokemon */
    _getCardDexNumber(card) {
        // First try the card's own nationalPokedexNumbers (new cache entries)
        const dex = card.nationalPokedexNumbers;
        if (dex && dex.length > 0) return dex[0];
        // Fallback: look up by name from Pokemon metadata
        if (this._dexLookup && card.supertype === 'Pokémon') {
            // Normalize: strip suffixes like " ex", " V", " VMAX", " GX", " EX", etc.
            const baseName = (card.name || '').toLowerCase()
                .replace(/\s+(ex|gx|vmax|vstar|v|lv\.\s*x|prime|break|δ)$/i, '')
                .replace(/[\s-]+/g, '-')
                .trim();
            const dexNum = this._dexLookup.get(baseName);
            if (dexNum) return dexNum;
        }
        return card.supertype === 'Pokémon' ? 99999 : Infinity;
    }

    /** Load the Pokemon name→dex# lookup from metadata endpoint */
    async _loadDexLookup() {
        if (this._dexLookup) return;
        try {
            const resp = await fetch('/api/pokemon/metadata');
            if (!resp.ok) return;
            const data = await resp.json();
            this._dexLookup = new Map();
            for (const [id, meta] of Object.entries(data)) {
                const name = (meta.name || '').toLowerCase().replace(/[\s-]+/g, '-');
                this._dexLookup.set(name, parseInt(id));
            }
            console.log(`🔢 Loaded dex lookup: ${this._dexLookup.size} Pokemon`);
        } catch (err) {
            console.warn('Failed to load dex lookup:', err);
        }
    }

    _sortCards(cards, sortBy) {
        const sorted = [...cards];
        switch (sortBy) {
            case 'number':
                sorted.sort((a, b) => {
                    const setA = a.set?.releaseDate || '';
                    const setB = b.set?.releaseDate || '';
                    const setCmp = setB.localeCompare(setA);
                    if (setCmp !== 0) return setCmp;
                    return (a.number || '').localeCompare(b.number || '', undefined, { numeric: true });
                });
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
                sorted.sort((a, b) => this._getCardPrice(b) - this._getCardPrice(a));
                break;
            case 'price-asc':
                sorted.sort((a, b) => this._getCardPrice(a) - this._getCardPrice(b));
                break;
            case 'set-asc':
                sorted.sort((a, b) => {
                    const dateA = a.set?.releaseDate || '';
                    const dateB = b.set?.releaseDate || '';
                    return dateA.localeCompare(dateB) || (a.number || '').localeCompare(b.number || '', undefined, { numeric: true });
                });
                break;
            case 'set-desc':
            default:
                sorted.sort((a, b) => {
                    const dateA = a.set?.releaseDate || '';
                    const dateB = b.set?.releaseDate || '';
                    return dateB.localeCompare(dateA) || (a.number || '').localeCompare(b.number || '', undefined, { numeric: true });
                });
                break;
        }
        return sorted;
    }

    _renderCardGrid() {
        const container = document.getElementById('tcgAllCardsGrid');
        if (!container) return;

        // Clean up previous observer
        if (this._gridObserver) {
            this._gridObserver.disconnect();
            this._gridObserver = null;
        }
        container.innerHTML = '';

        const cards = this._getDisplayCards();
        const sorted = this._sortCards(cards, this.cardSort);

        // Progressive rendering: render first batch immediately, rest via IntersectionObserver
        const BATCH_SIZE = 60;
        const grid = document.createElement('div');
        grid.className = 'tcg-all-cards-set-grid';

        // Store sorted cards for AI indexed access
        this._displayedCards = sorted;
        this.app.currentTcgCards = sorted;

        // Render first batch immediately
        const firstBatch = sorted.slice(0, BATCH_SIZE);
        firstBatch.forEach((card, i) => {
            grid.appendChild(this._createFlatCardElement(card, i + 1));
        });
        container.appendChild(grid);

        // If more cards, render remaining in batches as user scrolls
        if (sorted.length > BATCH_SIZE) {
            let rendered = BATCH_SIZE;
            const sentinel = document.createElement('div');
            sentinel.className = 'tcg-grid-sentinel';
            container.appendChild(sentinel);

            const observer = new IntersectionObserver((entries) => {
                if (entries[0].isIntersecting && rendered < sorted.length) {
                    const nextBatch = sorted.slice(rendered, rendered + BATCH_SIZE);
                    const fragment = document.createDocumentFragment();
                    nextBatch.forEach((card, i) => {
                        fragment.appendChild(this._createFlatCardElement(card, rendered + i + 1));
                    });
                    grid.appendChild(fragment);
                    rendered += nextBatch.length;

                    if (rendered >= sorted.length) {
                        observer.disconnect();
                        sentinel.remove();
                    }
                }
            }, { rootMargin: '600px' });
            observer.observe(sentinel);

            // Store observer reference for cleanup
            this._gridObserver = observer;
        }
    }

    /** Rarity rank: lower = more common */
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

    _createFlatCardElement(card, displayIndex) {
        const el = document.createElement('div');
        el.className = 'tcg-card-item';
        el.style.position = 'relative';

        const imageUrl = card.images?.small || card.imageSmall || '';
        const name = card.name || 'Unknown';
        const setName = card.set?.name || '';
        const price = this._getCardPrice(card);
        const cc = typeof CurrencyConverter !== 'undefined' ? CurrencyConverter : null;
        const priceStr = price > 0 ? (cc ? cc.formatUSD(price) : `$${price.toFixed(2)}`) : '';
        const priceColor = price > 0 && cc ? cc.getPriceColor(price) : '';
        const priceStyle = priceColor ? `style="color:${priceColor}"` : '';
        const rarity = card.rarity || '';
        const badge = displayIndex ? `<div class="card-index-badge">#${displayIndex}</div>` : '';
        const collectionCount = this.app.cardCollection?.getCardCount?.(card.id) || card._collectionCount || 0;

        el.classList.toggle('is-owned', collectionCount > 0);
        el.classList.toggle('is-unowned', collectionCount <= 0);

        el.innerHTML = `
            ${badge}
            <img src="${imageUrl}" alt="${name}" loading="lazy">
            <div class="tcg-collection-counter camera-summary-counter" data-card-id="${card.id}">
                <button class="tcg-collection-counter-btn" type="button" data-action="decrement" aria-label="Decrease ${name} count">−</button>
                <input class="tcg-collection-counter-input" type="number" min="0" value="${collectionCount}" aria-label="${name} owned count">
                <button class="tcg-collection-counter-btn" type="button" data-action="increment" aria-label="Increase ${name} count">+</button>
            </div>
            <div class="tcg-card-info">
                <span class="tcg-card-name">${name}</span>
                <span class="tcg-card-set-label">${setName}</span>
                ${priceStr || rarity ? `<span class="tcg-card-meta">${priceStr ? `<span class="tcg-card-price" ${priceStyle}>${priceStr}</span>` : ''}${priceStr && rarity ? ' · ' : ''}${rarity}</span>` : ''}
                ${collectionCount > 0 ? `<span class="tcg-card-collection-tag">Owned: ${collectionCount}</span>` : ''}
            </div>
        `;

        const counter = el.querySelector('.tcg-collection-counter');
        const input = el.querySelector('.tcg-collection-counter-input');
        const applyCount = (nextValue) => {
            const safeValue = Math.max(0, Number(nextValue) || 0);
            this.app.cardCollection?.setCardCount?.(card, safeValue);
            if (input) input.value = safeValue;
            el.classList.toggle('is-owned', safeValue > 0);
            el.classList.toggle('is-unowned', safeValue <= 0);
            const ownedTag = el.querySelector('.tcg-card-collection-tag');
            if (safeValue > 0) {
                if (ownedTag) {
                    ownedTag.textContent = `Owned: ${safeValue}`;
                } else {
                    el.querySelector('.tcg-card-info')?.insertAdjacentHTML('beforeend', `<span class="tcg-card-collection-tag">Owned: ${safeValue}</span>`);
                }
            } else if (ownedTag) {
                ownedTag.remove();
            }
            if (this.viewMode === 'collection') {
                this._renderCardGrid();
            }
        };

        counter?.addEventListener('click', (event) => {
            event.stopPropagation();
            const action = event.target?.dataset?.action;
            if (!action) return;
            const currentValue = Number(input?.value || collectionCount || 0);
            applyCount(action === 'increment' ? currentValue + 1 : currentValue - 1);
        });

        input?.addEventListener('click', event => event.stopPropagation());
        input?.addEventListener('change', (event) => {
            event.stopPropagation();
            applyCount(event.target.value);
        });
        input?.addEventListener('keydown', (event) => event.stopPropagation());

        el.addEventListener('click', async () => {
            // Fetch full card details for the detail view
            try {
                const resp = await fetch('/api/realtime/tool', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tool_name: 'get_card_details', arguments: { card_id: card.id } })
                });
                if (resp.ok) {
                    const data = await resp.json();
                    if (data?.result) {
                        this.app.tcgDetail.show(data.result);
                        return;
                    }
                }
            } catch (err) {
                console.warn('Failed to fetch card details, using slim data:', err);
            }
            // Fallback to slim data
            this.app.tcgDetail.show(card);
        });

        // Hover tracking for AI context
        el.addEventListener('mouseenter', () => {
            const hoverParts = [`TCG card #${displayIndex} "${name}"`];
            if (setName) hoverParts.push(`from ${setName}`);
            if (priceStr) hoverParts.push(`price ${priceStr}`);
            if (rarity) hoverParts.push(`(${rarity})`);
            hoverParts.push(`(card_id: ${card.id})`);
            this.app.updateHoverContext('tcg-card', hoverParts.join(' '), card.id);
        });
        el.addEventListener('mouseleave', () => {
            this.app.clearHoverContext();
        });

        return el;
    }

    refreshCollectionState() {
        if (this.viewMode === 'all-cards' || this.viewMode === 'collection') {
            this._reapplyActiveFilters();
            this._updateCardCount();
            this._renderCardGrid();
        }
    }

    /** Filter cards by criteria from the search panel */
    filterCards(filters) {
        // Remember filters so they can be re-applied when expansions change
        this._activeFilters = filters;
        const sourceCards = this.viewMode === 'collection'
            ? (this.app.cardCollection?.getOwnedCards?.() || [])
            : this.allCards;

        if (!filters || (!filters.name && !filters.types?.size && !filters.categories?.size && !filters.priceMin && !filters.priceMax && !filters.rarity)) {
            this.filteredCards = null;
        } else {
            this.filteredCards = sourceCards.filter(card => {
                // Name filter
                if (filters.name) {
                    const name = (card.name || '').toLowerCase();
                    const setName = (card.set?.name || '').toLowerCase();
                    if (!name.includes(filters.name) && !setName.includes(filters.name)) return false;
                }
                // Category filter (supertype + subtypes)
                if (filters.categories?.size > 0) {
                    const supertype = card.supertype || '';
                    const subtypes = card.subtypes || [];
                    const matchesSupertype = filters.categories.has(supertype);
                    const matchesSubtype = subtypes.some(st => filters.categories.has(st));
                    if (!matchesSupertype && !matchesSubtype) return false;
                }
                // Energy type filter
                if (filters.types?.size > 0) {
                    const cardTypes = card.types || [];
                    if (!cardTypes.some(t => filters.types.has(t))) return false;
                }
                // Price range filter (user enters in display currency, card price is USD)
                const rawPrice = this._getCardPrice(card);
                const cc = typeof CurrencyConverter !== 'undefined' ? CurrencyConverter : null;
                const displayPrice = cc ? cc.fromUSD(rawPrice) : rawPrice;
                if (filters.priceMin && displayPrice < parseFloat(filters.priceMin)) return false;
                if (filters.priceMax && displayPrice > parseFloat(filters.priceMax)) return false;
                // Rarity filter
                if (filters.rarity && card.rarity !== filters.rarity) return false;
                return true;
            });
        }

        this._updateCardCount();
        this._renderCardGrid();
    }

    /** Re-apply the last active filters after the card pool changes (expansion add/remove) */
    _reapplyActiveFilters() {
        if (this._activeFilters) {
            // Re-run filterCards logic without re-saving (already saved)
            const filters = this._activeFilters;
            const sourceCards = this.viewMode === 'collection'
                ? (this.app.cardCollection?.getOwnedCards?.() || [])
                : this.allCards;
            if (!filters.name && !filters.types?.size && !filters.categories?.size && !filters.priceMin && !filters.priceMax && !filters.rarity) {
                this.filteredCards = null;
            } else {
                this.filteredCards = sourceCards.filter(card => {
                    if (filters.name) {
                        const name = (card.name || '').toLowerCase();
                        const setName = (card.set?.name || '').toLowerCase();
                        if (!name.includes(filters.name) && !setName.includes(filters.name)) return false;
                    }
                    if (filters.categories?.size > 0) {
                        const supertype = card.supertype || '';
                        const subtypes = card.subtypes || [];
                        if (!filters.categories.has(supertype) && !subtypes.some(st => filters.categories.has(st))) return false;
                    }
                    if (filters.types?.size > 0) {
                        const cardTypes = card.types || [];
                        if (!cardTypes.some(t => filters.types.has(t))) return false;
                    }
                    const rawPrice = this._getCardPrice(card);
                    const cc = typeof CurrencyConverter !== 'undefined' ? CurrencyConverter : null;
                    const displayPrice = cc ? cc.fromUSD(rawPrice) : rawPrice;
                    if (filters.priceMin && displayPrice < parseFloat(filters.priceMin)) return false;
                    if (filters.priceMax && displayPrice > parseFloat(filters.priceMax)) return false;
                    if (filters.rarity && card.rarity !== filters.rarity) return false;
                    return true;
                });
            }
        } else {
            this.filteredCards = null;
        }
    }
}
