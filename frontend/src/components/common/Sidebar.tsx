import React from 'react';
import {
  LayoutDashboard,
  Grid3X3,
  TrendingUp,
  AlertTriangle,
  Scale,
  Clock,
  Database,
  BrainCircuit,
  ChevronRight,
  Terminal,
  Activity,
} from 'lucide-react';
import { PageRoute } from '../../types';
import { useBenchmark } from '../../context/BenchmarkContext';

interface NavItem {
  id: PageRoute;
  label: string;
  sublabel: string;
  icon: React.ElementType;
  badge?: string;
  badgeColor?: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: 'dashboard',
    label: 'Overview & Classic',
    sublabel: 'Full Dashboard & Heatmap',
    icon: LayoutDashboard,
  },
  {
    id: 'heatmaps',
    label: '2D NIAH Heatmap',
    sublabel: 'Context × Depth Matrix',
    icon: Grid3X3,
    badge: 'Flagship',
    badgeColor: 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-500/20 dark:text-emerald-400 dark:border-emerald-500/30',
  },
  {
    id: 'trends',
    label: 'Retrieval Curves',
    sublabel: 'Context & Depth Dynamics',
    icon: TrendingUp,
  },
  {
    id: 'failures',
    label: 'Failure Inspector',
    sublabel: 'Repudiation & Denial Audit',
    icon: AlertTriangle,
    badge: 'Audit',
    badgeColor: 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-500/20 dark:text-amber-400 dark:border-amber-500/30',
  },
  {
    id: 'comparison',
    label: 'Model Compare Lab',
    sublabel: 'Head-to-Head & Delta Matrix',
    icon: Scale,
    badge: 'Compare',
    badgeColor: 'bg-sky-100 text-sky-800 border-sky-300 dark:bg-sky-500/20 dark:text-sky-400 dark:border-sky-500/30',
  },
  {
    id: 'latency',
    label: 'Latency & Compute',
    sublabel: 'TTFT & Token Overhead',
    icon: Clock,
  },
  {
    id: 'data',
    label: 'Raw Data Explorer',
    sublabel: 'Search, Filter & Export',
    icon: Database,
  },
  {
    id: 'judge',
    label: 'AI Judge Studio',
    sublabel: 'LLM Agreement & Guardrails',
    icon: BrainCircuit,
    badge: 'AI',
    badgeColor: 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-500/20 dark:text-purple-400 dark:border-purple-500/30',
  },
];

export const Sidebar: React.FC = () => {
  const { activeRoute, setActiveRoute, filteredRecords, records } = useBenchmark();

  return (
    <aside className="w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col shrink-0 min-h-screen select-none transition-colors duration-200">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800/80 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center shadow-md shadow-emerald-500/10">
            <Terminal className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-bold text-base text-slate-900 dark:text-white tracking-tight">ProbeBench</span>
              <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/30">
                v2.0
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">LLM Diagnostic Lab</p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 py-4 px-3 space-y-1.5 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 font-mono">
          Diagnostic Views
        </div>

        {NAV_ITEMS.map(item => {
          const Icon = item.icon;
          const isActive = activeRoute === item.id;

          return (
            <button
              key={item.id}
              onClick={() => setActiveRoute(item.id)}
              className={`w-full group text-left px-3 py-2.5 rounded-xl text-xs transition-all duration-200 flex items-center justify-between relative ${
                isActive
                  ? 'bg-emerald-50 dark:bg-slate-800/90 text-emerald-950 dark:text-white shadow-sm border border-emerald-200 dark:border-slate-700/80 font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100/70 dark:hover:bg-slate-800/40'
              }`}
            >
              <div className="flex items-center space-x-3 min-w-0">
                <div
                  className={`p-1.5 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-emerald-600 text-white dark:bg-emerald-500/20 dark:text-emerald-400'
                      : 'text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300 group-hover:bg-slate-200/60 dark:group-hover:bg-slate-800'
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                </div>
                <div className="truncate">
                  <div className="font-medium truncate">{item.label}</div>
                  <div className="text-[10px] text-slate-400 dark:text-slate-400 truncate font-normal">
                    {item.sublabel}
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-1 shrink-0 ml-1">
                {item.badge && (
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                      item.badgeColor || 'bg-slate-100 text-slate-600 border-slate-300 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
                {isActive && <ChevronRight className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />}
              </div>

              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-emerald-600 dark:bg-emerald-500 rounded-r-full" />
              )}
            </button>
          );
        })}
      </div>

      {/* Active Run Status Widget */}
      <div className="p-3 border-t border-slate-200 dark:border-slate-800/80 bg-slate-50/60 dark:bg-slate-900/60">
        <div className="p-3 rounded-xl bg-white dark:bg-slate-850/80 border border-slate-200 dark:border-slate-800 text-xs space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-slate-700 dark:text-slate-300">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-mono text-[11px] font-medium">Live Workspace</span>
            </div>
            <Activity className="w-3.5 h-3.5 text-slate-400" />
          </div>

          <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-100 dark:border-slate-800 text-[11px]">
            <div>
              <span className="text-slate-400 block text-[10px]">Loaded</span>
              <span className="font-mono font-semibold text-slate-800 dark:text-white">{records.length} cases</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px]">Filtered</span>
              <span className="font-mono font-semibold text-emerald-600 dark:text-sky-400">
                {filteredRecords.length} cases
              </span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};
