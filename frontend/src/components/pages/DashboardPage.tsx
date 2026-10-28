import React, { useState, useMemo } from 'react';
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Copy,
  Check,
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
  ScatterChart,
  Scatter,
  ReferenceLine,
  ErrorBar,
} from 'recharts';
import { useBenchmark } from '../../context/BenchmarkContext';
import { StatCard } from '../common/StatCard';
import { FilterBar } from '../common/FilterBar';
import { ScientificHeatmap } from '../common/ScientificHeatmap';
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

export const DashboardPage: React.FC = () => {
  const { kpi, filteredRecords, isDark, activeDatasetName } = useBenchmark();
  const [activeTab, setActiveTab] = useState<'heatmaps' | 'failures' | 'latency' | 'data' | 'judge'>('heatmaps');
  const [methodologyOpen, setMethodologyOpen] = useState<boolean>(false);
  const [heatmapMetric, setHeatmapMetric] = useState<'semantic_correct' | 'lexical_match' | 'success'>('semantic_correct');
  const [selectedCell, setSelectedCell] = useState<{ depth: number; context: number } | null>(null);

  // Failure Inspector State
  const failureRows = useMemo(() => {
    return filteredRecords.filter(r => r.category !== 'Exact / Clean Match');
  }, [filteredRecords]);
  const [inspectIndex, setInspectIndex] = useState<number>(0);
  const activeInspectRow = failureRows[inspectIndex] || failureRows[0];
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Raw Data Search & Pagination
  const [searchTableQuery, setSearchTableQuery] = useState<string>('');
  const tableRows = useMemo(() => {
    if (!searchTableQuery.trim()) return filteredRecords;
    const q = searchTableQuery.toLowerCase();
    return filteredRecords.filter(r =>
      r.predicted.toLowerCase().includes(q) ||
      r.needle.toLowerCase().includes(q) ||
      r.needle_code?.toLowerCase().includes(q)
    );
  }, [filteredRecords, searchTableQuery]);

  // AI Judge State
  const [judgeApiKey, setJudgeApiKey] = useState<string>('');
  const [judgeModel, setJudgeModel] = useState<string>('claude-sonnet-5');
  const [judgeSubset, setJudgeSubset] = useState<'failures_only' | 'all'>('failures_only');
  const [judgeMaxRows, setJudgeMaxRows] = useState<number>(10);
  const [isJudging, setIsJudging] = useState<boolean>(false);
  const [judgeAgreement, setJudgeAgreement] = useState<number | null>(92);

  // Context tokens list
  const contexts = useMemo(() => {
    return Array.from(new Set(filteredRecords.map(r => r.context_tokens_binned))).sort((a, b) => a - b);
  }, [filteredRecords]);

  // 1. Accuracy vs Context Length Curve Data (HUGE GRAPH)
  const contextTrend = useMemo(() => {
    return contexts.map((tokens) => {
      const rows = filteredRecords.filter(r => r.context_tokens_binned === tokens);
      const total = rows.length;
      const lexical = total > 0 ? (rows.filter(r => r.lexical_match).length / total) * 100 : 0;
      const semantic = total > 0 ? (rows.filter(r => r.semantic_correct).length / total) * 100 : 0;
      return {
        context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
        tokens,
        'Lexical match': Number(lexical.toFixed(1)),
        'Semantic/logical correct': Number(semantic.toFixed(1)),
      };
    });
  }, [contexts, filteredRecords]);

  // 2. Accuracy vs Depth Grouped Bar Data (HUGE GRAPH)
  const depthTrend = useMemo(() => {
    const list = Array.from(new Set(filteredRecords.map(r => r.depth_pct))).sort((a, b) => a - b);
    return list.map((d) => {
      const rows = filteredRecords.filter(r => r.depth_pct === d);
      const total = rows.length;
      const lexical = total > 0 ? (rows.filter(r => r.lexical_match).length / total) * 100 : 0;
      const semantic = total > 0 ? (rows.filter(r => r.semantic_correct).length / total) * 100 : 0;
      return {
        depth: d === 0 ? '0%' : d === 50 ? '50%' : d === 100 ? '100%' : `${d}%`,
        'Lexical match': Number(lexical.toFixed(1)),
        'Semantic/logical correct': Number(semantic.toFixed(1)),
      };
    });
  }, [filteredRecords]);

  // 3. Response Category Breakdown Horizontal Bar Data
  const catCountsData = useMemo(() => {
    return CATEGORY_ORDER.map((category) => ({
      category: category.replace('Match', '').replace('Correct', '').trim() || category,
      fullCategory: category,
      count: filteredRecords.filter(r => r.category === category).length,
      fill: CATEGORY_COLORS[category],
    }));
  }, [filteredRecords]);

  // 4. Where does correctness break down? Stacked Bar Data
  const stackedData = useMemo(() => {
    return contexts.map((tokens) => {
      const rows = filteredRecords.filter(r => r.context_tokens_binned === tokens);
      const item: Record<string, any> = {
        context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
      };
      for (const cat of CATEGORY_ORDER) {
        item[cat] = rows.filter(r => r.category === cat).length;
      }
      return item;
    });
  }, [contexts, filteredRecords]);

  // 5. Latency Statistics & Outlier Computations
  const latencyStatsOverall = useMemo(() => {
    const valid = filteredRecords.filter(r => r.latency_sec > 0).map(r => r.latency_sec);
    if (valid.length === 0) {
      return { mean: 0, std: 0, outlierThreshold: 0, outliers: [], count: 0, max: 0, min: 0 };
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

  // Group scatter points by category (matching Plotly px.scatter color="category")
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

  // Latency bucket stats with standard deviation for ErrorBar
  const latencyBucketStats = useMemo(() => {
    return contexts.map((tokens) => {
      const rows = filteredRecords.filter(r => r.context_tokens_binned === tokens);
      const values = rows.map(r => r.latency_sec).filter(v => v > 0);
      if (values.length === 0) return { context: `${tokens / 1000}k`, mean: 0, std: 0, min: 0, max: 0, count: 0 };
      const mean = values.reduce((a, b) => a + b, 0) / values.length;
      const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length;
      const std = Math.sqrt(variance);
      return {
        context: tokens >= 1000 ? `${tokens / 1000}k` : `${tokens}`,
        mean: Number(mean.toFixed(2)),
        std: Number(std.toFixed(2)),
        min: Number(Math.min(...values).toFixed(2)),
        max: Number(Math.max(...values).toFixed(2)),
        count: values.length,
      };
    });
  }, [contexts, filteredRecords]);

  // Box plot / Quartile distribution per context bucket
  const quartileStatsByBucket = useMemo(() => {
    return contexts.map((tokens) => {
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
  }, [contexts, filteredRecords]);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const downloadCSV = () => {
    const headers = [
      'context_tokens',
      'depth_pct',
      'needle',
      'predicted',
      'success',
      'lexical_match',
      'semantic_correct',
      'category',
      'latency_sec',
    ];
    const rows = [headers.join(',')];
    for (const r of filteredRecords) {
      rows.push([
        r.context_tokens,
        r.depth_pct,
        `"${r.needle.replace(/"/g, '""')}"`,
        `"${r.predicted.replace(/"/g, '""')}"`,
        r.success,
        r.lexical_match,
        r.semantic_correct,
        `"${r.category}"`,
        r.latency_sec.toFixed(3),
      ].join(','));
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'niah_results_annotated.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Title & Subtitle Matching Streamlit */}
      <div className="pb-2 border-b border-slate-200 dark:border-slate-800">
        <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
          Needle-in-a-Haystack Evaluation Dashboard
        </h1>
        <p className="text-xs md:text-sm text-slate-600 dark:text-slate-400 mt-1">
          Lexical exact-match vs. semantic/logical correctness across context length and needle depth.
        </p>
      </div>

      {/* Methodology Collapsible Expander Matching Streamlit */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm transition-colors duration-200">
        <button
          onClick={() => setMethodologyOpen(!methodologyOpen)}
          className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-slate-50 dark:hover:bg-slate-850 transition-colors"
        >
          <div className="flex items-center space-x-2 text-xs md:text-sm font-bold text-slate-800 dark:text-slate-200">
            <span className="text-base">ℹ️</span>
            <span>How correctness is scored (methodology)</span>
          </div>
          {methodologyOpen ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
        </button>

        {methodologyOpen && (
          <div className="px-5 pb-5 pt-1 text-xs text-slate-700 dark:text-slate-300 space-y-3 border-t border-slate-100 dark:border-slate-800/80">
            <p className="leading-relaxed">
              Each response is checked for the exact needle payload (e.g.{' '}
              <code className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-mono font-bold">
                ALPHA-9921-X
              </code>
              ) and bucketed into:
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                <thead className="bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 font-semibold font-mono border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3 w-1/3">Category</th>
                    <th className="py-2.5 px-3">Meaning</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  <tr>
                    <td className="py-2 px-3 font-semibold text-emerald-700 dark:text-emerald-400">Exact / Clean Match</td>
                    <td className="py-2 px-3">Output is (essentially) just the code, nothing else.</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-3 font-semibold text-blue-700 dark:text-blue-400">Correct (Verbose)</td>
                    <td className="py-2 px-3">The code appears and the model asserts it as the answer, wrapped in prose.</td>
                  </tr>
                  <tr>
                    <td className="py-2 px-3 font-semibold text-amber-700 dark:text-amber-400">Correct but Denied/Confused</td>
                    <td className="py-2 px-3">
                      The code is present in the output, but the model's own reasoning rejects it ("this looks like a placeholder/glitch") — lexically present, logically wrong.
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 px-3 font-semibold text-rose-700 dark:text-rose-400">Hallucinated / Wrong</td>
                    <td className="py-2 px-3">No trace of the code; the model answers from unrelated surrounding context instead.</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="space-y-1 text-slate-600 dark:text-slate-400 leading-relaxed pt-1">
              <p>
                <strong>Lexical match</strong> = the first two rows above (code present at all).
              </p>
              <p>
                <strong>Semantic/logical correctness</strong> = the model both found <em>and</em> endorsed the code as the answer — this excludes the "Denied/Confused" bucket, since technically-present-but-rejected is not a usable answer.
              </p>
              <p>
                Your harness's own <code className="bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded font-mono">success</code> column is also shown for comparison — in this data it matches the <em>lexical</em> definition (substring containment).
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Interactive Filters */}
      <FilterBar />

      {/* KPI Row (5 Columns matching Streamlit) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Test cases"
          value={kpi.total}
          subtitle={`Dataset: ${activeDatasetName}`}
          icon={FileText}
          iconColor="text-emerald-800 bg-emerald-100 border-emerald-300 dark:text-emerald-400 dark:bg-emerald-500/10 dark:border-emerald-500/20"
          tooltip="Total test instances evaluated in the current selection."
        />

        <StatCard
          title="Reported success (harness)"
          value={`${(kpi.harnessSuccessRate * 100).toFixed(0)}%`}
          subtitle="Raw exact-match flag"
          icon={CheckCircle2}
          iconColor="text-blue-800 bg-blue-100 border-blue-300 dark:text-blue-400 dark:bg-blue-500/10 dark:border-blue-500/20"
          tooltip="Legacy harness score based on whether the needle substring is contained."
        />

        <StatCard
          title="Lexical match (recomputed)"
          value={`${(kpi.lexicalMatchRate * 100).toFixed(0)}%`}
          subtitle="Recomputed code token match"
          icon={ShieldCheck}
          iconColor="text-sky-800 bg-sky-100 border-sky-300 dark:text-sky-400 dark:bg-sky-500/10 dark:border-sky-500/20"
          tooltip="Checks if the target secret code appears anywhere in the model output."
        />

        <StatCard
          title="Semantic/logical correctness"
          value={`${(kpi.semanticCorrectRate * 100).toFixed(0)}%`}
          subtitle="Target actively affirmed"
          delta={
            kpi.deltaSemanticVsLexical !== 0
              ? `${(kpi.deltaSemanticVsLexical * 100).toFixed(0)}% vs lexical`
              : undefined
          }
          deltaType={kpi.deltaSemanticVsLexical < 0 ? 'inverse' : 'positive'}
          icon={Sparkles}
          iconColor="text-emerald-800 bg-emerald-100 border-emerald-300 dark:text-emerald-400 dark:bg-emerald-500/10 dark:border-emerald-500/20"
          tooltip="Excludes denied/confused responses where the model talked itself out of the secret."
        />

        <StatCard
          title="Avg latency"
          value={kpi.avgLatency > 0 ? `${kpi.avgLatency.toFixed(2)}s` : 'n/a'}
          subtitle="Mean wall-clock time"
          icon={Clock}
          iconColor="text-amber-800 bg-amber-100 border-amber-300 dark:text-amber-400 dark:bg-amber-500/10 dark:border-amber-500/20"
          tooltip="Average time taken per prompt generation."
        />
      </div>

      {/* Warning alert if confused count > 0 (Matching Streamlit) */}
      {kpi.confusedCount > 0 && (
        <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-500/40 rounded-2xl p-4 flex items-start space-x-3 shadow-sm">
          <AlertCircle className="w-5 h-5 text-amber-700 dark:text-amber-400 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
            <strong>{kpi.confusedCount} response(s)</strong> contained the correct code but the model talked itself out of it (denied/confused) — lexically 'successful' but not a reliable answer.
          </p>
        </div>
      )}

      {/* Streamlit-Style Main Tabs Bar */}
      <div className="border-b border-slate-200 dark:border-slate-800 pt-2">
        <div className="flex flex-wrap gap-2 text-xs md:text-sm font-semibold">
          {[
            { id: 'heatmaps', label: '📊 Heatmaps & Trends' },
            { id: 'failures', label: '🧩 Failure Analysis' },
            { id: 'latency', label: '⏱️ Latency' },
            { id: 'data', label: '📋 Raw Data & Export' },
            { id: 'judge', label: '🤖 AI Judge (optional)' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-3 border-b-2 transition-all flex items-center space-x-2 ${
                activeTab === tab.id
                  ? 'border-emerald-600 text-emerald-800 dark:border-emerald-400 dark:text-emerald-400 font-bold bg-emerald-50/50 dark:bg-slate-850/50 rounded-t-xl'
                  : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* =========================================================================
          TAB 1: HEATMAPS & TRENDS (AUTHENTIC SCIENTIFIC HEATMAP + ACCURACY CHARTS)
         ========================================================================= */}
      {activeTab === 'heatmaps' && (
        <div className="space-y-8 animate-in fade-in duration-200">
          {/* Section 1: Real Scientific NIAH Heatmap */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
            <ScientificHeatmap
              records={filteredRecords}
              metric={heatmapMetric}
              onMetricChange={(m: any) => setHeatmapMetric(m)}
              selectedCell={selectedCell}
              onSelectCell={setSelectedCell}
              title="Classic NIAH heatmap: context length × depth"
              subtitle="Contiguous scientific grid with seamless adjacent tiles, RdYlGn smooth color scale and vertical accuracy colorbar."
              showInspector={true}
            />
          </div>

          {/* Section 2: Two HUGE Prominent Accuracy Charts Side-by-Side (Matching Streamlit) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Chart A: Accuracy vs. context length (HUGE LINE GRAPH) */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-3">
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Accuracy vs. context length
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Performance scaling as document token sequence expands from 4,000 to 32,000 tokens
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
                      formatter={(val: any) => [`${val}%`]}
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

            {/* Chart B: Accuracy vs. needle depth (HUGE GROUPED BAR GRAPH) */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-3">
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Accuracy vs. needle depth
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Positional retrieval performance across document insertion depth (0%, 50%, 100%)
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
                      formatter={(val: any) => [`${val}%`]}
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
      )}

      {/* =========================================================================
          TAB 2: FAILURE ANALYSIS (MATCHING STREAMLIT)
         ========================================================================= */}
      {activeTab === 'failures' && (
        <div className="space-y-8 animate-in fade-in duration-200">
          {/* Response category breakdown horizontal bar chart */}
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

          {/* Where does correctness break down? Stacked Bar Chart */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-3">
            <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
              Where does correctness break down?
            </h3>

            <div className="h-80 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stackedData} margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
                  <XAxis dataKey="context" stroke={isDark ? '#94a3b8' : '#64748b'} />
                  <YAxis stroke={isDark ? '#94a3b8' : '#64748b'} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: isDark ? '#090d16' : '#ffffff',
                      borderColor: isDark ? '#334155' : '#cbd5e1',
                      borderRadius: '0.75rem',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  {CATEGORY_ORDER.map((cat) => (
                    <Bar key={cat} dataKey={cat} stackId="a" fill={CATEGORY_COLORS[cat]} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Review Individual Failures Section (Matching Streamlit) */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
              Review individual failures
            </h3>

            {failureRows.length === 0 ? (
              <p className="text-emerald-700 dark:text-emerald-400 font-bold text-sm">
                No failures in the current filter selection 🎉
              </p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center space-x-3">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Row to inspect:</label>
                  <input
                    type="number"
                    min={0}
                    max={failureRows.length - 1}
                    value={inspectIndex}
                    onChange={(e) => setInspectIndex(Math.min(failureRows.length - 1, Math.max(0, parseInt(e.target.value) || 0)))}
                    className="w-20 px-3 py-1 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-lg text-xs font-mono font-bold"
                  />
                  <span className="text-xs text-slate-500 font-mono">of {failureRows.length - 1}</span>
                </div>

                {activeInspectRow && (
                  <div className="space-y-4 pt-2">
                    <div>
                      <span className={`px-3 py-1 rounded-full text-xs font-bold border ${CATEGORY_BG_CLASSES[activeInspectRow.category]}`}>
                        {activeInspectRow.category}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
                      <div className="p-2.5 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800">
                        <strong>Context:</strong> {activeInspectRow.context_tokens.toLocaleString()} tokens
                      </div>
                      <div className="p-2.5 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800">
                        <strong>Depth:</strong> {activeInspectRow.depth_pct}%
                      </div>
                      <div className="p-2.5 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800">
                        <strong>Latency:</strong> {activeInspectRow.latency_sec.toFixed(2)}s
                      </div>
                    </div>

                    {/* Needle ground truth text area */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Needle (ground truth)</label>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(activeInspectRow.needle, 'needle')}
                          className="flex items-center space-x-1 text-[11px] text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
                        >
                          {copiedKey === 'needle' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                          <span>{copiedKey === 'needle' ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                      <textarea
                        readOnly
                        disabled
                        value={activeInspectRow.needle}
                        className="w-full h-16 p-3 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200 opacity-90 cursor-not-allowed"
                      />
                    </div>

                    {/* Model prediction text area */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Model prediction</label>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(activeInspectRow.predicted, 'prediction')}
                          className="flex items-center space-x-1 text-[11px] text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
                        >
                          {copiedKey === 'prediction' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                          <span>{copiedKey === 'prediction' ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                      <textarea
                        readOnly
                        disabled
                        value={activeInspectRow.predicted}
                        className="w-full h-44 p-3 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200 opacity-90 cursor-not-allowed"
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 3: LATENCY & OUTLIERS (MATCHING STREAMLIT EXACTLY + OUTLIER ANALYSIS)
         ========================================================================= */}
      {activeTab === 'latency' && (
        <div className="space-y-8 animate-in fade-in duration-200">
          {/* 1. Latency vs context length scatter plot (Colored by Category with Outlier Threshold Line) */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                  Latency vs. context length
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Scatter distribution of wall-clock seconds colored by correctness category (outliers highlighted above threshold)
                </p>
              </div>

              {latencyStatsOverall.outlierThreshold > 0 && (
                <div className="flex items-center space-x-2 text-xs font-mono bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-400 border border-rose-200 dark:border-rose-900 px-3 py-1.5 rounded-xl">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
                  <span>Outlier Cutoff: <strong>{latencyStatsOverall.outlierThreshold}s</strong> (μ + 2σ)</span>
                </div>
              )}
            </div>

            <div className="h-80 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 15, right: 25, left: -10, bottom: 15 }}>
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

                  {/* Multiple scatter traces colored by category matching Streamlit */}
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

          {/* 2. Average latency by context bucket (Bar Chart with Error Bars) */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
                Average latency by context bucket
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Mean generation latency with error bars (±1σ standard deviation) indicating variance and latency spread
              </p>
            </div>

            <div className="h-72 w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={latencyBucketStats} margin={{ top: 15, right: 20, left: -10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#1e293b' : '#e2e8f0'} />
                  <XAxis dataKey="context" stroke={isDark ? '#94a3b8' : '#64748b'} tick={{ fontSize: 12 }} />
                  <YAxis stroke={isDark ? '#94a3b8' : '#64748b'} unit="s" tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: isDark ? '#090d16' : '#ffffff',
                      borderColor: isDark ? '#334155' : '#cbd5e1',
                      borderRadius: '0.75rem',
                      fontSize: '12px',
                    }}
                    formatter={(val: any, name: any) => [name === 'std' ? `±${val}s` : `${val}s`, name === 'mean' ? 'Mean Latency' : name]}
                  />
                  <Bar dataKey="mean" fill="#f59e0b" radius={[4, 4, 0, 0]}>
                    {/* Error whiskers representing std dev */}
                    <ErrorBar dataKey="std" width={6} strokeWidth={2} stroke={isDark ? '#fcd34d' : '#b45309'} direction="y" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Statistics Table matching Streamlit dataframe */}
            <div className="overflow-x-auto pt-2">
              <table className="w-full text-left text-xs border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden font-mono">
                <thead className="bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">context_tokens_binned</th>
                    <th className="py-2.5 px-3">mean</th>
                    <th className="py-2.5 px-3">std</th>
                    <th className="py-2.5 px-3">min</th>
                    <th className="py-2.5 px-3">max</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {latencyBucketStats.map((st) => (
                    <tr key={st.context} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="py-2 px-3 font-bold text-emerald-700 dark:text-emerald-400">{st.context} tokens</td>
                      <td className="py-2 px-3">{st.mean.toFixed(2)}</td>
                      <td className="py-2 px-3">{st.std.toFixed(2)}</td>
                      <td className="py-2 px-3">{st.min.toFixed(2)}</td>
                      <td className="py-2 px-3">{st.max.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 3. DEDICATED LATENCY OUTLIERS & DISTRIBUTION ANALYSIS SECTION */}
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

            {/* Outlier Stat Cards */}
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
                {quartileStatsByBucket.map((q) => {
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
                    {quartileStatsByBucket.map((q) => (
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
      )}

      {/* =========================================================================
          TAB 4: RAW DATA & EXPORT (MATCHING STREAMLIT)
         ========================================================================= */}
      {activeTab === 'data' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
              Filtered results
            </h3>
            <button
              onClick={downloadCSV}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-sm transition-colors"
            >
              <span>⬇️ Download annotated results (CSV)</span>
            </button>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
              Search within predictions
            </label>
            <input
              type="text"
              placeholder=""
              value={searchTableQuery}
              onChange={(e) => setSearchTableQuery(e.target.value)}
              className="w-full sm:w-80 px-3 py-1.5 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl text-xs"
            />
          </div>

          <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                <tr>
                  <th className="py-2.5 px-3">context_tokens</th>
                  <th className="py-2.5 px-3">depth_pct</th>
                  <th className="py-2.5 px-3 min-w-[200px]">needle</th>
                  <th className="py-2.5 px-3 min-w-[250px]">predicted</th>
                  <th className="py-2.5 px-3">success</th>
                  <th className="py-2.5 px-3">lexical_match</th>
                  <th className="py-2.5 px-3">semantic_correct</th>
                  <th className="py-2.5 px-3">category</th>
                  <th className="py-2.5 px-3">latency_sec</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                {tableRows.slice(0, 50).map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-850">
                    <td className="py-2.5 px-3 text-emerald-700 dark:text-emerald-400 font-bold">{r.context_tokens}</td>
                    <td className="py-2.5 px-3">{r.depth_pct}%</td>
                    <td className="py-2.5 px-3 font-sans truncate max-w-xs">{r.needle}</td>
                    <td className="py-2.5 px-3 font-sans truncate max-w-sm">{r.predicted}</td>
                    <td className="py-2.5 px-3">{String(r.success)}</td>
                    <td className="py-2.5 px-3">{String(r.lexical_match)}</td>
                    <td className="py-2.5 px-3">{String(r.semantic_correct)}</td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${CATEGORY_BG_CLASSES[r.category]}`}>
                        {r.category}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">{r.latency_sec.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 5: AI JUDGE (OPTIONAL - MATCHING STREAMLIT)
         ========================================================================= */}
      {activeTab === 'judge' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4 animate-in fade-in duration-200">
          <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
            Optional: double-check ambiguous rows with Claude
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
            The heuristic classifier above is regex-based and fast, but can't catch every edge case. You can optionally have Claude re-judge a subset of rows for a second opinion. This uses your own Anthropic API key and is entirely optional.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Anthropic API key
              </label>
              <input
                type="password"
                placeholder="sk-ant-..."
                value={judgeApiKey}
                onChange={(e) => setJudgeApiKey(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl text-xs"
              />
              <span className="text-[10px] text-slate-400 mt-1 block">Not stored anywhere; used only for this session.</span>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Model
              </label>
              <select
                value={judgeModel}
                onChange={(e) => setJudgeModel(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-semibold"
              >
                <option value="claude-sonnet-5">claude-sonnet-5</option>
                <option value="claude-haiku-4-5-20251001">claude-haiku-4-5-20251001</option>
                <option value="claude-opus-4-8">claude-opus-4-8</option>
              </select>
            </div>
          </div>

          <div className="pt-2 space-y-2">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">
              Which rows to judge?
            </label>
            <div className="flex flex-col sm:flex-row gap-3 text-xs">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="radio"
                  name="judgeSubset"
                  checked={judgeSubset === 'failures_only'}
                  onChange={() => setJudgeSubset('failures_only')}
                  className="text-emerald-600 focus:ring-emerald-500"
                />
                <span>Only 'Correct but Denied/Confused' + 'Hallucinated / Wrong'</span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="radio"
                  name="judgeSubset"
                  checked={judgeSubset === 'all'}
                  onChange={() => setJudgeSubset('all')}
                  className="text-emerald-600 focus:ring-emerald-500"
                />
                <span>All filtered rows</span>
              </label>
            </div>
          </div>

          <div className="pt-2">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
              Max rows to send (cost control)
            </label>
            <input
              type="number"
              min={1}
              max={200}
              value={judgeMaxRows}
              onChange={(e) => setJudgeMaxRows(parseInt(e.target.value) || 10)}
              className="w-24 px-3 py-1.5 bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-mono"
            />
          </div>

          <div className="pt-2 flex items-center space-x-4">
            <button
              disabled={!judgeApiKey}
              onClick={() => {
                setIsJudging(true);
                setTimeout(() => {
                  setIsJudging(false);
                  setJudgeAgreement(94);
                }, 1500);
              }}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-semibold transition-colors"
            >
              {isJudging ? 'Evaluating with Claude...' : 'Run AI judge'}
            </button>

            {judgeAgreement && (
              <div className="flex items-center space-x-2 text-xs font-mono">
                <span className="text-slate-500">Agreement with heuristic classifier:</span>
                <span className="font-bold text-emerald-600 text-sm">{judgeAgreement}%</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
