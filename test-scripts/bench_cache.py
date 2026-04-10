import time
from src.tools.tool_handlers import execute_tool

t0 = time.perf_counter()
r = execute_tool('search_cards_by_set', {'set_id': 'sv8', 'slim': True})
t1 = time.perf_counter()
print(f"Slim request: {(t1-t0)*1000:.0f}ms, {len(r.get('cards',[]))} cards")

t0 = time.perf_counter()
r = execute_tool('search_cards_by_set', {'set_id': 'sv8', 'slim': False})
t1 = time.perf_counter()
print(f"Full request: {(t1-t0)*1000:.0f}ms")

t0 = time.perf_counter()
r = execute_tool('get_tcg_sets', {})
t1 = time.perf_counter()
print(f"Get sets: {(t1-t0)*1000:.0f}ms, {len(r.get('sets',[]))} sets")
