# Features

All implemented features, categorized. Every new feature must be added here.

---

## Pokemon

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| Pokemon Grid/Index | Browse all Pokemon in a visual grid with sprites | ✅ `show_pokemon_index` |
| Pokemon Detail View | Full stats, abilities, evolution chain, typing, flavor text | ✅ `get_pokemon_info` |
| Pokemon Search & Filter | Search by name, type, generation, legendary/mythical status, number range, height/weight, ability | ❌ |
| Random Pokemon | Get a random Pokemon from the entire Pokedex | ✅ `get_random_pokemon` |
| Random by Region | Get a random Pokemon from a specific region (Kanto, Johto, etc.) | ✅ `get_random_pokemon_from_region` |
| Random by Type | Get a random Pokemon of a specific type | ✅ `get_random_pokemon_by_type` |
| Evolution Chain | View full evolution tree with sprites and methods | ❌ (shown in detail) |
| Pokemon Compare | Compare two Pokemon side by side with stats, traits, abilities, descriptions, and weaknesses | ✅ `compare_pokemon` |
| Popular Pokemon | Pre-curated list of well-known Pokemon for quick access | ❌ |

## Trading Card Game (TCG)

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| TCG Card Gallery | Browse all TCG cards for a specific Pokemon with pricing | ✅ `search_pokemon_cards` |
| TCG Card Detail | Full card info: rarity, pricing (TCGPlayer), attacks, abilities, legalities | ✅ `show_tcg_card_by_index` |
| TCG Database | Browse all 172+ card expansions/sets | ❌ |
| Expansions View | Lazy-loaded set previews with card thumbnails | ❌ |
| All Cards View | Flat grid of all cards across selected expansions | ❌ |
| My Collection Toggle | Switch TCG Database and Trading Card Gallery between clean default cards and collection mode where owned cards stay color and unowned cards appear monochrome with editable counts | ✅ `show_my_collection` |
| Collection Counters | Adjust owned counts inline from the TCG database and auto-save to browser storage | N/A |
| Expansion Picker | Collapsible checklist to select which sets to load | ❌ |
| TCG Sort Options | Sort by set, card #, Pokédex #, name, rarity, price (10 options) | ❌ |
| TCG Gallery Sort | Sort gallery cards by 13 options including dex#, rarity, price, year | ❌ |
| TCG Filters | Filter by card name/set, category, energy type, price range, rarity | ❌ |
| Currency Conversion | Convert all TCG prices to 22 currencies (USD, EUR, GBP, SEK, etc.) via settings | N/A |
| Number Locale Formatting | Thousand separator style: English (1,000.00), European (1.000,00), Swiss (1'000.00), Space (1 000,00) | N/A |
| Price Color Buckets | Color-coded prices (green/yellow/orange/red) with configurable thresholds via draggable slider or typed input | N/A |
| Slim Payloads | Grid views receive ~80% smaller card data for faster loading | N/A |
| Progressive Rendering | Cards render in batches of 60 via IntersectionObserver | N/A |

## Navigation

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| Back/Forward Buttons | Navigate through view history | ❌ |
| Canvas State System | Centralized navigation + GPT context via `updateCanvasState()` | N/A |
| Canvas Auto-Display | Chat responses auto-navigate the canvas: Pokemon detail, TCG gallery, or name detection fallback | N/A |
| URL Routing | Direct links: `/pokemon/<name>`, `/tcg/<cardId>`, `/tcg/set/<setId>` | N/A |
| Index Button | Jump to Pokemon grid from footer | ❌ |
| TCG Database Button | Jump to TCG database from footer | ❌ |

## Chat & Voice

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| Voice Conversation | Real-time voice chat with AI Pokédex assistant | ✅ (core) |
| Text Chat Sidebar | Text-based chat with streaming responses | N/A |
| Camera/Scan | Identify physical Pokemon cards via camera | ❌ |
| Collection Scanner | Camera collection mode with preview, accept/retry flow, scan history, and local save summary | N/A |
| TCG Image Similarity Matching | Collection scanner reranks candidate cards by comparing the camera frame to official card images | N/A |
| Tyrantrum Embedding POC | Standalone browser POC with camera-on load, resizable card-ratio alignment overlay, simple guide-area snapshots, expandable candidate metadata and image embeddings, structured LLM metadata extraction, attribute scoring with calculation tooltips, cosine fallback, and default LLM judge reranking | N/A |
| Face Recognition | Identify people via camera | ❌ |

## Caching & Performance

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| Stale-While-Revalidate | Serve cached data instantly, refresh in background, silent re-render | N/A |
| PokeAPI Proxy | All PokeAPI calls proxied through Flask for local caching | N/A |
| TCG Cache | Card data cached with 7-day TTL, stale data served while refreshing | N/A |
| Cache Management API | Enable/disable cache, set TTL, clear/invalidate entries | ❌ |
| Pagination Fix | Sets with >250 cards now paginate properly | N/A |

## UI/UX

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| Help Overlay | Interactive guide showing available commands | ❌ |
| Loading Indicator | Rotom loading bubble with hover tooltip describing the active request reason | N/A |
| Voice Backend Badge | Header badge shows whether voice is using GPT Realtime or browser fallback with connection details on hover | N/A |
| Status Indicator | Online/Offline connection status | N/A |
| Purple Gradient Theme | TCG views use consistent purple gradient background | N/A |
| Transparent Card Backgrounds | TCG cards display with transparent backgrounds | N/A |
| Collection Import/Export | Save and restore the local card collection as JSON from Settings | N/A |

---

## GPT Realtime Tool Summary

Tools the voice AI can call to navigate and act on behalf of the user:

| Tool | Action |
|------|--------|
| `get_pokemon_info` | Look up and display a Pokemon by name or number |
| `get_random_pokemon` | Show a random Pokemon |
| `get_random_pokemon_from_region` | Show random Pokemon from a region |
| `get_random_pokemon_by_type` | Show random Pokemon of a type |
| `search_pokemon_cards` | Search and display TCG cards for a Pokemon |
| `show_tcg_card_by_index` | Show a specific card by number in the current gallery |
| `show_pokemon_index` | Navigate back to the Pokemon grid |
| `show_tcg_database` | Navigate to the TCG Card Database page |
| `show_my_collection` | Navigate to the TCG Database and open the locally saved My Collection view |
| `compare_pokemon` | Navigate to the first named Pokemon, scroll to Compare Pokemon, and compare against the second named Pokemon |
| `navigate_back` | Go back to the previous page in history |
| `navigate_forward` | Go forward to the next page in history |
| `filter_pokemon_by_type` | Filter the grid by one or more Pokemon types |
| `filter_pokemon_by_generation` | Filter the grid by one or more generations |
| `filter_pokemon_by_classification` | Filter the grid by legendary and/or mythical status |
| `sort_tcg_cards` | Sort the current TCG card gallery (price, rarity, name, etc.) |
| `sort_tcg_database` | Sort the TCG Database view (by release date, name, card count, etc.) |
| `search_cards_by_set` | Browse all cards in a specific TCG expansion |
| `get_tcg_sets` | List all available TCG expansions/sets |
| `get_card_details` | Show detailed info for a specific TCG card by ID |
