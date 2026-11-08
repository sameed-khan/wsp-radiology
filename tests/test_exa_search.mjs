import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { searchExa } from '../harness/pi-ext/exa-search.mjs';

async function withCredential(fn) {
  const dir = await mkdtemp(join(tmpdir(), 'wsp-exa-test-'));
  try {
    const credentialPath = join(dir, 'credential.json');
    await writeFile(credentialPath, JSON.stringify({ exaApiKey: 'secret-key' }), { mode: 0o600 });
    await fn(credentialPath);
  } finally { await rm(dir, { recursive: true, force: true }); }
}

test('missing and invalid credentials fail without network access', async () => {
  await withCredential(async credentialPath => {
    const opts = { credentialPath, fetchImpl: () => { throw Error('called'); } };
    await writeFile(credentialPath, '{');
    assert.match(await searchExa('x', undefined, opts), /unavailable/);
    await writeFile(credentialPath, '{}');
    assert.match(await searchExa('x', undefined, opts), /unavailable/);
    await rm(credentialPath);
    assert.match(await searchExa('x', undefined, opts), /unavailable/);
  });
});

test('requests highlights only and bounds and redacts returned fields', async () => {
  await withCredential(async credentialPath => {
    const result = await searchExa('test query', undefined, { credentialPath, fetchImpl: async (url, opts) => {
      assert.equal(url, 'https://api.exa.ai/search');
      assert.equal(opts.method, 'POST');
      assert.equal(opts.headers['x-api-key'], 'secret-key');
      assert.equal(opts.redirect, 'error');
      assert.deepEqual(JSON.parse(opts.body), { query: 'test query', numResults: 10, contents: { highlights: { maxCharacters: 1000 } } });
      return { ok: true, json: async () => ({ results: Array.from({ length: 12 }, (_, i) => ({ title: `title${i} secret-key`, url: 'https://example.org', publishedDate: '2020-01-01', highlights: ['snippet secret-key', 'a'.repeat(1200)], text: 'full-page-content' })) }) };
    }});
    assert.match(result, /title0 \[REDACTED\]/);
    assert.match(result, /2020-01-01/);
    assert.match(result, /snippet \[REDACTED\]/);
    assert.doesNotMatch(result, /secret-key|full-page-content|title10|a{1001}/);
  });
});

test('provider errors and exceptions do not disclose bodies or secrets', async () => {
  await withCredential(async credentialPath => {
    assert.equal(await searchExa('x', undefined, { credentialPath, fetchImpl: async () => { throw Error('secret-key'); } }), 'Web search failed or was aborted.');
    assert.equal(await searchExa('x', undefined, { credentialPath, fetchImpl: async () => ({ ok: false, status: 401, json: () => { throw Error('secret-key'); } }) }), 'Web search failed (HTTP 401).');
    assert.equal(await searchExa('x', undefined, { credentialPath, fetchImpl: async () => ({ ok: true, json: async () => ({ results: [] }) }) }), 'No web search results.');
  });
});
