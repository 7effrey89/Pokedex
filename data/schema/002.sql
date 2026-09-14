-- Catalog schema v2: normalized PokeAPI type damage relations.

CREATE TABLE type_damage_relation (
	type_id INTEGER NOT NULL REFERENCES type(id) ON DELETE CASCADE,
	related_type_id INTEGER NOT NULL REFERENCES type(id) ON DELETE CASCADE,
	relation_kind TEXT NOT NULL CHECK (relation_kind IN (
		'double_damage_from', 'double_damage_to',
		'half_damage_from', 'half_damage_to',
		'no_damage_from', 'no_damage_to'
	)),
	PRIMARY KEY (type_id, related_type_id, relation_kind)
);

CREATE INDEX idx_type_damage_relation_kind
	ON type_damage_relation(type_id, relation_kind);

PRAGMA user_version = 2;
