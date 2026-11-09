import React from 'react';
import {
  getStageLabel,
  getStatusBadgeClass,
  formatDuration,
} from '../../contracts/analysisContracts.js';

export default function AnalysisExecution({ analysis }) {
  const activeJob = analysis?.active_job;
  const stages = Array.isArray(analysis?.stages) ? analysis.stages : [];

  // Sort stages by order
  const sortedStages = [...stages].sort((a, b) => (a.order || 0) - (b.order || 0));

  return (
    <div className="analysis-execution-container">
      {/* Active Job Card */}
      <div className="execution-job-card">
        <div className="tab-card-header">
          <div>
            <h3 className="tab-card-title">Background Worker Job</h3>
            <p className="tab-card-subtitle">
              Execution worker assignment, retry attempts, and heartbeat telemetry.
            </p>
          </div>
          {activeJob && (
            <span className={`badge-status ${getStatusBadgeClass(activeJob.status)}`}>
              <span className="badge-status-dot" />
              <span>{activeJob.status?.toUpperCase()}</span>
            </span>
          )}
        </div>

        {activeJob ? (
          <div className="execution-job-grid">
            <div className="execution-job-item">
              <span className="execution-job-label">Job ID</span>
              <span className="execution-job-val mono-cell" title={activeJob.id}>
                {activeJob.id ? activeJob.id.slice(0, 12) + '...' : '—'}
              </span>
            </div>

            <div className="execution-job-item">
              <span className="execution-job-label">Attempt</span>
              <span className="execution-job-val">
                {activeJob.attempt} / {activeJob.max_attempts}
              </span>
            </div>

            <div className="execution-job-item">
              <span className="execution-job-label">Worker Assignment</span>
              <span className="execution-job-val mono-cell">
                {activeJob.worker_id || 'default-worker'}
              </span>
            </div>

            <div className="execution-job-item">
              <span className="execution-job-label">Heartbeat</span>
              <span className="execution-job-val">
                {activeJob.heartbeat_at ? new Date(activeJob.heartbeat_at).toLocaleTimeString() : '—'}
              </span>
            </div>

            <div className="execution-job-item">
              <span className="execution-job-label">Started At</span>
              <span className="execution-job-val">
                {activeJob.started_at ? new Date(activeJob.started_at).toLocaleString() : '—'}
              </span>
            </div>

            <div className="execution-job-item">
              <span className="execution-job-label">Completed At</span>
              <span className="execution-job-val">
                {activeJob.completed_at ? new Date(activeJob.completed_at).toLocaleString() : '—'}
              </span>
            </div>

            {activeJob.error_message && (
              <div className="execution-job-item" style={{ gridColumn: '1 / -1' }}>
                <span className="execution-job-label" style={{ color: '#F87171' }}>
                  Execution Error ({activeJob.error_code || 'error'})
                </span>
                <span className="execution-job-val" style={{ color: '#F87171' }}>
                  {activeJob.error_message}
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="analyses-empty-box" style={{ padding: '1.5rem', marginTop: '1rem' }}>
            <p className="analyses-empty-desc" style={{ margin: 0 }}>
              No active worker job record associated with this run.
            </p>
          </div>
        )}
      </div>

      {/* Stage Execution Table */}
      <div className="analyses-card" style={{ marginTop: '1.5rem' }}>
        <div className="tab-card-header" style={{ marginBottom: '1.25rem' }}>
          <div>
            <h3 className="tab-card-title">Stage Execution Telemetry</h3>
            <p className="tab-card-subtitle">
              Granular state, item counts, and duration for each pipeline stage.
            </p>
          </div>
        </div>

        {sortedStages.length === 0 ? (
          <div className="analyses-empty-box">
            <p className="analyses-empty-title">No Stages Initialized</p>
            <p className="analyses-empty-desc">
              Pipeline stages have not yet been generated for this analysis run.
            </p>
          </div>
        ) : (
          <div className="analyses-table-container">
            <table className="analyses-table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Stage Name</th>
                  <th scope="col">Status</th>
                  <th scope="col">Mandatory</th>
                  <th scope="col">Processed / Total</th>
                  <th scope="col">Started</th>
                  <th scope="col">Duration</th>
                  <th scope="col">Error</th>
                </tr>
              </thead>
              <tbody>
                {sortedStages.map((stage) => (
                  <tr key={stage.id || stage.order}>
                    <td className="mono-cell">{stage.order}</td>
                    <td style={{ fontWeight: 500 }}>{getStageLabel(stage.stage_name)}</td>
                    <td>
                      <span className={`badge-status ${getStatusBadgeClass(stage.status)}`}>
                        <span className="badge-status-dot" />
                        <span>{stage.status}</span>
                      </span>
                    </td>
                    <td>{stage.is_mandatory ? 'Yes' : 'No'}</td>
                    <td className="mono-cell">
                      {typeof stage.total_items === 'number' && stage.total_items > 0
                        ? `${stage.processed_items.toLocaleString()} / ${stage.total_items.toLocaleString()}`
                        : typeof stage.processed_items === 'number' && stage.processed_items > 0
                          ? `${stage.processed_items.toLocaleString()} items`
                          : '—'}
                    </td>
                    <td>{stage.started_at ? new Date(stage.started_at).toLocaleTimeString() : '—'}</td>
                    <td>{formatDuration(stage.started_at, stage.completed_at)}</td>
                    <td style={{ maxWidth: '200px', color: stage.error_message ? '#F87171' : '#64748B' }}>
                      {stage.error_message || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

