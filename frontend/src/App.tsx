import React from 'react';
import { Header } from './components/Header';
import { StepProgress } from './components/StepProgress';
import { useCareerLens } from './context/CareerLensContext';
import { LandingUpload } from './pages/LandingUpload';
import { ProfileView } from './pages/ProfileView';
import { JobSearch } from './pages/JobSearch';
import { MatchResults } from './pages/MatchResults';
import { SkillGaps } from './pages/SkillGaps';
import { WhatIfSimulator } from './pages/WhatIfSimulator';
import { LearningHub } from './pages/LearningHub';

export const App: React.FC = () => {
  const { currentStep } = useCareerLens();

  const renderCurrentStep = () => {
    switch (currentStep) {
      case 'upload':
        return <LandingUpload />;
      case 'profile':
        return <ProfileView />;
      case 'jobs':
        return <JobSearch />;
      case 'matches':
        return <MatchResults />;
      case 'gaps':
        return <SkillGaps />;
      case 'what-if':
        return <WhatIfSimulator />;
      case 'learning':
        return <LearningHub />;
      default:
        return <LandingUpload />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-brand-500 selection:text-white">
      {/* Top Navigation */}
      <Header />
      <StepProgress />

      {/* Main Dynamic View */}
      <main className="flex-1 pb-16">
        {renderCurrentStep()}
      </main>

      {/* Minimal Footer */}
      <footer className="border-t border-slate-900 py-6 px-4 text-center text-xs text-slate-400 bg-slate-950">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>© 2026 CareerLensAI — AI-Powered Job Alignment & Skill Gap Simulator for Students.</p>
          <p className="text-slate-400">
            Powered by NuExtract-tiny LoRA, FastAPI, and Sentence Transformers
          </p>
        </div>
      </footer>
    </div>
  );
};

export default App;
