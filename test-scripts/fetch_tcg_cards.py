import requests
import json

# Test the Pokemon TCG API - Search for Pikachu cards
API = "https://api.pokemontcg.io/v2/cards"
PARAMS = {"q": "name:pikachu", "pageSize": 5}

print("Fetching Pikachu cards from Pokemon TCG API...")
print(f"URL: {API}")
print(f"Query: {PARAMS['q']}")
print("-" * 60)

resp = requests.get(API, params=PARAMS, timeout=30)
resp.raise_for_status()

data = resp.json()

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
output_file = "tcg_cards_response.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nFull response saved to: {output_file}")
