const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const tar = require('tar');

/**
 * Creates a zip archive with arbitrary entries (including malicious paths)
 * using Python's zipfile module.
 *
 * @param {string} zipPath Destination zip file path
 * @param {Record<string, string|Buffer>} entries Map of entry name to content
 */
function createTestZip(zipPath, entries) {
  const resolvedZip = path.resolve(zipPath);
  fs.mkdirSync(path.dirname(resolvedZip), { recursive: true });

  const pyScript = `
import sys, json, zipfile
zip_path = sys.argv[1]
entries_json = sys.argv[2]
entries = json.loads(entries_json)

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for name, content in entries.items():
        zf.writestr(name, content.encode('utf-8'))
`;

  execFileSync('python', ['-c', pyScript, resolvedZip, JSON.stringify(entries)]);
  return resolvedZip;
}

/**
 * Creates a tar or tar.gz archive with specified entries.
 *
 * @param {string} tarPath Destination tar path
 * @param {Record<string, string>} entries Map of relative path to string content
 * @param {object} [options]
 * @param {boolean} [options.gzip=false]
 */
async function createTestTar(tarPath, entries, { gzip = false } = {}) {
  const resolvedTar = path.resolve(tarPath);
  fs.mkdirSync(path.dirname(resolvedTar), { recursive: true });

  const tempStage = path.join(path.dirname(resolvedTar), 'stage_' + Date.now());
  fs.mkdirSync(tempStage, { recursive: true });

  const files = [];
  for (const [relPath, content] of Object.entries(entries)) {
    const fullPath = path.join(tempStage, relPath);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content);
    files.push(relPath);
  }

  await tar.c(
    {
      file: resolvedTar,
      cwd: tempStage,
      gzip,
    },
    files
  );

  fs.rmSync(tempStage, { recursive: true, force: true });
  return resolvedTar;
}

/**
 * Creates a raw tar archive with arbitrary entry path (such as ../traversal)
 * bypassing npm tar's internal client validation.
 *
 * @param {string} tarPath
 * @param {string} entryPath
 * @param {string} [content='evil']
 */
function createRawTarWithTraversal(tarPath, entryPath, content = 'evil') {
  const resolvedTar = path.resolve(tarPath);
  fs.mkdirSync(path.dirname(resolvedTar), { recursive: true });

  const contentBuf = Buffer.from(content, 'utf8');
  const buf = Buffer.alloc(512 * 4); // header + data block + 2 zero blocks
  buf.write(entryPath, 0, 100, 'utf8');
  buf.write('0000644\0', 100, 8, 'utf8');
  buf.write('0000000\0', 108, 8, 'utf8');
  buf.write('0000000\0', 116, 8, 'utf8');
  const sizeOctal = contentBuf.length.toString(8).padStart(11, '0') + '\0';
  buf.write(sizeOctal, 124, 12, 'utf8');
  buf.write('00000000000\0', 136, 12, 'utf8');
  buf.fill(32, 148, 156); // 8 spaces for checksum calc
  buf.write('0', 156, 1, 'utf8');
  buf.write('ustar\0', 257, 6, 'utf8');
  buf.write('00', 263, 2, 'utf8');

  let sum = 0;
  for (let i = 0; i < 512; i++) sum += buf[i];
  const chk = sum.toString(8).padStart(6, '0') + '\0 ';
  buf.write(chk, 148, 8, 'utf8');
  contentBuf.copy(buf, 512);

  fs.writeFileSync(resolvedTar, buf);
  return resolvedTar;
}

module.exports = {
  createTestZip,
  createTestTar,
  createRawTarWithTraversal,
};
