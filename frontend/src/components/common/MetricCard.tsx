import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: {
    text: string;
    positive?: boolean;
  };
  variant?: 'default' | 'critical' | 'warning' | 'success' | 'info';
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtitle,
  icon,
  trend,
  variant = 'default',
  className = '',
}) => {
  const variantStyles = {
    default: 'text-slate-900',
    critical: 'text-red-700',
    warning: 'text-amber-700',
    success: 'text-green-700',
    info: 'text-blue-700',
  };

  const iconBgStyles = {
    default: 'bg-blue-50 text-blue-600',
    critical: 'bg-red-50 text-red-600',
    warning: 'bg-amber-50 text-amber-600',
    success: 'bg-green-50 text-green-600',
    info: 'bg-blue-50 text-blue-600',
  };

  return (
    <div className={`bg-white border border-[#DCE5F0] rounded-lg p-4 shadow-xs hover:border-blue-200 transition-colors ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</span>
        {icon && (
          <div className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 ${iconBgStyles[variant]}`}>
            {icon}
          </div>
        )}
      </div>
      <div className={`text-2xl font-bold tracking-tight ${variantStyles[variant]}`}>
        {value}
      </div>
      {(subtitle || trend) && (
        <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
          {trend && (
            <span className={trend.positive ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
              {trend.text}
            </span>
          )}
          {subtitle && <span>{subtitle}</span>}
        </div>
      )}
    </div>
  );
};
