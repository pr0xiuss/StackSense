import React, { useState } from 'react';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen);
  };

  const closeMenu = () => {
    setMobileMenuOpen(false);
  };

  return (
    <header className="navbar">
      <div className="container navbar-container">
        <a href="#" className="brand-link" aria-label="StackSense Home">
          <svg className="brand-icon" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 4L26 9.5V14.5L16 20L6 14.5V9.5L16 4Z" fill="#38BDF8" fillOpacity="0.9" />
            <path d="M6 17.5L16 23L26 17.5V21L16 26.5L6 21V17.5Z" fill="#6366F1" />
            <path d="M6 13.5L16 19L26 13.5V16.5L16 22L6 16.5V13.5Z" fill="#8B5CF6" fillOpacity="0.8" />
          </svg>
          <span>StackSense</span>
        </a>

        <nav aria-label="Main Navigation">
          <ul className="nav-menu">
            <li><a href="#overview" className="nav-link">Product</a></li>
            <li><a href="#how-it-works" className="nav-link">How It Works</a></li>
            <li><a href="#why-stacksense" className="nav-link">Features</a></li>
            <li><a href="#architecture" className="nav-link">Use Cases</a></li>
            <li><a href="#docs" className="nav-link">Docs</a></li>
          </ul>
        </nav>

        <div className="nav-actions">
          <a
            href="https://github.com/pr0xiuss/StackSense"
            target="_blank"
            rel="noopener noreferrer"
            className="github-btn"
            aria-label="GitHub Repository"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
            </svg>
          </a>
          <a href="#/login" className="nav-link nav-signin-link">
            Sign In
          </a>
          <a href="#/signup" className="btn-primary">
            Get Started
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </a>
          <button
            type="button"
            className="mobile-toggle"
            onClick={toggleMenu}
            aria-label="Toggle navigation menu"
            aria-expanded={mobileMenuOpen}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {mobileMenuOpen ? (
                <path d="M18 6L6 18M6 6l12 12" />
              ) : (
                <path d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {mobileMenuOpen && (
        <div className="mobile-nav-panel">
          <a href="#overview" className="mobile-nav-link" onClick={closeMenu}>Product</a>
          <a href="#how-it-works" className="mobile-nav-link" onClick={closeMenu}>How It Works</a>
          <a href="#why-stacksense" className="mobile-nav-link" onClick={closeMenu}>Features</a>
          <a href="#architecture" className="mobile-nav-link" onClick={closeMenu}>Use Cases</a>
          <a href="#docs" className="mobile-nav-link" onClick={closeMenu}>Docs</a>
        </div>
      )}
    </header>
  );
}
