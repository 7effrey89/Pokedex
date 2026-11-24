import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.api.pokemon_tcg_api import PokemonTCGTools

print("Fetching Pikachu cards from free TCGdex...")
print("-" * 60)

data = PokemonTCGTools().search_cards("Pikachu", page_size=5)

# Pretty print the response
print(f"\nTotal cards found: {data.get('totalCount', 0)}")
print(f"Showing {len(data.get('data', []))} cards:\n")

for i, card in enumerate(data.get('data', []), 1):
    print(f"{i}. {card.get('name')} - {card.get('id')}")
    print(f"   Set: {card.get('set', {}).get('name', 'Unknown')}")
    print(f"   Types: {', '.join(card.get('types', []))}")
    if card.get('hp'):
        print(f"   HP: {card.get('hp')}")
    print(f"   Image: {card.get('images', {}).get('small', 'N/A')}")
    print()

# Save full response to file
output_file = os.path.join(os.path.dirname(__file__), "fetch_tcg_cards_response.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nFull response saved to: {output_file}")
