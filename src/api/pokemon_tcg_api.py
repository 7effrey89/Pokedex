"""Compatibility facade for callers; all upstream TCG access uses free TCGdex."""

from __future__ import annotations

from typing import Any

from src.api.tcgdex_api import TcgDexClient


class PokemonTCGTools(TcgDexClient):
    """Retain existing public helpers without the deprecated API or its keys."""

    def get_card_price(self, card_id: str) -> dict[str, Any]:
        card = self.get_card(card_id)["data"]
        return {
            "id": card["id"], "name": card["name"], "set": card["set"]["name"],
            "number": card["number"], "rarity": card.get("rarity"),
            "image": card.get("images", {}).get("small"),
            **{provider: {
                "url": card.get(provider, {}).get("url"),
                "updated": card.get(provider, {}).get("updatedAt"),
                "prices": card.get(provider, {}).get("prices", {}),
            } for provider in ("tcgplayer", "cardmarket")},
        }

    def format_card_info(self, card: dict[str, Any]) -> dict[str, Any]:
        info = {key: value for key, value in card.items() if not key.startswith("_")}
        set_data = card.get("set", {})
        images = set_data.get("images", {})
        info["set"] = {**set_data, "logo": images.get("logo"), "symbol": images.get("symbol")}
        return info

    def format_cards_response(self, cards_data: dict[str, Any]) -> list[dict[str, Any]]:
        return [self.format_card_info(card) for card in cards_data["data"]]

    def search_pokemon_cards(self, pokemon_name: str) -> str:
        response = self.search_cards(pokemon_name, page_size=5)
        cards = self.format_cards_response(response)
        if not cards:
            return f"Sorry, I couldn't find any trading cards for '{pokemon_name}'."
        total = response["totalCount"]
        text = f"**{pokemon_name.title()} Trading Cards** ({total} total cards found)\n\n"
        for card in cards:
            text += f"**{card['name']}** - {card['set']['name']}\n"
            if card.get("types"):
                text += f"Type: {', '.join(card['types'])} | "
            if card.get("hp"):
                text += f"HP: {card['hp']} | "
            if card.get("rarity"):
                text += f"Rarity: {card['rarity']}"
            text += "\n\n"
        if total > 5:
            text += f"_...and {total - 5} more cards_"
        return text
