"""
Test script for the get_card_price feature
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.api.pokemon_tcg_api import PokemonTCGTools
from src.tools.tool_handlers import handle_get_card_price

def test_get_card_price():
    """Test the get_card_price functionality"""
    
    # Store all results for JSON output
    all_results = {}
    
    # Test 1: Direct API call
    print("Test 1: Direct API call to PokemonTCGTools.get_card_price()")
    print("-" * 60)
    tcg_api = PokemonTCGTools()
    
    # Using a valid modern card: Pikachu ex from Prismatic Evolutions
    card_id = "sv8pt5-179"
    print(f"Fetching price for card: {card_id}")
    
    result = tcg_api.get_card_price(card_id)
    all_results['test1_direct_api'] = result
    
    if result:
        print(f"✅ Success!")
        print(f"Card: {result.get('name')}")
        print(f"Set: {result.get('set')}")
        print(f"Number: {result.get('number')}")
        print(f"Rarity: {result.get('rarity')}")
        
        # TCGPlayer prices
        tcgplayer = result.get('tcgplayer', {})
        if tcgplayer.get('prices'):
            print("\nTCGPlayer Prices:")
            for variant, prices in tcgplayer['prices'].items():
                print(f"  {variant}:")
                if isinstance(prices, dict):
                    for price_type, value in prices.items():
                        print(f"    {price_type}: ${value}")
        
        # Cardmarket prices
        cardmarket = result.get('cardmarket', {})
        if cardmarket.get('prices'):
            print("\nCardmarket Prices:")
            for price_type, value in cardmarket['prices'].items():
                print(f"  {price_type}: ${value}")
    else:
        print(f"❌ Failed to fetch card price")
    
    print("\n")
    
    # Test 2: Tool handler call
    print("Test 2: Tool handler call (handle_get_card_price)")
    print("-" * 60)
    
    handler_result = handle_get_card_price(card_id)
    all_results['test2_tool_handler'] = handler_result
    
    if "error" in handler_result:
        print(f"❌ Error: {handler_result['error']}")
    elif "card" in handler_result:
        print(f"✅ Success!")
        card_info = handler_result['card']
        print(f"Card: {card_info.get('name')}")
        print(f"Set: {card_info.get('set')}")
    else:
        print(f"❌ Unexpected result format")
    
    print("\n")
    
    # Test 3: Invalid card ID
    print("Test 3: Invalid card ID")
    print("-" * 60)
    
    invalid_result = handle_get_card_price("invalid-999")
    all_results['test3_invalid_card'] = invalid_result
    
    if "error" in invalid_result:
        print(f"✅ Correctly handled invalid card: {invalid_result['error']}")
    else:
        print(f"❌ Should have returned an error for invalid card")
    
    # Save all results to JSON file
    output_file = os.path.join(os.path.dirname(__file__), "test_card_price_response.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        import json
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\nFull test results saved to: {output_file}")
    
    return all_results

if __name__ == "__main__":
    print("=" * 60)
    print("Pokemon TCG Card Price Feature Test")
    print("=" * 60)
    print()
    test_get_card_price()
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
