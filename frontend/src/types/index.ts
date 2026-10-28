export type TaxonomyCategory =
  | 'Exact / Clean Match'
  | 'Correct (Verbose)'
  | 'Correct but Denied/Confused'
  | 'Hallucinated / Wrong'
  | 'Unscored';

export interface BenchmarkRecord {
  id: string;
  context_tokens: number;
  depth: number; // 0.0 to 1.0
  needle: string;
  predicted: string;
  success: boolean;
  latency_sec: number;
  context_tokens_binned: number;
  
  // Computed taxonomy & evaluation metrics
  category: TaxonomyCategory;
  lexical_match: boolean;
  semantic_correct: boolean;
  needle_code: string | null;
  depth_pct: number;
  reported_vs_recomputed_agree: boolean;
  model_name?: string;
}

export interface KPISummary {
  total: number;
  harnessSuccessRate: number;
  lexicalMatchRate: number;
  semanticCorrectRate: number;
  deltaSemanticVsLexical: number;
  avgLatency: number;
  confusedCount: number;
  exactMatchCount: number;
  verboseMatchCount: number;
  wrongCount: number;
}

export interface FilterOptions {
  selectedNeedles: string[];
  selectedContextTokens: number[];
  selectedDepths: number[];
  selectedCategories: TaxonomyCategory[];
  searchQuery: string;
}

export type PageRoute =
  | 'dashboard'
  | 'heatmaps'
  | 'trends'
  | 'failures'
  | 'comparison'
  | 'latency'
  | 'data'
  | 'judge';

export interface ModelComparisonData {
  modelA: string;
  modelB: string;
  recordsA: BenchmarkRecord[];
  recordsB: BenchmarkRecord[];
}

