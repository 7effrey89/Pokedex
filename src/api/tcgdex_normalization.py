"""Convert TCGdex data to the catalog's existing card and price contracts."""

from __future__ import annotations

import math
from typing import Any


def legalities(value: dict[str, Any]) -> dict[str, str]:
    return {name: "Legal" if status else "Not Legal"
            for name, status in value.items() if isinstance(status, bool)}


def normalize_set(value: dict[str, Any], set_id: str) -> dict[str, Any]:
    counts = value.get("cardCount", {})
    return {
        "id": set_id, "name": value["name"],
        "series": value.get("serie", {}).get("name"),
        "printedTotal": counts.get("official"), "total": counts.get("total"),
        "ptcgoCode": value.get("tcgOnline") or value.get("abbreviation", {}).get("official"),
        "releaseDate": value.get("releaseDate") or "", "updatedAt": value.get("updated"),
        "legalities": legalities(value.get("legal", {})),
        "images": {kind: f"{value[kind]}.png" for kind in ("logo", "symbol") if value.get(kind)},
    }


def _amount(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def normalize_prices(value: dict[str, Any]) -> dict[str, Any]:
    """Keep USD/EUR and variant distinctions; never turn unavailable amounts into zero."""
    result = {}
    tcg = value.get("tcgplayer")
    if isinstance(tcg, dict):
        if tcg.get("unit") != "USD":
            raise ValueError(f"Unexpected TCGdex TCGPlayer currency: {tcg.get('unit')}")
        metric_names = {
            "lowPrice": "low", "midPrice": "mid", "highPrice": "high",
            "marketPrice": "market", "directLowPrice": "directLow",
        }
        variant_names = {
            "reverse-holofoil": "reverseHolofoil", "1st-edition": "1stEditionNormal",
            "1st-edition-holofoil": "1stEditionHolofoil",
            "unlimited": "unlimitedNormal", "unlimited-holofoil": "unlimitedHolofoil",
        }
        prices = {}
        product_id = None
        for variant, metrics in tcg.items():
            if not isinstance(metrics, dict):
                continue
            converted = {target: metrics[source] for source, target in metric_names.items()
                         if _amount(metrics.get(source))}
            if converted:
                prices[variant_names.get(variant, variant)] = converted
                product_id = product_id or metrics.get("productId")
        result["tcgplayer"] = {
            "url": f"https://www.tcgplayer.com/product/{product_id}" if product_id else None,
            "updatedAt": tcg.get("updated"), "prices": prices,
        }
    market = value.get("cardmarket")
    if isinstance(market, dict):
        if market.get("unit") != "EUR":
            raise ValueError(f"Unexpected TCGdex Cardmarket currency: {market.get('unit')}")
        metric_names = {
            "avg": "averageSellPrice", "low": "lowPrice", "trend": "trendPrice",
            "avg1": "avg1", "avg7": "avg7", "avg30": "avg30",
            "avg-holo": "reverseHoloSell", "low-holo": "reverseHoloLow",
            "trend-holo": "reverseHoloTrend", "avg1-holo": "reverseHoloAvg1",
            "avg7-holo": "reverseHoloAvg7", "avg30-holo": "reverseHoloAvg30",
        }
        result["cardmarket"] = {
            "url": "https://www.cardmarket.com/en/Pokemon/Products?idProduct="
                   + str(market["idProduct"]) if market.get("idProduct") else None,
            "updatedAt": market.get("updated"),
            "prices": {target: market[source] for source, target in metric_names.items()
                       if _amount(market.get(source))},
        }
    return result


def normalize_card(value: dict[str, Any], card_id: str, number: str, set_data: dict[str, Any]) -> dict[str, Any]:
    category = value["category"]
    if category not in {"Pokemon", "Trainer", "Energy"}:
        raise ValueError(f"Unsupported TCGdex card category: {category}")
    stage = {"Stage1": "Stage 1", "Stage2": "Stage 2"}.get(value.get("stage"), value.get("stage"))
    subtypes = [item for item in (stage, value.get("suffix"), value.get("trainerType"),
                                value.get("energyType")) if item]
    retreat = value.get("retreat", 0)
    card = {
        "_source": "tcgdex", "id": card_id, "number": number, "name": value["name"],
        "supertype": "Pok\u00e9mon" if category == "Pokemon" else category,
        "subtypes": subtypes, "set": set_data, "types": value.get("types", []),
        "hp": value.get("hp"), "level": value.get("level"), "evolvesFrom": value.get("evolveFrom"),
        "nationalPokedexNumbers": value.get("dexId", []), "rarity": value.get("rarity"),
        "artist": value.get("illustrator"), "flavorText": value.get("description"),
        "regulationMark": value.get("regulationMark"),
        "rules": [value["effect"]] if value.get("effect") else [],
        "legalities": legalities(value.get("legal", {})),
        "retreatCost": ["Colorless"] * retreat, "convertedRetreatCost": retreat,
        "weaknesses": value.get("weaknesses", []), "resistances": value.get("resistances", []),
        "abilities": [{"name": ability["name"], "type": ability.get("type"), "text": ability.get("effect")}
                      for ability in value.get("abilities", [])],
        "attacks": [{"name": attack["name"], "cost": attack.get("cost", []),
                     "convertedEnergyCost": len(attack.get("cost", [])),
                     "damage": "" if attack.get("damage") is None else str(attack["damage"]), "text": attack.get("effect")}
                    for attack in value.get("attacks", [])],
        "images": {"small": f"{value['image']}/low.png", "large": f"{value['image']}/high.png"}
                  if value.get("image") else {},
    }
    card.update(normalize_prices(value.get("pricing") or {}))
    return card
