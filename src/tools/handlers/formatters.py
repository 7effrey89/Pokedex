"""
Shared Formatting Utilities for Tool Handlers

Contains helper functions for formatting Pokemon data and building responses.
"""

from typing import Dict, Any, Optional
import re


def build_pokemon_assistant_text(pokemon_info: Dict[str, Any]) -> Optional[str]:
    """Generate the markdown-style assistant message for a Pokemon entry."""
    if not pokemon_info or 'name' not in pokemon_info:
        return None

    lines = []
    header = f"**{pokemon_info.get('name').title()}**"
    if pokemon_info.get('id'):
        header += f" (#{pokemon_info.get('id')})"
    lines.append(header)

    description = pokemon_info.get('description')
    if description:
        lines.append('')
        lines.append(description.strip())

    types = pokemon_info.get('types') or []
    if types:
        rendered_types = ', '.join([t.title() for t in types])
        lines.append('')
        lines.append(f"**Type(s):** {rendered_types}")

    if pokemon_info.get('height') is not None:
        lines.append(f"**Height:** {pokemon_info.get('height')}m")
    if pokemon_info.get('weight') is not None:
        lines.append(f"**Weight:** {pokemon_info.get('weight')}kg")

    abilities = pokemon_info.get('abilities') or []
    if abilities:
        rendered_abilities = ', '.join([a.title() for a in abilities])
        lines.append(f"**Abilities:** {rendered_abilities}")

    stats = pokemon_info.get('stats') or {}
    if stats:
        lines.append('')
        lines.append("**Base Stats:**")
        for stat_name, value in stats.items():
            pretty_name = stat_name.replace('-', ' ').title()
            lines.append(f"- {pretty_name}: {value}")

    markdown = '\n'.join(line for line in lines if line is not None)
    return markdown.strip() if markdown.strip() else None


def build_official_artwork_url(pokemon_id: Any) -> Optional[str]:
    """Build the official artwork URL for a Pokemon by ID."""
    try:
        pokemon_id = int(pokemon_id)
    except (TypeError, ValueError):
        return None

    return (
        "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"
        "/other/official-artwork/" f"{pokemon_id}.png"
    )


def extract_pokemon_identity_from_content(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract Pokemon name and ID from result content."""
    for item in result.get('content', []):
        if item.get('type') != 'text':
            continue
        text = item.get('text', '')
        match = re.search(r"#\s*(.+?)\s*\(#(\d+)\)", text)
        if match:
            name = match.group(1).strip()
            try:
                pokemon_id = int(match.group(2))
            except ValueError:
                continue
            return {'name': name, 'id': pokemon_id}
    return None


def apply_official_artwork(result: Dict[str, Any]) -> None:
    """Apply official artwork URL to Pokemon result."""
    if not result or 'error' in result:
        return

    pokemon_data = result.get('pokemon_data') if isinstance(result.get('pokemon_data'), dict) else {}
    pokemon_id = result.get('id') or pokemon_data.get('id')
    identity = None
    if not pokemon_id:
        identity = extract_pokemon_identity_from_content(result)
        if identity:
            pokemon_id = identity.get('id')
            if identity.get('name') and not result.get('name'):
                result['name'] = identity['name']
    if identity and identity.get('name') and not pokemon_data.get('name'):
        pokemon_data['name'] = identity['name']

    if not pokemon_id:
        return

    if not result.get('id'):
        result['id'] = pokemon_id
    if not pokemon_data.get('id'):
        pokemon_data['id'] = pokemon_id

    artwork = build_official_artwork_url(pokemon_id)
    if not artwork:
        return

    if not result.get('image'):
        result['image'] = artwork
    if not result.get('sprite'):
        result['sprite'] = artwork

    if not pokemon_data:
        pokemon_data = {}
        result['pokemon_data'] = pokemon_data
    if not pokemon_data.get('image'):
        pokemon_data['image'] = artwork
    if not pokemon_data.get('sprite'):
        pokemon_data['sprite'] = artwork


def annotate_pokemon_result_with_text(result: Dict[str, Any]) -> Dict[str, Any]:
    """Annotate Pokemon result with formatted text and artwork."""
    if not result or 'error' in result:
        return result
    if not result.get('assistant_text'):
        assistant_text = build_pokemon_assistant_text(result)
        if assistant_text:
            result['assistant_text'] = assistant_text
    apply_official_artwork(result)
    return result
