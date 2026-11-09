import React, { useState, useEffect } from 'react';
import { AuthProvider } from './auth/AuthContext.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import ProjectsDashboardPage from './pages/ProjectsDashboardPage.jsx';
import RepositoryDetailPage from './pages/RepositoryDetailPage.jsx';
import AnalysisDetailPage from './pages/AnalysisDetailPage.jsx';
import ArchitectureModelPage from './pages/ArchitectureModelPage.jsx';
import LandingPage from './pages/LandingPage.jsx';
import AuthPage from './pages/AuthPage.jsx';

import './styles/index.css';
import './styles/landing.css';
import './styles/auth.css';
import './styles/dashboard.css';
import './styles/repository.css';
import './styles/analysis.css';
import './styles/architecture.css';

/**
 * Determine current route and parameters from location hash and pathname.
 * Routes are matched in strict descending order of specificity.
 */
function parseCurrentRoute() {
  const hash = window.location.hash || '';
  const pathname = window.location.pathname || '';

  // 1. Architecture Model Route (most specific):
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

  if (route.view === 'architecture') {
    return (
      <ProtectedRoute>
        <ArchitectureModelPage
          projectId={route.projectId}
          repositoryId={route.repositoryId}
          analysisId={route.analysisId}
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
