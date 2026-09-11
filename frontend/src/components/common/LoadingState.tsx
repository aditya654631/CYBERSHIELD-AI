import React from 'react';

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading data...',
  className = '',
}) => {
  return (
    <div className={`p-8 flex flex-col items-center justify-center text-center space-y-3 ${className}`}>
      <div className="w-8 h-8 border-2 border-slate-300 border-t-slate-800 rounded-full animate-spin" />
      <p className="text-xs text-slate-500 font-medium">{message}</p>
    </div>
  );
};
