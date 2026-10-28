# Architecture

## API Response Caching

Stable Pokemon and TCG catalog records are read from SQLite, while downloaded
assets are persisted under `data/assets` and tracked in SQLite. There is no
runtime JSON response cache. Raw seeds and immutable refresh snapshots are rebuild
and provenance inputs, not runtime lookup sources. TCG prices have a dedicated
database-backed refresh interval because they change regularly.

Normal Pokemon detail, species, and evolution-chain routes reconstruct their
PokeAPI-shaped response contracts from normalized SQLite tables. They do not read
or create runtime JSON response-cache files. An explicit `?refresh=1` request is
the update path: it fetches PokeAPI and persists normalized changes to SQLite.
Type damage relations are normalized in `type_damage_relation`. SQLite rebuilds
hydrate all six relation groups for every type. Migrated databases backfill a
type once on first use when rows are absent, then serve subsequent weakness
lookups entirely from SQLite without a runtime JSON cache file.

### Flow

```
TCG price request → SQLite card refresh timestamp still current?
  ├─ YES → Build response from normalized market listings/prices
  └─ NO  → Fetch raw card from TCG API → normalize into SQLite → return
```

### Database Cache and Refresh Policy

- Schema v3 adds `catalog_setting`; `CatalogSettings` migrates the legacy price interval once and never creates a JSON cache directory.
- TCG price TTL uses `tcg_price_expiry_seconds`: 5 minutes, 1 hour, 1 day, 3 days, 7 days, or unlimited. It compares `tcg_card.last_refreshed_at` with the interval, without deleting catalog rows.
- `force_refresh: true` always calls the TCG API for searches, set cards, sets, or card prices. Pagination completes before an atomic write; failures leave existing catalog data intact.
- TCG refresh reuses importer normalization, preserves local card/set assets whose source URLs are unchanged, and stores both providers' price metrics.
- Pokemon tools read the same normalized catalog as the detail routes. The Pokemon refresh button explicitly refreshes Pokemon, species, and evolution data through Flask.
- Catalog rebuilds preserve `catalog_setting`; accounts, collections, and existing asset files are not cleared.

### Cache Management Endpoints

```
GET  /api/cache/config      → SQLite refresh config + catalog status
POST /api/cache/expiry      → Set TCG price refresh interval (`seconds`: 300, 3600, 86400, 259200, 604800, or 0)
```

The legacy clear, invalidate, enable, and PokeAPI-cache toggle endpoints have been
removed. Refresh updates catalog data; it is not implemented by deleting files.

## Seed Preparation and Shared Backup Bundles

Raw API acquisition and bulk asset preparation never write into the live data
root. `seeds/prepared/` contains `data/assets/{pokemon,cries,tcg}`,
`data/index` for **TCG image embeddings**, and `asset-manifest.json`, not a
database. The manifest uses the shared backup asset-registration shape
(owner, kind, source URL, portable path, hash, and media metadata).
The downloader reads raw API responses and calls the same SQL-free validated
file materializer as the runtime `AssetManager`. Offline embeddings read these
registrations and verify file hashes, never querying SQLite or runtime assets.

Script 03 normalizes raw seeds into a disposable database outside `seeds/`.
Preview validates inputs without creating the target; explicit
`--apply --server-stopped` SQL-merges them into the runtime catalog. Temporary
normalization is cleaned up on success or failure. Missing metadata fails
offline unless `--allow-network` is explicitly supplied.

`seeds/backup-bundles/` holds one category-named ZIP per prepared component.
The CLI and admin panel both use `BackupService.create_backup` and
`restore_backup`; there is no second ZIP format or bespoke extraction path.
Seed ZIPs contain media and embeddings, not the derived catalog. Admin database
exports remain available. Optional accounts exports use SQLite's online backup
API in disposable storage, never leaving a database in seeds.
Accounts require an explicit existing source and are excluded from automatic
CLI restores by default. Generated account data and bundles are private,
Git-ignored outputs; no default seed accounts are generated.

The shared version-1 manifest optionally includes portable asset registrations.
Asset-only restores attach installed files to matching catalog owner/kind/source
URL rows, preserving valid existing registrations and files. Catalog imports use
`CatalogMerger` to insert/update normalized rows in one SQLite transaction instead
of swapping the database file. Destination-only data and local settings remain.
Global catalog IDs are stable; generated lookup/detail IDs are resolved by
natural keys and foreign keys remapped. Incoming timestamps must be newer to
update metadata; provider source dates govern prices independently. Ties and
missing dates preserve existing values; missing child rows can be added when
their incoming parent is not older. This is additive import, not deletion or
exact snapshot replacement. Invalid source-machine asset paths are not adopted.
Older manifests without registrations remain supported. Embeddings are
an additional directory component, validated for encoder, dtype, vector shape,
and aligned card count before promotion. Active mapped indexes are locked,
released, and reloaded after an admin restore.
Embeddings-only imports do not open catalog or accounts databases. Explicit
account restores retain their separate database-replacement behavior.

CLI import verifies all selected ZIPs before changing the target, rejects
duplicate categories, restores the catalog first, and requires explicit
`--apply --server-stopped`. UI restore imports the categories declared in the
ZIP, independently of locally available export selections. Neither multi-ZIP
installation nor an operating-system file replacement failure is advertised as
a cross-file transaction.

---

## Slim Payloads

For grid/list views that display many cards, the backend supports a `slim: true` parameter that strips unnecessary fields (attacks, abilities, legalities, cardmarket data, etc.) and returns only what's needed for display, sorting, and filtering.

- **Full card**: ~8KB (id, name, attacks, abilities, weaknesses, resistances, legalities, tcgplayer, cardmarket, etc.)
- **Slim card**: ~1.7KB (id, name, number, supertype, subtypes, types, rarity, nationalPokedexNumbers, small image, set basics, market/mid prices)
- **Reduction**: ~78-80%

Detail views fetch full card data on click via `get_card_details`.

TCG set listing, searches, cards-by-set, and card-detail handlers query the
normalized SQLite database without a JSON response-cache lookup. Card image
URLs point to `/api/tcg/card-image/<card_id>/<asset_kind>`; that route serves the
registered local file or materializes the registered upstream asset before serving.

Pokemon artwork, selectable sprite variants, and cries follow the same persistent
materialization boundary. Browser URLs point to `/api/pokemon/<id>/sprite/<style>`
or `/api/pokemon/<id>/cry`; the Flask asset manager validates the upstream payload,
writes it under `data/assets`, and updates `pokemon_asset.local_path` before serving
it. Catalog imports and refreshes register every available sprite style so the
admin bulk workflow can hydrate the same rows ahead of first use. Frontend code
must not render upstream sprite or cry URLs directly.

TCG card faces, set logos, and set symbols use the same rule. Browser views derive
`/api/tcg/card-image/<card-id>/<kind>` and `/api/tcg/set-image/<set-id>/<kind>`
URLs from stable catalog IDs. Those endpoints serve an existing local file or
download, validate, persist, and catalog the registered source before responding.
Existing card files are revalidated before serving; corrupt files trigger a fresh
download or fall back to the other registered card size in preference order.
Frontend TCG views must not prefer upstream image URLs when a stable card or set ID
is available.

Settings reports catalog content independently of local image downloads: species,
forms, cards, and sets come from SQLite row counts. Asset inventory
`available_count` includes rows with a local path or a nonempty source URL, counted
once; `stored` and `missing` remain the separate local-file and registered-remote-source
counts. These are catalog counts, not live upstream connectivity checks. TCG
inventory counts large card faces and set logos/symbols, without double-counting
small card thumbnails. Legacy database `available` still measures full default
artwork hydration; the settings catalog summary does not use it to hide metadata
that is already browsable.

## SQLite Journaling

Local development uses SQLite WAL mode. Azure App Service stores both databases
under the network-mounted `/home/data` path, where WAL shared-memory semantics are
not reliable. App Service connections therefore use SQLite's DELETE rollback
journal mode. The container remains limited to one Gunicorn worker so catalog asset
materialization and account writes have a single process coordinating them.

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

The collection scanner supports two retrieval architectures so their accuracy and latency can be compared:

### Candidate-first pipelines

1. `app.js` maps the visible card guide through the video's `object-fit: cover` scale and offsets, then crops that exact intrinsic camera region. One resulting data URL drives the captured-shot preview and every matching request.
2. `POST /api/tcg/extract-card-text` uses the configured vision model to extract structured card metadata. The realtime ten-line parser remains a fallback when structured extraction is unavailable.
3. `findBestMatchingCards()` searches the SQLite-backed TCG catalog by the extracted card name and scores printed fields locally.
4. At most 24 candidates are sent with the crop to `POST /api/tcg/image-match`.
5. `tcg_image_routes.py` fetches official candidate images server-side and compares them with Pillow-based average hash, difference hash, edge hash, and color signature scores. Candidate image features are cached in process memory.
6. The frontend combines visual similarity at 58% with metadata similarity at 42%, then sends at most 12 candidates to `POST /api/tcg/rerank-match` for an optional LLM judge pass.
7. The six highest-ranked candidates appear over the camera feed; the user explicitly chooses the correct card before it is added to local collection storage.

This route exists server-side so browser canvas security rules do not block comparisons against remote card images.

### Full-catalog NumPy pipeline

The experimental `numpy` setting deliberately bypasses OCR, metadata candidate lookup, and the LLM judge:

1. `scripts/05-build_tcg_image_embeddings.py` reads the TCG seed archive and deduplicates cards by stable TCG card ID.
2. Script 04 first downloads and validates official card images into `seeds/prepared/data/assets/tcg/`, registering paths and hashes in `seeds/prepared/asset-manifest.json`. The embeddings build itself performs no downloads or SQL queries.
3. `src/services/tcg_image_index.py` center-crops each image and builds a deterministic 1,432-dimensional vector from `32×44` standardized grayscale pixels plus eight histogram buckets for each RGB channel.
4. The index build L2-normalizes the vectors and writes `vectors.npy`, a row-aligned `cards.json`, and a version/source manifest under `seeds/prepared/data/index/`. The TCG image embeddings ZIP installs that unit into the configured runtime `data/index/`. The matrix is persisted as contiguous `float32` rows and memory-mapped by the application rather than stored as individual JSON vectors.
5. `POST /api/tcg/numpy-image-match` receives the same guide crop shown in the captured-shot preview, uses the shared encoder, and builds four query variants containing 100%, 90%, 86%, and 82% of the captured content. The padded variants compensate for cards framed too tightly without increasing the runtime index size.
6. The service lazy-loads the generated matrix once per process, performs exact cosine similarity for every query scale, and keeps each card's highest score.
7. The endpoint returns the six highest-scoring complete card records for the existing scanner candidate UI.

The JSON archive remains the source of truth for index rebuilding. Rerun the seed asset downloader and embeddings builder whenever source URLs or `ENCODER_VERSION` change, then package/install the corresponding ZIPs. Missing card images fail the embeddings build unless partial output is explicitly requested. Downloaded images are not required for index searches after the embeddings are installed. Deployments must include the complete configured TCG index directory because `vectors.npy`, `cards.json`, and `manifest.json` are one row-aligned unit. The large generated artifacts should be supplied by the build or release pipeline instead of being committed with source images. Exact search is intentional for the current catalog size; an approximate index is unnecessary until measured latency or catalog growth justifies it.

Script 08 archives the `seeds/` workspace (raw responses, asset manifest,
downloaded media, and embeddings) with per-file hashes, excluding derived
SQLite artifacts/sidecars and generated `backup-bundles/` to avoid redundant
copies. A legacy staged user accounts database is
excluded unless `--include-users` is explicitly supplied. This is an archival
format, distinct from the category ZIPs used for application restore.

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

## Database Architecture & Versioned Migrations

The application uses two separate SQLite databases stored under `POKEDEX_DATA_ROOT` (defaults to `./data/` locally, `/home/data/data/` in Azure persistent storage):

1. **Catalog Database (`pokedex.sqlite3`)**:
   - Source of truth for Pokémon, species, evolutions, TCG cards, expansions, market listings, and local asset mappings.
   - Built and updated reproducibly from raw API seed data and explicit upstream syncs.
2. **User Database (`users.sqlite3`)**:
   - Stores user accounts, password hashes, multi-member face enrollments, card collections, and user preferences.
   - Kept completely separate from the catalog so catalog rebuilds, restores, or re-indexes can never overwrite user-owned data.

### Schema Versioning & Migration Mechanism

Database migrations are managed via versioned SQL files located in `data/schema/` and tracked using SQLite's native `PRAGMA user_version`:

| Database | Migration File Pattern | Schema Version Constant (`src/db/database.py`) | Runner Function |
|----------|------------------------|------------------------------------------------|-----------------|
| Catalog | `data/schema/001.sql`, `002.sql`, ... | `SCHEMA_VERSION` | `apply_catalog_schema(connection)` |
| User DB | `data/schema/users-001.sql`, `users-002.sql`, ... | `USERS_SCHEMA_VERSION` | `apply_users_schema(connection)` |

### Workflow for Future Database Changes

When modifying the database schema in the future:

1. **Do not modify existing migration scripts** if databases exist in deployment environments.
2. **Create a new migration script**:
   - For catalog schema changes: add `data/schema/<version:03d>.sql` (e.g. `003.sql`).
   - For user database changes: add `data/schema/users-<version:03d>.sql` (e.g. `users-004.sql`).
3. **Write incremental DDL**:
   - Use `ALTER TABLE`, `CREATE TABLE`, `CREATE INDEX`, etc.
   - Conclude the file with `PRAGMA user_version = <N>;`.
4. **Update the version constant in `src/db/database.py`**:
   - Set `SCHEMA_VERSION = <N>` or `USERS_SCHEMA_VERSION = <N>`.
5. **Automatic Execution**:
   - On application startup, `apply_catalog_schema()` and `apply_users_schema()` check the database's current `PRAGMA user_version` and sequentially apply any newer migration scripts inside a transaction.

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
