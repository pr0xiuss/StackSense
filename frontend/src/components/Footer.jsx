import React from 'react';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-top">
          <a href="#" className="brand-link" aria-label="StackSense Home">
            <svg className="brand-icon" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M16 4L26 9.5V14.5L16 20L6 14.5V9.5L16 4Z" fill="#38BDF8" fillOpacity="0.9" />
              <path d="M6 17.5L16 23L26 17.5V21L16 26.5L6 21V17.5Z" fill="#6366F1" />
              <path d="M6 13.5L16 19L26 13.5V16.5L16 22L6 16.5V13.5Z" fill="#8B5CF6" fillOpacity="0.8" />
            </svg>
            <span>StackSense</span>
          </a>

          <ul className="footer-links">
            <li><a href="#overview" className="footer-link">Product</a></li>
            <li><a href="#how-it-works" className="footer-link">How It Works</a></li>
            <li><a href="#why-stacksense" className="footer-link">Features</a></li>
            <li><a href="#architecture" className="footer-link">Use Cases</a></li>
          </ul>
        </div>

        <div className="footer-bottom">
          <div>&copy; {currentYear} StackSense. All rights reserved.</div>
          <div>Built for developers who want to understand.</div>
        </div>
      </div>
    </footer>
  );
}
