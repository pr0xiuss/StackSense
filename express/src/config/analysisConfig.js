/**
 * Configuration for Express-to-FastAPI Analysis and Architecture Gateway.
 *
 * Enforces server secret presence, bounded request timeouts, and SSE connection policy.
 * Fails closed outside test environment if secret or base URL is unconfigured.
 */

function validateAnalysisConfig(env = process.env) {
  const isTest = env.NODE_ENV === 'test';
  const baseUrl =
    env.ANALYSIS_API_BASE_URL || (isTest ? 'http://127.0.0.1:8000/api/v1' : '');
  const secretKey =
    env.ANALYSIS_INTERNAL_API_SECRET_KEY ||
    (isTest ? 'test-internal-analysis-secret-key-at-least-32-chars' : '');

  if (!isTest) {
    if (!baseUrl) {
      throw new Error('ANALYSIS_API_BASE_URL must be configured.');
    }
    if (!secretKey || secretKey.length < 16) {
      throw new Error(
        'ANALYSIS_INTERNAL_API_SECRET_KEY must be set and at least 16 characters.'
      );
    }
  }

  const jsonTimeoutMs = parseInt(env.ANALYSIS_JSON_TIMEOUT_MS, 10) || 15000;
  const sseTimeoutMs = parseInt(env.ANALYSIS_SSE_TIMEOUT_MS, 10) || 300000;

  return {
    baseUrl: baseUrl ? baseUrl.replace(/\/+$/, '') : '',
    secretKey,
    jsonTimeoutMs: Math.max(1000, Math.min(jsonTimeoutMs, 60000)),
    sseTimeoutMs: Math.max(5000, sseTimeoutMs),
  };
}

let analysisConfig;
try {
  analysisConfig = validateAnalysisConfig();
} catch (err) {
  // If in test or if process will configure later
  if (process.env.NODE_ENV === 'test') {
    analysisConfig = {
      baseUrl: 'http://127.0.0.1:8000/api/v1',
      secretKey: 'test-internal-analysis-secret-key-at-least-32-chars',
      jsonTimeoutMs: 15000,
      sseTimeoutMs: 300000,
    };
  } else {
    throw err;
  }
}

module.exports = {
  analysisConfig,
  validateAnalysisConfig,
};

