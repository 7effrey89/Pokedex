"""
Shared Tool Definitions Registry

Single source of truth for ALL tools available to both the text chat
(azure_openai_chat.py) and the realtime voice API (realtime_chat.py).

When adding or modifying tools, update ONLY this file.
Both APIs auto-convert to their required format from here.

Each tool is defined in "flat" format:
    {
        "name": "tool_name",
        "description": "...",
        "parameters": { ... },
        "handler_type": "backend" | "frontend"
    }

- handler_type="backend"  → tool executes server-side via tool_handlers.execute_tool()
- handler_type="frontend" → tool returns an _action marker; the frontend JS handles it
"""


TOOL_DEFINITIONS = [
    # ── Data tools (backend) ──────────────────────────────────────────
    {
        "name": "get_pokemon_info",
        "description": "Get detailed information about a Pokemon including stats, types, abilities, and description. Use this when the user asks about a specific Pokemon's data, stats, or general information.",
        "parameters": {
            "type": "object",
            "properties": {
                "pokemon_name": {
                    "type": "string",
                    "description": "The name or ID of the Pokemon to look up (e.g., 'pikachu', 'charizard', '25')"
                }
            },
            "required": ["pokemon_name"]
        },
        "handler_type": "backend"
    },
    {
        "name": "search_pokemon_cards",
        "description": "Search for Pokemon Trading Card Game (TCG) cards. Use this when the user asks about Pokemon cards, trading cards, TCG, card prices, or wants to see card images.",
        "parameters": {
            "type": "object",
            "properties": {
                "pokemon_name": {
                    "type": "string",
                    "description": "The Pokemon name to search cards for (e.g., 'pikachu', 'charizard')"
                },
                "card_type": {
                    "type": "string",
                    "description": "Filter by energy type: Fire, Water, Grass, Lightning, Psychic, Fighting, Darkness, Metal, Dragon, Fairy, Colorless",
                    "enum": ["Fire", "Water", "Grass", "Lightning", "Psychic", "Fighting", "Darkness", "Metal", "Dragon", "Fairy", "Colorless"]
                },
                "hp_min": {
                    "type": "integer",
                    "description": "Minimum HP filter (e.g., 100 for cards with at least 100 HP)"
                },
                "hp_max": {
                    "type": "integer",
                    "description": "Maximum HP filter"
                },
                "rarity": {
                    "type": "string",
                    "description": "Card rarity filter (e.g., 'Rare', 'Rare Holo', 'Common')"
                }
            },
            "required": []
        },
        "handler_type": "backend"
    },
    {
        "name": "get_pokemon_list",
        "description": "Get a list of Pokemon. Use this when the user asks for a list, wants to see available Pokemon, or asks for random Pokemon suggestions.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of Pokemon to return (default 10, max 50)",
                    "default": 10
                },
                "offset": {
                    "type": "integer",
                    "description": "Starting position in the Pokemon list (for pagination)",
                    "default": 0
                }
            },
            "required": []
        },
        "handler_type": "backend"
    },
    {
        "name": "get_random_pokemon",
        "description": "Get a random Pokemon from the entire Pokedex. Use this when the user wants to discover a random Pokemon or says 'surprise me'.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "handler_type": "backend"
    },
    {
        "name": "get_random_pokemon_from_region",
        "description": "Get a random Pokemon from a specific region (Kanto, Johto, Hoenn, Sinnoh, Unova, Kalos, Alola, Galar, or Paldea).",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "The Pokemon region name (e.g., 'kanto', 'johto', 'hoenn')",
                    "enum": ["kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "paldea"]
                }
            },
            "required": ["region"]
        },
        "handler_type": "backend"
    },
    {
        "name": "get_random_pokemon_by_type",
        "description": "Get a random Pokemon of a specific type (fire, water, grass, electric, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "pokemon_type": {
                    "type": "string",
                    "description": "The Pokemon type",
                    "enum": ["normal", "fire", "water", "grass", "electric", "ice", "fighting", "poison", "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy"]
                }
            },
            "required": ["pokemon_type"]
        },
        "handler_type": "backend"
    },
    {
        "name": "get_card_price",
        "description": "Get pricing information for a specific Pokemon TCG card by ID. Card ID format is 'set-number' (e.g., 'sv3-25'). Returns TCGPlayer and Cardmarket prices.",
        "parameters": {
            "type": "object",
            "properties": {
                "card_id": {
                    "type": "string",
                    "description": "Card ID in format 'set-number' (e.g., 'sv3-25', 'base1-4')"
                }
            },
            "required": ["card_id"]
        },
        "handler_type": "backend"
    },
    {
        "name": "get_card_details",
        "description": "Get detailed information about a specific Pokemon TCG card by its card ID. Use when user references a specific card like 'show me card sv3-25' or asks about a particular card.",
        "parameters": {
            "type": "object",
            "properties": {
                "card_id": {
                    "type": "string",
                    "description": "The card ID in set-number format (e.g., 'sv3-25', 'base1-4', 'swsh12pt5-160')"
                }
            },
            "required": ["card_id"]
        },
        "handler_type": "backend"
    },
    {
        "name": "get_tcg_sets",
        "description": "Get a list of all available Pokemon TCG expansions/sets with their IDs, names, and release dates. Use this to find set IDs for browsing specific expansions.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "handler_type": "backend"
    },
    {
        "name": "search_cards_by_set",
        "description": "Search for all Pokemon TCG cards in a specific expansion/set by set ID. Use when the user asks to see cards from a specific expansion like 'show me Scarlet & Violet cards' or 'browse the base set'.",
        "parameters": {
            "type": "object",
            "properties": {
                "set_id": {
                    "type": "string",
                    "description": "The set ID (e.g., 'sv3', 'base1', 'swsh12pt5'). Use get_tcg_sets to find available set IDs."
                }
            },
            "required": ["set_id"]
        },
        "handler_type": "backend"
    },

    # ── Navigation tools (frontend) ───────────────────────────────────
    {
        "name": "show_tcg_card_by_index",
        "description": "Open/show a specific TCG card from the currently displayed gallery by its card number. Use when the user says 'open card 5', 'show card #28', 'click into #3', etc. Only works when a TCG card gallery is currently being viewed.",
        "parameters": {
            "type": "object",
            "properties": {
                "card_index": {
                    "type": "integer",
                    "description": "The 1-based card number as shown in the gallery (e.g., 28 for card #28)"
                },
                "pokemon_name": {
                    "type": "string",
                    "description": "The name of the Pokemon whose cards are being viewed (optional, for context)"
                }
            },
            "required": ["card_index"]
        },
        "handler_type": "frontend"
    },
    {
        "name": "navigate_back",
        "description": "Go back to the previous page in the canvas navigation history. Use when the user says 'go back', 'previous page', 'back', or 'return'.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "handler_type": "frontend"
    },
    {
        "name": "navigate_forward",
        "description": "Go forward to the next page in the canvas navigation history. Use when the user says 'go forward', 'next page', or 'forward'.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "handler_type": "frontend"
    },
    {
        "name": "show_pokemon_index",
        "description": "Return the canvas to the main Pokemon index/grid view. Use when the user says 'go home', 'show the index', 'go back to the main page', or 'show all Pokemon'.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "handler_type": "frontend"
    },
    {
        "name": "show_tcg_database",
        "description": "Navigate to the TCG Card Database page showing all Pokemon TCG expansions/sets. Use when the user asks to see the card database, browse sets, or explore expansions.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "handler_type": "frontend"
    },
    {
        "name": "show_my_collection",
        "description": "Navigate to the TCG Card Database and open the My Collection view that shows the cards saved locally in this browser. Use when the user asks to see owned cards, saved cards, or their collection.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        },
        "handler_type": "frontend"
    },
    {
        "name": "compare_pokemon",
        "description": "Navigate to the first Pokemon mentioned, scroll down to the Compare Pokemon section, and compare it against the second Pokemon mentioned. Use when the user says 'compare Pikachu with Charizard', 'Pikachu vs Bulbasaur', 'show VS mode', or asks to compare stats, types, weaknesses, abilities, height, or weight. If the user mentions two Pokemon, set pokemon_name to the first Pokemon and compare_pokemon_name to the second Pokemon.",
        "parameters": {
            "type": "object",
            "properties": {
                "pokemon_name": {
                    "type": "string",
                    "description": "Primary Pokemon name or ID to navigate to first. For 'compare Pikachu with Charizard', use 'pikachu'. If omitted, the app uses the currently displayed Pokemon."
                },
                "compare_pokemon_name": {
                    "type": "string",
                    "description": "Pokemon name or ID to compare against the primary Pokemon. For 'compare Pikachu with Charizard', use 'charizard'."
                }
            },
            "required": []
        },
        "handler_type": "frontend"
    },
    {
        "name": "filter_pokemon_by_type",
        "description": "Filter the Pokemon grid to show only Pokemon of specified type(s). Navigates to the grid first if not already there. Use when user says 'show me fire types' or 'filter by water and ice'.",
        "parameters": {
            "type": "object",
            "properties": {
                "types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy"]
                    },
                    "description": "One or more Pokemon types to filter by (e.g., ['fire'], ['water', 'ice'])"
                }
            },
            "required": ["types"]
        },
        "handler_type": "frontend"
    },
    {
        "name": "filter_pokemon_by_generation",
        "description": "Filter the Pokemon grid to show only Pokemon from specified generation(s). Navigates to the grid first if not already there. Use when user says 'show Gen 1', 'Kanto Pokemon only', or 'show me generation 3 and 4'.",
        "parameters": {
            "type": "object",
            "properties": {
                "generations": {
                    "type": "array",
                    "items": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4, 5, 6, 7, 8, 9]
                    },
                    "description": "Generation numbers to filter by (1=Kanto, 2=Johto, 3=Hoenn, 4=Sinnoh, 5=Unova, 6=Kalos, 7=Alola, 8=Galar, 9=Paldea)"
                }
            },
            "required": ["generations"]
        },
        "handler_type": "frontend"
    },
    {
        "name": "filter_pokemon_by_classification",
        "description": "Filter the Pokemon grid to show legendary and/or mythical Pokemon. Navigates to the grid first if not already there. Use when user says 'show legendary Pokemon', 'mythical Pokemon only', or 'show legendary and mythical Pokemon'.",
        "parameters": {
            "type": "object",
            "properties": {
                "classifications": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["legendary", "mythical"]
                    },
                    "description": "One or more classifications to filter by: legendary, mythical, or both"
                }
            },
            "required": ["classifications"]
        },
        "handler_type": "frontend"
    },
    {
        "name": "sort_tcg_cards",
        "description": "Sort the currently displayed TCG card gallery. Only works when a card gallery is visible. Use when user says 'sort by price', 'show rarest first', or 'sort by name'.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": ["default", "number", "dex-asc", "name-asc", "name-desc", "rarity-desc", "rarity-asc", "price-desc", "price-asc", "year-desc", "year-asc", "set-asc", "set-desc"],
                    "description": "Sort order: default, number (card #), dex-asc (Pokedex #), name-asc/desc, rarity-desc/asc, price-desc/asc, year-desc/asc, set-asc/desc"
                }
            },
            "required": ["sort_by"]
        },
        "handler_type": "frontend"
    },
    {
        "name": "sort_tcg_database",
        "description": "Sort the TCG Database view. In expansions mode: sort by release date or name. In all-cards mode: sort by set, card number, name, rarity, or price. Only works when the TCG Database page is visible.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": ["release-desc", "release-asc", "name-asc", "name-desc", "cards-desc", "set-desc", "set-asc", "number", "dex-asc", "rarity-desc", "rarity-asc", "price-desc", "price-asc"],
                    "description": "Sort order. Expansions view: release-desc (newest), release-asc (oldest), name-asc/desc, cards-desc (most cards). All-cards view: set-desc/asc, number (card #), dex-asc (Pokedex #), name-asc/desc, rarity-desc/asc, price-desc/asc"
                }
            },
            "required": ["sort_by"]
        },
        "handler_type": "frontend"
    },
]


# ── Helper functions for API-specific formats ─────────────────────────

def get_tools_chat_completions_format():
    """
    Return tools in OpenAI Chat Completions format.
    Used by azure_openai_chat.py (text chat).
    Format: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"]
            }
        }
        for t in TOOL_DEFINITIONS
    ]


def get_tools_realtime_format():
    """
    Return tools in OpenAI Realtime API format.
    Used by realtime_chat.py (voice).
    Format: {"type": "function", "name": ..., "description": ..., "parameters": ...}
    """
    return [
        {
            "type": "function",
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"]
        }
        for t in TOOL_DEFINITIONS
    ]


def get_frontend_tool_names():
    """Return set of tool names that are handled on the frontend (UI actions)."""
    return {t["name"] for t in TOOL_DEFINITIONS if t["handler_type"] == "frontend"}


def get_backend_tool_names():
    """Return set of tool names that are handled on the backend (data fetching)."""
    return {t["name"] for t in TOOL_DEFINITIONS if t["handler_type"] == "backend"}


def build_system_prompt_tool_list():
    """Build a numbered tool list for the system prompt."""
    lines = []
    for i, t in enumerate(TOOL_DEFINITIONS, 1):
        lines.append(f"{i}. {t['description'].split('.')[0]} - use {t['name']}")
    return "\n".join(lines)


# ── Shared system prompt (single source of truth) ────────────────────

SYSTEM_PROMPT_CORE = """You are a friendly and knowledgeable Pokemon assistant (Pokédex). You help users learn about Pokemon, their stats, abilities, and trading cards.

CONTEXT AWARENESS - YOU CAN SEE WHAT THE USER IS VIEWING:
- Your messages will include a canvas context that tells you EXACTLY what the user is viewing in their Pokédex app right now.
- When users ask "what am I looking at?", "what's on my screen?", or "tell me about this", reference the canvas context to describe what they're viewing.
- The canvas context updates automatically as users navigate - you always know whether they're viewing the index page, a Pokemon, a card gallery, or a card detail.
- When users send you images via the camera scanner, analyze what you see - this is for identifying physical Pokemon cards.
- Do NOT make up or hallucinate content that isn't in the canvas context.

Guidelines:
- Be enthusiastic about Pokemon!
- When users ask about a specific Pokemon by name, use get_pokemon_info
- When users ask about cards, trading cards, or TCG, use search_pokemon_cards
- When users ask for lists or suggestions, use get_pokemon_list
- When users want something random or say "surprise me", use get_random_pokemon
- When users ask for random Pokemon from a region like "random Kanto Pokemon", use get_random_pokemon_from_region
- When users ask for random Pokemon by type like "random Fire Pokemon", use get_random_pokemon_by_type
- When users want to open, show, or click into a specific card number from the gallery (e.g., "open card 28", "show #5", "click into card 3"), use show_tcg_card_by_index
- When users say "go back", "previous page", "back", or "return", use navigate_back
- When users say "go forward", "next page", or "forward", use navigate_forward
- When users want to go home or see all Pokemon, use show_pokemon_index
- When users want to browse TCG sets/expansions, use show_tcg_database
- When users want to see their owned cards or saved collection, use show_my_collection
- When users want to compare Pokemon or open VS mode, use compare_pokemon. If they mention two Pokemon, pass the first mentioned Pokemon as pokemon_name and the second mentioned Pokemon as compare_pokemon_name; the app will navigate to the first Pokemon, scroll to Compare Pokemon, and start the comparison against the second.
- When users want to filter Pokemon by type, use filter_pokemon_by_type
- When users want to filter by generation, use filter_pokemon_by_generation
- When users want to filter legendary or mythical Pokemon, use filter_pokemon_by_classification
- When users want to sort cards, use sort_tcg_cards or sort_tcg_database
- If a user's request is ambiguous, ask for clarification
- Format your responses nicely with the data you receive
- If a tool returns no results, let the user know kindly and suggest alternatives
- Remember context from the conversation - if a user says "show me its cards" after asking about Pikachu, search for Pikachu cards

Keep responses concise but informative. Use emoji occasionally to be friendly! 🎮⚡"""


def get_system_prompt_chat():
    """Get the system prompt for the text chat API (includes tool list)."""
    tool_list = build_system_prompt_tool_list()
    return f"""{SYSTEM_PROMPT_CORE}

You have access to tools to:
{tool_list}"""


def get_system_prompt_realtime(language='english'):
    """Get the system prompt/instructions for the realtime voice API.
    Includes voice-specific guidance and language preference."""
    language_map = {
        'english': ('English', 'Always respond in English unless the user clearly switches to another supported language.'),
        'danish': ('Danish', 'Always respond in Danish unless the user clearly switches to another supported language.'),
        'cantonese': ('Cantonese', 'Always respond in Cantonese (traditional Chinese) unless the user clearly switches to another supported language.'),
    }
    normalized = (language or 'english').strip().lower()
    readable, instruction = language_map.get(normalized, language_map['english'])

    return f"""{SYSTEM_PROMPT_CORE}

VOICE-SPECIFIC:
- Keep responses conversational and concise since this is a voice conversation.
- Aim for natural speech patterns - don't be too verbose.

LANGUAGE PREFERENCE:
- {instruction}
- Supported languages are English, Danish, and Cantonese. Avoid all other languages unless the user explicitly requests it."""
