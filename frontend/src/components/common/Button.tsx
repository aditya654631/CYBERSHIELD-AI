import React from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: React.ReactNode;
  loading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  loading = false,
  className = '',
  disabled,
  ...props
}) => {
  const baseClasses = 'inline-flex items-center justify-center font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed rounded-md select-none';

  const sizeClasses: Record<ButtonSize, string> = {
    sm: 'px-2.5 py-1.5 text-xs gap-1.5',
    md: 'px-3.5 py-2 text-sm gap-2',
    lg: 'px-4 py-2.5 text-base gap-2.5',
  };

  const variantClasses: Record<ButtonVariant, string> = {
    primary: 'bg-[#468189] text-white hover:bg-[#386970] focus:ring-[#468189] border border-[#468189] shadow-sm',
    secondary: 'bg-white text-slate-700 hover:bg-[#F0F6F6] hover:text-[#031926] border border-[#DCE5F0] focus:ring-[#468189] shadow-xs',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-600 border border-red-600 shadow-sm',
    outline: 'bg-transparent text-slate-700 hover:bg-[#F0F6F6] hover:text-[#031926] border border-[#DCE5F0] focus:ring-[#468189]',
    ghost: 'bg-transparent text-slate-600 hover:bg-[#F0F6F6] hover:text-[#031926] focus:ring-[#468189]',
  };

  return (
    <button
      disabled={disabled || loading}
      className={`${baseClasses} ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {loading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin shrink-0" />
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  );
};
