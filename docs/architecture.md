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

## Local Card Collection Store

Owned card data is stored entirely in the browser via `localStorage` using the `CardCollectionStore` helper (`static/js/card-collection.js`).

- `cards` map stores normalized card snapshots keyed by card ID plus the owned count
- `history` stores recent accepted scanner events so the scanner modal can show removable scan history
- TCG database counters update the same store directly, so scanner saves, My Collection, and inline count editing stay in sync
- Settings export/import simply serialize and restore this local JSON payload

---

## TCG Scanner Image Matching

The collection scanner uses a two-stage match so visual variants can be distinguished without losing reliable text clues:

1. `app.js` asks the realtime model for printed details: card name, Pokemon, set, card number, HP, type, rarity, and visible attack names.
2. `findBestMatchingCard()` searches TCG candidates and scores those printed fields locally.
3. The top candidates are sent with the captured frame to `POST /api/tcg/image-match`.
4. `tcg_image_routes.py` fetches official candidate card images server-side and compares them to the camera frame with Pillow-based average hash, difference hash, edge hash, and color signature scores.
5. The frontend blends the visual score with the printed-detail score and displays the selected card with a visual confidence percentage.

This route exists server-side so browser canvas security rules do not block comparisons against remote card images.

The standalone POC at `/static/tyrantrum-embedding-poc.html` uses `GET /api/tcg/image-proxy?url=...` to load official card images into a browser canvas, builds local grayscale/color image embeddings, starts the camera by default, and shows a live lightbox alignment zone over the camera feed. The default scan zone uses a narrower card-like ratio, and the user can drag its yellow edges to resize the crop area. Snapshot matching captures the camera frame and crops the current guide area at its visible proportions, then uses that cropped image for the browser image-embedding ranking pipeline. It can run in either cosine-only mode or rerank mode, with rerank mode selected by default. Rerank mode sends the cropped card image to `POST /api/tcg/extract-card-text`, where the configured Azure OpenAI vision model extracts structured card metadata: name, HP, card types, set/number, rarity, attacks, attack energy costs, weakness, resistance, and retreat. The browser scores those extracted attributes against candidate card metadata using weighted field matching, combines the attribute score with image cosine similarity as `image_embedding * 0.58 + text * 0.42`, then calls `POST /api/tcg/rerank-match` so an Azure OpenAI judge can rerank the candidates with the same structured evidence. The UI exposes candidate metadata and score calculation tooltips. If API settings are missing or the judge fails, the endpoint returns the deterministic combined-score order.

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

## Shared Tool Registry

All AI tools (for both text chat and realtime voice) are defined in a **single shared registry**: `src/tools/tool_definitions.py`. This guarantees that both APIs always have identical capabilities.

### Why

Previously, tools were defined separately in `azure_openai_chat.py` (text chat) and `realtime_chat.py` (voice), leading to drift where voice had tools that text chat lacked. The shared registry eliminates this.

### Structure

Each tool in `TOOL_DEFINITIONS` has:
- `name` — tool function name
- `description` — what the AI sees
- `parameters` — JSON Schema for arguments
- `handler_type` — `"backend"` (server-side data) or `"frontend"` (client-side UI action)

### Format Converters

The two APIs need different JSON shapes:
- `get_tools_chat_completions_format()` → `{"type": "function", "function": {"name": ...}}` for Chat Completions API
- `get_tools_realtime_format()` → `{"type": "function", "name": ...}` for Realtime API

### Tool Execution Flow

```
Text Chat:
  User message → azure_openai_chat.py (tools from registry)
    → LLM picks tool → chat_routes.py handler
    → Backend tool: execute_tool() → return data
    → Frontend tool: return {_action: "name", ...} → frontend_actions[]
    → app.js executeFrontendAction() dispatches UI action

Realtime Voice:
  User speech → realtime_chat.py (tools from registry)
    → LLM picks tool → realtime-voice.js executeToolCall()
    → Backend tool: POST /api/realtime/tool → return data
    → Frontend tool: call window.* function directly
```

### Adding a New Tool

1. Add to `TOOL_DEFINITIONS` in `src/tools/tool_definitions.py`
2. If backend: add handler in `src/routes/chat_routes.py` tool_handlers dict + `src/tools/tool_handlers.py`
3. If frontend: add case in `executeFrontendAction()` (app.js) AND in `realtime-voice.js` executeToolCall()
4. Both APIs auto-pick up the definition — no edits to `azure_openai_chat.py` or `realtime_chat.py`

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

---

## Shared Context Resources (Text Chat ↔ Realtime Voice)

The text chat (Chat Completions API) and realtime voice (Realtime API) share **all** context resources through a single source of truth. This guarantees both interfaces behave identically and stay in sync.

### Shared Resource Map

| Resource | Source of Truth | Text Chat Consumer | Voice Consumer |
|----------|----------------|-------------------|----------------|
| Tools | `tool_definitions.py` → `TOOL_DEFINITIONS` | `get_tools_chat_completions_format()` | `get_tools_realtime_format()` |
| System Prompt | `tool_definitions.py` → `SYSTEM_PROMPT_CORE` | `get_system_prompt_chat()` | `get_system_prompt_realtime(lang)` |
| Canvas Context | `app.js` → `buildCanvasContextDescription()` | Injected via `_update_canvas_context()` in `azure_openai_chat.py` | Injected via `updateCanvasContext()` in `realtime-voice.js` |
| Chat History | `azure_openai_chat.py` → `conversation_history` | Direct read/write | Synced via `syncVoiceMessageToBackend()` → `/api/chat/record` |
| View History | `app.js` → `viewHistory[]` | Same app instance | Same app instance |
| UI Display | `app.js` → `chatContainer` DOM | `addMessage()` from `sendMessage()` | `addMessage()` from `onResponse`/`onTranscript` |

### System Prompt Architecture

`SYSTEM_PROMPT_CORE` in `tool_definitions.py` contains all shared personality, context awareness rules, and tool usage guidelines. Two wrappers add channel-specific instructions:

- **`get_system_prompt_chat()`** — appends the numbered tool list (since Chat Completions API benefits from explicit tool descriptions in the system message)
- **`get_system_prompt_realtime(language)`** — appends voice-specific guidance (concise responses, natural speech) and language preference (English/Danish/Cantonese)

When updating the AI's personality, context rules, or tool guidelines, edit `SYSTEM_PROMPT_CORE` only. Channel-specific additions go in the respective wrapper functions.

### Voice ↔ Backend History Sync

Voice messages are synced to the backend so the text chat LLM has full conversation context:

```
Voice user speaks → onTranscript callback
  → addMessage('user', text)              ← UI display
  → syncVoiceMessageToBackend('user', text) ← POST /api/chat/record

Voice AI responds → onResponse callback
  → addMessage('assistant', text, pokemon, tcg)
  → syncVoiceMessageToBackend('assistant', text, pokemon, tcg)

/api/chat/record endpoint:
  → conversations[user_id].append(...)            ← route-level history
  → azure_chat.add_message(user_id, role, text)   ← LLM conversation history
```

This means if a user asks Pikachu questions via voice, then switches to text chat, the AI remembers the voice conversation.

### Unified Clear

`DELETE /api/chat/clear/<user_id>` clears both:
- Route-level `conversations` dict (used for `/api/history`)
- `azure_openai_chat.conversation_history` (used for LLM context)

### Rules

- **NEVER** define tools, system prompts, or AI personality inline in `azure_openai_chat.py` or `realtime_chat.py`
- **ALWAYS** update `tool_definitions.py` as the single source of truth
- **ALWAYS** sync voice messages to backend via `syncVoiceMessageToBackend()`
- When clearing history, clear **both** stores (already handled by the `/api/chat/clear` endpoint)

---

## Azure OpenAI Endpoint Strategy

The app now targets the Azure OpenAI resource endpoint instead of Azure AI Foundry project URLs for both chat and realtime voice.

### Preferred Environment Variables

- `AZURE_OPENAI_ENDPOINT` → Azure OpenAI resource endpoint for chat and default realtime fallback
- `AZURE_OPENAI_REALTIME_ENDPOINT` → optional explicit Azure OpenAI resource endpoint for realtime voice
- `AZURE_OPENAI_DEPLOYMENT` → chat/text deployment name
- `AZURE_OPENAI_REALTIME_DEPLOYMENT` → realtime deployment name
- `AZURE_TOKEN_SCOPE=https://cognitiveservices.azure.com/.default` when using service principal auth

### Compatibility Behavior

- Legacy Foundry-style values such as `https://...services.ai.azure.com/api/projects/...` are still accepted during transition.
- Endpoints that include `/openai` or `/openai/v1` are normalized back to the Azure OpenAI resource root before SDK or WebSocket use.
- Chat uses the Azure OpenAI SDK with `azure_ad_token_provider` for app registration auth.
- Realtime voice builds the WebSocket URL from the same Azure OpenAI resource host and deployment.
- Realtime WebSocket URL format depends on API generation: preview API versions use `/openai/realtime?api-version=...&deployment=...`, while GA API versions use `/openai/v1/realtime?model=...`. Mixing those formats returns HTTP 404 from Azure.

### Adding a New Virtual Page

1. **Flask**: Add catch-all route if the URL prefix is new (existing `/pokemon/` and `/tcg/` prefixes are already covered)
2. **`buildUrl()`**: Map the new canvas type → URL path
3. **`routeFromUrl()`**: Add regex match for the new path → call the view's `show()` method
4. **`handlePopState()`**: Add the same match → call the view's `showWithoutHistory()` method
5. **`navigateBack()` / `navigateForward()`**: Add restoration logic using the view key
6. **`buildViewKey()`**: Define a unique key pattern for deduplication
7. **`buildCanvasContextDescription()`**: Add a description for GPT realtime context
