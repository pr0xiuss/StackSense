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
          </ul>
        </nav>

        <div className="nav-actions">
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
        </div>
      )}
    </header>
  );
}
