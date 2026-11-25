import React from 'react';

/**
 * Panel-level Error Boundary for Intelligence Panels.
 * Isolates rendering failures within a single panel so that other panels and navigation remain functional.
 */
export class IntelligenceErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Intelligence panel error boundary caught an error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="intelligence-error-boundary" role="alert">
          <div className="intelligence-error-card">
            <h3 className="intelligence-error-title">
              {this.props.title || 'Panel Error'}
            </h3>
            <p className="intelligence-error-message">
              {this.state.error?.message || 'An unexpected rendering error occurred in this panel.'}
            </p>
            <div className="intelligence-error-actions">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={this.handleReset}
              >
                Retry Panel
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
