// Interface definitions for Pokemon data

export interface PokemonResponse {
  content: Array<{
    type: "text";
    text: string;
  }>;
  [key: string]: unknown;
}

export interface PokemonSpecies {
  name: string;
  url: string;
}

export interface GenerationData {
  pokemon_species: PokemonSpecies[];
}

export interface PokemonType {
  type: {
    name: string;
  };
}

export interface PokemonAbility {
  ability: {
    name: string;
  };
}

export interface FlavorTextEntry {
  flavor_text: string;
  language: {
    name: string;
  };
}

export interface Pokemon {
  id: number;
  name: string;
  height: number;
  weight: number;
  types: PokemonType[];
  abilities: PokemonAbility[];
  sprites: {
    front_default: string;
    other?: {
      "official-artwork"?: {
        front_default: string;
      };
    };
  };
  stats: Array<{
    base_stat: number;
    stat: {
      name: string;
    };
  }>;
}

export interface PokemonSpeciesDetails {
  flavor_text_entries: FlavorTextEntry[];
}

export interface TypeData {
  pokemon: {
    pokemon: {
      name: string;
      url: string;
    };
  }[];
}
