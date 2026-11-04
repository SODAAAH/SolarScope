import React, { useState } from 'react';
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

  return (
    <span
      className={`group relative inline-flex items-center gap-1 ${underline ? 'cursor-help border-b border-dotted border-slate-400 dark:border-slate-500' : ''} ${className}`}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onFocus={() => setIsOpen(true)}
      onBlur={() => setIsOpen(false)}
      tabIndex={0}
      role="tooltip"
      aria-label={typeof content === 'string' ? content : title}
    >
      {children}
      {showIcon && (
        <span className="inline-flex text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
          <HelpCircle className="w-3 h-3" />
        </span>
      )}
      <span
        className={`absolute ${positionClasses} z-50 pointer-events-none transition-all duration-150 ease-out ${
          isOpen ? 'opacity-100 scale-100 visible' : 'opacity-0 scale-95 invisible'
        } w-64 max-w-xs p-3 rounded-xl bg-slate-900 text-slate-100 dark:bg-slate-800 dark:text-slate-100 text-xs shadow-2xl border border-slate-700/80 backdrop-blur-xs font-normal normal-case tracking-normal leading-relaxed text-left select-none`}
      >
        {(title || provenance) && (
          <span className="flex items-center justify-between gap-2 mb-1.5 pb-1 border-b border-slate-700/60">
            {title && <span className="font-semibold text-white text-[12px]">{title}</span>}
            {provenance && (
              <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-800 dark:bg-slate-700 text-slate-300 font-medium">
                {provenance}
              </span>
            )}
          </span>
        )}
        <span className="block text-slate-300 text-[11px] leading-relaxed">
          {content}
        </span>
        {formula && (
          <span className="block mt-2 pt-1.5 border-t border-slate-800 font-mono text-[10px] text-amber-300/90 bg-slate-950/40 px-1.5 py-0.5 rounded">
            {formula}
          </span>
        )}
        <span className={`absolute w-0 h-0 border-solid ${arrowClasses}`} />
      </span>
    </span>
  );
};
