"""PokeAPI-shaped Pokemon detail reads from the normalized SQLite catalog."""

from __future__ import annotations

from typing import Any

from src.db.database import SqliteDatabase


POKEAPI_ROOT = "https://pokeapi.co/api/v2"


def _resource(name: str | None, kind: str) -> dict[str, str] | None:
    if not name:
        return None
    return {"name": name, "url": f"{POKEAPI_ROOT}/{kind}/{name}/"}


class SqlitePokemonRepository:
    """Build the detail-view response contract without runtime PokeAPI calls."""

    def __init__(self, database: SqliteDatabase | None = None):
        self.database = database or SqliteDatabase()

    def get_pokemon(self, identifier: str) -> dict[str, Any] | None:
        connection = self.database.connect(read_only=True)
        try:
            row = connection.execute(
                """
                SELECT id, species_id, name, display_order, is_default,
                       base_experience, height_decimetres, weight_hectograms
                FROM pokemon WHERE name = ? COLLATE NOCASE OR id = ?
                ORDER BY CASE WHEN name = ? COLLATE NOCASE THEN 0 ELSE 1 END LIMIT 1
                """,
                (identifier, int(identifier) if identifier.isdigit() else -1, identifier),
            ).fetchone()
            if row is None:
                return None
            pokemon_id = int(row["id"])
            types = [
                {"slot": item["slot"], "type": _resource(item["name"], "type")}
                for item in connection.execute(
                    """
                    SELECT pt.slot, t.name FROM pokemon_type pt
                    JOIN type t ON t.id = pt.type_id
                    WHERE pt.pokemon_id = ? ORDER BY pt.slot
                    """,
                    (pokemon_id,),
                )
            ]
            abilities = [
                {
                    "slot": item["slot"],
                    "is_hidden": bool(item["is_hidden"]),
                    "ability": _resource(item["name"], "ability"),
                }
                for item in connection.execute(
                    """
                    SELECT pa.slot, pa.is_hidden, a.name FROM pokemon_ability pa
                    JOIN ability a ON a.id = pa.ability_id
                    WHERE pa.pokemon_id = ? ORDER BY pa.slot
                    """,
                    (pokemon_id,),
                )
            ]
            stats = [
                {
                    "base_stat": item["base_stat"],
                    "effort": item["effort"],
                    "stat": _resource(item["name"], "stat"),
                }
                for item in connection.execute(
                    """
                    SELECT ps.base_stat, ps.effort, s.name FROM pokemon_stat ps
                    JOIN stat s ON s.id = ps.stat_id
                    WHERE ps.pokemon_id = ? ORDER BY s.id
                    """,
                    (pokemon_id,),
                )
            ]
            cries = {
                item["asset_kind"].replace("cry_", ""): item["source_url"]
                for item in connection.execute(
                    """
                    SELECT asset_kind, source_url FROM pokemon_asset
                    WHERE pokemon_id = ? AND asset_kind IN ('cry_latest', 'cry_legacy')
                    """,
                    (pokemon_id,),
                )
            }
            return {
                "id": pokemon_id,
                "name": row["name"],
                "order": row["display_order"],
                "is_default": bool(row["is_default"]),
                "base_experience": row["base_experience"],
                "height": row["height_decimetres"],
                "weight": row["weight_hectograms"],
                "species": {
                    "name": connection.execute(
                        "SELECT name FROM pokemon_species WHERE id = ?", (row["species_id"],)
                    ).fetchone()["name"],
                    "url": f"{POKEAPI_ROOT}/pokemon-species/{row['species_id']}/",
                },
                "types": types,
                "abilities": abilities,
                "stats": stats,
                "cries": cries,
                "sprites": {},
            }
        finally:
            connection.close()

    def get_species(self, identifier: str) -> dict[str, Any] | None:
        connection = self.database.connect(read_only=True)
        try:
            row = connection.execute(
                """
                SELECT * FROM pokemon_species
                WHERE name = ? COLLATE NOCASE OR id = ?
                ORDER BY CASE WHEN name = ? COLLATE NOCASE THEN 0 ELSE 1 END LIMIT 1
                """,
                (identifier, int(identifier) if identifier.isdigit() else -1, identifier),
            ).fetchone()
            if row is None:
                return None
            species_id = int(row["id"])
            flavor = [
                {
                    "flavor_text": item["text"],
                    "language": _resource(item["language"], "language"),
                    "version": _resource(item["version_name"], "version"),
                }
                for item in connection.execute(
                    """
                    SELECT language, version_name, text FROM species_text
                    WHERE species_id = ? AND text_kind = 'flavor_text'
                    ORDER BY id
                    """,
                    (species_id,),
                )
            ]
            varieties = [
                {
                    "is_default": bool(item["is_default"]),
                    "pokemon": {
                        "name": item["name"],
                        "url": f"{POKEAPI_ROOT}/pokemon/{item['id']}/",
                    },
                }
                for item in connection.execute(
                    "SELECT id, name, is_default FROM pokemon WHERE species_id = ? ORDER BY display_order",
                    (species_id,),
                )
            ]
            chain_id = row["evolution_chain_id"]
            return {
                "id": species_id,
                "name": row["name"],
                "gender_rate": row["gender_rate"],
                "capture_rate": row["capture_rate"],
                "base_happiness": row["base_happiness"],
                "hatch_counter": row["hatch_counter"],
                "is_baby": bool(row["is_baby"]),
                "is_legendary": bool(row["is_legendary"]),
                "is_mythical": bool(row["is_mythical"]),
                "growth_rate": _resource(row["growth_rate_name"], "growth-rate"),
                "habitat": _resource(row["habitat_name"], "pokemon-habitat"),
                "egg_groups": [],
                "flavor_text_entries": flavor,
                "varieties": varieties,
                "evolution_chain": (
                    {"url": f"{POKEAPI_ROOT}/evolution-chain/{chain_id}/"} if chain_id else None
                ),
            }
        finally:
            connection.close()

    def get_evolution_chain(self, chain_id: int) -> dict[str, Any] | None:
        connection = self.database.connect(read_only=True)
        try:
            chain = connection.execute(
                "SELECT id, baby_trigger_item_name FROM evolution_chain WHERE id = ?", (chain_id,)
            ).fetchone()
            if chain is None:
                return None
            nodes = connection.execute(
                """
                SELECT n.id, n.parent_node_id, n.sort_order, s.id AS species_id, s.name
                FROM evolution_node n JOIN pokemon_species s ON s.id = n.species_id
                WHERE n.chain_id = ? ORDER BY n.sort_order, n.id
                """,
                (chain_id,),
            ).fetchall()
            conditions: dict[int, list[dict[str, Any]]] = {}
            for item in connection.execute(
                "SELECT * FROM evolution_condition WHERE node_id IN (SELECT id FROM evolution_node WHERE chain_id = ?)",
                (chain_id,),
            ):
                conditions.setdefault(item["node_id"], []).append(self._evolution_condition(item))
            children: dict[int | None, list[Any]] = {}
            for node in nodes:
                children.setdefault(node["parent_node_id"], []).append(node)

            def build(node) -> dict[str, Any]:
                return {
                    "is_baby": False,
                    "species": {
                        "name": node["name"],
                        "url": f"{POKEAPI_ROOT}/pokemon-species/{node['species_id']}/",
                    },
                    "evolution_details": conditions.get(node["id"], []),
                    "evolves_to": [build(child) for child in children.get(node["id"], [])],
                }

            roots = children.get(None, [])
            if not roots:
                return None
            return {
                "id": chain_id,
                "baby_trigger_item": _resource(chain["baby_trigger_item_name"], "item"),
                "chain": build(roots[0]),
            }
        finally:
            connection.close()

    def get_type(self, identifier: str) -> dict[str, Any] | None:
        """Return a PokeAPI-shaped type chart when normalized relations exist."""
        connection = self.database.connect(read_only=True)
        try:
            row = connection.execute(
                """
                SELECT id, name FROM type
                WHERE name = ? COLLATE NOCASE OR id = ?
                ORDER BY CASE WHEN name = ? COLLATE NOCASE THEN 0 ELSE 1 END LIMIT 1
                """,
                (identifier, int(identifier) if identifier.isdigit() else -1, identifier),
            ).fetchone()
            if row is None:
                return None
            relations = {
                key: [] for key in (
                    "double_damage_from", "double_damage_to",
                    "half_damage_from", "half_damage_to",
                    "no_damage_from", "no_damage_to",
                )
            }
            for item in connection.execute(
                """
                SELECT r.relation_kind, t.id, t.name
                FROM type_damage_relation r
                JOIN type t ON t.id = r.related_type_id
                WHERE r.type_id = ? ORDER BY r.relation_kind, t.id
                """,
                (row["id"],),
            ):
                relations[item["relation_kind"]].append({
                    "name": item["name"],
                    "url": f"{POKEAPI_ROOT}/type/{item['id']}/",
                })
            if not any(relations.values()):
                return None
            return {"id": row["id"], "name": row["name"], "damage_relations": relations}
        finally:
            connection.close()

    @staticmethod
    def _evolution_condition(item) -> dict[str, Any]:
        return {
            "trigger": _resource(item["trigger_name"], "evolution-trigger"),
            "item": _resource(item["item_name"], "item"),
            "held_item": _resource(item["held_item_name"], "item"),
            "known_move": _resource(item["known_move_name"], "move"),
            "known_move_type": _resource(item["known_move_type_name"], "type"),
            "location": _resource(item["location_name"], "location"),
            "min_level": item["min_level"],
            "min_happiness": item["min_happiness"],
            "min_beauty": item["min_beauty"],
            "min_affection": item["min_affection"],
            "time_of_day": item["time_of_day"] or "",
            "gender": item["gender"],
            "needs_overworld_rain": bool(item["needs_overworld_rain"]),
            "turn_upside_down": bool(item["turn_upside_down"]),
            "relative_physical_stats": item["relative_physical_stats"],
        }
