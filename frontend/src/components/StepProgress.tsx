import React from 'react';
import {
  FileText,
  UserCheck,
  Search,
  CheckCircle2,
  AlertTriangle,
  Zap,
  GraduationCap,
} from 'lucide-react';
import { AppStep } from '../types';
import { useCareerLens } from '../context/CareerLensContext';

interface StepDef {
  key: AppStep;
  label: string;
  shortLabel: string;
  icon: React.ElementType;
}

const STEPS: StepDef[] = [
  { key: 'upload', label: '1. Upload Resume', shortLabel: 'Upload', icon: FileText },
  { key: 'profile', label: '2. Your Profile', shortLabel: 'Profile', icon: UserCheck },
  { key: 'jobs', label: '3. Find Jobs', shortLabel: 'Jobs', icon: Search },
  { key: 'matches', label: '4. Match Analysis', shortLabel: 'Matches', icon: CheckCircle2 },
  { key: 'gaps', label: '5. Skill Gaps', shortLabel: 'Gaps', icon: AlertTriangle },
  { key: 'what-if', label: '6. What-If Simulator', shortLabel: 'What-If', icon: Zap },
  { key: 'learning', label: '7. Learn Resources', shortLabel: 'Learn', icon: GraduationCap },
];

export const StepProgress: React.FC = () => {
  const { currentStep, setCurrentStep, resumeId, searchId, matchSummary, skillGaps } = useCareerLens();

  const stepOrder = STEPS.map((s) => s.key);
  const currentIndex = stepOrder.indexOf(currentStep);

  const isAccessible = (stepKey: AppStep): boolean => {
    if (stepKey === 'upload') return true;
    if (stepKey === 'profile') return !!resumeId;
    if (stepKey === 'jobs') return !!resumeId;
    if (stepKey === 'matches') return !!resumeId && !!searchId;
    if (stepKey === 'gaps') return !!resumeId && !!searchId;
    if (stepKey === 'what-if') return !!resumeId && !!searchId && !!matchSummary;
    if (stepKey === 'learning') return !!resumeId && (!!skillGaps.length || !!searchId);
    return false;
  };

  return (
    <nav aria-label="Progress" className="w-full bg-slate-900/60 border-b border-slate-800/80 px-4 py-3 overflow-x-auto">
      <div className="max-w-7xl mx-auto flex items-center justify-between min-w-[640px] lg:min-w-0">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const isActive = currentStep === step.key;
          const isPassed = idx < currentIndex;
          const canClick = isAccessible(step.key);

          return (
            <React.Fragment key={step.key}>
              <button
                type="button"
                disabled={!canClick}
                onClick={() => canClick && setCurrentStep(step.key)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all group ${
                  isActive
                    ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/25 ring-2 ring-brand-400/30'
                    : isPassed
                    ? 'bg-slate-800/80 text-emerald-400 hover:bg-slate-800'
                    : canClick
                    ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    : 'text-slate-600 cursor-not-allowed opacity-50'
                }`}
              >
                <span
                  className={`flex items-center justify-center w-5 h-5 rounded-md text-[11px] ${
                    isActive
                      ? 'bg-white/20 text-white'
                      : isPassed
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                </span>
                <span className="whitespace-nowrap">
                  <span className="hidden md:inline">{step.label}</span>
                  <span className="md:hidden">{step.shortLabel}</span>
                </span>
              </button>

              {idx < STEPS.length - 1 && (
                <div
                  className={`h-[1px] flex-1 mx-1.5 transition-colors hidden sm:block ${
                    idx < currentIndex ? 'bg-emerald-500/40' : 'bg-slate-800'
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </nav>
  );
};
