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
        this._setupLazyObserver();
    }

    /** IntersectionObserver to lazy-load set cards when set section scrolls into view */
    _setupLazyObserver() {
        this.observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const setId = entry.target.dataset.setId;
                    if (setId && !this.loadedSets.has(setId)) {
                        this._loadSetCards(setId, entry.target);
                    }
                    this.observer.unobserve(entry.target);
                }
            });
        }, { rootMargin: '400px' });
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

    async show() {
        this._hideOtherViews();
        this.databaseView.style.display = 'block';

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
            return; // Already loaded
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
                <button class="tcg-set-browse-btn" data-set-id="${set.id}" data-set-name="${set.name}" title="Browse all cards">
                    Browse →
                </button>
            </div>
            <div class="tcg-set-cards-placeholder" data-set-id="${set.id}">
                <div class="tcg-set-loading">Loading cards...</div>
            </div>
        `;

        // Browse button → open full gallery for this set
        const browseBtn = section.querySelector('.tcg-set-browse-btn');
        browseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.app.tcgGallery.searchBySet(set.id, set.name);
        });

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
                    arguments: { set_id: setId }
                })
            });

            if (!response.ok) throw new Error('Failed');

            const data = await response.json();
            if (data.result && data.result.cards && data.result.cards.length > 0) {
                this._renderSetCards(placeholderEl, data.result.cards);
            } else {
                placeholderEl.innerHTML = '<div class="tcg-set-loading">No cards found</div>';
            }
        } catch (err) {
            console.warn(`Failed to load cards for set ${setId}:`, err);
            placeholderEl.innerHTML = '<div class="tcg-set-loading">Failed to load cards</div>';
        }
    }

    _renderSetCards(placeholderEl, cards) {
        // Show a preview row of cards (max 8), rest accessible via Browse
        const previewCards = cards.slice(0, 8);
        const grid = document.createElement('div');
        grid.className = 'tcg-set-cards-row';

        previewCards.forEach(card => {
            const cardEl = document.createElement('div');
            cardEl.className = 'tcg-db-card-item';
            const imageUrl = card.images?.small || card.imageSmall || '';
            const cardName = card.name || 'Unknown';

            cardEl.innerHTML = `
                <img src="${imageUrl}" alt="${cardName}" loading="lazy">
                <span class="tcg-db-card-name">${cardName}</span>
            `;
            cardEl.addEventListener('click', () => {
                this.app.tcgDetail.show(card);
            });
            grid.appendChild(cardEl);
        });

        if (cards.length > 8) {
            const moreEl = document.createElement('div');
            moreEl.className = 'tcg-db-card-more';
            moreEl.textContent = `+${cards.length - 8} more`;
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

    /** Called from the TCG search panel to filter sets by name */
    filterSets(query) {
        if (!this.cardList) return;
        const lcQuery = query.toLowerCase();
        const sections = this.cardList.querySelectorAll('.tcg-set-section');
        const separators = this.cardList.querySelectorAll('.tcg-series-separator');

        let visibleCount = 0;
        sections.forEach(section => {
            const setName = section.querySelector('.tcg-set-name')?.textContent?.toLowerCase() || '';
            const series = section.dataset?.series || '';
            const visible = !lcQuery || setName.includes(lcQuery) || series.toLowerCase().includes(lcQuery);
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
        this.currentSort = sortValue;
        this._renderDatabase();
    }
}
