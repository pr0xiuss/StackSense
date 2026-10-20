const fs = require('fs');
const path = require('path');

describe('StackSense Architecture Compliance Tests', () => {
  const srcDir = path.resolve(__dirname, '../../src');

  /**
   * Helper to recursively collect all JavaScript files in a directory.
   */
  function getAllJsFiles(dir) {
    let results = [];
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        results = results.concat(getAllJsFiles(fullPath));
      } else if (entry.isFile() && entry.name.endsWith('.js')) {
        results.push(fullPath);
      }
    }
    return results;
  }

  const allSrcFiles = getAllJsFiles(srcDir);

  it('ensures no Organization models, routes, or organization_id are introduced', () => {
    for (const file of allSrcFiles) {
      const content = fs.readFileSync(file, 'utf8').toLowerCase();
      expect(content).not.toContain('organization_id');
      expect(content).not.toContain('organizationrole');
      expect(content).not.toContain('organizationaccess');
    }
  });

  it('ensures Project model does not contain owner_id (ownership via ProjectAccess)', () => {
    const projectModelPath = path.join(srcDir, 'models/Project.js');
    const content = fs.readFileSync(projectModelPath, 'utf8');
    expect(content).not.toContain('owner_id');
  });

  it('ensures models do not import Express or routing infrastructure', () => {
    const modelsDir = path.join(srcDir, 'models');
    const modelFiles = getAllJsFiles(modelsDir);

    for (const file of modelFiles) {
      const content = fs.readFileSync(file, 'utf8');
      expect(content).not.toContain("require('express')");
      expect(content).not.toContain('express.Router');
    }
  });

  it('ensures models do not depend on controllers or services', () => {
    const modelsDir = path.join(srcDir, 'models');
    const modelFiles = getAllJsFiles(modelsDir);

    for (const file of modelFiles) {
      const content = fs.readFileSync(file, 'utf8');
      expect(content).not.toMatch(/require\(.*controllers/);
      expect(content).not.toMatch(/require\(.*services/);
    }
  });

  it('ensures project roles conform exactly to authoritative frozen values', () => {
    const { PROJECT_ROLES, VALID_PROJECT_ROLES } = require('../../src/constants/projectRoles');
    expect(PROJECT_ROLES).toEqual({
      OWNER: 'owner',
      ADMIN: 'admin',
      DEVELOPER: 'developer',
      VIEWER: 'viewer',
    });
    expect(VALID_PROJECT_ROLES).toEqual(['owner', 'admin', 'developer', 'viewer']);
  });
});
