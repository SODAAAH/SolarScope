import React, { useState, useRef, useEffect, useCallback } from 'react';
import { HelpCircle } from 'lucide-react';

export interface TooltipProps {
  content: React.ReactNode;
  title?: string;
  formula?: string;
  provenance?: 'Measured' | 'Calculated' | 'Estimated' | 'Simulated';
  position?: 'top' | 'bottom' | 'left' | 'right';
  underline?: boolean;
  showIcon?: boolean;
  className?: string;
  children: React.ReactNode;
}

export const Tooltip: React.FC<TooltipProps> = ({
  content,
  title,
  formula,
  provenance,
  position = 'top',
  underline = false,
  showIcon = false,
  className = '',
  children
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [shiftX, setShiftX] = useState(0);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const popupRef = useRef<HTMLSpanElement>(null);

  const adjustHorizontalPosition = useCallback(() => {
    const el = popupRef.current;
    if (!el || typeof window === 'undefined') return;
    el.style.marginLeft = '0px';
    const rect = el.getBoundingClientRect();
    const pad = 10;
    let delta = 0;
    if (rect.left < pad) {
      delta = pad - rect.left;
    } else if (rect.right > window.innerWidth - pad) {
      delta = window.innerWidth - pad - rect.right;
    }
    setShiftX(Math.round(delta));
  }, []);

  useEffect(() => {
    if (!isOpen) {
      setShiftX(0);
      return;
    }
    const raf = requestAnimationFrame(adjustHorizontalPosition);
    const handlePointerDown = (e: PointerEvent) => {
      if (triggerRef.current && !triggerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', adjustHorizontalPosition);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('resize', adjustHorizontalPosition);
    };
  }, [isOpen, adjustHorizontalPosition]);

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2'
  }[position];

  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-slate-900 dark:border-t-slate-800 border-x-transparent border-b-transparent border-t-4 border-x-4 border-b-0',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-slate-900 dark:border-b-slate-800 border-x-transparent border-t-transparent border-b-4 border-x-4 border-t-0',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-slate-900 dark:border-l-slate-800 border-y-transparent border-r-transparent border-l-4 border-y-4 border-r-0',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-slate-900 dark:border-r-slate-800 border-y-transparent border-l-transparent border-r-4 border-y-4 border-l-0'
  }[position];

  const handleClick = (e: React.MouseEvent<HTMLSpanElement>) => {
    const target = e.target as HTMLElement | null;
    if (target && target.closest('button, a, input, select, textarea')) {
      return;
    }
    setIsOpen((prev) => !prev);
  };

  return (
    <span
      ref={triggerRef}
      className={`group relative inline-flex items-center gap-1 ${underline ? 'cursor-help border-b border-dotted border-slate-400 dark:border-slate-500' : ''} ${className}`}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onFocus={() => setIsOpen(true)}
      onBlur={() => setIsOpen(false)}
      onClick={handleClick}
      tabIndex={0}
      role="tooltip"
      aria-label={typeof content === 'string' ? content : title}
    >
      {children}
      {showIcon && (
        <span className="inline-flex text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors shrink-0">
          <HelpCircle className="w-3 h-3" />
        </span>
      )}
      <span
        ref={popupRef}
        style={shiftX !== 0 && (position === 'top' || position === 'bottom') ? { marginLeft: `${shiftX}px` } : undefined}
        className={`absolute ${positionClasses} z-50 pointer-events-none transition-all duration-150 ease-out ${
          isOpen ? 'opacity-100 scale-100 visible' : 'opacity-0 scale-95 invisible'
        } w-[min(16rem,calc(100vw-1.5rem))] p-3 rounded-xl bg-slate-900 text-slate-100 dark:bg-slate-800 dark:text-slate-100 text-xs shadow-2xl border border-slate-700 font-normal normal-case tracking-normal leading-relaxed text-left select-none`}
      >
        {(title || provenance) && (
          <span className="flex items-center justify-between gap-2 mb-1.5 pb-1 border-b border-slate-700/60">
            {title && <span className="font-semibold text-white text-[12px]">{title}</span>}
            {provenance && (
              <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-800 dark:bg-slate-700 text-slate-300 font-medium shrink-0">
                {provenance}
              </span>
            )}
          </span>
        )}
        <span className="block text-slate-300 text-[11px] leading-relaxed">
          {content}
        </span>
        {formula && (
          <span className="block mt-2 pt-1.5 border-t border-slate-800 font-mono text-[10px] text-amber-300/90 bg-slate-950/40 px-1.5 py-0.5 rounded break-words">
            {formula}
          </span>
        )}
        <span className={`absolute w-0 h-0 border-solid ${arrowClasses}`} />
      </span>
    </span>
  );
};

