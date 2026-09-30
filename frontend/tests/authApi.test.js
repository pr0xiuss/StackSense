/**
 * Verification test for authApi.js, auth contracts, and component acceptance criteria.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const srcDir = path.resolve(__dirname, '../src');

// Mock localStorage
const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => storage.get(key) || null,
  setItem: (key, val) => storage.set(key, String(val)),
  removeItem: (key) => storage.delete(key),
  clear: () => storage.clear(),
};

// Import module under test
const { authApi, AuthApiError } = await import('../src/api/authApi.js');

async function testTokenStorage() {
  console.log('Testing token storage...');
  authApi.clearTokens();
  assert.equal(authApi.getStoredToken(), null);
  assert.equal(authApi.getStoredRefreshToken(), null);

  authApi.setStoredToken('access-token-123');
  assert.equal(authApi.getStoredToken(), 'access-token-123');
  assert.equal(storage.get('stacksense_access_token'), 'access-token-123');

  authApi.setStoredRefreshToken('refresh-token-456');
  assert.equal(authApi.getStoredRefreshToken(), 'refresh-token-456');
  assert.equal(storage.get('stacksense_refresh_token'), 'refresh-token-456');

  // Test legacy fallback
  storage.delete('stacksense_access_token');
  storage.set('stacksense_auth_token', 'legacy-access-token');
  assert.equal(authApi.getStoredToken(), 'legacy-access-token');

  // Test clearTokens
  authApi.clearTokens();
  assert.equal(authApi.getStoredToken(), null);
  assert.equal(authApi.getStoredRefreshToken(), null);
  assert.equal(storage.get('stacksense_access_token'), undefined);
  assert.equal(storage.get('stacksense_refresh_token'), undefined);
  assert.equal(storage.get('stacksense_auth_token'), undefined);
  console.log('✓ Token storage tests passed');
}

async function testLogin() {
  console.log('Testing authApi.login...');
  authApi.clearTokens();

  let capturedUrl = null;
  let capturedOptions = null;
  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      json: async () => ({
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        token_type: 'bearer',
        expires_in: 900,
        refresh_expires_in: 604800,
      }),
    };
  };

  const res = await authApi.login('TestUser', 'Password123!');
  assert.equal(capturedUrl, '/api/v1/auth/login');
  assert.equal(capturedOptions.method, 'POST');
  const payload = JSON.parse(capturedOptions.body);
  assert.equal(payload.identifier, 'testuser');
  assert.equal(payload.password, 'Password123!');
  assert.equal(res.access_token, 'new-access-token');
  assert.equal(res.refresh_token, 'new-refresh-token');
  assert.equal(authApi.getStoredToken(), 'new-access-token');
  assert.equal(authApi.getStoredRefreshToken(), 'new-refresh-token');

  // Also test object argument style
  await authApi.login({ identifier: 'user@example.com', password: 'secret' });
  const payload2 = JSON.parse(capturedOptions.body);
  assert.equal(payload2.identifier, 'user@example.com');
  assert.equal(payload2.password, 'secret');
  console.log('✓ Login tests passed');
}

async function testRegister() {
  console.log('Testing authApi.register...');
  authApi.clearTokens();

  let capturedUrl = null;
  let capturedOptions = null;
  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      status: 201,
      json: async () => ({
        id: 'u-1',
        email: 'test@example.com',
        username: 'testuser',
        is_active: true,
      }),
    };
  };

  const res = await authApi.register('Test@Example.COM', 'TestUser', 'Password123!');
  assert.equal(capturedUrl, '/api/v1/auth/register');
  assert.equal(capturedOptions.method, 'POST');
  const payload = JSON.parse(capturedOptions.body);
  assert.equal(payload.email, 'test@example.com');
  assert.equal(payload.username, 'testuser');
  assert.equal(payload.password, 'Password123!');
  assert.equal(res.username, 'testuser');

  // Test register when tokens are returned
  globalThis.fetch = async () => ({
    ok: true,
    status: 201,
    json: async () => ({
      id: 'u-2',
      email: 'user2@example.com',
      username: 'user2',
      access_token: 'reg-access',
      refresh_token: 'reg-refresh',
    }),
  });
  await authApi.register('user2@example.com', 'user2', 'Password123!');
  assert.equal(authApi.getStoredToken(), 'reg-access');
  assert.equal(authApi.getStoredRefreshToken(), 'reg-refresh');
  console.log('✓ Register tests passed');
}

async function testRefreshToken() {
  console.log('Testing authApi.refreshToken...');
  authApi.clearTokens();
  authApi.setStoredRefreshToken('old-refresh');

  let capturedUrl = null;
  let capturedOptions = null;
  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      json: async () => ({
        access_token: 'rotated-access',
        refresh_token: 'rotated-refresh',
        token_type: 'bearer',
        expires_in: 900,
        refresh_expires_in: 604800,
      }),
    };
  };

  const res = await authApi.refreshToken();
  assert.equal(capturedUrl, '/api/v1/auth/refresh');
  const payload = JSON.parse(capturedOptions.body);
  assert.equal(payload.refresh_token, 'old-refresh');
  assert.equal(authApi.getStoredToken(), 'rotated-access');
  assert.equal(authApi.getStoredRefreshToken(), 'rotated-refresh');

  // Explicit token passed
  await authApi.refreshToken('explicit-token');
  const payload2 = JSON.parse(capturedOptions.body);
  assert.equal(payload2.refresh_token, 'explicit-token');
  console.log('✓ RefreshToken tests passed');
}

async function testLogout() {
  console.log('Testing authApi.logout...');
  authApi.setStoredToken('active-access');
  authApi.setStoredRefreshToken('active-refresh');

  let capturedUrl = null;
  let capturedOptions = null;
  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      status: 204,
      json: async () => { throw new Error('No content'); },
    };
  };

  await authApi.logout();
  assert.equal(capturedUrl, '/api/v1/auth/logout');
  const payload = JSON.parse(capturedOptions.body);
  assert.equal(payload.refresh_token, 'active-refresh');
  assert.equal(authApi.getStoredToken(), null);
  assert.equal(authApi.getStoredRefreshToken(), null);
  console.log('✓ Logout tests passed');
}

function testNavbarContract() {
  console.log('Testing Navbar acceptance criteria...');
  const navbarSrc = fs.readFileSync(path.join(srcDir, 'components/Navbar.jsx'), 'utf-8');
  assert.ok(!navbarSrc.includes('github.com/pr0xiuss/StackSense'), 'Navbar must not contain GitHub repository link');
  assert.ok(!navbarSrc.includes('aria-label="GitHub Repository"'), 'Navbar must not contain GitHub aria-label');
  console.log('✓ Navbar checks passed');
}

function testLoginFormContract() {
  console.log('Testing LoginForm acceptance criteria...');
  const loginSrc = fs.readFileSync(path.join(srcDir, 'components/auth/LoginForm.jsx'), 'utf-8');
  assert.ok(loginSrc.includes('label="Username or email"'), 'LoginForm must have "Username or email" label');
  assert.ok(loginSrc.includes('identifier'), 'LoginForm must manage identifier state');
  assert.ok(!loginSrc.includes('onSubmit({ email, password })'), 'LoginForm must NOT submit email');
  assert.ok(loginSrc.includes('onSubmit({ identifier: identifier.trim(), password })'), 'LoginForm must submit trimmed identifier');
  console.log('✓ LoginForm checks passed');
}

function testSignupFormContract() {
  console.log('Testing SignupForm acceptance criteria...');
  const signupSrc = fs.readFileSync(path.join(srcDir, 'components/auth/SignupForm.jsx'), 'utf-8');
  assert.ok(signupSrc.includes('label="Username"'), 'SignupForm must have "Username" label');
  assert.ok(signupSrc.includes('name="username"'), 'SignupForm must have username input');
  assert.ok(!signupSrc.includes('fullName'), 'SignupForm must NOT contain fullName');
  assert.ok(!signupSrc.includes('Full name'), 'SignupForm must NOT contain "Full name"');
  assert.ok(!signupSrc.includes('terms-checkbox-group'), 'SignupForm must NOT contain terms checkbox group');
  assert.ok(!signupSrc.includes('agree-terms'), 'SignupForm must NOT contain agree-terms checkbox');
  assert.ok(signupSrc.includes('USERNAME_REGEX = /^[a-zA-Z0-9_]{3,30}$/'), 'SignupForm must enforce 3-30 alnum+underscore regex');
  assert.ok(signupSrc.includes('username: username.trim().toLowerCase()'), 'SignupForm must normalize username to lowercase');
  console.log('✓ SignupForm checks passed');
}

function testAuthPageAndAppContract() {
  console.log('Testing AuthPage and App routing post-auth navigation...');
  const authPageSrc = fs.readFileSync(path.join(srcDir, 'pages/AuthPage.jsx'), 'utf-8');
  assert.ok(authPageSrc.includes('#/projects'), 'AuthPage must redirect to #/projects on successful auth');

  const appSrc = fs.readFileSync(path.join(srcDir, 'App.jsx'), 'utf-8');
  assert.ok(appSrc.includes('#/projects'), 'App.jsx must handle #/projects route');
  console.log('✓ AuthPage & App route checks passed');
}

async function runAll() {
  await testTokenStorage();
  await testLogin();
  await testRegister();
  await testRefreshToken();
  await testLogout();
  testNavbarContract();
  testLoginFormContract();
  testSignupFormContract();
  testAuthPageAndAppContract();
  console.log('\nAll authApi, component, and contract tests passed successfully!');
}

runAll().catch((err) => {
  console.error(err);
  process.exit(1);
});
