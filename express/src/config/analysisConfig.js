const os = require('os');
const path = require('path');

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

  // Additive P5 Transport Configuration
  const intelligenceQueryMaxBytes =
    parseInt(env.INTELLIGENCE_QUERY_MAX_BYTES, 10) || 32768; // 32 KiB
  const intelligenceMaxFilterElements =
    parseInt(env.INTELLIGENCE_MAX_FILTER_ELEMENTS, 10) || 50;
  const intelligenceJsonRequestMaxBytes =
    parseInt(env.INTELLIGENCE_JSON_REQUEST_MAX_BYTES, 10) || 131072; // 128 KiB
  const intelligenceJsonResponseMaxBytes =
    parseInt(env.INTELLIGENCE_JSON_RESPONSE_MAX_BYTES, 10) || 4194304; // 4 MiB
  const intelligenceC3ResponseMaxBytes =
    parseInt(env.INTELLIGENCE_C3_RESPONSE_MAX_BYTES, 10) || 2097152; // 2 MiB
  const intelligenceDiagramSpecMaxBytes =
    parseInt(env.INTELLIGENCE_DIAGRAM_SPEC_MAX_BYTES, 10) || 16777216; // 16 MiB
  const intelligenceDiagramLayoutMaxBytes =
    parseInt(env.INTELLIGENCE_DIAGRAM_LAYOUT_MAX_BYTES, 10) || 33554432; // 32 MiB
  const intelligenceDiagramExportMaxBytes =
    parseInt(env.INTELLIGENCE_DIAGRAM_EXPORT_MAX_BYTES, 10) || 67108864; // 64 MiB
  const intelligenceDiagramSvgMaxBytes =
    parseInt(env.INTELLIGENCE_DIAGRAM_SVG_MAX_BYTES, 10) || 50331648; // 48 MiB
  const intelligencePdfMaxBytes =
    parseInt(env.INTELLIGENCE_PDF_MAX_BYTES, 10) || 67108864; // 64 MiB

  const intelligenceMetadataTimeoutMs =
    parseInt(env.INTELLIGENCE_METADATA_TIMEOUT_MS, 10) || 30000; // 30s
  const intelligenceLongTimeoutMs =
    parseInt(env.INTELLIGENCE_LONG_TIMEOUT_MS, 10) || 120000; // 120s
  const intelligenceArtifactUpstreamTimeoutMs =
    parseInt(env.INTELLIGENCE_ARTIFACT_UPSTREAM_TIMEOUT_MS, 10) || 90000; // 90s
  const intelligenceArtifactRelayTimeoutMs =
    parseInt(env.INTELLIGENCE_ARTIFACT_RELAY_TIMEOUT_MS, 10) || 60000; // 60s
  const intelligenceArtifactCombinedTimeoutMs =
    parseInt(env.INTELLIGENCE_ARTIFACT_COMBINED_TIMEOUT_MS, 10) || 150000; // 150s

  const intelligenceMaxConcurrentArtifactRelays =
    parseInt(env.INTELLIGENCE_MAX_CONCURRENT_ARTIFACT_RELAYS, 10) || 2;
  const intelligenceArtifactSpoolDir =
    env.INTELLIGENCE_ARTIFACT_SPOOL_DIR ||
    path.join(os.tmpdir(), 'stacksense-intelligence-spool');

  return {
    baseUrl: baseUrl ? baseUrl.replace(/\/+$/, '') : '',
    secretKey,
    jsonTimeoutMs: Math.max(1000, Math.min(jsonTimeoutMs, 60000)),
    sseTimeoutMs: Math.max(5000, sseTimeoutMs),
    // P5 limits
    intelligenceQueryMaxBytes,
    intelligenceMaxFilterElements,
    intelligenceJsonRequestMaxBytes,
    intelligenceJsonResponseMaxBytes,
    intelligenceC3ResponseMaxBytes,
    intelligenceDiagramSpecMaxBytes,
    intelligenceDiagramLayoutMaxBytes,
    intelligenceDiagramExportMaxBytes,
    intelligenceDiagramSvgMaxBytes,
    intelligencePdfMaxBytes,
    // P5 timeouts
    intelligenceMetadataTimeoutMs,
    intelligenceLongTimeoutMs,
    intelligenceArtifactUpstreamTimeoutMs,
    intelligenceArtifactRelayTimeoutMs,
    intelligenceArtifactCombinedTimeoutMs,
    // P5 admission & spool
    intelligenceMaxConcurrentArtifactRelays,
    intelligenceArtifactSpoolDir,
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
      intelligenceQueryMaxBytes: 32768,
      intelligenceMaxFilterElements: 50,
      intelligenceJsonRequestMaxBytes: 131072,
      intelligenceJsonResponseMaxBytes: 4194304,
      intelligenceC3ResponseMaxBytes: 2097152,
      intelligenceDiagramSpecMaxBytes: 16777216,
      intelligenceDiagramLayoutMaxBytes: 33554432,
      intelligenceDiagramExportMaxBytes: 67108864,
      intelligenceDiagramSvgMaxBytes: 50331648,
      intelligencePdfMaxBytes: 67108864,
      intelligenceMetadataTimeoutMs: 30000,
      intelligenceLongTimeoutMs: 120000,
      intelligenceArtifactUpstreamTimeoutMs: 90000,
      intelligenceArtifactRelayTimeoutMs: 60000,
      intelligenceArtifactCombinedTimeoutMs: 150000,
      intelligenceMaxConcurrentArtifactRelays: 2,
      intelligenceArtifactSpoolDir: path.join(os.tmpdir(), 'stacksense-intelligence-spool'),
    };
  } else {
    throw err;
  }
}

module.exports = {
  analysisConfig,
  validateAnalysisConfig,
};

