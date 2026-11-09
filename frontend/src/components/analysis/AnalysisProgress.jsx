import React from 'react';
import {
  STAGE_NAME,
  getStageLabel,
  formatDuration,
} from '../../contracts/analysisContracts.js';

const ORDERED_STAGE_KEYS = [
  STAGE_NAME.INPUT_VALIDATION,
  STAGE_NAME.INVENTORY,
  STAGE_NAME.LANGUAGE_DETECTION,
  STAGE_NAME.FRAMEWORK_DETECTION,
  STAGE_NAME.SYNTAX_EXTRACTION,
  STAGE_NAME.IR_CONSTRUCTION,
  STAGE_NAME.IDENTITY_RESOLUTION,
  STAGE_NAME.ARCHITECTURE_BUILD,
];

export default function AnalysisProgress({ analysis }) {
  const stages = Array.isArray(analysis?.stages) ? analysis.stages : [];

  // Match stage data by stage_name or fallback to order
  const stageMap = new Map();
  stages.forEach((s) => {
    if (s.stage_name) stageMap.set(s.stage_name.toLowerCase(), s);
  });

  const orderedStages = ORDERED_STAGE_KEYS.map((key, index) => {
    const existing = stageMap.get(key) || stages.find((s) => s.order === index + 1);
    return (
      existing || {
        stage_name: key,
        status: 'pending',
        order: index + 1,
        processed_items: 0,
        total_items: 0,
      }
    );
  });

  // Calculate overall progress percentage
  const isTerminal = ['completed', 'completed_with_warnings'].includes(analysis?.status?.toLowerCase());
  let overallPercent = 0;
  let isIndeterminate = false;

  if (isTerminal) {
    overallPercent = 100;
  } else {
    const stageWeight = 100 / orderedStages.length;
    let completedWeight = 0;

    for (const stage of orderedStages) {
      const st = (stage.status || '').toLowerCase();
      if (st === 'completed') {
        completedWeight += stageWeight;
      } else if (st === 'running') {
        if (typeof stage.total_items === 'number' && stage.total_items > 0) {
          const ratio = Math.min(1, Math.max(0, stage.processed_items / stage.total_items));
          completedWeight += ratio * stageWeight;
        } else {
          isIndeterminate = true;
        }
      }
    }
    overallPercent = Math.min(100, Math.round(completedWeight));
  }

  const completeness = analysis?.completeness;
  const analyzedFiles = completeness?.analyzed_files_count ?? 0;
  const failedFiles = completeness?.failed_files_count ?? 0;
  const excludedFiles = completeness?.excluded_files_count ?? 0;
  const unsupportedFiles = completeness?.unsupported_files_count ?? 0;

  return (
    <div className="analysis-progress-container">
      {/* Metric Cards Row */}
      <div className="analysis-metrics-grid">
        {/* Progress Metric Card */}
        <div className="analysis-metric-card">
          <span className="metric-label">Pipeline Progress</span>
          <div className="metric-value-row">
            <span className="metric-primary-value">
              {isTerminal ? '100%' : isIndeterminate ? `${overallPercent}% (Active)` : `${overallPercent}%`}
            </span>
            <span className="metric-sub-value">
              {orderedStages.filter((s) => s.status?.toLowerCase() === 'completed').length} / {orderedStages.length} stages
            </span>
          </div>
          <div className="progress-track" role="progressbar" aria-valuenow={overallPercent} aria-valuemin="0" aria-valuemax="100">
            <div
              className={`progress-fill ${isIndeterminate ? 'indeterminate' : ''}`}
              style={{ width: `${overallPercent}%` }}
            />
          </div>
        </div>

        {/* Files Analyzed Metric Card */}
        <div className="analysis-metric-card">
          <span className="metric-label">Files Analyzed</span>
          <div className="metric-value-row">
            <span className="metric-primary-value">{analyzedFiles.toLocaleString()}</span>
            <span className="metric-sub-value">
              {failedFiles > 0 ? `${failedFiles} failed` : `${excludedFiles} excluded`}
            </span>
          </div>
          <div className="metric-extra-info">
            <span>{unsupportedFiles} unsupported</span>
            {completeness?.is_partial && <span className="partial-badge">Partial Run</span>}
          </div>
        </div>

        {/* Configuration Summary Metric Card */}
        <div className="analysis-metric-card">
          <span className="metric-label">Max File Size / Timeout</span>
          <div className="metric-value-row">
            <span className="metric-primary-value">
              {analysis?.configuration?.max_file_size_bytes
                ? `${Math.round(analysis.configuration.max_file_size_bytes / (1024 * 1024))} MiB`
                : '5 MiB'}
            </span>
            <span className="metric-sub-value">
              {analysis?.configuration?.timeout_seconds
                ? `${Math.round(analysis.configuration.timeout_seconds / 60)} min`
                : '30 min'}
            </span>
          </div>
          <span className="metric-extra-info">Limits & guardrails</span>
        </div>

        {/* Model Version Metric Card */}
        <div className="analysis-metric-card">
          <span className="metric-label">Published Model</span>
          <div className="metric-value-row">
            <span className="metric-primary-value">
              {analysis?.published_version_id ? (
                <span className="mono-cell" title={analysis.published_version_id}>
                  v{analysis.published_version_id.slice(0, 8)}
                </span>
              ) : (
                <span style={{ color: '#64748B' }}>None</span>
              )}
            </span>
          </div>
          <span className="metric-extra-info">
            {analysis?.published_version_id ? 'Architecture compiled' : 'Pending completion'}
          </span>
        </div>
      </div>

      {/* Stage Progress Rail */}
      <div className="stage-rail-wrapper">
        <h3 className="stage-rail-title">Pipeline Stage Progression</h3>
        <div className="stage-rail-track" role="list" aria-label="Pipeline Stages">
          {orderedStages.map((stage, idx) => {
            const st = (stage.status || 'pending').toLowerCase();
            const isCompleted = st === 'completed';
            const isRunning = st === 'running';
            const isFailed = st === 'failed';
            const isSkipped = st === 'skipped' || st === 'cancelled';

            let statusIcon = (
              <span className="stage-order-num">{idx + 1}</span>
            );
            if (isCompleted) {
              statusIcon = (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              );
            } else if (isRunning) {
              statusIcon = <span className="btn-spinner" aria-hidden="true" style={{ width: '12px', height: '12px' }} />;
            } else if (isFailed) {
              statusIcon = (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              );
            }

            return (
              <div
                key={stage.stage_name || idx}
                role="listitem"
                className={`stage-rail-node stage-${st}`}
              >
                <div className="stage-node-icon-box">
                  {statusIcon}
                </div>

                <div className="stage-node-content">
                  <span className="stage-node-title">{getStageLabel(stage.stage_name)}</span>
                  <div className="stage-node-meta">
                    <span className="stage-node-status">{st}</span>
                    {typeof stage.total_items === 'number' && stage.total_items > 0 && (
                      <span className="stage-node-counts">
                        ({stage.processed_items}/{stage.total_items})
                      </span>
                    )}
                  </div>
                  {stage.started_at && (
                    <span className="stage-node-duration">
                      {formatDuration(stage.started_at, stage.completed_at)}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

