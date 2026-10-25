import React, { useState, useEffect } from 'react';
import { AuthProvider } from './auth/AuthContext.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import ProjectsDashboardPage from './pages/ProjectsDashboardPage.jsx';
import LandingPage from './pages/LandingPage.jsx';
import AuthPage from './pages/AuthPage.jsx';

import './styles/index.css';
import './styles/landing.css';
import './styles/auth.css';
import './styles/dashboard.css';

function parseCurrentRoute() {
  const hash = window.location.hash || '';
  const pathname = window.location.pathname || '';
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

  if (
    lowerHash.startsWith('#/signup') ||
    lowerHash.startsWith('#signup') ||
    lowerPath === '/signup' ||
    lowerPath === '/register'
  ) {
    return { view: 'auth', mode: 'signup' };
  }

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
