import React, { useState, useEffect } from 'react';
import { AuthProvider } from './auth/AuthContext.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import DashboardHeader from './components/dashboard/DashboardHeader.jsx';
import ProjectsDashboardPage from './pages/ProjectsDashboardPage.jsx';
import RepositoryDetailPage from './pages/RepositoryDetailPage.jsx';
import AnalysisDetailPage from './pages/AnalysisDetailPage.jsx';
import ArchitectureModelPage from './pages/ArchitectureModelPage.jsx';
import LandingPage from './pages/LandingPage.jsx';
import AuthPage from './pages/AuthPage.jsx';
import { isValidUuid } from './contracts/graphContracts.js';

const ArchitectureExplorerPage = React.lazy(() => import('./pages/ArchitectureExplorerPage.jsx'));
const RepositoryIntelligencePage = React.lazy(() => import('./pages/RepositoryIntelligencePage.jsx'));

import './styles/index.css';
import './styles/landing.css';
import './styles/auth.css';
import './styles/dashboard.css';
import './styles/repository.css';
import './styles/analysis.css';
import './styles/architecture.css';
import './styles/graph.css';

/**
 * Determine current route and parameters from location hash and pathname.
 * Routes are matched in strict descending order of specificity.
 */
export function parseCurrentRoute() {
  const hash = window.location.hash || '';
  const pathname = window.location.pathname || '';

  // 1. Intelligence Route (most specific, end-anchored):
  //    #/projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture/:versionId/intelligence
  //    /projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture/:versionId/intelligence
  const intelHashMatch = hash.match(/^#\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)\/architecture\/([^/]+)\/intelligence([/?].*|$)/i);
  const intelPathMatch = pathname.match(/^\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)\/architecture\/([^/]+)\/intelligence([/?].*|$)/i);
  const intelMatch = intelHashMatch || intelPathMatch;

  if (intelMatch) {
    let pId, rId, aId, vId;
    try {
      pId = decodeURIComponent(intelMatch[1]);
      rId = decodeURIComponent(intelMatch[2]);
      aId = decodeURIComponent(intelMatch[3]);
      vId = decodeURIComponent(intelMatch[4]);
    } catch {
      return { view: 'route_error', message: 'Malformed URL encoding in route identifiers.' };
    }

    const trailing = intelMatch[5];
    if (trailing && trailing !== '/' && !trailing.startsWith('?')) {
      return { view: 'route_error', message: 'Unmatched trailing path on Intelligence route.' };
    }

    if (!isValidUuid(pId) || !isValidUuid(rId) || !isValidUuid(aId) || !isValidUuid(vId)) {
      return { view: 'route_error', message: 'Malformed UUID in Intelligence route parameters.' };
    }

    return {
      view: 'intelligence',
      projectId: pId,
      repositoryId: rId,
      analysisId: aId,
      versionId: vId,
    };
  }

  // 2. Graph Explorer Route (most specific, end-anchored):
  //    #/projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture/:versionId/graph
  //    /projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture/:versionId/graph
  const explorerHashMatch = hash.match(/^#\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)\/architecture\/([^/]+)\/graph(?:\/|$)(.*)/i);
  const explorerPathMatch = pathname.match(/^\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)\/architecture\/([^/]+)\/graph(?:\/|$)(.*)/i);
  const explorerMatch = explorerHashMatch || explorerPathMatch;

  if (explorerMatch) {
    let pId, rId, aId, vId;
    try {
      pId = decodeURIComponent(explorerMatch[1]);
      rId = decodeURIComponent(explorerMatch[2]);
      aId = decodeURIComponent(explorerMatch[3]);
      vId = decodeURIComponent(explorerMatch[4]);
    } catch {
      return { view: 'route_error', message: 'Malformed URL encoding in route identifiers.' };
    }

    const trailing = explorerMatch[5];
    if (trailing && trailing !== '/') {
      return { view: 'route_error', message: 'Unmatched trailing path on Graph Explorer route.' };
    }

    if (!isValidUuid(pId) || !isValidUuid(rId) || !isValidUuid(aId) || !isValidUuid(vId)) {
      return { view: 'route_error', message: 'Malformed UUID in Graph Explorer route parameters.' };
    }

    return {
      view: 'explorer',
      projectId: pId,
      repositoryId: rId,
      analysisId: aId,
      versionId: vId,
    };
  }

  // 2. Exact-version Architecture Model Route:
  //    #/projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture/:versionId
  //    /projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture/:versionId
  const exactArchHashMatch = hash.match(/^#\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)\/architecture\/([^/]+)(?:\/|$)(.*)/i);
  const exactArchPathMatch = pathname.match(/^\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)\/architecture\/([^/]+)(?:\/|$)(.*)/i);
  const exactArchMatch = exactArchHashMatch || exactArchPathMatch;

  if (exactArchMatch) {
    let pId, rId, aId, vId;
    try {
      pId = decodeURIComponent(exactArchMatch[1]);
      rId = decodeURIComponent(exactArchMatch[2]);
      aId = decodeURIComponent(exactArchMatch[3]);
      vId = decodeURIComponent(exactArchMatch[4]);
    } catch {
      return { view: 'route_error', message: 'Malformed URL encoding in route identifiers.' };
    }

    const trailing = exactArchMatch[5];
    if (trailing && trailing !== '/') {
      return { view: 'route_error', message: 'Unmatched trailing path on Architecture Model route.' };
    }

    if (!isValidUuid(pId) || !isValidUuid(rId) || !isValidUuid(aId) || !isValidUuid(vId)) {
      return { view: 'route_error', message: 'Malformed UUID in Architecture Model route parameters.' };
    }

    return {
      view: 'architecture',
      projectId: pId,
      repositoryId: rId,
      analysisId: aId,
      versionId: vId,
    };
  }

  // 3. Legacy Architecture Model Route (analysis current version):
  //    #/projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture
  //    /projects/:projectId/repositories/:repositoryId/analyses/:analysisId/architecture
  const archHashMatch = hash.match(/^#\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)\/architecture(?:\/|$)/i);
  const archPathMatch = pathname.match(/^\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)\/architecture(?:\/|$)/i);
  const archMatch = archHashMatch || archPathMatch;

  if (archMatch) {
    return {
      view: 'architecture',
      projectId: decodeURIComponent(archMatch[1]),
      repositoryId: decodeURIComponent(archMatch[2]),
      analysisId: decodeURIComponent(archMatch[3]),
      versionId: undefined,
    };
  }

  // 2. Analysis Detail Route:
  //    #/projects/:projectId/repositories/:repositoryId/analyses/:analysisId
  //    /projects/:projectId/repositories/:repositoryId/analyses/:analysisId
  const analysisHashMatch = hash.match(/^#\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)(?:\/|$)/i);
  const analysisPathMatch = pathname.match(/^\/?projects\/([^/]+)\/repositories\/([^/]+)\/analyses\/([^/]+)(?:\/|$)/i);
  const analysisMatch = analysisHashMatch || analysisPathMatch;

  if (analysisMatch) {
    return {
      view: 'analysis',
      projectId: decodeURIComponent(analysisMatch[1]),
      repositoryId: decodeURIComponent(analysisMatch[2]),
      analysisId: decodeURIComponent(analysisMatch[3]),
    };
  }

  // 3. Repository Detail Route:
  //    #/projects/:projectId/repositories/:repositoryId
  //    /projects/:projectId/repositories/:repositoryId
  const repoHashMatch = hash.match(/^#\/?projects\/([^/]+)\/repositories\/([^/]+)(?:\/|$)/i);
  const repoPathMatch = pathname.match(/^\/?projects\/([^/]+)\/repositories\/([^/]+)(?:\/|$)/i);
  const repoMatch = repoHashMatch || repoPathMatch;

  if (repoMatch) {
    return {
      view: 'repository',
      projectId: decodeURIComponent(repoMatch[1]),
      repositoryId: decodeURIComponent(repoMatch[2]),
    };
  }

  // 2. Projects Dashboard Route:
  //    #/projects, /projects, or legacy #/app, /app
  const lowerHash = hash.toLowerCase();
  const lowerPath = pathname.toLowerCase();

  if (
    lowerHash.startsWith('#/projects') ||
    lowerHash.startsWith('#projects') ||
    lowerHash.startsWith('#/app') ||
    lowerHash.startsWith('#app') ||
    lowerPath === '/projects' ||
    lowerPath === '/app'
  ) {
    return { view: 'projects', mode: 'projects' };
  }

  // 3. Signup / Register Route:
  if (
    lowerHash.startsWith('#/signup') ||
    lowerHash.startsWith('#signup') ||
    lowerPath === '/signup' ||
    lowerPath === '/register'
  ) {
    return { view: 'auth', mode: 'signup' };
  }

  // 4. Login / Signin Route:
  if (
    lowerHash.startsWith('#/login') ||
    lowerHash.startsWith('#login') ||
    lowerHash.startsWith('#/auth') ||
    lowerPath === '/login' ||
    lowerPath === '/signin' ||
    lowerPath === '/auth'
  ) {
    return { view: 'auth', mode: 'login' };
  }

  // 5. Default Public Landing Route
  return { view: 'landing', mode: 'login' };
}

function AppContent() {
  const [route, setRoute] = useState(parseCurrentRoute);

  useEffect(() => {
    const handleRouteChange = () => {
      setRoute(parseCurrentRoute());
    };

    window.addEventListener('hashchange', handleRouteChange);
    window.addEventListener('popstate', handleRouteChange);

    return () => {
      window.removeEventListener('hashchange', handleRouteChange);
      window.removeEventListener('popstate', handleRouteChange);
    };
  }, []);

  const navigateToHome = () => {
    if (window.history.pushState) {
      window.history.pushState(null, '', '#/');
    } else {
      window.location.hash = '#/';
    }
    setRoute({ view: 'landing', mode: 'login' });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (route.view === 'intelligence') {
    return (
      <ProtectedRoute>
        <React.Suspense
          fallback={
            <div className="repo-loading-screen" role="status">
              <span className="btn-spinner" aria-hidden="true" />
              <p>Loading Repository Intelligence...</p>
            </div>
          }
        >
          <RepositoryIntelligencePage
            key={`${route.projectId}-${route.repositoryId}-${route.analysisId}-${route.versionId}`}
            projectId={route.projectId}
            repositoryId={route.repositoryId}
            analysisId={route.analysisId}
            versionId={route.versionId}
          />
        </React.Suspense>
      </ProtectedRoute>
    );
  }

  if (route.view === 'explorer') {
    return (
      <ProtectedRoute>
        <React.Suspense
          fallback={
            <div className="repo-loading-screen" role="status">
              <span className="btn-spinner" aria-hidden="true" />
              <p>Loading Architecture Explorer...</p>
            </div>
          }
        >
          <ArchitectureExplorerPage
            key={`${route.projectId}-${route.repositoryId}-${route.analysisId}-${route.versionId}`}
            projectId={route.projectId}
            repositoryId={route.repositoryId}
            analysisId={route.analysisId}
            versionId={route.versionId}
          />
        </React.Suspense>
      </ProtectedRoute>
    );
  }

  if (route.view === 'route_error') {
    return (
      <div className="repository-page-wrapper">
        <DashboardHeader />
        <main className="container" style={{ padding: '2rem' }}>
          <div className="repo-error-screen" role="alert">
            <div className="error-icon-box">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h2>Invalid Route</h2>
            <p>{route.message || 'The requested URL parameters or format are invalid.'}</p>
            <div style={{ marginTop: '1.25rem' }}>
              <a href="#/projects" className="btn-gradient-primary">
                Return to Projects
              </a>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (route.view === 'architecture') {
    return (
      <ProtectedRoute>
        <ArchitectureModelPage
          key={
            route.versionId
              ? `${route.projectId}-${route.repositoryId}-${route.analysisId}-${route.versionId}`
              : `${route.projectId}-${route.repositoryId}-${route.analysisId}`
          }
          projectId={route.projectId}
          repositoryId={route.repositoryId}
          analysisId={route.analysisId}
          versionId={route.versionId}
        />
      </ProtectedRoute>
    );
  }

  if (route.view === 'analysis') {
    return (
      <ProtectedRoute>
        <AnalysisDetailPage
          projectId={route.projectId}
          repositoryId={route.repositoryId}
          analysisId={route.analysisId}
        />
      </ProtectedRoute>
    );
  }

  if (route.view === 'repository') {
    return (
      <ProtectedRoute>
        <RepositoryDetailPage
          projectId={route.projectId}
          repositoryId={route.repositoryId}
        />
      </ProtectedRoute>
    );
  }

  if (route.view === 'projects') {
    return (
      <ProtectedRoute>
        <ProjectsDashboardPage />
      </ProtectedRoute>
    );
  }

  if (route.view === 'auth') {
    return (
      <AuthPage
        initialMode={route.mode}
        onNavigateHome={navigateToHome}
      />
    );
  }

  return <LandingPage onNavigateHome={navigateToHome} />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
