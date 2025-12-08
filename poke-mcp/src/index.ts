import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { createServer } from "http";
import { URL } from "url";
import { z } from "zod";
import {
  Pokemon,
  PokemonAbility,
  PokemonResponse,
  PokemonSpeciesDetails,
  PokemonType,
  GenerationData,
  TypeData,
} from "./types.js";

const POKEAPI_BASE_URL = "https://pokeapi.co/api/v2";
const USER_AGENT = "pokedex-mcp/1.0";

// Region to generation mapping
const REGION_TO_GENERATION: Record<string, number> = {
  kanto: 1,
  johto: 2,
  hoenn: 3,
  sinnoh: 4,
  unova: 5,
  kalos: 6,
  alola: 7,
  galar: 8,
  paldea: 9,
};

// Create server instance
const server = new McpServer({
  name: "pokedex",
  version: "1.0.0",
});

// Helper function for making PokeAPI requests
async function fetchFromPokeAPI<T>(endpoint: string): Promise<T | null> {
  const headers = {
    "User-Agent": USER_AGENT,
  };

  try {
    const response = await fetch(`${POKEAPI_BASE_URL}${endpoint}`, { headers });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    console.error("Error making PokeAPI request:", error);
    return null;
  }
}

// Helper function to get a random item from an array
function getRandomItem<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)];
}

// Helper function to capitalize the first letter of a string
function capitalizeFirstLetter(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// Helper function to get English flavor text
function getEnglishFlavorText(species: PokemonSpeciesDetails): string {
  return (
    species.flavor_text_entries
      .find((entry) => entry.language.name === "en")
      ?.flavor_text.replace(/\n/g, " ")
      .replace(/\f/g, " ") || "No description available."
  );
}

// Helper function to format Pokémon types
function formatPokemonTypes(types: PokemonType[]): string {
  return types.map((t) => capitalizeFirstLetter(t.type.name)).join(", ");
}

// Helper function to format Pokémon abilities
function formatPokemonAbilities(abilities: PokemonAbility[]): string {
  return abilities.map((a) => capitalizeFirstLetter(a.ability.name)).join(", ");
}

// Helper function to get detailed Pokémon information
async function getPokemonDetails(pokemonNameOrId: string) {
  const pokemon = await fetchFromPokeAPI<Pokemon>(
    `/pokemon/${pokemonNameOrId.toLowerCase()}`
  );
  if (!pokemon) return null;

  const species = await fetchFromPokeAPI<PokemonSpeciesDetails>(
    `/pokemon-species/${pokemon.id}`
  );
  if (!species) return null;

  return { pokemon, species };
}

// Helper function to format Pokémon response
function formatPokemonResponse(
  pokemon: Pokemon,
  species: PokemonSpeciesDetails
): PokemonResponse {
  const types = formatPokemonTypes(pokemon.types);
  const abilities = formatPokemonAbilities(pokemon.abilities);
  const flavorText = getEnglishFlavorText(species);

  const text = `
# ${capitalizeFirstLetter(pokemon.name)} (#${pokemon.id})

**Types:** ${types}
**Height:** ${pokemon.height / 10}m
**Weight:** ${pokemon.weight / 10}kg
**Abilities:** ${abilities}

**Description:** ${flavorText}
  `.trim();

  return {
    content: [
      {
        type: "text",
        text: text,
      },
    ],
  };
}

// Helper function to get a random Pokémon
async function getRandomPokemon(): Promise<PokemonResponse> {
  // There are currently around 1000+ Pokémon, but we'll limit to 1000 to be safe
  const randomId = Math.floor(Math.random() * 1000) + 1;
  const details = await getPokemonDetails(randomId.toString());

  if (!details) {
    return {
      content: [
        {
          type: "text",
          text: "Failed to retrieve a random Pokémon. Please try again.",
        },
      ],
    };
  }

  return formatPokemonResponse(details.pokemon, details.species);
}

// Helper function to get a random Pokémon from a region
async function getRandomPokemonFromRegion(
  region: string
): Promise<PokemonResponse> {
  const normalizedRegion = region.toLowerCase();
  const generation = REGION_TO_GENERATION[normalizedRegion];

  if (!generation) {
    return {
      content: [
        {
          type: "text",
          text: `Unknown region: ${region}. Available regions are: ${Object.keys(
            REGION_TO_GENERATION
          ).join(", ")}`,
        },
      ],
    };
  }

  // Get all Pokémon from this generation
  const generationData = await fetchFromPokeAPI<GenerationData>(
    `/generation/${generation}`
  );

  if (
    !generationData ||
    !generationData.pokemon_species ||
    generationData.pokemon_species.length === 0
  ) {
    return {
      content: [
        {
          type: "text",
          text: `Failed to retrieve Pokémon from the ${normalizedRegion} region.`,
        },
      ],
    };
  }

  // Select a random Pokémon
  const randomPokemon = getRandomItem(generationData.pokemon_species);

  // Get detailed information about this Pokémon
  const details = await getPokemonDetails(randomPokemon.name);

  if (!details) {
    return {
      content: [
        {
          type: "text",
          text: `Failed to retrieve details for the selected Pokémon from ${normalizedRegion}.`,
        },
      ],
    };
  }

  // Add region information to the response
  const types = formatPokemonTypes(details.pokemon.types);
  const abilities = formatPokemonAbilities(details.pokemon.abilities);
  const flavorText = getEnglishFlavorText(details.species);

  return {
    content: [
      {
        type: "text",
        text: `
# Random ${capitalizeFirstLetter(
          normalizedRegion
        )} Pokémon: ${capitalizeFirstLetter(details.pokemon.name)} (#${
          details.pokemon.id
        })

**Types:** ${types}
**Height:** ${details.pokemon.height / 10}m
**Weight:** ${details.pokemon.weight / 10}kg
**Abilities:** ${abilities}

**Description:** ${flavorText}
        `.trim(),
      },
    ],
  };
}

// Helper function to get a random Pokémon of a specific type
async function getRandomPokemonByType(type: string): Promise<PokemonResponse> {
  const normalizedType = type.toLowerCase();

  // Get all Pokémon of this type
  const typeData = await fetchFromPokeAPI<TypeData>(`/type/${normalizedType}`);

  if (!typeData || !typeData.pokemon || typeData.pokemon.length === 0) {
    return {
      content: [
        {
          type: "text",
          text: `Unknown type: ${type} or no Pokémon found of this type.`,
        },
      ],
    };
  }

  // Select a random Pokémon
  const randomPokemon = getRandomItem(typeData.pokemon);

  // Get detailed information about this Pokémon
  const details = await getPokemonDetails(randomPokemon.pokemon.name);

  if (!details) {
    return {
      content: [
        {
          type: "text",
          text: `Failed to retrieve details for the selected ${normalizedType} Pokémon.`,
        },
      ],
    };
  }

  // Add type information to the response
  const types = formatPokemonTypes(details.pokemon.types);
  const abilities = formatPokemonAbilities(details.pokemon.abilities);
  const flavorText = getEnglishFlavorText(details.species);

  return {
    content: [
      {
        type: "text",
        text: `
# Random ${capitalizeFirstLetter(
          normalizedType
        )} Pokémon: ${capitalizeFirstLetter(details.pokemon.name)} (#${
          details.pokemon.id
        })

**Types:** ${types}
**Height:** ${details.pokemon.height / 10}m
**Weight:** ${details.pokemon.weight / 10}kg
**Abilities:** ${abilities}

**Description:** ${flavorText}
        `.trim(),
      },
    ],
  };
}

// Helper function to get Pokémon by ID
async function getPokemonById(id: number): Promise<PokemonResponse> {
  const details = await getPokemonDetails(id.toString());

  if (!details) {
    return {
      content: [
        {
          type: "text",
          text: `No Pokémon found with ID #${id}.`,
        },
      ],
    };
  }

  return formatPokemonResponse(details.pokemon, details.species);
}

// Register Pokémon tools

// Tool: get-pokemon - Get detailed info about a specific Pokemon
server.tool(
  "get-pokemon",
  "Get detailed information about a specific Pokémon by name or ID",
  {
    name: z
      .string()
      .describe("The name or ID of the Pokémon (e.g., 'pikachu', '25')"),
  },
  async ({ name }, _extra) => {
    const details = await getPokemonDetails(name);

    if (!details) {
      return {
        content: [
          {
            type: "text",
            text: `No Pokémon found with name or ID: ${name}`,
          },
        ],
      };
    }

    return formatPokemonResponse(details.pokemon, details.species);
  }
);

// Tool: random-pokemon - Get a random Pokemon
server.tool(
  "random-pokemon",
  "Get a random Pokémon",
  {},
  async (_args, _extra) => {
    return await getRandomPokemon();
  }
);

// Tool: random-pokemon-from-region - Get random Pokemon from a specific region
server.tool(
  "random-pokemon-from-region",
  "Get a random Pokémon from a specific region",
  {
    region: z
      .string()
      .describe("The Pokémon region (e.g., kanto, johto, hoenn, sinnoh, unova, kalos, alola, galar, paldea)"),
  },
  async ({ region }, _extra) => {
    return await getRandomPokemonFromRegion(region);
  }
);

// Tool: random-pokemon-by-type - Get random Pokemon of a specific type
server.tool(
  "random-pokemon-by-type",
  "Get a random Pokémon of a specific type",
  {
    type: z
      .string()
      .describe("The Pokémon type (e.g., fire, water, grass, electric, psychic, etc.)"),
  },
  async ({ type }, _extra) => {
    return await getRandomPokemonByType(type);
  }
);

// Tool: pokemon-query - Natural language query interface
server.tool(
  "pokemon-query",
  "Answer natural language Pokémon queries",
  {
    query: z.string().describe("A natural language query about Pokémon"),
  },
  async ({ query }, _extra) => {
    const normalizedQuery = query.toLowerCase();

    // Check for Pokémon number query
    const numberMatch =
      normalizedQuery.match(/pokemon\s+#?(\d+)/i) ||
      normalizedQuery.match(/what\s+is\s+pokemon\s+#?(\d+)/i);
    if (numberMatch) {
      const pokemonId = parseInt(numberMatch[1], 10);
      return await getPokemonById(pokemonId);
    }

    // Check for random Pokémon request
    if (
      normalizedQuery.includes("random pokemon") &&
      !normalizedQuery.includes("from") &&
      !normalizedQuery.includes("type")
    ) {
      return await getRandomPokemon();
    }

    // Check for random Pokémon from region
    const regionMatch = normalizedQuery.match(/random pokemon from (\w+)/i);
    if (regionMatch) {
      const region = regionMatch[1].toLowerCase();
      return await getRandomPokemonFromRegion(region);
    }

    // Check for random Pokémon by type
    const typeMatch =
      normalizedQuery.match(/random (\w+) pokemon/i) ||
      normalizedQuery.match(/random pokemon of type (\w+)/i);
    if (typeMatch) {
      const type = typeMatch[1].toLowerCase();
      const validTypes = [
        "normal", "fire", "water", "grass", "electric", "ice",
        "fighting", "poison", "ground", "flying", "psychic",
        "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy",
      ];
      if (validTypes.includes(type)) {
        return await getRandomPokemonByType(type);
      }
    }

    // Default response for unrecognized queries
    return {
      content: [
        {
          type: "text",
          text: `
I can help with Pokémon queries! Try asking:
- "What is pokemon #25?"
- "Give me a random Pokémon"
- "Give me a random Pokémon from Kanto"
- "Give me a random Fire Pokémon"
          `.trim(),
        },
      ],
    };
  }
);

// Main function to start the HTTP server
async function main() {
  const port = process.env.PORT ? parseInt(process.env.PORT) : 3001;
  const transports = new Map<string, SSEServerTransport>();

  const httpServer = createServer(async (req, res) => {
    const url = new URL(req.url!, `http://${req.headers.host}`);
    const path = url.pathname;
    const sessionId = url.searchParams.get("sessionId");

    // Enable CORS for all requests
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader(
      "Access-Control-Allow-Headers",
      "Content-Type, Authorization"
    );

    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    if (path === "/sse") {
      if (req.method === "GET") {
        // Handle SSE connection
        const transport = new SSEServerTransport("/message", res);
        transports.set(transport.sessionId, transport);

        // Clean up on close
        transport.onclose = () => {
          transports.delete(transport.sessionId);
        };

        await server.connect(transport);
        console.error(`New SSE connection established: ${transport.sessionId}`);
      } else {
        res.writeHead(405).end("Method not allowed");
      }
    } else if (path === "/message") {
      if (req.method === "POST" && sessionId) {
        // Handle message posting
        const transport = transports.get(sessionId);
        if (transport) {
          // @ts-ignore - handlePostMessage exists on SSEServerTransport
          await transport.handlePostMessage(req, res);
        } else {
          res.writeHead(404).end("Session not found");
        }
      } else {
        res.writeHead(400).end("Bad request");
      }
    } else if (path === "/") {
      // Simple info endpoint
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          name: "Pokédex MCP Server",
          version: "1.0.0",
          endpoints: {
            sse: "/sse",
            message: "/message",
          },
          tools: [
            "get-pokemon",
            "random-pokemon",
            "random-pokemon-from-region",
            "random-pokemon-by-type",
            "pokemon-query",
          ],
          activeConnections: transports.size,
        })
      );
    } else {
      res.writeHead(404).end("Not found");
    }
  });

  httpServer.listen(port, "127.0.0.1", () => {
    console.error(`Pokédex MCP Server running on HTTP port ${port}`);
    console.error(`Connect via SSE at: http://127.0.0.1:${port}/sse`);
  });

  // Graceful shutdown
  process.on("SIGINT", () => {
    console.error("Shutting down server...");
    for (const transport of transports.values()) {
      transport.close();
    }
    httpServer.close(() => {
      process.exit(0);
    });
  });
}

main().catch((error) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});
