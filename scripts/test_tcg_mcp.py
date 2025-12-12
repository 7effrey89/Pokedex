"""
Test Pokemon TCG card search via MCP server
This tests the same infrastructure used by the chat app
"""
import sys
import os

# Add parent directory to path to import tool_handlers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool_handlers import execute_tool
import json

print("Testing Pokemon TCG Card Search via MCP Server")
print("=" * 60)

# Test 1: Search for Pikachu cards
print("\nTest 1: Searching for Pikachu cards...")
print("-" * 60)
result = execute_tool('search_pokemon_cards', {'pokemon_name': 'pikachu'})

if 'error' in result:
    print(f"❌ Error: {result['error']}")
else:
    print(f"✅ Success!")
    print(f"Cards found: {result.get('card_count', 0)}")
    
    cards = result.get('cards', [])
    for i, card in enumerate(cards[:5], 1):  # Show first 5
        print(f"\n{i}. {card.get('name')} ({card.get('id')})")
        print(f"   Set: {card.get('set', 'Unknown')}")
        print(f"   HP: {card.get('hp', 'N/A')}")
        print(f"   Types: {', '.join(card.get('types', []))}")
        print(f"   Rarity: {card.get('rarity', 'Unknown')}")

# Test 2: Search with filters
print("\n\n" + "=" * 60)
print("\nTest 2: Searching for Fire-type cards with 100+ HP...")
print("-" * 60)
result2 = execute_tool('search_pokemon_cards', {
    'card_type': 'Fire',
    'hp_min': 100
})

if 'error' in result2:
    print(f"❌ Error: {result2['error']}")
else:
    print(f"✅ Success!")
    print(f"Cards found: {result2.get('card_count', 0)}")
    
    cards = result2.get('cards', [])
    for i, card in enumerate(cards[:3], 1):  # Show first 3
        print(f"\n{i}. {card.get('name')} ({card.get('id')})")
        print(f"   HP: {card.get('hp', 'N/A')}")
        print(f"   Types: {', '.join(card.get('types', []))}")

# Save results
print("\n\n" + "=" * 60)
output_file = "mcp_tcg_test_results.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump({
        'test1_pikachu': result,
        'test2_fire_100hp': result2
    }, f, indent=2, ensure_ascii=False)

print(f"\nFull results saved to: {output_file}")
