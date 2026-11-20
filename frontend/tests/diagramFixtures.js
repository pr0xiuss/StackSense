// Actual rootless ELK + real prepared glyph fixtures; not accepted production data.
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
export const templates = ['system_overview', 'component_architecture', 'dependency_map', 'data_flow'];
export function diagramFixture(template = templates[0]) {
  const encoded = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), `../../tests/fixtures/p5/diagrams/b4_${template}.json.gz.b64`), 'utf8');
  return JSON.parse(gunzipSync(Buffer.from(encoded.trim(), 'base64')).toString());
}
