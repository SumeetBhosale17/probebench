import React, { useMemo } from 'react';
import {
  Clock,
  Activity,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  ReferenceLine,
  ErrorBar,
  Legend,
} from 'recharts';
import { useBenchmark } from '../../context/BenchmarkContext';
import { FilterBar } from '../common/FilterBar';
import { CATEGORY_ORDER, CATEGORY_COLORS, CATEGORY_BG_CLASSES } from '../../utils/taxonomy';
import { TaxonomyCategory } from '../../types';

interface CustomScatterTooltipProps {
  active?: boolean;
  payload?: any[];
  isDark?: boolean;
  outlierThreshold?: number;
}

const CustomScatterTooltip: React.FC<CustomScatterTooltipProps> = ({
  active,
  payload,
  isDark,
  outlierThreshold = 0,
}) => {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0].payload;
  const isOutlier = outlierThreshold > 0 && data.latency >= outlierThreshold;

  return (
    <div
      className={`p-3 rounded-xl shadow-xl border text-xs font-sans space-y-2 max-w-xs ${
        isDark ? 'bg-slate-900 border-slate-700 text-slate-100' : 'bg-white border-slate-200 text-slate-900'
      }`}
    >
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-1.5">
        <span className="font-mono font-bold">{data.context.toLocaleString()} tokens</span>
        <span className="font-mono font-extrabold text-amber-600 dark:text-amber-400 text-sm">
          {data.latency.toFixed(2)}s
        </span>
      </div>

      <div className="flex items-center justify-between text-[11px]">
        <span className="text-slate-500 dark:text-slate-400">Response Category:</span>
        <span
          className="px-2 py-0.5 rounded font-mono text-[10px] font-bold border"
          style={{
            backgroundColor: `${CATEGORY_COLORS[data.category as TaxonomyCategory]}20`,
            color: CATEGORY_COLORS[data.category as TaxonomyCategory],
            borderColor: `${CATEGORY_COLORS[data.category as TaxonomyCategory]}40`,
          }}
        >
          {data.category}
        </span>
      </div>

      <div className="flex items-center justify-between text-[11px]">
        <span className="text-slate-500 dark:text-slate-400">Needle Depth:</span>
        <span className="font-mono font-bold">{data.depth}%</span>
      </div>

      {data.code && data.code !== 'N/A' && (
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-slate-500 dark:text-slate-400">Target Code:</span>
          <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">{data.code}</span>
        </div>
      )}

      {isOutlier && (
        <div className="mt-1 pt-1.5 border-t border-rose-300 dark:border-rose-800 text-rose-600 dark:text-rose-400 font-bold flex items-center space-x-1.5 text-[11px] animate-pulse">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>Statistical Latency Outlier (above μ + 2σ)</span>
        </div>
      )}
    </div>
  );
};

export const LatencyPage: React.FC = () => {
  const { filteredRecords, isDark } = useBenchmark();

  // Unique sorted context buckets
  const buckets = useMemo(() => {
    return Array.from(new Set(filteredRecords.map(r => r.context_tokens_binned))).sort((a, b) => a - b);
  }, [filteredRecords]);

  // Overall latency statistics & outlier cutoff computation
  const latencyStatsOverall = useMemo(() => {
    const valid = filteredRecords.filter(r => r.latency_sec > 0).map(r => r.latency_sec);
    if (valid.length === 0) {
      return { mean: 0, std: 0, outlierThreshold: 0, outliers: [], count: 0, min: 0, max: 0 };
    }
    const mean = valid.reduce((a, b) => a + b, 0) / valid.length;
    const variance = valid.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / valid.length;
    const std = Math.sqrt(variance);
    const outlierThreshold = Number((mean + 2 * std).toFixed(2));
    const outliers = filteredRecords
      .filter(r => r.latency_sec > outlierThreshold)
      .sort((a, b) => b.latency_sec - a.latency_sec);

    return {
      mean: Number(mean.toFixed(2)),
      std: Number(std.toFixed(2)),
      outlierThreshold,
      outliers,
      count: valid.length,
      max: Number(Math.max(...valid).toFixed(2)),
      min: Number(Math.min(...valid).toFixed(2)),
    };
  }, [filteredRecords]);

  // Group scatter data by category for multi-colored scatter plot
  const scatterByCategory = useMemo(() => {
    const map: Record<string, any[]> = {};
    for (const cat of CATEGORY_ORDER) {
      map[cat] = [];
    }
    for (const r of filteredRecords) {
      if (r.latency_sec > 0) {
        if (!map[r.category]) map[r.category] = [];
        map[r.category].push({
          context: r.context_tokens,
          latency: Number(r.latency_sec.toFixed(2)),
          category: r.category,
          depth: r.depth_pct,
          needle: r.needle,
          code: r.needle_code || 'N/A',
        });
      }
    }
    return map;
  }, [filteredRecords]);

  // Grouped statistics by context bucket with std for ErrorBar
  const latencyStats = useMemo(() => {
    return buckets.map((tokens) => {
      const rows = filteredRecords.filter(r => r.context_tokens_binned === tokens);
      const values = rows.map(r => r.latency_sec).filter(v => v > 0);

      if (values.length === 0) {
        return {
          context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
          mean: 0,
          std: 0,
          min: 0,
          max: 0,
          count: 0,
        };
      }

      const mean = values.reduce((a, b) => a + b, 0) / values.length;
      const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length;
      const std = Math.sqrt(variance);
      const min = Math.min(...values);
      const max = Math.max(...values);

      return {
        context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
        mean: Number(mean.toFixed(2)),
        std: Number(std.toFixed(2)),
        min: Number(min.toFixed(2)),
        max: Number(max.toFixed(2)),
        count: values.length,
      };
    });
  }, [buckets, filteredRecords]);

  // Quartile summary per context bucket
  const quartileStats = useMemo(() => {
    return buckets.map((tokens) => {
      const rows = filteredRecords.filter(r => r.context_tokens_binned === tokens && r.latency_sec > 0);
      const vals = rows.map(r => r.latency_sec).sort((a, b) => a - b);
      if (vals.length === 0) {
        return {
          context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
          count: 0,
          min: 0,
          q1: 0,
          median: 0,
          mean: 0,
          q3: 0,
          max: 0,
          iqr: 0,
          outliersCount: 0,
        };
      }
      const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
      const min = vals[0];
      const max = vals[vals.length - 1];
      const median = vals[Math.floor(vals.length * 0.5)];
      const q1 = vals[Math.floor(vals.length * 0.25)];
      const q3 = vals[Math.floor(vals.length * 0.75)];
      const iqr = q3 - q1;
      const upperFence = q3 + 1.5 * iqr;
      const outliersCount = vals.filter(v => v > upperFence).length;

      return {
        context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
        count: vals.length,
        min: Number(min.toFixed(2)),
        q1: Number(q1.toFixed(2)),
        median: Number(median.toFixed(2)),
        mean: Number(mean.toFixed(2)),
        q3: Number(q3.toFixed(2)),
        max: Number(max.toFixed(2)),
        iqr: Number(iqr.toFixed(2)),
        outliersCount,
      };
    });
  }, [buckets, filteredRecords]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Latency & Systems Performance</h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-500/10 text-amber-800 dark:text-amber-400 border border-amber-300 dark:border-amber-500/20 font-semibold">
              Latency & Outliers
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Wall-clock latency scaling as KV-cache and attention token sequence lengthens. Statistical outlier detection at μ + 2σ.
          </p>
        </div>

        {latencyStatsOverall.outlierThreshold > 0 && (
          <div className="flex items-center space-x-2 text-xs font-mono bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-400 border border-rose-200 dark:border-rose-900 px-3 py-1.5 rounded-xl">
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
            <span>Outlier Cutoff: <strong>{latencyStatsOverall.outlierThreshold}s</strong> (μ + 2σ)</span>
          </div>
        )}
      </div>

      <FilterBar />

      {/* Grid: Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Scatter Plot: Latency vs Context Tokens (Colored by Category) */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Latency vs. context length
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">Individual test runs</span>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            Scatter distribution of wall-clock seconds across all context sizes, colored by correctness category.
          </p>

          <div className="h-80 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 15, right: 20, left: -10, bottom: 15 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
                <XAxis
                  type="number"
                  dataKey="context"
                  name="Context length (tokens)"
                  stroke={isDark ? '#94a3b8' : '#64748b'}
                  tick={{ fontSize: 12, fill: isDark ? '#94a3b8' : '#64748b' }}
                  tickFormatter={(v) => Number(v).toLocaleString()}
                  domain={['dataMin - 1000', 'dataMax + 1000']}
                  label={{ value: 'Context length (tokens)', position: 'insideBottom', offset: -8, fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                />
                <YAxis
                  type="number"
                  dataKey="latency"
                  name="Latency (s)"
                  unit="s"
                  stroke={isDark ? '#94a3b8' : '#64748b'}
                  tick={{ fontSize: 12, fill: isDark ? '#94a3b8' : '#64748b' }}
                  label={{ value: 'Latency (s)', angle: -90, position: 'insideLeft', offset: 15, fontSize: 11, fill: isDark ? '#94a3b8' : '#64748b' }}
                />
                <Tooltip content={<CustomScatterTooltip isDark={isDark} outlierThreshold={latencyStatsOverall.outlierThreshold} />} />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '15px' }} />

                {/* Outlier Threshold Line at μ + 2σ */}
                {latencyStatsOverall.outlierThreshold > 0 && (
                  <ReferenceLine
                    y={latencyStatsOverall.outlierThreshold}
                    stroke="#f43f5e"
                    strokeDasharray="4 4"
                    strokeWidth={1.5}
                    label={{
                      value: `Outlier Cutoff (${latencyStatsOverall.outlierThreshold}s)`,
                      position: 'insideTopRight',
                      fill: '#f43f5e',
                      fontSize: 11,
                    }}
                  />
                )}

                {CATEGORY_ORDER.map((cat) => (
                  <Scatter
                    key={cat}
                    name={cat}
                    data={scatterByCategory[cat]}
                    fill={CATEGORY_COLORS[cat]}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bar Chart: Average Latency by Context Bucket with Error Bars */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Average latency by context bucket
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">Bucket means ± 1σ</span>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            Average time taken per prompt generation bucketed by context tokens with error bars (±1σ std dev).
          </p>

          <div className="h-80 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={latencyStats} margin={{ top: 15, right: 20, left: -10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
                <XAxis dataKey="context" stroke={isDark ? '#94a3b8' : '#64748b'} tick={{ fontSize: 12 }} />
                <YAxis stroke={isDark ? '#94a3b8' : '#64748b'} unit="s" tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDark ? '#090d16' : '#ffffff',
                    borderColor: isDark ? '#334155' : '#cbd5e1',
                    color: isDark ? '#ffffff' : '#0f172a',
                    borderRadius: '0.75rem',
                  }}
                  formatter={(val: any, name: any) => [name === 'std' ? `±${val}s` : `${val}s`, name === 'mean' ? 'Mean Latency' : name]}
                />
                <Bar dataKey="mean" fill="#f59e0b" radius={[4, 4, 0, 0]}>
                  <ErrorBar dataKey="std" width={6} strokeWidth={2} stroke={isDark ? '#fcd34d' : '#b45309'} direction="y" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Summary Stats Table (Matching Streamlit) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-3">
        <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">Latency Statistics Summary</h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 text-[11px] border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="py-2.5 px-3">context_tokens_binned</th>
                <th className="py-2.5 px-3">mean</th>
                <th className="py-2.5 px-3">std</th>
                <th className="py-2.5 px-3">min</th>
                <th className="py-2.5 px-3">max</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {latencyStats.map((stat) => (
                <tr key={stat.context} className="hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                  <td className="py-2.5 px-3 text-emerald-700 dark:text-emerald-400 font-bold">{stat.context} tokens</td>
                  <td className="py-2.5 px-3">{stat.mean.toFixed(2)}</td>
                  <td className="py-2.5 px-3">{stat.std.toFixed(2)}</td>
                  <td className="py-2.5 px-3">{stat.min.toFixed(2)}</td>
                  <td className="py-2.5 px-3">{stat.max.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* DEDICATED LATENCY OUTLIERS & SPREAD DISTRIBUTION SECTION */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-500/20">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Latency Outliers & Spread Distribution Analysis
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Explicit detection of timing spikes, tail latency bottlenecks, and statistical outliers
              </p>
            </div>
          </div>

          <span className="text-xs font-mono px-3 py-1 rounded-full bg-rose-100 dark:bg-rose-500/15 text-rose-800 dark:text-rose-300 font-bold border border-rose-200 dark:border-rose-500/30">
            {latencyStatsOverall.outliers.length} Outlier(s) Detected
          </span>
        </div>

        {/* 4 KPI cards */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 block uppercase">
              Mean Latency (μ)
            </span>
            <span className="text-xl font-bold font-mono text-slate-900 dark:text-white">
              {latencyStatsOverall.mean.toFixed(2)}s
            </span>
            <span className="text-[10px] text-slate-400 block font-mono mt-0.5">σ = ±{latencyStatsOverall.std.toFixed(2)}s</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 block uppercase">
              Outlier Cutoff (μ + 2σ)
            </span>
            <span className="text-xl font-bold font-mono text-rose-600 dark:text-rose-400">
              {latencyStatsOverall.outlierThreshold.toFixed(2)}s
            </span>
            <span className="text-[10px] text-slate-400 block font-mono mt-0.5">95.4% confidence bound</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 block uppercase">
              Maximum Latency Spike
            </span>
            <span className="text-xl font-bold font-mono text-amber-600 dark:text-amber-400">
              {latencyStatsOverall.max.toFixed(2)}s
            </span>
            <span className="text-[10px] text-slate-400 block font-mono mt-0.5">Min observed: {latencyStatsOverall.min.toFixed(2)}s</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 block uppercase">
              Outlier Percentage
            </span>
            <span className="text-xl font-bold font-mono text-slate-900 dark:text-white">
              {latencyStatsOverall.count > 0 ? ((latencyStatsOverall.outliers.length / latencyStatsOverall.count) * 100).toFixed(1) : 0}%
            </span>
            <span className="text-[10px] text-slate-400 block font-mono mt-0.5">of {latencyStatsOverall.count} runs</span>
          </div>
        </div>

        {/* Outliers Table */}
        {latencyStatsOverall.outliers.length > 0 ? (
          <div className="space-y-3">
            <h4 className="text-xs font-bold text-slate-900 dark:text-white font-mono uppercase tracking-wider">
              Detected Latency Outlier Runs (Exceeding {latencyStatsOverall.outlierThreshold}s)
            </h4>

            <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
              <table className="w-full text-left text-xs border-collapse font-mono">
                <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-400">
                  <tr>
                    <th className="py-2.5 px-3">Context</th>
                    <th className="py-2.5 px-3">Depth</th>
                    <th className="py-2.5 px-3">Secret Code</th>
                    <th className="py-2.5 px-3 min-w-[200px]">Model Output Snippet</th>
                    <th className="py-2.5 px-3">Category</th>
                    <th className="py-2.5 px-3">Latency</th>
                    <th className="py-2.5 px-3">Deviation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-[11px]">
                  {latencyStatsOverall.outliers.map((row, idx) => {
                    const zScore = latencyStatsOverall.std > 0
                      ? ((row.latency_sec - latencyStatsOverall.mean) / latencyStatsOverall.std).toFixed(1)
                      : '0.0';
                    return (
                      <tr key={idx} className="hover:bg-slate-50 dark:hover:bg-slate-850">
                        <td className="py-2.5 px-3 font-bold text-emerald-700 dark:text-emerald-400">
                          {row.context_tokens.toLocaleString()} tokens
                        </td>
                        <td className="py-2.5 px-3">{row.depth_pct}%</td>
                        <td className="py-2.5 px-3 text-blue-600 dark:text-blue-400 font-bold">
                          {row.needle_code || 'N/A'}
                        </td>
                        <td className="py-2.5 px-3 max-w-xs truncate font-sans text-slate-700 dark:text-slate-300" title={row.predicted}>
                          {row.predicted}
                        </td>
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${CATEGORY_BG_CLASSES[row.category]}`}>
                            {row.category}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-bold text-rose-600 dark:text-rose-400">
                          {row.latency_sec.toFixed(2)}s
                        </td>
                        <td className="py-2.5 px-3 font-bold text-amber-600 dark:text-amber-400">
                          +{zScore}σ
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/40 text-emerald-800 dark:text-emerald-300 text-xs flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            <span>
              No extreme statistical outliers detected in the active filter selection. Latencies conform stably within the 95% confidence interval (<span className="font-mono font-bold">μ + 2σ = {latencyStatsOverall.outlierThreshold}s</span>).
            </span>
          </div>
        )}

        {/* Quartile / Box Plot Summary Table & Visual Diagrams */}
        <div className="space-y-4 pt-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <h4 className="text-xs font-bold text-slate-900 dark:text-white font-mono uppercase tracking-wider">
              Latency Box Plot & Quartile Spread Visualization
            </h4>
            <span className="text-[10px] font-mono text-slate-500">
              Box: IQR (Q1 to Q3) | Center: Median | Whiskers: Min to Max | Red Dots: Spikes
            </span>
          </div>

          {/* Visual Box & Whisker Bars */}
          <div className="space-y-3 bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800">
            {quartileStats.map((q) => {
              const globalMax = Math.max(1, latencyStatsOverall.max);
              const minPct = (q.min / globalMax) * 100;
              const q1Pct = (q.q1 / globalMax) * 100;
              const medPct = (q.median / globalMax) * 100;
              const q3Pct = (q.q3 / globalMax) * 100;
              const maxPct = (q.max / globalMax) * 100;
              const upperFence = q.q3 + 1.5 * q.iqr;
              const rawTokens = parseInt(q.context.replace('k', '')) * 1000 || parseInt(q.context);
              const bucketOutliers = filteredRecords.filter(
                r => r.context_tokens_binned === rawTokens && r.latency_sec > upperFence
              );

              return (
                <div key={q.context} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="font-bold text-slate-800 dark:text-slate-200">{q.context} tokens (n={q.count})</span>
                    <div className="flex items-center space-x-3 text-[11px] text-slate-500">
                      <span>Min: <strong className="text-slate-700 dark:text-slate-300">{q.min}s</strong></span>
                      <span>Q1: <strong className="text-slate-700 dark:text-slate-300">{q.q1}s</strong></span>
                      <span>Median: <strong className="text-amber-600 dark:text-amber-400">{q.median}s</strong></span>
                      <span>Q3: <strong className="text-slate-700 dark:text-slate-300">{q.q3}s</strong></span>
                      <span>Max: <strong className="text-rose-600 dark:text-rose-400">{q.max}s</strong></span>
                      {q.outliersCount > 0 && (
                        <span className="text-rose-600 font-bold bg-rose-100 dark:bg-rose-950/60 px-1.5 py-0.5 rounded border border-rose-300 dark:border-rose-800">
                          {q.outliersCount} outlier(s)
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Box & Whisker Track */}
                  <div className="relative h-7 bg-slate-200/60 dark:bg-slate-900 rounded-lg overflow-hidden flex items-center border border-slate-300 dark:border-slate-800">
                    {/* Whisker Line */}
                    <div
                      className="absolute h-0.5 bg-slate-400 dark:bg-slate-600"
                      style={{
                        left: `${Math.max(0, minPct)}%`,
                        width: `${Math.max(1, maxPct - minPct)}%`,
                      }}
                    />
                    {/* Whisker End Caps */}
                    <div
                      className="absolute w-0.5 h-3 bg-slate-500 dark:bg-slate-500"
                      style={{ left: `${minPct}%` }}
                    />
                    <div
                      className="absolute w-0.5 h-3 bg-slate-500 dark:bg-slate-500"
                      style={{ left: `${maxPct}%` }}
                    />
                    {/* Interquartile Box (Q1 to Q3) */}
                    <div
                      className="absolute h-4.5 rounded bg-amber-400/30 dark:bg-amber-500/20 border border-amber-500/60 dark:border-amber-400/40 z-10"
                      style={{
                        left: `${q1Pct}%`,
                        width: `${Math.max(2, q3Pct - q1Pct)}%`,
                      }}
                    />
                    {/* Median Line */}
                    <div
                      className="absolute w-1 h-5 bg-amber-600 dark:bg-amber-400 z-20 rounded-full"
                      style={{ left: `${medPct}%` }}
                      title={`Median: ${q.median}s`}
                    />
                    {/* Outlier Dots */}
                    {bucketOutliers.map((o, idx) => {
                      const oPct = Math.min(99, (o.latency_sec / globalMax) * 100);
                      return (
                        <div
                          key={idx}
                          className="absolute w-2.5 h-2.5 rounded-full bg-rose-600 dark:bg-rose-400 ring-2 ring-white dark:ring-slate-900 z-30 animate-pulse"
                          style={{ left: `${oPct}%` }}
                          title={`Outlier Spike: ${o.latency_sec.toFixed(2)}s (${o.category})`}
                        />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs border-collapse font-mono">
              <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-400">
                <tr>
                  <th className="py-2.5 px-3">Context Bucket</th>
                  <th className="py-2.5 px-3">Count</th>
                  <th className="py-2.5 px-3">Min</th>
                  <th className="py-2.5 px-3">Q1 (25%)</th>
                  <th className="py-2.5 px-3">Median (50%)</th>
                  <th className="py-2.5 px-3">Mean</th>
                  <th className="py-2.5 px-3">Q3 (75%)</th>
                  <th className="py-2.5 px-3">Max</th>
                  <th className="py-2.5 px-3">IQR</th>
                  <th className="py-2.5 px-3">Outliers</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-[11px]">
                {quartileStats.map((q) => (
                  <tr key={q.context} className="hover:bg-slate-50 dark:hover:bg-slate-850">
                    <td className="py-2.5 px-3 font-bold text-emerald-700 dark:text-emerald-400">{q.context} tokens</td>
                    <td className="py-2.5 px-3 text-slate-600 dark:text-slate-400">{q.count}</td>
                    <td className="py-2.5 px-3">{q.min.toFixed(2)}s</td>
                    <td className="py-2.5 px-3">{q.q1.toFixed(2)}s</td>
                    <td className="py-2.5 px-3 font-bold text-slate-900 dark:text-white">{q.median.toFixed(2)}s</td>
                    <td className="py-2.5 px-3 text-amber-600 dark:text-amber-400">{q.mean.toFixed(2)}s</td>
                    <td className="py-2.5 px-3">{q.q3.toFixed(2)}s</td>
                    <td className="py-2.5 px-3 font-bold text-rose-600 dark:text-rose-400">{q.max.toFixed(2)}s</td>
                    <td className="py-2.5 px-3 text-slate-500">{q.iqr.toFixed(2)}s</td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${q.outliersCount > 0 ? 'bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300' : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'}`}>
                        {q.outliersCount}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
