import React, { createContext, useContext, useState, useMemo, useEffect } from 'react';
import {
  BenchmarkRecord,
  FilterOptions,
  KPISummary,
  PageRoute,
  TaxonomyCategory,
} from '../types';
import {
  DEFAULT_RECORDS_LLAMA3,
  DEFAULT_RECORDS_QWEN3,
  RAW_CSV_RUN_2,
} from '../utils/defaultData';
import { parseAndPrepareRow } from '../utils/taxonomy';

interface BenchmarkContextType {
  activeRoute: PageRoute;
  setActiveRoute: (route: PageRoute) => void;
  
  // Data
  records: BenchmarkRecord[];
  allRecords: BenchmarkRecord[];
  filteredRecords: BenchmarkRecord[];
  setRecordsFromCSV: (csvData: Record<string, any>[], name: string) => void;
  resetToDefault: () => void;
  activeDatasetName: string;
  switchPreset: (presetKey: 'llama3' | 'run2' | 'all') => void;
  
  // Filter state
  filters: FilterOptions;
  setFilter: <K extends keyof FilterOptions>(key: K, value: FilterOptions[K]) => void;
  toggleNeedleFilter: (needle: string) => void;
  toggleContextFilter: (tokens: number) => void;
  toggleDepthFilter: (depth: number) => void;
  toggleCategoryFilter: (category: TaxonomyCategory) => void;
  resetFilters: () => void;
  
  // Unique filter values
  availableNeedles: string[];
  availableContextTokens: number[];
  availableDepths: number[];
  
  // KPIs
  kpi: KPISummary;
  
  // Comparison
  modelA: string;
  modelB: string;
  setModelA: (m: string) => void;
  setModelB: (m: string) => void;
  recordsModelA: BenchmarkRecord[];
  recordsModelB: BenchmarkRecord[];
  
  // Theme (default light/white)
  isDark: boolean;
  setIsDark: (dark: boolean) => void;
  toggleTheme: () => void;
}

const BenchmarkContext = createContext<BenchmarkContextType | null>(null);

export const BenchmarkProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeRoute, setActiveRoute] = useState<PageRoute>('dashboard');
  const [records, setRecords] = useState<BenchmarkRecord[]>(DEFAULT_RECORDS_LLAMA3);
  const [activeDatasetName, setActiveDatasetName] = useState<string>('Llama-3-8B NIAH Sweep (4k-32k)');
  
  // Default to light mode (white background) as requested
  const [isDark, setIsDark] = useState<boolean>(false);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
    }
  }, [isDark]);

  // Model comparison state
  const [modelA, setModelA] = useState<string>('Meta-Llama-3-8B');
  const [modelB, setModelB] = useState<string>('Qwen-2.5-7B');
  const [recordsModelA] = useState<BenchmarkRecord[]>(DEFAULT_RECORDS_LLAMA3);
  const [recordsModelB] = useState<BenchmarkRecord[]>(DEFAULT_RECORDS_QWEN3);

  // Unique lists from current records
  const availableNeedles = useMemo(() => {
    return Array.from(new Set(records.map(r => r.needle))).sort();
  }, [records]);

  const availableContextTokens = useMemo(() => {
    return Array.from(new Set(records.map(r => r.context_tokens_binned))).sort((a, b) => a - b);
  }, [records]);

  const availableDepths = useMemo(() => {
    return Array.from(new Set(records.map(r => r.depth_pct))).sort((a, b) => a - b);
  }, [records]);

  // Filters state
  const [filters, setFilters] = useState<FilterOptions>({
    selectedNeedles: [],
    selectedContextTokens: [],
    selectedDepths: [],
    selectedCategories: [],
    searchQuery: '',
  });

  const setFilter = <K extends keyof FilterOptions>(key: K, value: FilterOptions[K]) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const toggleNeedleFilter = (needle: string) => {
    setFilters(prev => {
      const active = prev.selectedNeedles.length > 0 ? prev.selectedNeedles : availableNeedles;
      const next = active.includes(needle)
        ? active.filter(n => n !== needle)
        : [...active, needle];
      return { ...prev, selectedNeedles: next.length === availableNeedles.length ? [] : next };
    });
  };

  const toggleContextFilter = (tokens: number) => {
    setFilters(prev => {
      const active = prev.selectedContextTokens.length > 0 ? prev.selectedContextTokens : availableContextTokens;
      const next = active.includes(tokens)
        ? active.filter(t => t !== tokens)
        : [...active, tokens];
      return { ...prev, selectedContextTokens: next.length === availableContextTokens.length ? [] : next };
    });
  };

  const toggleDepthFilter = (depth: number) => {
    setFilters(prev => {
      const active = prev.selectedDepths.length > 0 ? prev.selectedDepths : availableDepths;
      const next = active.includes(depth)
        ? active.filter(d => d !== depth)
        : [...active, depth];
      return { ...prev, selectedDepths: next.length === availableDepths.length ? [] : next };
    });
  };

  const toggleCategoryFilter = (category: TaxonomyCategory) => {
    setFilters(prev => {
      const next = prev.selectedCategories.includes(category)
        ? prev.selectedCategories.filter(c => c !== category)
        : [...prev.selectedCategories, category];
      return { ...prev, selectedCategories: next };
    });
  };

  const resetFilters = () => {
    setFilters({
      selectedNeedles: [],
      selectedContextTokens: [],
      selectedDepths: [],
      selectedCategories: [],
      searchQuery: '',
    });
  };

  // Filtered records
  const filteredRecords = useMemo(() => {
    return records.filter(r => {
      if (filters.selectedNeedles.length > 0 && !filters.selectedNeedles.includes(r.needle)) {
        return false;
      }
      if (filters.selectedContextTokens.length > 0 && !filters.selectedContextTokens.includes(r.context_tokens_binned)) {
        return false;
      }
      if (filters.selectedDepths.length > 0 && !filters.selectedDepths.includes(r.depth_pct)) {
        return false;
      }
      if (filters.selectedCategories.length > 0 && !filters.selectedCategories.includes(r.category)) {
        return false;
      }
      if (filters.searchQuery.trim()) {
        const q = filters.searchQuery.toLowerCase();
        const inPred = r.predicted.toLowerCase().includes(q);
        const inNeedle = r.needle.toLowerCase().includes(q);
        const inCode = r.needle_code?.toLowerCase().includes(q);
        if (!inPred && !inNeedle && !inCode) return false;
      }
      return true;
    });
  }, [records, filters]);

  // Compute KPIs
  const kpi = useMemo<KPISummary>(() => {
    const total = filteredRecords.length;
    if (total === 0) {
      return {
        total: 0,
        harnessSuccessRate: 0,
        lexicalMatchRate: 0,
        semanticCorrectRate: 0,
        deltaSemanticVsLexical: 0,
        avgLatency: 0,
        confusedCount: 0,
        exactMatchCount: 0,
        verboseMatchCount: 0,
        wrongCount: 0,
      };
    }

    const harnessSuccesses = filteredRecords.filter(r => r.success).length;
    const lexicalMatches = filteredRecords.filter(r => r.lexical_match).length;
    const semanticCorrects = filteredRecords.filter(r => r.semantic_correct).length;
    const confused = filteredRecords.filter(r => r.category === 'Correct but Denied/Confused').length;
    const exact = filteredRecords.filter(r => r.category === 'Exact / Clean Match').length;
    const verbose = filteredRecords.filter(r => r.category === 'Correct (Verbose)').length;
    const wrong = filteredRecords.filter(r => r.category === 'Hallucinated / Wrong').length;

    const latencies = filteredRecords.map(r => r.latency_sec).filter(l => !isNaN(l) && l > 0);
    const avgLatency = latencies.length > 0
      ? latencies.reduce((a, b) => a + b, 0) / latencies.length
      : 0;

    const harnessSuccessRate = harnessSuccesses / total;
    const lexicalMatchRate = lexicalMatches / total;
    const semanticCorrectRate = semanticCorrects / total;
    const deltaSemanticVsLexical = semanticCorrectRate - lexicalMatchRate;

    return {
      total,
      harnessSuccessRate,
      lexicalMatchRate,
      semanticCorrectRate,
      deltaSemanticVsLexical,
      avgLatency,
      confusedCount: confused,
      exactMatchCount: exact,
      verboseMatchCount: verbose,
      wrongCount: wrong,
    };
  }, [filteredRecords]);

  // Switch datasets
  const switchPreset = (presetKey: 'llama3' | 'run2' | 'all') => {
    if (presetKey === 'llama3') {
      setRecords(DEFAULT_RECORDS_LLAMA3);
      setActiveDatasetName('Llama-3-8B (4K-32K Sweep)');
    } else if (presetKey === 'run2') {
      const parsed = RAW_CSV_RUN_2.map((r, i) => parseAndPrepareRow(r, i, 'Run 2 (2K-8K)'));
      setRecords(parsed);
      setActiveDatasetName('Run 2 (2K-8K Short Context)');
    } else if (presetKey === 'all') {
      const parsed2 = RAW_CSV_RUN_2.map((r, i) => parseAndPrepareRow(r, i + 500, 'Run 2 (2K-8K)'));
      setRecords([...DEFAULT_RECORDS_LLAMA3, ...parsed2]);
      setActiveDatasetName('Combined Multi-Run Archive (72 Cases)');
    }
    resetFilters();
  };

  const setRecordsFromCSV = (csvData: Record<string, any>[], name: string) => {
    const parsed = csvData.map((r, i) => parseAndPrepareRow(r, i, name));
    setRecords(parsed);
    setActiveDatasetName(name);
    resetFilters();
  };

  const resetToDefault = () => {
    setRecords(DEFAULT_RECORDS_LLAMA3);
    setActiveDatasetName('Llama-3-8B NIAH Sweep (4k-32k)');
    resetFilters();
  };

  const toggleTheme = () => {
    setIsDark(prev => !prev);
  };

  return (
    <BenchmarkContext.Provider
      value={{
        activeRoute,
        setActiveRoute,
        records,
        allRecords: records,
        filteredRecords,
        setRecordsFromCSV,
        resetToDefault,
        activeDatasetName,
        switchPreset,
        filters,
        setFilter,
        toggleNeedleFilter,
        toggleContextFilter,
        toggleDepthFilter,
        toggleCategoryFilter,
        resetFilters,
        availableNeedles,
        availableContextTokens,
        availableDepths,
        kpi,
        modelA,
        modelB,
        setModelA,
        setModelB,
        recordsModelA,
        recordsModelB,
        isDark,
        setIsDark,
        toggleTheme,
      }}
    >
      {children}
    </BenchmarkContext.Provider>
  );
};

export const useBenchmark = () => {
  const context = useContext(BenchmarkContext);
  if (!context) {
    throw new Error('useBenchmark must be used within a BenchmarkProvider');
  }
  return context;
};
