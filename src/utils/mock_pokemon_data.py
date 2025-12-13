"""
Mock Pokemon data for testing when PokeAPI is not accessible
This will be used as fallback data
"""

MOCK_POKEMON_DATA = {
    "pikachu": {
        "id": 25,
        "name": "pikachu",
        "height": 4,
        "weight": 60,
        "types": [{"type": {"name": "electric"}}],
        "abilities": [
            {"ability": {"name": "static"}},
            {"ability": {"name": "lightning-rod"}}
        ],
        "stats": [
            {"stat": {"name": "hp"}, "base_stat": 35},
            {"stat": {"name": "attack"}, "base_stat": 55},
            {"stat": {"name": "defense"}, "base_stat": 40},
            {"stat": {"name": "special-attack"}, "base_stat": 50},
            {"stat": {"name": "special-defense"}, "base_stat": 50},
            {"stat": {"name": "speed"}, "base_stat": 90}
        ],
        "sprites": {
            "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png",
            "other": {
                "official-artwork": {
                    "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"
                }
            }
        }
    },
    "charizard": {
        "id": 6,
        "name": "charizard",
        "height": 17,
        "weight": 905,
        "types": [{"type": {"name": "fire"}}, {"type": {"name": "flying"}}],
        "abilities": [
            {"ability": {"name": "blaze"}},
            {"ability": {"name": "solar-power"}}
        ],
        "stats": [
            {"stat": {"name": "hp"}, "base_stat": 78},
            {"stat": {"name": "attack"}, "base_stat": 84},
            {"stat": {"name": "defense"}, "base_stat": 78},
            {"stat": {"name": "special-attack"}, "base_stat": 109},
            {"stat": {"name": "special-defense"}, "base_stat": 85},
            {"stat": {"name": "speed"}, "base_stat": 100}
        ],
        "sprites": {
            "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/6.png",
            "other": {
                "official-artwork": {
                    "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png"
                }
            }
        }
    },
    "mewtwo": {
        "id": 150,
        "name": "mewtwo",
        "height": 20,
        "weight": 1220,
        "types": [{"type": {"name": "psychic"}}],
        "abilities": [
            {"ability": {"name": "pressure"}},
            {"ability": {"name": "unnerve"}}
        ],
        "stats": [
            {"stat": {"name": "hp"}, "base_stat": 106},
            {"stat": {"name": "attack"}, "base_stat": 110},
            {"stat": {"name": "defense"}, "base_stat": 90},
            {"stat": {"name": "special-attack"}, "base_stat": 154},
            {"stat": {"name": "special-defense"}, "base_stat": 90},
            {"stat": {"name": "speed"}, "base_stat": 130}
        ],
        "sprites": {
            "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/150.png",
            "other": {
                "official-artwork": {
                    "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/150.png"
                }
            }
        }
    },
    "bulbasaur": {
        "id": 1,
        "name": "bulbasaur",
        "height": 7,
        "weight": 69,
        "types": [{"type": {"name": "grass"}}, {"type": {"name": "poison"}}],
        "abilities": [
            {"ability": {"name": "overgrow"}},
            {"ability": {"name": "chlorophyll"}}
        ],
        "stats": [
            {"stat": {"name": "hp"}, "base_stat": 45},
            {"stat": {"name": "attack"}, "base_stat": 49},
            {"stat": {"name": "defense"}, "base_stat": 49},
            {"stat": {"name": "special-attack"}, "base_stat": 65},
            {"stat": {"name": "special-defense"}, "base_stat": 65},
            {"stat": {"name": "speed"}, "base_stat": 45}
        ],
        "sprites": {
            "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png",
            "other": {
                "official-artwork": {
                    "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/1.png"
                }
            }
        }
    },
    "eevee": {
        "id": 133,
        "name": "eevee",
        "height": 3,
        "weight": 65,
        "types": [{"type": {"name": "normal"}}],
        "abilities": [
            {"ability": {"name": "run-away"}},
            {"ability": {"name": "adaptability"}}
        ],
        "stats": [
            {"stat": {"name": "hp"}, "base_stat": 55},
            {"stat": {"name": "attack"}, "base_stat": 55},
            {"stat": {"name": "defense"}, "base_stat": 50},
            {"stat": {"name": "special-attack"}, "base_stat": 45},
            {"stat": {"name": "special-defense"}, "base_stat": 65},
            {"stat": {"name": "speed"}, "base_stat": 55}
        ],
        "sprites": {
            "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/133.png",
            "other": {
                "official-artwork": {
                    "front_default": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/133.png"
                }
            }
        }
    }
}

MOCK_SPECIES_DATA = {
    "pikachu": {
        "flavor_text_entries": [
            {
                "flavor_text": "When several of these POKéMON gather, their electricity could build and cause lightning storms.",
                "language": {"name": "en"}
            }
        ]
    },
    "charizard": {
        "flavor_text_entries": [
            {
                "flavor_text": "Spits fire that is hot enough to melt boulders. Known to cause forest fires unintentionally.",
                "language": {"name": "en"}
            }
        ]
    },
    "mewtwo": {
        "flavor_text_entries": [
            {
                "flavor_text": "It was created by a scientist after years of horrific gene splicing and DNA engineering experiments.",
                "language": {"name": "en"}
            }
        ]
    },
    "bulbasaur": {
        "flavor_text_entries": [
            {
                "flavor_text": "A strange seed was planted on its back at birth. The plant sprouts and grows with this POKéMON.",
                "language": {"name": "en"}
            }
        ]
    },
    "eevee": {
        "flavor_text_entries": [
            {
                "flavor_text": "Its genetic code is irregular. It may mutate if it is exposed to radiation from element stones.",
                "language": {"name": "en"}
            }
        ]
    }
}

MOCK_POKEMON_LIST = [
    {"name": "bulbasaur", "url": "https://pokeapi.co/api/v2/pokemon/1/"},
    {"name": "charmander", "url": "https://pokeapi.co/api/v2/pokemon/4/"},
    {"name": "squirtle", "url": "https://pokeapi.co/api/v2/pokemon/7/"},
    {"name": "pikachu", "url": "https://pokeapi.co/api/v2/pokemon/25/"},
    {"name": "eevee", "url": "https://pokeapi.co/api/v2/pokemon/133/"},
    {"name": "mewtwo", "url": "https://pokeapi.co/api/v2/pokemon/150/"},
    {"name": "charizard", "url": "https://pokeapi.co/api/v2/pokemon/6/"},
    {"name": "dragonite", "url": "https://pokeapi.co/api/v2/pokemon/149/"},
    {"name": "mew", "url": "https://pokeapi.co/api/v2/pokemon/151/"},
    {"name": "snorlax", "url": "https://pokeapi.co/api/v2/pokemon/143/"}
]
