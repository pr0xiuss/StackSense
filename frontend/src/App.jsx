import React, { useState, useEffect } from 'react';
import LandingPage from './pages/LandingPage.jsx';
import AuthPage from './pages/AuthPage.jsx';
import './styles/index.css';
import './styles/landing.css';
import './styles/auth.css';

/**
 * Determine current route and auth mode from location hash and pathname.
 */
function parseCurrentRoute() {
  const hash = (window.location.hash || '').toLowerCase();
  const pathname = (window.location.pathname || '').toLowerCase();

  if (
    hash.startsWith('#/signup') ||
    hash.startsWith('#signup') ||
    pathname === '/signup' ||
    pathname === '/register'
  ) {
    return { view: 'auth', mode: 'signup' };
  }

  if (
    hash.startsWith('#/login') ||
    hash.startsWith('#login') ||
    hash.startsWith('#/auth') ||
    pathname === '/login' ||
    pathname === '/signin' ||
    pathname === '/auth'
  ) {
    return { view: 'auth', mode: 'login' };
  }

  return { view: 'landing', mode: 'login' };
}

export default function App() {
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

  if (route.view === 'auth') {
    return (
      <AuthPage
        initialMode={route.mode}
        onNavigateHome={navigateToHome}
      />
    );
  }

  return <LandingPage />;
}
