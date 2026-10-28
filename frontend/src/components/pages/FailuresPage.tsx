import React, { useState, useMemo } from 'react';
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Copy,
  Check,
  Layers,
} from 'lucide-react';
import {
  ResponsiveContainer,
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
import { CATEGORY_ORDER, CATEGORY_COLORS, CATEGORY_BG_CLASSES } from '../../utils/taxonomy';

export const FailuresPage: React.FC = () => {
  const { filteredRecords, isDark } = useBenchmark();
  const [copied, setCopied] = useState<string | null>(null);

  // Failure cases: everything that isn't Clean Match
  const failureRows = useMemo(() => {
    return filteredRecords.filter(r => r.category !== 'Exact / Clean Match');
  }, [filteredRecords]);

  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const activeCase = failureRows[currentIndex] || failureRows[0];

  // Response Category Breakdown horizontal bar data (matching Streamlit Tab 2)
  const catCountsData = useMemo(() => {
    return CATEGORY_ORDER.map((category) => ({
      category: category.replace('Match', '').replace('Correct', '').trim() || category,
      fullCategory: category,
      count: filteredRecords.filter(r => r.category === category).length,
      fill: CATEGORY_COLORS[category],
    }));
  }, [filteredRecords]);

  // Stacked breakdown data by context length
  const stackedData = useMemo(() => {
    const buckets = Array.from(new Set(filteredRecords.map(r => r.context_tokens_binned))).sort((a, b) => a - b);

    return buckets.map((tokens) => {
      const rows = filteredRecords.filter(r => r.context_tokens_binned === tokens);
      const item: Record<string, any> = {
        context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
      };

      for (const cat of CATEGORY_ORDER) {
        item[cat] = rows.filter(r => r.category === cat).length;
      }

      return item;
    });
  }, [filteredRecords]);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Failure & Repudiation Inspector</h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-500/10 text-rose-800 dark:text-rose-400 border border-rose-300 dark:border-rose-500/20 font-semibold">
              Diagnostic Audit
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Isolating why and where models talk themselves out of retrieved answers or hallucinate from context.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-slate-500 dark:text-slate-400">Total Imperfect Responses:</span>
          <span className="px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-500/20 text-rose-800 dark:text-rose-300 font-bold border border-rose-300 dark:border-rose-500/30">
            {failureRows.length} cases
          </span>
        </div>
      </div>

      <FilterBar />

      {/* Chart 1: Response Category Breakdown (Matching Streamlit Tab 2) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-3">
        <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
          Response category breakdown
        </h3>

        <div className="h-72 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={catCountsData} layout="vertical" margin={{ top: 10, right: 30, left: 40, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
              <XAxis type="number" stroke={isDark ? '#94a3b8' : '#64748b'} />
              <YAxis type="category" dataKey="category" stroke={isDark ? '#94a3b8' : '#64748b'} tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: isDark ? '#090d16' : '#ffffff',
                  borderColor: isDark ? '#334155' : '#cbd5e1',
                  borderRadius: '0.75rem',
                }}
              />
              <Bar dataKey="count" fill="#10b981" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Where does correctness break down? */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
              Where does correctness break down?
            </h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">Stacked Failure Breakdown</span>
        </div>

        <div className="h-80 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stackedData} margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
              <XAxis dataKey="context" stroke={isDark ? '#94a3b8' : '#64748b'} tick={{ fontSize: 12 }} />
              <YAxis stroke={isDark ? '#94a3b8' : '#64748b'} tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: isDark ? '#090d16' : '#ffffff',
                  borderColor: isDark ? '#334155' : '#cbd5e1',
                  color: isDark ? '#ffffff' : '#0f172a',
                  borderRadius: '0.75rem',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              {CATEGORY_ORDER.map((cat) => (
                <Bar
                  key={cat}
                  dataKey={cat}
                  stackId="a"
                  fill={CATEGORY_COLORS[cat]}
                  radius={cat === 'Hallucinated / Wrong' ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Interactive Case Inspector */}
      {failureRows.length === 0 ? (
        <div className="p-8 text-center bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl space-y-2">
          <p className="text-emerald-600 dark:text-emerald-400 font-bold text-base">Zero Failures in Current Filter! 🎉</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">All responses in this filter achieved Exact / Clean Match.</p>
        </div>
      ) : activeCase ? (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-5">
          {/* Header row with navigation */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center space-x-3">
              <div className="p-2 rounded-xl bg-amber-50 dark:bg-slate-800 border border-amber-200 dark:border-slate-700">
                <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-tight">
                    Inspecting Case #{currentIndex + 1} of {failureRows.length}
                  </h3>
                  <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${CATEGORY_BG_CLASSES[activeCase.category]}`}>
                    {activeCase.category}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Detailed inspection of model prediction vs. ground truth needle
                </p>
              </div>
            </div>

            {/* Stepper buttons */}
            <div className="flex items-center space-x-2">
              <button
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex(prev => Math.max(0, prev - 1))}
                className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 disabled:opacity-40 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors"
                title="Previous failure"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <span className="font-mono text-xs text-slate-500 dark:text-slate-400 px-2 font-bold">
                {currentIndex + 1} / {failureRows.length}
              </span>

              <button
                disabled={currentIndex === failureRows.length - 1}
                onClick={() => setCurrentIndex(prev => Math.min(failureRows.length - 1, prev + 1))}
                className="p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-750 disabled:opacity-40 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors"
                title="Next failure"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Metadata Badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block font-mono">Context Length</span>
              <span className="font-mono font-bold text-slate-900 dark:text-white text-sm">
                {activeCase.context_tokens.toLocaleString()} tokens
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block font-mono">Needle Depth</span>
              <span className="font-mono font-bold text-emerald-700 dark:text-emerald-400 text-sm">
                {activeCase.depth_pct}% ({activeCase.depth_pct === 0 ? 'Top' : activeCase.depth_pct === 50 ? 'Middle' : 'Bottom'})
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block font-mono">Inference Latency</span>
              <span className="font-mono font-bold text-amber-700 dark:text-amber-400 text-sm">
                {activeCase.latency_sec.toFixed(2)} seconds
              </span>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] text-slate-500 dark:text-slate-400 block font-mono">Target Secret Code</span>
              <span className="font-mono font-bold text-blue-700 dark:text-blue-400 text-sm">
                {activeCase.needle_code || 'None'}
              </span>
            </div>
          </div>

          {/* Comparison Panels: Ground Truth vs Model Prediction */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left: Ground Truth Needle */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Ground Truth Needle Fact</span>
                <button
                  onClick={() => copyToClipboard(activeCase.needle, 'needle')}
                  className="text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 flex items-center space-x-1"
                >
                  {copied === 'needle' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied === 'needle' ? 'Copied' : 'Copy'}</span>
                </button>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 font-mono min-h-[90px] leading-relaxed">
                {activeCase.needle}
              </div>
            </div>

            {/* Right: Model Prediction */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Model's Actual Generation</span>
                <button
                  onClick={() => copyToClipboard(activeCase.predicted, 'predicted')}
                  className="text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 flex items-center space-x-1"
                >
                  {copied === 'predicted' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied === 'predicted' ? 'Copied' : 'Copy'}</span>
                </button>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 font-mono min-h-[90px] leading-relaxed overflow-y-auto max-h-48">
                {activeCase.predicted}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
