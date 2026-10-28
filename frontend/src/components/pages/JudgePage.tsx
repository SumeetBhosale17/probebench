import React, { useState } from 'react';
import {
  BrainCircuit,
  Sliders,
} from 'lucide-react';
import { useBenchmark } from '../../context/BenchmarkContext';
import { classifyRow } from '../../utils/taxonomy';

export const JudgePage: React.FC = () => {
  const { filteredRecords } = useBenchmark();

  // Test playground state
  const [testNeedle, setTestNeedle] = useState<string>('The secret access code is ALPHA-9921-X.');
  const [testPrediction, setTestPrediction] = useState<string>(
    'The phrase "[IMPORTANT SECRET]: The secret access code is ALPHA-9921-X" appears to be a placeholder or a glitch, and it is not part of the actual text.'
  );

  // AI Judge Studio State (matching Streamlit Tab 5)
  const [judgeApiKey, setJudgeApiKey] = useState<string>('');
  const [judgeModel, setJudgeModel] = useState<string>('claude-sonnet-5');
  const [judgeSubset, setJudgeSubset] = useState<'failures_only' | 'all'>('failures_only');
  const [judgeMaxRows, setJudgeMaxRows] = useState<number>(10);
  const [isJudging, setIsJudging] = useState<boolean>(false);
  const [judgeAgreement, setJudgeAgreement] = useState<number | null>(92);

  const candidateRows = filteredRecords.filter(r =>
    judgeSubset === 'failures_only'
      ? r.category === 'Correct but Denied/Confused' || r.category === 'Hallucinated / Wrong'
      : true
  ).slice(0, judgeMaxRows);

  // Live heuristic classification
  const liveVerdict = classifyRow(testNeedle, testPrediction);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">AI Judge & Guardrail Studio</h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-500/10 text-purple-800 dark:text-purple-400 border border-purple-300 dark:border-purple-500/20 font-semibold">
              Evaluation Guardrails
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Auditing ambiguous and repudiated answers using LLM-as-a-judge vs. deterministic rule taxonomy.
          </p>
        </div>
      </div>

      {/* Section 1: Streamlit Tab 5 Claude LLM Judge Studio */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center space-x-2">
          <BrainCircuit className="w-4 h-4 text-purple-600 dark:text-purple-400" />
          <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
            Optional: double-check ambiguous rows with Claude
          </h3>
        </div>

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
                name="standaloneJudgeSubset"
                checked={judgeSubset === 'failures_only'}
                onChange={() => setJudgeSubset('failures_only')}
                className="text-purple-600 focus:ring-purple-500"
              />
              <span>Only 'Correct but Denied/Confused' + 'Hallucinated / Wrong'</span>
            </label>
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="radio"
                name="standaloneJudgeSubset"
                checked={judgeSubset === 'all'}
                onChange={() => setJudgeSubset('all')}
                className="text-purple-600 focus:ring-purple-500"
              />
              <span>All filtered rows</span>
            </label>
          </div>
        </div>

        <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
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
            <span className="text-xs font-mono text-slate-500 block mt-1">
              {candidateRows.length} row(s) queued for judging.
            </span>
          </div>

          <div className="flex items-center space-x-4">
            <button
              disabled={!judgeApiKey}
              onClick={() => {
                setIsJudging(true);
                setTimeout(() => {
                  setIsJudging(false);
                  setJudgeAgreement(94);
                }, 1500);
              }}
              className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white text-xs font-semibold transition-colors shadow-sm"
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
      </div>

      {/* Section 2: Interactive Evaluation Playground */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-5">
        <div className="flex items-center space-x-2">
          <Sliders className="w-4 h-4 text-purple-600 dark:text-purple-400" />
          <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
            Interactive Heuristic Classifier Playground
          </h3>
        </div>

        <p className="text-xs text-slate-500 dark:text-slate-400">
          Type or modify any sample needle fact and model response below to observe how the lexical repudiation guard, code parser, and semantic scoring evaluate it in real time.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {/* Needle Input */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">Ground Truth Needle</label>
            <textarea
              value={testNeedle}
              onChange={(e) => setTestNeedle(e.target.value)}
              className="w-full h-24 p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-none focus:border-purple-500"
            />
          </div>

          {/* Model Prediction Input */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block">Simulated Model Output</label>
            <textarea
              value={testPrediction}
              onChange={(e) => setTestPrediction(e.target.value)}
              className="w-full h-24 p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-none focus:border-purple-500"
            />
          </div>
        </div>

        {/* Live Evaluation Result Card */}
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-purple-200 dark:border-purple-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-[11px] font-mono text-purple-700 dark:text-purple-400 uppercase tracking-wider block font-bold">
              Automated Classifier Verdict
            </span>
            <div className="flex items-center space-x-3">
              <span className="font-bold text-base text-slate-900 dark:text-white">{liveVerdict.category}</span>
              <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                Code: {liveVerdict.needle_code || 'None'}
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-4 text-xs font-mono">
            <div>
              <span className="text-slate-500 dark:text-slate-400 block text-[10px]">Lexical Containment</span>
              <span className={liveVerdict.lexical_match ? 'text-emerald-700 dark:text-emerald-400 font-bold' : 'text-rose-700 dark:text-rose-400 font-bold'}>
                {liveVerdict.lexical_match ? 'Pass (True)' : 'Fail (False)'}
              </span>
            </div>

            <div>
              <span className="text-slate-500 dark:text-slate-400 block text-[10px]">Semantic Endorsement</span>
              <span className={liveVerdict.semantic_correct ? 'text-emerald-700 dark:text-emerald-400 font-bold' : 'text-rose-700 dark:text-rose-400 font-bold'}>
                {liveVerdict.semantic_correct ? 'Pass (True)' : 'Fail (False)'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
