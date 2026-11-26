import { createHash, webcrypto } from 'node:crypto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiDownload } from '../../src/services/apiClient.js';

describe('verified artifact downloads', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('accepts a PDF only when bytes, length and producer digest agree', async () => {
    vi.stubGlobal('crypto', webcrypto);
    const bytes = new TextEncoder().encode('%PDF-1.7 test');
    const sha = createHash('sha256').update(bytes).digest('base64');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(bytes, { headers: {
      'content-type': 'application/pdf', 'content-length': String(bytes.length),
      'content-digest': `sha-256=:${sha}:`,
    } })));
    const result = await apiDownload('/reports/example', { triggerBrowserDownload: false });
    expect(result.size).toBe(bytes.length);
    expect(result.sha256).toBe(createHash('sha256').update(bytes).digest('hex'));
    result.revoke();
  });

  it('rejects a PDF without a digest before creating a download', async () => {
    vi.stubGlobal('crypto', webcrypto);
    const bytes = new TextEncoder().encode('%PDF-1.7 test');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(bytes, { headers: {
      'content-type': 'application/pdf', 'content-length': String(bytes.length),
    } })));
    await expect(apiDownload('/reports/example', { triggerBrowserDownload: false }))
      .rejects.toMatchObject({ code: 'digest_mismatch' });
  });
});
