/**
 * TCG Cards Gallery View - Displays a grid of Pokemon trading cards
 */
class TcgCardsGalleryView {
    constructor(app) {
        this.app = app;
        this.galleryView = document.getElementById('tcgCardsView');
    }

    display(tcgData) {
        console.log('🃏 displayTcgCardsInCanvas called with:', tcgData);
        
        if (!tcgData || !tcgData.cards || !Array.isArray(tcgData.cards) || tcgData.cards.length === 0) {
            console.error('❌ Invalid TCG data:', tcgData);
            return;
        }
        
        console.log('✅ Valid TCG data with', tcgData.cards.length, 'cards');
        
        // Store for forward navigation
        this.app.currentTcgData = tcgData;
        
        // Hide other views
        this.app.pokemonGridView.style.display = 'none';
        this.app.pokemonDetailView.style.display = 'none';
        
        // Show TCG cards view
        this.galleryView.style.display = 'block';
        
        this.renderCards(tcgData);
        
        // Update canvas state for TCG gallery
        this.app.updateCanvasState('tcg-gallery', {
            pokemon_name: tcgData.search_query || tcgData.pokemon_name || 'Pokemon',
            cards: tcgData.cards,
            total_count: tcgData.total_count
        });
        
        // Scroll to top
        this.galleryView.scrollTop = 0;
        console.log('✅ TCG cards view updated and displayed');
    }

    displayWithoutHistory(tcgData) {
        console.log('🃏 displayTcgCardsInCanvasWithoutHistory called');
        
        if (!tcgData || !tcgData.cards || !Array.isArray(tcgData.cards) || tcgData.cards.length === 0) {
            return;
        }
        
        // Update canvas state for TCG gallery (without adding to history)
        this.app.updateCanvasState('tcg-gallery', {
            pokemon_name: tcgData.search_query || tcgData.pokemon_name || 'Pokemon',
            cards: tcgData.cards,
            total_count: tcgData.total_count
        }, false);
        
        // Hide other views
        this.app.pokemonGridView.style.display = 'none';
        this.app.pokemonDetailView.style.display = 'none';
        this.galleryView.style.display = 'block';
        
        this.renderCards(tcgData);
    }

    renderCards(tcgData) {
        // Clear existing content
        this.galleryView.innerHTML = '';
        
        // Create header without back button
        const header = document.createElement('div');
        header.className = 'tcg-canvas-header';
        header.innerHTML = `
            <div class="tcg-canvas-title">
                <h1>🃏 Trading Card Gallery</h1>
                <p>${tcgData.total_count || tcgData.cards.length} cards found</p>
            </div>
        `;
        this.galleryView.appendChild(header);
        
        // Create cards grid
        const cardsGrid = document.createElement('div');
        cardsGrid.className = 'tcg-cards-grid';
        
        tcgData.cards.forEach(card => {
            const cardDiv = this.createCardElement(card);
            cardsGrid.appendChild(cardDiv);
        });
        
        console.log('✅ Created', cardsGrid.children.length, 'card elements');
        this.galleryView.appendChild(cardsGrid);
    }

    createCardElement(card) {
        const cardDiv = document.createElement('div');
        cardDiv.className = 'tcg-card-item';
        
        const imageUrl = card.images?.small || card.imageSmall || card.images?.large || card.image;
        const cardName = card.name || 'Unknown';
        const setInfo = card.set?.name || card.set || '';
        
        cardDiv.innerHTML = `
            <img src="${imageUrl}" alt="${cardName}" loading="lazy">
            <div class="tcg-card-info">
                <h3>${cardName}</h3>
                ${setInfo ? `<p class="tcg-card-set">${setInfo}</p>` : ''}
            </div>
        `;
        
        cardDiv.addEventListener('click', () => {
            this.app.tcgDetail.show(card);
        });
        
        return cardDiv;
    }
}
