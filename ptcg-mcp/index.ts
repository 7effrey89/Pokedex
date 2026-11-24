import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import express from "express";
import { z } from "zod";

interface Card {
  id: string;
  name: string;
  supertype: string;
  subtypes?: string[];
  hp?: string;
  types?: string[];
  attacks?: {
    name: string;
    cost: string[];
    convertedEnergyCost: number;
    damage: string;
    text: string;
  }[];
  set: {
    id: string;
    name: string;
    series: string;
  };
  artist?: string;
  rarity?: string;
  images: {
    small: string;
    large: string;
  };
  tcgplayer?: {
    url: string;
    prices?: Record<string, {
      low?: number;
      mid?: number;
      high?: number;
      market?: number;
    }>;
  };
  cardmarket?: {
    url: string;
    prices?: {
      averageSellPrice?: number;
      trendPrice?: number;
    };
  };
}

// Create the MCP server
const server = new McpServer({
  name: "Pokemon TCG",
  version: "1.0.0",
});

// Helper function to build query string
const catalogBaseUrl = process.env.POKEDEX_API_URL || 'http://localhost:5050';

function buildQuery(params: Record<string, unknown>): URLSearchParams {
  const query = new URLSearchParams();
  for (const key of ['name', 'supertype', 'subtypes', 'types', 'set', 'rarity']) {
    if (typeof params[key] === 'string' && params[key]) query.set(key, params[key]);
  }
  if (typeof params.hp === 'string') {
    const range = params.hp.match(/^\[(\d+|\*) TO (\d+|\*)\]$/);
    if (range) {
      if (range[1] !== '*') query.set('hp_min', range[1]);
      if (range[2] !== '*') query.set('hp_max', range[2]);
    } else if (/^\d+$/.test(params.hp)) {
      query.set('hp_min', params.hp);
      query.set('hp_max', params.hp);
    } else {
      throw new Error('HP must be a number or a range such as [200 TO *].');
    }
  }
  return query;
}

// Search function
async function ptcg_search(query: URLSearchParams, pageSize: number = 20): Promise<Card[]> {
  const url = new URL('/api/tcg/catalog/cards', catalogBaseUrl);
  url.search = query.toString();
  url.searchParams.set('pageSize', pageSize.toString());
  
  const response = await fetch(url.toString(), {
    headers: {
      'Content-Type': 'application/json',
    },
  });
  
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }
  
  const data = await response.json() as { data: Card[] };
  return data.data;
}

// Register the pokemon-card-search tool with simple string parameters
// @ts-ignore - MCP SDK has excessive type depth issues with complex schemas
server.tool(
  "pokemon-card-search",
  "Search Pokemon TCG cards. Use params: name, supertype (Pokemon/Trainer/Energy), subtypes, types (Fire/Water/Grass/etc), hp (e.g. '[200 TO *]' for 200+ HP), set, rarity, pageSize",
  {
    name: z.string().optional().describe("Card name to search for"),
    supertype: z.string().optional().describe("Pokemon, Trainer, or Energy"),
    subtypes: z.string().optional().describe("Card subtype like Basic, Stage1, V, VMAX, ex"),
    types: z.string().optional().describe("Energy type: Fire, Water, Grass, Lightning, Psychic, Fighting, Darkness, Metal, Dragon, Fairy, Colorless"),
    hp: z.string().optional().describe("HP filter, e.g. '[200 TO *]' for 200+ HP"),
    set: z.string().optional().describe("Set ID to filter by"),
    rarity: z.string().optional().describe("Card rarity"),
    pageSize: z.number().optional().describe("Results to return (default 20)"),
  },
  async (params) => {
    try {
      const query = buildQuery(params);
      
      if (query.size === 0) {
        return {
          content: [{ type: "text", text: "Please provide at least one search parameter." }],
        };
      }
      
      const pageSize = params.pageSize ?? 20;
      const cards = await ptcg_search(query, pageSize);
      
      if (cards.length === 0) {
        return {
          content: [{ type: "text", text: "No cards found matching your criteria." }],
        };
      }
      
      const formattedCards = cards.map(card => ({
        id: card.id,
        name: card.name,
        supertype: card.supertype,
        subtypes: card.subtypes,
        hp: card.hp,
        types: card.types,
        set: card.set.name,
        rarity: card.rarity,
        artist: card.artist,
        image: card.images.small,
        imageLarge: card.images.large,
        tcgplayerUrl: card.tcgplayer?.url,
        attacks: card.attacks,
      }));
      
      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(formattedCards, null, 2)
        }],
      };
    } catch (error) {
      return {
        content: [{ 
          type: "text", 
          text: `Error searching cards: ${error instanceof Error ? error.message : String(error)}` 
        }],
      };
    }
  }
);

// Register the pokemon-card-price tool
server.tool(
  "pokemon-card-price",
  "Get price info for a Pokemon TCG card by ID (format: 'set-number', e.g., 'sv3-25')",
  {
    cardId: z.string().describe("Card ID in format 'set-number'"),
  },
  async (params) => {
    try {
      const response = await fetch(new URL(`/api/tcg/catalog/cards/${encodeURIComponent(params.cardId)}/price`, catalogBaseUrl), {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        if (response.status === 404) {
          return {
            content: [{ type: "text", text: `Card with ID "${params.cardId}" not found.` }],
          };
        }
        throw new Error(`API request failed: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json() as { data: {
        id: string; name: string; set: string; rarity?: string; image?: string;
        tcgplayer?: Card['tcgplayer']; cardmarket?: Card['cardmarket'];
      } };
      const card = data.data;
      
      const priceInfo: Record<string, unknown> = {
        cardId: card.id,
        name: card.name,
        set: card.set,
        rarity: card.rarity,
        image: card.image,
      };
      
      if (card.tcgplayer) {
        priceInfo.tcgplayer = {
          url: card.tcgplayer.url,
          prices: card.tcgplayer.prices,
        };
      }
      
      if (card.cardmarket) {
        priceInfo.cardmarket = {
          url: card.cardmarket.url,
          prices: card.cardmarket.prices,
        };
      }
      
      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(priceInfo, null, 2)
        }],
      };
    } catch (error) {
      return {
        content: [{ 
          type: "text", 
          text: `Error fetching card price: ${error instanceof Error ? error.message : String(error)}` 
        }],
      };
    }
  }
);

// Main function to start the server
async function main() {
  const args = process.argv.slice(2);
  const useHttp = args.includes('--http');
  const port = parseInt(args.find(a => a.startsWith('--port='))?.split('=')[1] || '3002');

  if (useHttp) {
    // HTTP/SSE mode for native MCP
    const app = express();
    let sseTransport: SSEServerTransport | null = null;

    app.get('/sse', (req, res) => {
      console.error('SSE connection established');
      sseTransport = new SSEServerTransport('/messages', res);
      server.connect(sseTransport);
    });

    app.post('/messages', (req, res) => {
      if (sseTransport) {
        sseTransport.handlePostMessage(req, res);
      } else {
        res.status(400).send('No SSE connection');
      }
    });

    app.listen(port, () => {
      console.error(`Pokemon TCG MCP Server running on http://localhost:${port}`);
      console.error('Connect via SSE at /sse');
    });
  } else {
    // Stdio mode (default)
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("Pokemon TCG MCP Server running on stdio");
  }
}

main().catch(console.error);
