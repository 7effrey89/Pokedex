# Features

All implemented features, categorized. Every new feature must be added here.

---

## Pokemon

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| Pokemon Grid/Index | Browse all Pokemon in a visual grid with sprites | ✅ `show_pokemon_index` |
| Pokemon Detail View | Full stats, abilities, evolution chain, typing, flavor text | ✅ `get_pokemon_info` |
| Pokemon Search & Filter | Search by name, type, generation, number range, height/weight, ability | ❌ |
| Random Pokemon | Get a random Pokemon from the entire Pokedex | ✅ `get_random_pokemon` |
| Random by Region | Get a random Pokemon from a specific region (Kanto, Johto, etc.) | ✅ `get_random_pokemon_from_region` |
| Random by Type | Get a random Pokemon of a specific type | ✅ `get_random_pokemon_by_type` |
| Evolution Chain | View full evolution tree with sprites and methods | ❌ (shown in detail) |
| Popular Pokemon | Pre-curated list of well-known Pokemon for quick access | ❌ |

## Trading Card Game (TCG)

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| TCG Card Gallery | Browse all TCG cards for a specific Pokemon with pricing | ✅ `search_pokemon_cards` |
| TCG Card Detail | Full card info: rarity, pricing (TCGPlayer), attacks, abilities, legalities | ✅ `show_tcg_card_by_index` |
| TCG Database | Browse all 172+ card expansions/sets | ❌ |
| Expansions View | Lazy-loaded set previews with card thumbnails | ❌ |
| All Cards View | Flat grid of all cards across selected expansions | ❌ |
| Expansion Picker | Collapsible checklist to select which sets to load | ❌ |
| TCG Sort Options | Sort by set, card #, Pokédex #, name, rarity, price (10 options) | ❌ |
| TCG Gallery Sort | Sort gallery cards by 13 options including dex#, rarity, price, year | ❌ |
| TCG Filters | Filter by card name/set, category, energy type, price range, rarity | ❌ |
| Slim Payloads | Grid views receive ~80% smaller card data for faster loading | N/A |
| Progressive Rendering | Cards render in batches of 60 via IntersectionObserver | N/A |

## Navigation

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| Back/Forward Buttons | Navigate through view history | ❌ |
| Canvas State System | Centralized navigation + GPT context via `updateCanvasState()` | N/A |
| URL Routing | Direct links: `/pokemon/<name>`, `/tcg/<cardId>`, `/tcg/set/<setId>` | N/A |
| Index Button | Jump to Pokemon grid from footer | ❌ |
| TCG Database Button | Jump to TCG database from footer | ❌ |

## Chat & Voice

| Feature | Description | GPT Realtime |
|---------|-------------|:------------:|
| Voice Conversation | Real-time voice chat with AI Pokédex assistant | ✅ (core) |
| Text Chat Sidebar | Text-based chat with streaming responses | N/A |
| Camera/Scan | Identify physical Pokemon cards via camera | ❌ |
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
| Loading Indicator | "Thinking..." spinner during API calls | N/A |
| Status Indicator | Online/Offline connection status | N/A |
| Purple Gradient Theme | TCG views use consistent purple gradient background | N/A |
| Transparent Card Backgrounds | TCG cards display with transparent backgrounds | N/A |

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
