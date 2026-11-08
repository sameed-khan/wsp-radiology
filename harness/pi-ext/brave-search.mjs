// Only Brave's search endpoint is used: no URL or page fetch capability.
export async function searchBrave(query, key, signal, fetchImpl = fetch) {
  if (!key) return 'Web search unavailable: BRAVE_API_KEY is not configured on the host.';
  const url = new URL('https://api.search.brave.com/res/v1/web/search');
  url.searchParams.set('q', query);
  url.searchParams.set('count', '10');
  try {
    const response = await fetchImpl(url, {
      headers: { Accept: 'application/json', 'X-Subscription-Token': key },
      redirect: 'error', signal: AbortSignal.any([signal, AbortSignal.timeout(30000)].filter(Boolean)),
    });
    if (!response.ok) return `Web search failed (HTTP ${response.status}).`;
    const data = await response.json();
    const results = Array.isArray(data?.web?.results) ? data.web.results : [];
    const safe = value => typeof value === 'string' ? value.split(key).join('[REDACTED]').slice(0, 2000) : '';
    if (!results.length) return 'No web search results.';
    return results.slice(0, 10).map(item =>
      `${safe(item.title)}\n${safe(item.url)}\n${safe(item.description)}`.trim()
    ).join('\n\n');
  } catch {
    // Never include provider/network exception text: it may contain credentials.
    return 'Web search failed or was aborted.';
  }
}
