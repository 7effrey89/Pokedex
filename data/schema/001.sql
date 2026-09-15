PRAGMA foreign_keys = ON;

CREATE TABLE schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE import_run (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    importer_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    error_message TEXT
);

CREATE TABLE import_file (
    id INTEGER PRIMARY KEY,
    import_run_id INTEGER NOT NULL REFERENCES import_run(id) ON DELETE CASCADE,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('pokeapi', 'tcg', 'asset')),
    resource_kind TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    source_cached_at TEXT,
    imported_at TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (import_run_id, relative_path)
);

CREATE TABLE evolution_chain (
    id INTEGER PRIMARY KEY,
    baby_trigger_item_name TEXT
);

CREATE TABLE pokemon_species (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    generation_name TEXT,
    evolution_chain_id INTEGER REFERENCES evolution_chain(id),
    color_name TEXT,
    shape_name TEXT,
    habitat_name TEXT,
    growth_rate_name TEXT,
    capture_rate INTEGER,
    base_happiness INTEGER,
    gender_rate INTEGER,
    hatch_counter INTEGER,
    is_baby INTEGER NOT NULL DEFAULT 0 CHECK (is_baby IN (0, 1)),
    is_legendary INTEGER NOT NULL DEFAULT 0 CHECK (is_legendary IN (0, 1)),
    is_mythical INTEGER NOT NULL DEFAULT 0 CHECK (is_mythical IN (0, 1)),
    last_refreshed_at TEXT
);

CREATE TABLE pokemon (
    id INTEGER PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES pokemon_species(id),
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_order INTEGER NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
    base_experience INTEGER,
    height_decimetres INTEGER,
    weight_hectograms INTEGER,
    last_refreshed_at TEXT
);

CREATE TABLE type (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE pokemon_type (
    pokemon_id INTEGER NOT NULL REFERENCES pokemon(id) ON DELETE CASCADE,
    type_id INTEGER NOT NULL REFERENCES type(id),
    slot INTEGER NOT NULL,
    PRIMARY KEY (pokemon_id, type_id)
);

CREATE TABLE ability (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE pokemon_ability (
    pokemon_id INTEGER NOT NULL REFERENCES pokemon(id) ON DELETE CASCADE,
    ability_id INTEGER NOT NULL REFERENCES ability(id),
    slot INTEGER NOT NULL,
    is_hidden INTEGER NOT NULL DEFAULT 0 CHECK (is_hidden IN (0, 1)),
    PRIMARY KEY (pokemon_id, ability_id, slot)
);

CREATE TABLE stat (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE pokemon_stat (
    pokemon_id INTEGER NOT NULL REFERENCES pokemon(id) ON DELETE CASCADE,
    stat_id INTEGER NOT NULL REFERENCES stat(id),
    base_stat INTEGER NOT NULL,
    effort INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (pokemon_id, stat_id)
);

CREATE TABLE species_text (
    id INTEGER PRIMARY KEY,
    species_id INTEGER NOT NULL REFERENCES pokemon_species(id) ON DELETE CASCADE,
    language TEXT NOT NULL,
    version_name TEXT NOT NULL DEFAULT '',
    text_kind TEXT NOT NULL CHECK (text_kind IN ('name', 'genus', 'flavor_text')),
    text TEXT NOT NULL,
    UNIQUE (species_id, language, version_name, text_kind, text)
);

CREATE TABLE evolution_node (
    id INTEGER PRIMARY KEY,
    chain_id INTEGER NOT NULL REFERENCES evolution_chain(id) ON DELETE CASCADE,
    species_id INTEGER NOT NULL REFERENCES pokemon_species(id),
    parent_node_id INTEGER REFERENCES evolution_node(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE evolution_condition (
    id INTEGER PRIMARY KEY,
    node_id INTEGER NOT NULL REFERENCES evolution_node(id) ON DELETE CASCADE,
    trigger_name TEXT,
    item_name TEXT,
    held_item_name TEXT,
    known_move_name TEXT,
    known_move_type_name TEXT,
    location_name TEXT,
    min_level INTEGER,
    min_happiness INTEGER,
    min_beauty INTEGER,
    min_affection INTEGER,
    time_of_day TEXT,
    gender INTEGER,
    needs_overworld_rain INTEGER CHECK (needs_overworld_rain IN (0, 1)),
    turn_upside_down INTEGER CHECK (turn_upside_down IN (0, 1)),
    relative_physical_stats INTEGER
);

CREATE TABLE pokemon_asset (
    id INTEGER PRIMARY KEY,
    pokemon_id INTEGER NOT NULL REFERENCES pokemon(id) ON DELETE CASCADE,
    asset_kind TEXT NOT NULL,
    local_path TEXT,
    source_url TEXT,
    media_type TEXT,
    sha256 TEXT,
    width INTEGER,
    height INTEGER,
    UNIQUE (pokemon_id, asset_kind)
);

CREATE TABLE tcg_set (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE,
    series TEXT,
    printed_total INTEGER,
    total INTEGER,
    ptcgo_code TEXT,
    release_date TEXT,
    api_updated_at TEXT,
    last_refreshed_at TEXT
);

CREATE TABLE tcg_card (
    id TEXT PRIMARY KEY,
    set_id TEXT NOT NULL REFERENCES tcg_set(id),
    name TEXT NOT NULL COLLATE NOCASE,
    number TEXT NOT NULL,
    supertype TEXT,
    level TEXT,
    hp INTEGER,
    evolves_from TEXT,
    converted_retreat_cost INTEGER,
    rarity TEXT,
    artist TEXT,
    flavor_text TEXT,
    regulation_mark TEXT,
    rules_text TEXT,
    last_refreshed_at TEXT
);

CREATE TABLE card_pokemon (
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    species_id INTEGER NOT NULL REFERENCES pokemon_species(id),
    PRIMARY KEY (card_id, species_id)
);

CREATE TABLE card_type (
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    type_id INTEGER NOT NULL REFERENCES type(id),
    slot INTEGER NOT NULL,
    PRIMARY KEY (card_id, type_id)
);

CREATE TABLE card_subtype (
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    subtype TEXT NOT NULL COLLATE NOCASE,
    slot INTEGER NOT NULL,
    PRIMARY KEY (card_id, subtype)
);

CREATE TABLE card_ability (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    ability_type TEXT,
    text TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE card_attack (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    damage TEXT,
    text TEXT,
    converted_energy_cost INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE card_attack_cost (
    attack_id INTEGER NOT NULL REFERENCES card_attack(id) ON DELETE CASCADE,
    energy_type TEXT NOT NULL,
    slot INTEGER NOT NULL,
    PRIMARY KEY (attack_id, slot)
);

CREATE TABLE card_effectiveness (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    effect_kind TEXT NOT NULL CHECK (effect_kind IN ('weakness', 'resistance')),
    type_name TEXT NOT NULL,
    value TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE card_retreat_cost (
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    energy_type TEXT NOT NULL,
    slot INTEGER NOT NULL,
    PRIMARY KEY (card_id, slot)
);

CREATE TABLE card_legality (
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    format_name TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (card_id, format_name)
);

CREATE TABLE set_legality (
    set_id TEXT NOT NULL REFERENCES tcg_set(id) ON DELETE CASCADE,
    format_name TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (set_id, format_name)
);

CREATE TABLE card_asset (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    asset_kind TEXT NOT NULL CHECK (asset_kind IN ('small', 'large')),
    local_path TEXT,
    source_url TEXT,
    media_type TEXT,
    sha256 TEXT,
    width INTEGER,
    height INTEGER,
    UNIQUE (card_id, asset_kind)
);

CREATE TABLE set_asset (
    id INTEGER PRIMARY KEY,
    set_id TEXT NOT NULL REFERENCES tcg_set(id) ON DELETE CASCADE,
    asset_kind TEXT NOT NULL CHECK (asset_kind IN ('logo', 'symbol')),
    local_path TEXT,
    source_url TEXT,
    media_type TEXT,
    sha256 TEXT,
    UNIQUE (set_id, asset_kind)
);

CREATE TABLE card_market_listing (
    id INTEGER PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES tcg_card(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    listing_url TEXT,
    source_updated_at TEXT,
    UNIQUE (card_id, provider)
);

CREATE TABLE card_price (
    listing_id INTEGER NOT NULL REFERENCES card_market_listing(id) ON DELETE CASCADE,
    variant TEXT NOT NULL,
    metric TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    PRIMARY KEY (listing_id, variant, metric)
);

CREATE INDEX idx_pokemon_display_order ON pokemon(display_order);
CREATE INDEX idx_pokemon_species_default ON pokemon(species_id, is_default);
CREATE INDEX idx_pokemon_type_type ON pokemon_type(type_id, pokemon_id);
CREATE INDEX idx_pokemon_ability_ability ON pokemon_ability(ability_id, pokemon_id);
CREATE INDEX idx_species_text_lookup ON species_text(species_id, language, text_kind);
CREATE INDEX idx_evolution_node_chain ON evolution_node(chain_id, parent_node_id, sort_order);
CREATE INDEX idx_tcg_set_release ON tcg_set(release_date DESC);
CREATE INDEX idx_tcg_card_name ON tcg_card(name COLLATE NOCASE);
CREATE INDEX idx_tcg_card_set_number ON tcg_card(set_id, number);
CREATE INDEX idx_tcg_card_rarity ON tcg_card(rarity);
CREATE INDEX idx_tcg_card_hp ON tcg_card(hp);
CREATE INDEX idx_card_pokemon_species ON card_pokemon(species_id, card_id);
CREATE INDEX idx_card_type_type ON card_type(type_id, card_id);
CREATE INDEX idx_card_subtype_value ON card_subtype(subtype, card_id);
CREATE INDEX idx_card_price_lookup ON card_price(listing_id, variant, metric);
CREATE INDEX idx_pokemon_refreshed ON pokemon(last_refreshed_at);
CREATE INDEX idx_tcg_card_refreshed ON tcg_card(last_refreshed_at);

INSERT INTO schema_metadata (key, value) VALUES ('schema_version', '1');
PRAGMA user_version = 1;