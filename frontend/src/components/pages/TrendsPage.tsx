import React, { useMemo } from 'react';
import {
  TrendingUp,
  BarChart2,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { useBenchmark } from '../../context/BenchmarkContext';
import { FilterBar } from '../common/FilterBar';

export const TrendsPage: React.FC = () => {
  const { filteredRecords, isDark } = useBenchmark();

  // 1. Trend by Context Length
  const contextTrend = useMemo(() => {
    const buckets = Array.from(new Set(filteredRecords.map(r => r.context_tokens_binned))).sort((a, b) => a - b);

    return buckets.map((tokens) => {
      const rows = filteredRecords.filter(r => r.context_tokens_binned === tokens);
      const total = rows.length;
      const lexical = total > 0 ? (rows.filter(r => r.lexical_match).length / total) * 100 : 0;
      const semantic = total > 0 ? (rows.filter(r => r.semantic_correct).length / total) * 100 : 0;
      const harness = total > 0 ? (rows.filter(r => r.success).length / total) * 100 : 0;

      return {
        context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
        tokens,
        'Lexical match': Number(lexical.toFixed(1)),
        'Semantic/logical correct': Number(semantic.toFixed(1)),
        'Harness Reported': Number(harness.toFixed(1)),
        total,
      };
    });
  }, [filteredRecords]);

  // 2. Trend by Depth
  const depthTrend = useMemo(() => {
    const depths = Array.from(new Set(filteredRecords.map(r => r.depth_pct))).sort((a, b) => a - b);

    return depths.map((d) => {
      const rows = filteredRecords.filter(r => r.depth_pct === d);
      const total = rows.length;
      const lexical = total > 0 ? (rows.filter(r => r.lexical_match).length / total) * 100 : 0;
      const semantic = total > 0 ? (rows.filter(r => r.semantic_correct).length / total) * 100 : 0;
      const harness = total > 0 ? (rows.filter(r => r.success).length / total) * 100 : 0;

      const label = d === 0 ? '0%' : d === 50 ? '50%' : d === 100 ? '100%' : `${d}%`;

      return {
        depth: label,
        depth_pct: d,
        'Lexical match': Number(lexical.toFixed(1)),
        'Semantic/logical correct': Number(semantic.toFixed(1)),
        'Harness Reported': Number(harness.toFixed(1)),
        total,
      };
    });
  }, [filteredRecords]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Retrieval Curves & Dynamics</h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/20 font-semibold">
              Performance Scaling
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Analyzing accuracy decay across increasing context token length and needle insertion depth.
          </p>
        </div>
      </div>

      <FilterBar />

      {/* Grid of Two Large Flagship Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart 1: Accuracy vs Context Tokens */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Accuracy vs. context length
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-400">Tokens scaling</span>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            Comparing how Lexical containment vs true Semantic correctness scales as context grows.
          </p>

          <div className="h-80 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={contextTrend} margin={{ top: 10, right: 25, left: -10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
                <XAxis
                  dataKey="context"
                  stroke={isDark ? '#94a3b8' : '#64748b'}
                  tick={{ fontSize: 12, fill: isDark ? '#94a3b8' : '#64748b' }}
                  label={{ value: 'Context length (tokens)', position: 'insideBottom', offset: -5, fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                />
                <YAxis
                  stroke={isDark ? '#94a3b8' : '#64748b'}
                  domain={[0, 105]}
                  tickFormatter={(v) => `${v}%`}
                  tick={{ fontSize: 12, fill: isDark ? '#94a3b8' : '#64748b' }}
                  label={{ value: 'Accuracy', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDark ? '#090d16' : '#ffffff',
                    borderColor: isDark ? '#334155' : '#cbd5e1',
                    color: isDark ? '#ffffff' : '#0f172a',
                    borderRadius: '0.75rem',
                    fontSize: '12px',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  }}
                  formatter={(value: any) => [`${value}%`]}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '15px' }} />
                <Line
                  type="monotone"
                  dataKey="Lexical match"
                  stroke="#0284c7"
                  strokeWidth={3}
                  dot={{ r: 5, fill: '#0284c7' }}
                  activeDot={{ r: 7 }}
                />
                <Line
                  type="monotone"
                  dataKey="Semantic/logical correct"
                  stroke="#10b981"
                  strokeWidth={3}
                  dot={{ r: 5, fill: '#10b981' }}
                  activeDot={{ r: 7 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Accuracy vs Depth */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <BarChart2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Accuracy vs. needle depth
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-400">Positional bias</span>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            Measures "Lost in the Middle" syndrome vs Top (0%) and Bottom (100%) document positions.
          </p>

          <div className="h-80 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={depthTrend} margin={{ top: 10, right: 25, left: -10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
                <XAxis
                  dataKey="depth"
                  stroke={isDark ? '#94a3b8' : '#64748b'}
                  tick={{ fontSize: 12, fill: isDark ? '#94a3b8' : '#64748b' }}
                  label={{ value: 'Needle depth (%)', position: 'insideBottom', offset: -5, fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                />
                <YAxis
                  stroke={isDark ? '#94a3b8' : '#64748b'}
                  domain={[0, 105]}
                  tickFormatter={(v) => `${v}%`}
                  tick={{ fontSize: 12, fill: isDark ? '#94a3b8' : '#64748b' }}
                  label={{ value: 'Accuracy', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDark ? '#090d16' : '#ffffff',
                    borderColor: isDark ? '#334155' : '#cbd5e1',
                    color: isDark ? '#ffffff' : '#0f172a',
                    borderRadius: '0.75rem',
                    fontSize: '12px',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  }}
                  formatter={(value: any) => [`${value}%`]}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '15px' }} />
                <Bar dataKey="Lexical match" fill="#0284c7" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Semantic/logical correct" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
