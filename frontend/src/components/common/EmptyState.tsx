import React from 'react';
import { FolderOpen } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No records found',
  description = 'There is no data matching the requested criteria.',
  icon,
  action,
  className = '',
}) => {
  return (
    <div className={`p-8 text-center flex flex-col items-center justify-center space-y-3 ${className}`}>
      <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
        {icon || <FolderOpen className="w-5 h-5" />}
      </div>
      <div className="space-y-1">
        <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">{description}</p>
      </div>
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
};
