import React from 'react';
import { format12HourDateTime, formatDateMMDDYYYY } from '../../lib/formatters';

interface MarkdownViewProps {
  content: string;
  className?: string;
}

export const MarkdownView: React.FC<MarkdownViewProps> = ({ content, className = '' }) => {
  if (!content) return null;

  const formatInlineText = (text: string): React.ReactNode[] => {
    const formattedText = text.replace(
      /\b(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}:\d{2}(?::\d{2})?))?\b/g,
      (_match, y, m, d, t) => {
        if (t) {
          return format12HourDateTime(`${y}-${m}-${d} ${t}`);
        }
        return formatDateMMDDYYYY(`${y}-${m}-${d}`);
      }
    );

    const tokenRegex = /(\*\*\*[^*]+?\*\*\*|\*\*[^*]+?\*\*|\*[^*]+?\*|`[^`]+?`)/g;
    const parts = formattedText.split(tokenRegex);

    return parts.map((part, index) => {
      if (!part) return null;

      if (part.startsWith('***') && part.endsWith('***') && part.length > 6) {
        return (
          <strong key={index} className="font-bold italic text-slate-900 dark:text-slate-100">
            {part.slice(3, -3)}
          </strong>
        );
      }

      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return (
          <strong key={index} className="font-semibold text-slate-900 dark:text-slate-100">
            {part.slice(2, -2)}
          </strong>
        );
      }

      if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
        return (
          <em key={index} className="italic text-slate-800 dark:text-slate-200">
            {part.slice(1, -1)}
          </em>
        );
      }

      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
        return (
          <code
            key={index}
            className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[11px] font-mono font-medium text-amber-700 dark:text-amber-400 border border-slate-200 dark:border-slate-700/60"
          >
            {part.slice(1, -1)}
          </code>
        );
      }

      return <span key={index}>{part}</span>;
    });
  };

  const paragraphs = content.split(/\n\n+/);

  return (
    <div className={`space-y-3.5 text-xs text-slate-700 dark:text-slate-300 ${className}`}>
      {paragraphs.map((para, pIdx) => {
        const trimmed = para.trim();
        if (!trimmed) return null;

        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={pIdx} className="text-sm font-bold text-slate-900 dark:text-slate-100 mt-4 mb-1">
              {formatInlineText(trimmed.replace(/^###\s+/, ''))}
            </h4>
          );
        }

        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={pIdx} className="text-base font-bold text-slate-900 dark:text-slate-100 mt-5 mb-1.5">
              {formatInlineText(trimmed.replace(/^##\s+/, ''))}
            </h3>
          );
        }

        if (trimmed.startsWith('# ')) {
          return (
            <h2 key={pIdx} className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-5 mb-2">
              {formatInlineText(trimmed.replace(/^#\s+/, ''))}
            </h2>
          );
        }

        const lines = trimmed.split('\n');
        const isList = lines.every((line) => {
          const l = line.trim();
          return l.startsWith('- ') || l.startsWith('* ') || /^\d+\.\s/.test(l);
        });

        if (isList) {
          return (
            <ul key={pIdx} className="space-y-2 my-2.5 pl-1">
              {lines.map((line, lIdx) => {
                const cleanLine = line.trim().replace(/^[-*]\s+|\d+\.\s+/, '');
                return (
                  <li key={lIdx} className="flex items-start gap-2.5 leading-relaxed">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 dark:bg-amber-400 mt-1.5 shrink-0" />
                    <span className="flex-1">{formatInlineText(cleanLine)}</span>
                  </li>
                );
              })}
            </ul>
          );
        }

        const isCallout =
          trimmed.startsWith('**System Recommendation:**') ||
          trimmed.startsWith('**Key Finding:**') ||
          trimmed.startsWith('**Diagnostic Confidence:**');

        if (isCallout) {
          return (
            <div
              key={pIdx}
              className="p-3.5 rounded-lg bg-amber-500/5 dark:bg-amber-500/10 border border-amber-500/20 text-slate-800 dark:text-slate-200 leading-relaxed font-medium"
            >
              {formatInlineText(trimmed)}
            </div>
          );
        }

        return (
          <p key={pIdx} className="leading-relaxed">
            {formatInlineText(trimmed)}
          </p>
        );
      })}
    </div>
  );
};
