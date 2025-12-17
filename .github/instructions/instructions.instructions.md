---
applyTo: '**'
---
Always at the end of the response tell developer to either refresh or restart the server.

## Project Architecture

This project follows a **modular, organized structure** to maintain clarity and scalability. All code is split by responsibility and feature area.

### Frontend Structure (JavaScript)

Located in `static/js/`:

- **app.js** - Main application controller (47 lines)
  - Instantiates view classes
  - Delegates rendering to view modules
  - Manages application state and routing

- **views/** - Modular view classes (~100-220 lines each)
  - `PokemonGridView.js` - Grid display, card creation
  - `PokemonDetailView.js` - Pokemon detail page rendering
  - `TcgCardsGalleryView.js` - TCG gallery rendering
  - `TcgCardDetailView.js` - Individual card details with pricing

**Frontend Guidelines:**
- Keep view classes focused on a single responsibility
- Delegate complex rendering logic to view methods
- Target ~100-200 lines per view file
- Add new views as separate files in `static/js/views/`

### Backend Structure (Python)

#### Flask Routes - `src/routes/`
Organized by feature area (~100-280 lines each):

- **chat_routes.py** - Chat endpoints (`/api/chat`, `/api/chat/stream`, `/api/history`)
- **realtime_routes.py** - WebSocket/realtime endpoints (`/api/realtime/*`)
- **tool_routes.py** - Tool CRUD operations (`/api/tools`)
- **cache_routes.py** - Cache management (`/api/cache/*`)
- **face_routes.py** - Face recognition endpoints (`/api/face/*`)

#### Tool Handlers - `src/tools/handlers/`
Organized by API category (~130-190 lines each):

- **pokemon_handlers.py** - PokeAPI tool handlers
- **tcg_handlers.py** - Pokemon TCG API tool handlers
- **formatters.py** - Shared data formatting utilities

#### Main Application - `app.py`
Simplified entry point (47 lines):
- Blueprint registration only
- Configuration setup
- No business logic

**Backend Guidelines:**
- Keep route files under 300 lines
- Group related endpoints into blueprints
- Extract shared logic into utilities/formatters
- Tool handlers should focus on single API integration
- Use `src/tools/tool_handlers.py` as dispatcher (imports handlers)

### CSS Architecture

The project uses **modular CSS files** for better organization and maintainability:

- **base.css** - CSS variables, reset, foundational styles
- **header.css** - App header, power lights, voice/camera buttons
- **chat.css** - Chat container, messages, bubbles, input, sidebar
- **pokemon.css** - Pokemon grid, detail views, type colors, stats
- **tcg.css** - TCG cards display, detail views, prices, canvas layouts
- **components.css** - Loading indicators, modals, toasts, toggles, help
- **layout.css** - Main canvas, forward button, responsive layouts
- **footer.css** - Footer navigation, action buttons

### CSS Guidelines:
- **ALWAYS use these modular CSS files** instead of creating new ones
- **Reuse existing classes** whenever possible before creating new styles
- Add new styles to the appropriate modular file based on the component/feature
- If unsure which file to use, follow this logic:
  - Header-related → `header.css`
  - Chat/messaging → `chat.css`
  - Pokemon-specific → `pokemon.css`
  - TCG cards → `tcg.css`
  - Modals, toasts, buttons, toggles → `components.css`
  - Layout/canvas → `layout.css`
  - Footer → `footer.css`
- Maintain the existing naming conventions and organization patterns
- The old `style.css` file should NOT be modified or imported

## Canvas Context & Navigation Management

The app uses a **centralized system** for both GPT realtime context updates AND navigation history management through the `updateCanvasState()` method.

### Core Principle:
**Every view change MUST call `updateCanvasState(type, data, addToHistory)`** - this single method handles:
1. Context injection for GPT realtime (so it knows what user is viewing)
2. Navigation history tracking (for back/forward buttons)
3. History logging for debugging

### Implementation Pattern:
```javascript
// When showing a new screen (with history):
this.app.updateCanvasState('your-screen-type', yourData);

// When restoring from history (without adding to history):
this.app.updateCanvasState('your-screen-type', yourData, false);

// Define view key in buildViewKey() (in app.js):
case 'your-screen-type':
    return data?.id ? `your-screen-${data.id}` : 'your-screen';

// Add context description in buildCanvasContextDescription() (in app.js):
case 'your-screen-type':
    return "User is viewing [description of screen]...";

// Add forward navigation in navigateForward() (in app.js):
} else if (view.startsWith('your-screen-')) {
    // Extract ID and restore view
    const id = view.replace('your-screen-', '');
    await this.yourView.show(dataWithId);
}

// Add backward navigation in navigateBack() (in app.js):
} else if (view.startsWith('your-screen-')) {
    // Extract ID and restore view
    const id = view.replace('your-screen-', '');
    await this.yourView.show(dataWithId);
}
```

**CRITICAL**: When adding new canvas pages, you MUST:
1. Call `updateCanvasState()` in your view's show method (adds to history automatically)
2. Add view key mapping in `buildViewKey()` (for unique history entries)
3. Add context description in `buildCanvasContextDescription()` (for GPT realtime)
4. Add navigation logic in BOTH `navigateForward()` AND `navigateBack()` (for back/forward buttons)
5. If using `await` in navigation, mark the navigation functions as `async`

### Existing Canvas Types:
- `grid` - Pokemon index/grid view (key: `'grid'`)
- `pokemon` - Pokemon detail view (key: `'pokemon-{id}'`)
- `tcg-gallery` - TCG cards gallery view (key: `'tcg'`)
- `tcg-detail` - Individual TCG card detail view (key: `'tcg-detail-{cardId}'`)

### Benefits:
- **Automatic history tracking** - No need to manually manage viewHistory in each view
- **Consistent navigation** - Back/forward buttons work automatically
- **Scalable** - Add new views by just calling updateCanvasState
- **Debug logging** - See history changes: `📚 History updated: [grid → pokemon-25 → tcg] (index: 2)`
- **GPT context sync** - Realtime API always knows current view

### Important Notes:
- View classes should NEVER directly modify `viewHistory` or `currentViewIndex`
- Use `addToHistory=false` when restoring from navigation (back/forward)
- Always define unique view keys in `buildViewKey()` to prevent duplicate history entries
- History automatically truncates forward entries when user navigates to a new view
- **IMPORTANT**: If `navigateForward()` or `navigateBack()` use `await`, they must be declared as `async` functions

## PokéAPI Fair Use & Caching

- **Never call `https://pokeapi.co` directly from the frontend or backend helpers.** All live Pokémon data must flow through the Flask proxy blueprint mounted at `/api/pokemon/*` so we can cache every response locally and comply with PokéAPI’s “locally cache resources whenever you request them” policy.
- The proxy already exposes `GET /api/pokemon/<name_or_id>`, `/species/<name_or_id>`, `/type/<type_name>`, and `/evolution-chain/<chain_id>` and transparently stores results via `CacheService`. Add new proxy endpoints (instead of raw fetches) if you need more PokéAPI resources.
- Use the `?refresh=1` query string when you intentionally want to bypass the cache (force refresh buttons, admin workflows, etc.). Do **not** delete cache files manually.
- Keep proxy routes lightweight (<300 lines) and reuse shared helpers for cache key generation so filenames stay descriptive in the `/cache` directory.