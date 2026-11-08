import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';
import { Type } from 'typebox';
import { searchBrave } from './brave-search.mjs';

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: 'web_search',
    label: 'Web search',
    description: 'Search the web and return result snippets; does not fetch pages.',
    parameters: Type.Object({ query: Type.String({ minLength: 1, maxLength: 1000 }) }, { additionalProperties: false }),
    async execute(_id, { query }, signal) {
      return { content: [{ type: 'text', text: await searchBrave(query, process.env.BRAVE_API_KEY, signal) }], details: {} };
    },
  });
}
