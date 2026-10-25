import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

const VIEWPORT_GAP = 8;

export default function ActionMenu({ label, items, size = 'default' }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const enabledItems = items.filter((item) => !item.hidden);

  const close = () => {
    setOpen(false);
    setPosition(null);
  };

  const updatePosition = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const menuWidth = 210;
    const estimatedHeight = Math.max(48, enabledItems.length * 42 + 12);
    const left = Math.max(VIEWPORT_GAP, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - VIEWPORT_GAP));
    const spaceBelow = window.innerHeight - rect.bottom;
    const top = spaceBelow >= estimatedHeight + VIEWPORT_GAP
      ? rect.bottom + 6
      : Math.max(VIEWPORT_GAP, rect.top - estimatedHeight - 6);
    setPosition({ top, left, width: menuWidth });
  };

  useLayoutEffect(() => {
    if (open) updatePosition();
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const handlePointer = (event) => {
      if (!triggerRef.current?.contains(event.target) && !menuRef.current?.contains(event.target)) close();
    };
    const handleKey = (event) => {
      if (event.key === 'Escape') {
        close();
        triggerRef.current?.focus();
      }
    };
    const handleLayout = () => updatePosition();
    document.addEventListener('mousedown', handlePointer);
    document.addEventListener('keydown', handleKey);
    window.addEventListener('resize', handleLayout);
    window.addEventListener('scroll', handleLayout, true);
    return () => {
      document.removeEventListener('mousedown', handlePointer);
      document.removeEventListener('keydown', handleKey);
      window.removeEventListener('resize', handleLayout);
      window.removeEventListener('scroll', handleLayout, true);
    };
  }, [open]);

  if (enabledItems.length === 0) return null;

  const handleTriggerKeyDown = (event) => {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setOpen(true);
      requestAnimationFrame(() => menuRef.current?.querySelector('[role="menuitem"]')?.focus());
    }
  };

  const handleMenuKeyDown = (event) => {
    const menuItems = [...menuRef.current.querySelectorAll('[role="menuitem"]:not(:disabled)')];
    const current = menuItems.indexOf(document.activeElement);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      menuItems[(current + direction + menuItems.length) % menuItems.length]?.focus();
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      menuItems[event.key === 'Home' ? 0 : menuItems.length - 1]?.focus();
    } else if (event.key === 'Tab') {
      close();
    }
  };

  return (
    <div className="project-menu-anchor">
      <button
        ref={triggerRef}
        type="button"
        className={`project-menu-btn ${size === 'compact' ? 'repo-menu-btn' : ''}`}
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
        onKeyDown={handleTriggerKeyDown}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <circle cx="12" cy="5" r="2" />
          <circle cx="12" cy="12" r="2" />
          <circle cx="12" cy="19" r="2" />
        </svg>
      </button>
      {open && position && createPortal(
        <div
          ref={menuRef}
          className="project-dropdown-menu shared-action-menu"
          style={position}
          role="menu"
          onKeyDown={handleMenuKeyDown}
        >
          {enabledItems.map((item, index) => (
            <React.Fragment key={item.label}>
              {item.dividerBefore && index > 0 && <div className="dropdown-divider" role="separator" />}
              <button
                type="button"
                className={`dropdown-item ${item.danger ? 'danger' : ''}`}
                onClick={(event) => {
                  event.stopPropagation();
                  close();
                  item.onSelect();
                }}
                role="menuitem"
              >
                <span className="action-menu-icon" aria-hidden="true">
                  {item.icon || <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="4" /></svg>}
                </span>
                <span>{item.label}</span>
              </button>
            </React.Fragment>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}
