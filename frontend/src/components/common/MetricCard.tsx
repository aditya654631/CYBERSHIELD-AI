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
    default: 'text-[#031926]',
    critical: 'text-red-700',
    warning: 'text-amber-700',
    success: 'text-emerald-700',
    info: 'text-[#468189]',
  };

  const iconBgStyles = {
    default: 'bg-[#F0F6F6] text-[#468189]',
    critical: 'bg-red-50 text-red-600',
    warning: 'bg-amber-50 text-amber-600',
    success: 'bg-emerald-50 text-emerald-600',
    info: 'bg-[#F0F6F6] text-[#468189]',
  };

  return (
    <div className={`bg-white border border-[#DCE5F0] rounded-lg p-3 sm:p-4 shadow-xs hover:border-[#9DBEBB] transition-colors min-w-0 ${className}`}>
      <div className="flex items-center justify-between mb-1.5 sm:mb-2 gap-1">
        <span className="text-[11px] sm:text-xs font-medium text-slate-500 uppercase tracking-wider truncate">{label}</span>
        {icon && (
          <div className={`w-7 h-7 sm:w-8 sm:h-8 rounded-md flex items-center justify-center shrink-0 ${iconBgStyles[variant]}`}>
            {icon}
          </div>
        )}
      </div>
      <div className={`text-xl sm:text-2xl font-bold tracking-tight truncate ${variantStyles[variant]}`}>
        {value}
      </div>
      {(subtitle || trend) && (
        <div className="mt-1 flex items-center gap-1.5 text-[11px] sm:text-xs text-slate-500 truncate">
          {trend && (
            <span className={trend.positive ? 'text-green-600 font-medium shrink-0' : 'text-red-600 font-medium shrink-0'}>
              {trend.text}
            </span>
          )}
          {subtitle && <span className="truncate">{subtitle}</span>}
        </div>
      )}
    </div>
  );
};
