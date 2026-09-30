import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../auth/AuthContext.jsx';

export default function DashboardHeader() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Compute initials from username or email
  const getInitials = () => {
    if (!user) return 'SS';
    if (user.username) {
      return user.username.slice(0, 2).toUpperCase();
    }
    if (user.email) {
      return user.email.slice(0, 2).toUpperCase();
    }
    return 'SS';
  };

  const displayName = user?.username || (user?.email ? user.email.split('@')[0] : 'User');
  const displayEmail = user?.email || '';

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  return (
    <header className="dashboard-navbar">
      <div className="dashboard-nav-container">
        {/* Brand */}
        <a href="#/projects" className="dashboard-brand" aria-label="StackSense Projects">
          <svg className="dashboard-brand-icon" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 4L26 9.5V14.5L16 20L6 14.5V9.5L16 4Z" fill="#38BDF8" fillOpacity="0.9" />
            <path d="M6 17.5L16 23L26 17.5V21L16 26.5L6 21V17.5Z" fill="#6366F1" />
            <path d="M6 13.5L16 19L26 13.5V16.5L16 22L6 16.5V13.5Z" fill="#8B5CF6" fillOpacity="0.8" />
          </svg>
          <span className="dashboard-brand-title">StackSense</span>
        </a>

        {/* User Capsule & Sign Out */}
        <div className="dashboard-user-area" ref={menuRef}>
          <button
            type="button"
            className="dashboard-user-capsule"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-expanded={menuOpen}
            aria-haspopup="true"
          >
            <div className="dashboard-avatar" aria-hidden="true">
              <span>{getInitials()}</span>
            </div>
            <div className="dashboard-user-meta">
              <span className="dashboard-user-name">{displayName}</span>
              {displayEmail && <span className="dashboard-user-email">{displayEmail}</span>}
            </div>
            <svg
              className={`dashboard-chevron ${menuOpen ? 'open' : ''}`}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          <button
            type="button"
            className="dashboard-signout-btn"
            onClick={logout}
            aria-label="Sign out"
          >
            Sign Out
          </button>

          {menuOpen && (
            <div className="dashboard-user-dropdown" role="menu">
              <div className="dropdown-user-info">
                <p className="dropdown-name">{displayName}</p>
                <p className="dropdown-email">{displayEmail}</p>
              </div>
              <div className="dropdown-divider" />
              <button
                type="button"
                className="dropdown-item"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
                role="menuitem"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
