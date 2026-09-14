-- Catalog schema v2: per-record refresh provenance for explicit upstream refreshes.

ALTER TABLE pokemon ADD COLUMN last_refreshed_at TEXT;
ALTER TABLE pokemon_species ADD COLUMN last_refreshed_at TEXT;
ALTER TABLE tcg_card ADD COLUMN last_refreshed_at TEXT;
ALTER TABLE tcg_set ADD COLUMN last_refreshed_at TEXT;

CREATE INDEX idx_pokemon_refreshed ON pokemon(last_refreshed_at);
CREATE INDEX idx_tcg_card_refreshed ON tcg_card(last_refreshed_at);

PRAGMA user_version = 2;
