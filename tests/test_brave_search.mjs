import { test } from 'node:test';
import assert from 'node:assert/strict';
import { searchBrave } from '../harness/pi-ext/brave-search.mjs';

test('missing host credential never calls the provider', async () => {
  assert.match(await searchBrave('x', '', undefined, () => { throw Error('called'); }), /not configured/);
});

test('requests snippets only, redacts credential and omits page content', async () => {
  const text = await searchBrave('test query', 'secret-key', undefined, async (url, options) => {
    assert.equal(url.origin + url.pathname, 'https://api.search.brave.com/res/v1/web/search');
    assert.equal(url.searchParams.get('q'), 'test query');
    assert.equal(options.headers['X-Subscription-Token'], 'secret-key');
    assert.equal(options.redirect, 'error');
    return { ok: true, json: async () => ({ web: { results: [{ title: 'secret-key', url: 'https://example.com', description: 'snippet', content: 'page content' }] } }) };
  });
  assert.match(text, /\[REDACTED\]/);
  assert.match(text, /snippet/);
  assert.doesNotMatch(text, /secret-key|page content/);
});

test('network and HTTP errors never expose provider body or exceptions', async () => {
  assert.equal(await searchBrave('x', 'secret-key', undefined, async () => { throw Error('secret-key'); }), 'Web search failed or was aborted.');
  assert.equal(await searchBrave('x', 'secret-key', undefined, async () => ({ok:false, status:401})), 'Web search failed (HTTP 401).');
});
