# Architecture

## Stale-While-Revalidate Caching

The entire app follows a **stale-while-revalidate** caching pattern. Cached data is served instantly, even if expired. If stale, a background refresh runs silently and re-renders only if data changed.

### Flow

```
Request → Cache hit?
  ├─ FRESH  → Return data immediately
  ├─ STALE  → Return data immediately + trigger background refresh
  └─ MISS   → Fetch from API → cache → return
```

### Backend (`CacheService`)

- File-based JSON cache in `/cache/` directory
- `get_with_stale(tool_name, params)` returns `(data, status)` where status is `'hit'`, `'stale'`, or `'miss'`
- Stale responses get `_cache_stale: true` injected into the response dict
- `force_refresh: true` in tool arguments bypasses cache entirely
- TTL configured in `cache/cache_config.json` (`expiry_days`, default: 7)
- Cache keys are hashed from tool name + params, filenames are descriptive

### Frontend Revalidation

Each view handles its own background revalidation:

| View | Stale Signal | Revalidation Method | Re-render |
|------|-------------|---------------------|-----------|
| Pokemon Detail | `X-PokeAPI-Stale` header | `_revalidateAndRerender()` | `updateDisplay()` without history |
| TCG Gallery Search | `_cache_stale` flag | `_revalidateTcgSearch()` | `displayWithoutHistory()` |
| TCG Database – Sets list | `_cache_stale` flag | `_revalidateSets()` | `_renderDatabase()` |
| TCG Database – Expansion previews | `_cache_stale` flag | `_revalidateSetCards()` | `_renderSetCards()` |
| TCG Database – All Cards | `_cache_stale` flag | `_revalidateAllCardsSet()` | `_renderCardGrid()` |
| TCG Card Details | `_cache_stale` flag | Fetches full details on click | N/A (detail shown fresh) |

### Pattern for New Features

When adding cached data flows:

1. **Backend handler**: Use `cache_service.get_with_stale()` instead of `get()`
2. **Set stale flag**: When `cache_status == 'stale'`, add `response['_cache_stale'] = True`
3. **Frontend**: After rendering stale data, check for `_cache_stale` and re-fetch with `force_refresh: true`
4. **Silent re-render**: Only update UI if fresh data differs from stale (compare JSON)
5. **No history**: Use `WithoutHistory` variants or `addToHistory=false` for background re-renders

### Cache Management Endpoints

```
GET  /api/cache/config      → Current config + stats
POST /api/cache/enable      → Toggle all caching
POST /api/cache/pokeapi     → Toggle PokeAPI cache
POST /api/cache/tcg         → Toggle TCG cache
POST /api/cache/expiry      → Set expiry days (0-90)
POST /api/cache/clear       → Delete all cache files
POST /api/cache/invalidate  → Delete specific cache entry
```

---

## Slim Payloads

For grid/list views that display many cards, the backend supports a `slim: true` parameter that strips unnecessary fields (attacks, abilities, legalities, cardmarket data, etc.) and returns only what's needed for display, sorting, and filtering.

- **Full card**: ~8KB (id, name, attacks, abilities, weaknesses, resistances, legalities, tcgplayer, cardmarket, etc.)
- **Slim card**: ~1.7KB (id, name, number, supertype, subtypes, types, rarity, nationalPokedexNumbers, small image, set basics, market/mid prices)
- **Reduction**: ~78-80%

Detail views fetch full card data on click via `get_card_details`.

---

## Progressive Rendering

The All Cards grid uses progressive DOM rendering to avoid jank with 1000+ cards:

1. First batch of 60 cards rendered immediately
2. IntersectionObserver watches a sentinel element
3. As user scrolls near bottom (600px margin), next batch of 60 appended
4. Observer disconnects when all cards rendered

---

## PokeAPI Proxy & Fair Use

All PokeAPI calls go through the Flask proxy at `/api/pokemon/*` which caches responses locally:

- `GET /api/pokemon/<name_or_id>` → Pokemon data
- `GET /api/pokemon/species/<name_or_id>` → Species data
- `GET /api/pokemon/type/<type_name>` → Type data
- `GET /api/pokemon/evolution-chain/<chain_id>` → Evolution chain
- `?refresh=1` query param bypasses cache
- Response header `X-PokeAPI-Stale: true` signals stale data to frontend

---

## Canvas Context & Navigation

See the main instructions file (`.github/instructions/instructions.instructions.md`) for the `updateCanvasState()` system that manages:
- GPT realtime context injection
- Navigation history (back/forward)
- View key deduplication

---

## URL Routing & Virtual Pages

The app is a **single-page application** with URL support for every virtual page. Users can bookmark, share, and refresh any view without losing state.

### SPA Catch-All (Flask)

Three Flask routes in `app.py` serve the same `index.html` shell:

```python
@app.route('/')
@app.route('/pokemon/<path:subpath>')
@app.route('/tcg/<path:subpath>')
def index(subpath=None):
    return render_template('index.html')
```

### URL Patterns

| View | Canvas Type | URL Pattern | View Key | Example |
|------|-------------|-------------|----------|---------|
| Pokemon Grid | `grid` | `/` | `grid` | `/` |
| Pokemon Detail | `pokemon` | `/pokemon/{name}` | `pokemon-{id}` | `/pokemon/pikachu` |
| TCG Gallery (by Pokemon) | `tcg-gallery` | `/pokemon/{name}/cards` | `tcg` | `/pokemon/charizard/cards` |
| TCG Gallery (by Set) | `tcg-gallery` | `/tcg/set/{setId}` | `tcg` | `/tcg/set/sv3pt5` |
| TCG Card Detail | `tcg-detail` | `/tcg/{cardId}` | `tcg-detail-{cardId}` | `/tcg/sv3pt5-25` |
| TCG Database | `tcg-database` | `/tcg/database` | `tcg-database` | `/tcg/database` |

### How It Works

#### Page Load: `routeFromUrl()`

Called once in the `app.js` constructor. Reads `window.location.pathname`, matches against the URL patterns above, and renders the correct view. Sets `_suppressPushState = true` during load so `updateCanvasState()` won't push a duplicate history entry, then calls `history.replaceState()` to set the correct state object.

#### View Navigation → URL Update

```
View.show()
  → app.updateCanvasState(type, data)
      ├── buildViewKey(type, data)     → deduplicate history entries
      ├── viewHistory[] push           → internal back/forward tracking
      ├── buildUrl(type, data)         → compute URL path
      ├── history.pushState(state, '', url)  → update browser URL bar
      ├── buildCanvasContextDescription()    → GPT realtime context
      └── updateNavigationButtons()          → enable/disable back/forward
```

`buildUrl()` in `app.js` maps canvas types to URL paths:
- `grid` → `/`
- `pokemon` → `/pokemon/{name}`
- `tcg-gallery` → `/tcg/set/{setId}` or `/pokemon/{name}/cards`
- `tcg-detail` → `/tcg/{cardId}`
- `tcg-database` → `/tcg/database`

#### Browser Back/Forward: `handlePopState()`

Listens to `window.popstate`. Re-reads `window.location.pathname` and renders the matching view using `*WithoutHistory` variants (to avoid re-pushing history entries).

### Dual Navigation System

Two parallel systems are kept in sync:

1. **Browser history** (`pushState` / `popstate`) — real browser back/forward, URL bar updates
2. **Internal `viewHistory[]` array** — powers the app's custom back/forward footer buttons via `navigateBack()` / `navigateForward()`, uses `replaceState` to sync URLs

Both are managed centrally through `updateCanvasState()`.

### Adding a New Virtual Page

1. **Flask**: Add catch-all route if the URL prefix is new (existing `/pokemon/` and `/tcg/` prefixes are already covered)
2. **`buildUrl()`**: Map the new canvas type → URL path
3. **`routeFromUrl()`**: Add regex match for the new path → call the view's `show()` method
4. **`handlePopState()`**: Add the same match → call the view's `showWithoutHistory()` method
5. **`navigateBack()` / `navigateForward()`**: Add restoration logic using the view key
6. **`buildViewKey()`**: Define a unique key pattern for deduplication
7. **`buildCanvasContextDescription()`**: Add a description for GPT realtime context
