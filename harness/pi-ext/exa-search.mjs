import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

// Credentials and network access are host-only. Never request full page text.
export async function searchExa(query, signal, { fetchImpl = fetch, credentialPath = join(homedir(), '.pi', 'exa-search.json') } = {}) {
  let key;
  try {
    const config = JSON.parse(await readFile(credentialPath, 'utf8'));
    key = typeof config.exaApiKey === 'string' ? config.exaApiKey.trim() : '';
  } catch {
    return 'Web search unavailable: Exa host credential is missing or invalid.';
  }
  if (!key) return 'Web search unavailable: Exa host credential is missing or invalid.';
  try {
    const response = await fetchImpl('https://api.exa.ai/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': key },
      body: JSON.stringify({ query, numResults: 10, contents: { highlights: { maxCharacters: 1000 } } }),
      redirect: 'error', signal: AbortSignal.any([signal, AbortSignal.timeout(30000)].filter(Boolean)),
    });
    if (!response.ok) return `Web search failed (HTTP ${Number(response.status) || 0}).`;
    const data = await response.json();
    const results = Array.isArray(data?.results) ? data.results : [];
    const safe = (value, limit) => typeof value === 'string' ? value.split(key).join('[REDACTED]').slice(0, limit) : '';
    if (!results.length) return 'No web search results.';
    return results.slice(0, 10).map(item => {
      const highlights = Array.isArray(item?.highlights) ? item.highlights : [];
      return [safe(item?.title, 300), safe(item?.url, 2000), safe(item?.publishedDate, 100),
        safe(highlights.filter(x => typeof x === 'string').join(' '), 1000)].filter(Boolean).join('\n');
    }).join('\n\n');
  } catch {
    // Exceptions and provider bodies can contain the credential; never echo them.
    return 'Web search failed or was aborted.';
  }
}
