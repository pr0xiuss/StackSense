/**
 * Project-scoped access roles.
 * Authoritative values matching Python P2 and master.txt:
 * OWNER, ADMIN, DEVELOPER, VIEWER.
 */

const PROJECT_ROLES = Object.freeze({
  OWNER: 'owner',
  ADMIN: 'admin',
  DEVELOPER: 'developer',
  VIEWER: 'viewer',
});

const VALID_PROJECT_ROLES = Object.freeze(Object.values(PROJECT_ROLES));

module.exports = {
  PROJECT_ROLES,
  VALID_PROJECT_ROLES,
};
