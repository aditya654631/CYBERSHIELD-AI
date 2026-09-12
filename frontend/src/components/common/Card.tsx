import React from 'react';

interface CardProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({
  children,
  title,
  subtitle,
  action,
  icon,
  className = '',
  padding = 'md',
}) => {
  const paddingMap = {
    none: '',
    sm: 'p-3 sm:p-4',
    md: 'p-4 sm:p-5',
    lg: 'p-4 sm:p-6',
  };

  return (
    <div className={`bg-white border border-[#DCE5F0] rounded-lg shadow-xs min-w-0 ${className}`}>
      {(title || action || icon) && (
        <div className="px-4 sm:px-5 py-3 sm:py-4 border-b border-[#DCE5F0] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center space-x-2.5 min-w-0">
            {icon && <span className="text-blue-600 shrink-0">{icon}</span>}
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-[#173A63] truncate">{title}</h3>
              {subtitle && <p className="text-xs text-slate-500 truncate mt-0.5">{subtitle}</p>}
            </div>
          </div>
          {action && <div className="shrink-0 sm:ml-4">{action}</div>}
        </div>
      )}
      <div className={paddingMap[padding]}>{children}</div>
    </div>
  );
};
