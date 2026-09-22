import React, { useState, useRef, useEffect } from 'react';
import { Info, X } from 'lucide-react';

interface InfoPopoverProps {
  title?: string;
  content: string | React.ReactNode;
  ariaLabel?: string;
  placement?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
  iconClassName?: string;
}

export const InfoPopover: React.FC<InfoPopoverProps> = ({
  title,
  content,
  ariaLabel = 'More information',
  placement = 'top',
  className = '',
  iconClassName = 'w-3.5 h-3.5 text-slate-400 hover:text-blue-600 transition-colors',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [isOpen]);

  // Close on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const getPositionClasses = () => {
    switch (placement) {
      case 'bottom':
        return 'top-full mt-2 left-1/2 -translate-x-1/2';
      case 'left':
        return 'right-full mr-2 top-1/2 -translate-y-1/2';
      case 'right':
        return 'left-full ml-2 top-1/2 -translate-y-1/2';
      case 'top':
      default:
        return 'bottom-full mb-2 left-1/2 -translate-x-1/2';
    }
  };

  return (
    <div className={`relative inline-flex items-center ${className}`} ref={containerRef}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className="inline-flex items-center justify-center p-0.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
        aria-label={title ? `More information about ${title}` : ariaLabel}
        aria-expanded={isOpen}
      >
        <Info className={iconClassName} />
      </button>

      {isOpen && (
        <div
          className={`absolute z-50 w-72 sm:w-80 p-3.5 bg-slate-900 text-white rounded-lg shadow-xl border border-slate-700 text-xs leading-relaxed animate-in fade-in zoom-in-95 duration-150 ${getPositionClasses()}`}
          style={{ maxWidth: 'calc(100vw - 32px)' }}
          role="tooltip"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start justify-between gap-2 mb-1.5">
            {title && <span className="font-semibold text-slate-100 text-[12px]">{title}</span>}
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-slate-400 hover:text-white p-0.5 rounded focus:outline-none ml-auto"
              aria-label="Close information dialog"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="text-slate-300 text-[11px] leading-normal">{content}</div>
        </div>
      )}
    </div>
  );
};
