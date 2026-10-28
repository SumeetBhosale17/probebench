import React from 'react';
import { ArrowUpRight, ArrowDownRight, Info } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  delta?: string;
  deltaType?: 'positive' | 'negative' | 'neutral' | 'inverse';
  icon: React.ElementType;
  iconColor?: string;
  tooltip?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  delta,
  deltaType = 'neutral',
  icon: Icon,
  iconColor = 'text-emerald-700 bg-emerald-100 border-emerald-300 dark:text-emerald-400 dark:bg-emerald-500/10 dark:border-emerald-500/20',
  tooltip,
}) => {
  return (
    <div className="bg-white dark:bg-slate-900/90 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-4 shadow-sm hover:border-slate-300 dark:hover:border-slate-700/80 transition-all duration-200 relative group overflow-hidden">
      {/* Top row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-1.5 text-slate-500 dark:text-slate-400 text-xs font-medium">
          <span>{title}</span>
          {tooltip && (
            <div className="relative group/tip cursor-help">
              <Info className="w-3.5 h-3.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors" />
              <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 hidden group-hover/tip:block w-48 p-2 rounded-xl bg-slate-900 text-white dark:bg-slate-950 border border-slate-700 text-[11px] shadow-xl z-50 pointer-events-none">
                {tooltip}
              </div>
            </div>
          )}
        </div>

        <div className={`w-8 h-8 rounded-xl flex items-center justify-center border ${iconColor}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      {/* Main value */}
      <div className="flex items-baseline space-x-2">
        <span className="font-mono text-2xl font-bold text-slate-900 dark:text-white tracking-tight">{value}</span>

        {delta && (
          <span
            className={`text-[11px] font-mono font-semibold px-1.5 py-0.5 rounded flex items-center space-x-0.5 ${
              deltaType === 'positive'
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/20'
                : deltaType === 'inverse' || deltaType === 'negative'
                ? 'bg-rose-100 text-rose-800 dark:bg-rose-500/10 dark:text-rose-400 border border-rose-300 dark:border-rose-500/20'
                : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
            }`}
          >
            {deltaType === 'positive' ? (
              <ArrowUpRight className="w-3 h-3" />
            ) : deltaType === 'negative' || deltaType === 'inverse' ? (
              <ArrowDownRight className="w-3 h-3" />
            ) : null}
            <span>{delta}</span>
          </span>
        )}
      </div>

      {subtitle && <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 font-medium">{subtitle}</p>}
    </div>
  );
};
