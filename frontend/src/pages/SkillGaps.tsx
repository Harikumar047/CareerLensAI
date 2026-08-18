import React, { useEffect, useState } from 'react';
import {
  Flame,
  Zap,
  GraduationCap,
  ArrowRight,
  Loader2,
  CheckCircle,
} from 'lucide-react';
import { useCareerLens } from '../context/CareerLensContext';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';

export const SkillGaps: React.FC = () => {
  const {
    resumeId,
    searchId,
    skillGaps,
    setSkillGaps,
    setCurrentStep,
  } = useCareerLens();

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (resumeId && searchId && skillGaps.length === 0) {
      fetchGaps();
    }
  }, [resumeId, searchId]);

  const fetchGaps = async () => {
    if (!resumeId || !searchId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.getSkillGaps(resumeId, searchId);
      setSkillGaps(res.skill_gaps);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze skill gaps across target jobs.');
    } finally {
      setIsLoading(false);
    }
  };

  const getPriorityTheme = (priority: 'HIGH' | 'MEDIUM' | 'LOW') => {
    switch (priority) {
      case 'HIGH':
        return {
          badge: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
          bar: 'bg-gradient-to-r from-rose-500 to-amber-500',
          text: 'text-rose-400',
          card: 'border-rose-500/20 bg-rose-950/10',
        };
      case 'MEDIUM':
        return {
          badge: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
          bar: 'bg-gradient-to-r from-amber-500 to-cyan-500',
          text: 'text-amber-400',
          card: 'border-amber-500/20 bg-amber-950/10',
        };
      default:
        return {
          badge: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
          bar: 'bg-slate-600',
          text: 'text-slate-400',
          card: 'border-slate-800 bg-slate-900/40',
        };
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 mb-8 shadow-xl backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs font-semibold uppercase tracking-wider mb-2">
              <Flame className="w-3.5 h-3.5 text-rose-400" />
              Aggregated Market Demand
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white mb-1">
              High-Impact Skill Gaps
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 max-w-xl">
              Skills most frequently required by your target jobs that are not yet detected on your resume.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setCurrentStep('learning')}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white font-bold text-xs sm:text-sm flex items-center gap-2 shadow-lg shadow-emerald-500/20 transition-all hover:scale-[1.02]"
            >
              <GraduationCap className="w-4 h-4" />
              <span>Get Learning Resources</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <ErrorAlert message={error} onDismiss={() => setError(null)} />

      {/* Loading state */}
      {isLoading ? (
        <div className="text-center py-20">
          <Loader2 className="w-10 h-10 text-brand-400 animate-spin mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Aggregating skill frequencies from target jobs...</p>
        </div>
      ) : skillGaps.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {skillGaps.map((gap, idx) => {
            const theme = getPriorityTheme(gap.priority);

            return (
              <div
                key={idx}
                className={`rounded-2xl border p-5 flex flex-col justify-between shadow-md transition-all hover:scale-[1.01] ${theme.card}`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[11px] font-extrabold tracking-wider border ${theme.badge}`}
                    >
                      {gap.priority} PRIORITY
                    </span>
                    <span className="text-xs text-slate-400 font-semibold">
                      {gap.percentage}% of jobs
                    </span>
                  </div>

                  <h3 className="text-xl font-bold text-white mb-2">{gap.skill}</h3>

                  <p className="text-xs text-slate-300 mb-4">
                    Required or preferred in <strong className="text-white">{gap.jobs_affected}</strong> active job posting
                    {gap.jobs_affected === 1 ? '' : 's'}.
                  </p>

                  {/* Progress Bar */}
                  <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden mb-5 border border-slate-800">
                    <div
                      className={`h-full rounded-full ${theme.bar}`}
                      style={{ width: `${Math.min(100, gap.percentage)}%` }}
                    />
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                  <button
                    onClick={() => setCurrentStep('what-if')}
                    className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                  >
                    <Zap className="w-3.5 h-3.5" />
                    <span>Simulate</span>
                  </button>

                  <button
                    onClick={() => setCurrentStep('learning')}
                    className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                  >
                    <GraduationCap className="w-3.5 h-3.5" />
                    <span>Learn Course</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-16 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
          <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white mb-1">No significant skill gaps found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto mb-4">
            Your candidate profile matches the primary skills requested across these jobs.
          </p>
          <button
            onClick={() => setCurrentStep('matches')}
            className="px-4 py-2 rounded-xl bg-brand-500 text-white text-xs font-bold shadow"
          >
            Review Job Matches
          </button>
        </div>
      )}
    </div>
  );
};
