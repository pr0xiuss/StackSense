import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authService } from '../services/authService.js';
import { tokenStorage } from '../services/apiClient.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  const clearSession = useCallback(() => {
    tokenStorage.clearTokens();
    setUser(null);
    setIsAuthenticated(false);
    setLoading(false);
  }, []);

  // Restore authenticated session on application mount
  useEffect(() => {
    let isMounted = true;

    async function restoreSession() {
      const accessToken = tokenStorage.getAccessToken();
      const refreshToken = tokenStorage.getRefreshToken();

      if (!accessToken && !refreshToken) {
        if (isMounted) {
          clearSession();
        }
        return;
      }

      try {
        const currentUser = await authService.getCurrentUser();
        if (isMounted && currentUser) {
          setUser(currentUser);
          setIsAuthenticated(true);
        }
      } catch (err) {
        // If getting current user fails even after refresh attempts, clear session
        if (isMounted) {
          clearSession();
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    restoreSession();

    // Listen for auth:expired event dispatched by apiClient when refresh token is rejected
    const handleAuthExpired = () => {
      clearSession();
      if (window.location.hash.startsWith('#/projects') || window.location.pathname.startsWith('/projects')) {
        if (window.history.replaceState) {
          window.history.replaceState(null, '', '#/login');
        } else {
          window.location.hash = '#/login';
        }
        window.dispatchEvent(new HashChangeEvent('hashchange'));
      }
    };

    window.addEventListener('auth:expired', handleAuthExpired);
    return () => {
      isMounted = false;
      window.removeEventListener('auth:expired', handleAuthExpired);
    };
  }, [clearSession]);

  const login = useCallback(async (identifier, password) => {
    setAuthError(null);
    const data = await authService.login(identifier, password);
    const currentUser = await authService.getCurrentUser();
    setUser(currentUser);
    setIsAuthenticated(true);
    return currentUser;
  }, []);

  const register = useCallback(async (email, username, password) => {
    setAuthError(null);
    return await authService.register(email, username, password);
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = tokenStorage.getRefreshToken();
    try {
      await authService.logout(refreshToken);
    } catch {
      // Ignore network failures during logout; local session must always clear
    } finally {
      clearSession();
      // Replace history state to prevent browser Back from returning to protected views
      if (window.history.replaceState) {
        window.history.replaceState(null, '', '#/');
      } else {
        window.location.hash = '#/';
      }
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    }
  }, [clearSession]);

  const value = {
    user,
    isAuthenticated,
    loading,
    authError,
    setAuthError,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
