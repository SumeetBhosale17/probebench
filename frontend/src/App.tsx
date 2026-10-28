import React from 'react';
import { BenchmarkProvider, useBenchmark } from './context/BenchmarkContext';
import { Sidebar } from './components/common/Sidebar';
import { Navbar } from './components/common/Navbar';
import { DashboardPage } from './components/pages/DashboardPage';
import { HeatmapPage } from './components/pages/HeatmapPage';
import { TrendsPage } from './components/pages/TrendsPage';
import { FailuresPage } from './components/pages/FailuresPage';
import { ComparisonPage } from './components/pages/ComparisonPage';
import { LatencyPage } from './components/pages/LatencyPage';
import { DataPage } from './components/pages/DataPage';
import { JudgePage } from './components/pages/JudgePage';

const AppContent: React.FC = () => {
  const { activeRoute } = useBenchmark();

  const renderActivePage = () => {
    switch (activeRoute) {
      case 'dashboard':
        return <DashboardPage />;
      case 'heatmaps':
        return <HeatmapPage />;
      case 'trends':
        return <TrendsPage />;
      case 'failures':
        return <FailuresPage />;
      case 'comparison':
        return <ComparisonPage />;
      case 'latency':
        return <LatencyPage />;
      case 'data':
        return <DataPage />;
      case 'judge':
        return <JudgePage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-100 overflow-hidden font-sans transition-colors duration-200">
      {/* Left Navigation Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar with Theme Toggle Bar */}
        <Navbar />

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-slate-50 dark:bg-slate-950 transition-colors duration-200">
          <div className="max-w-7xl mx-auto pb-12">
            {renderActivePage()}
          </div>
        </main>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <BenchmarkProvider>
      <AppContent />
    </BenchmarkProvider>
  );
};

export default App;
