import React, { useState } from 'react';
import {
  Zap,
  ArrowRight,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Info,
} from 'lucide-react';
import { useCareerLens } from '../context/CareerLensContext';
import { JobMatchResult, Job } from '../types';

export const MatchResults: React.FC = () => {
  const {
    jobs,
    matchSummary,
    setSelectedJobForWhatIf,
    setCurrentStep,
  } = useCareerLens();

  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);

  if (!matchSummary || !matchSummary.matches || matchSummary.matches.length === 0) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-400 mb-4">No match analysis found for this session.</p>
        <button
          onClick={() => setCurrentStep('jobs')}
          className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm font-semibold"
        >
          Back to Job Search
        </button>
      </div>
    );
  }

  const getJobDetails = (jobId: string): Job | undefined => {
    return jobs.find((j) => j.id === jobId);
  };

  const getCategoryBadge = (match: JobMatchResult) => {
    if (!match.eligible) {
      return {
        label: 'Not Recommended',
        color: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
        dot: 'bg-rose-400',
      };
    }
    if (match.fit_score >= 75) {
      return {
        label: 'Strong Match',
        color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        dot: 'bg-emerald-400',
      };
    }
    if (match.fit_score >= 50) {
      return {
        label: 'Good Match',
        color: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
        dot: 'bg-cyan-400',
      };
    }
    return {
      label: 'Needs Improvement',
      color: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      dot: 'bg-amber-400',
    };
  };

  const handleTriggerWhatIf = (jobId: string) => {
    const jobObj = getJobDetails(jobId) || {
      id: jobId,
      title: 'Target Job',
      company: 'Employer',
      location: 'India',
      description: '',
      source: 'adzuna',
      url: '#',
    };
    setSelectedJobForWhatIf(jobObj);
    setCurrentStep('what-if');
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 animate-in fade-in duration-200">
      {/* Header Overview Banner */}
      <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 mb-8 shadow-xl backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-400 block mb-1">
              Match Intelligence
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white mb-2">
              Ranked Job Alignment Results
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 max-w-xl">
              Evaluated <strong className="text-white">{matchSummary.total_jobs}</strong> live jobs against your profile.
              Found <strong className="text-emerald-400">{matchSummary.strong_matches}</strong> strong matches and{' '}
              <strong className="text-cyan-400">{matchSummary.eligible_jobs}</strong> eligible positions.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setCurrentStep('gaps')}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-brand-600 hover:from-purple-700 hover:to-brand-700 text-white font-bold text-xs sm:text-sm flex items-center gap-2 shadow-lg shadow-brand-500/20 transition-all hover:scale-[1.02]"
            >
              <span>View Aggregated Skill Gaps</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Disclaimer Alert */}
        <div className="mt-4 p-3 rounded-xl bg-slate-950/60 border border-slate-800 flex items-start gap-2.5 text-xs text-slate-400">
          <Info className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
          <span>
            <strong>Transparency Notice:</strong> Job Fit Score represents technical alignment between your demonstrated profile and stated employer requirements. It does not represent or guarantee a recruiter shortlisting probability.
          </span>
        </div>
      </div>

      {/* Match Cards List */}
      <div className="space-y-4">
        {matchSummary.matches.map((match, idx) => {
          const job = getJobDetails(match.job_id);
          const badge = getCategoryBadge(match);
          const isExpanded = expandedJobId === match.job_id;

          return (
            <div
              key={match.job_id}
              className="bg-slate-900/85 rounded-2xl border border-slate-800 p-5 sm:p-6 transition-all hover:border-slate-700 shadow-md"
            >
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                {/* Left: Job & Company */}
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <span className="text-xs font-bold text-slate-500">#{idx + 1}</span>
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badge.color}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                      {badge.label}
                    </span>
                    {job?.location && (
                      <span className="text-xs text-slate-400">• {job.location}</span>
                    )}
                  </div>

                  <h3 className="text-lg font-bold text-white mb-1">
                    {job?.title || `Job ID: ${match.job_id}`}
                  </h3>
                  <p className="text-xs text-slate-400 font-medium mb-3">
                    {job?.company || 'Employer'}
                  </p>

                  {/* Skills quick chips */}
                  <div className="flex flex-wrap items-center gap-1.5">
                    {match.matched_skills.slice(0, 4).map((s, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-[11px] font-medium"
                      >
                        ✓ {s}
                      </span>
                    ))}
                    {match.missing_required_skills.slice(0, 3).map((s, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 text-[11px] font-medium"
                      >
                        ✗ {s}
                      </span>
                    ))}
                    {(match.matched_skills.length + match.missing_required_skills.length > 7) && (
                      <span className="text-[11px] text-slate-500">
                        +{match.matched_skills.length + match.missing_required_skills.length - 7} more
                      </span>
                    )}
                  </div>
                </div>

                {/* Right: Score & Actions */}
                <div className="flex flex-row lg:flex-col items-center lg:items-end justify-between lg:justify-center gap-4 pt-3 lg:pt-0 border-t lg:border-t-0 border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
                        Fit Score
                      </span>
                      <span
                        className={`text-2xl sm:text-3xl font-extrabold ${
                          match.fit_score >= 75
                            ? 'text-emerald-400'
                            : match.fit_score >= 50
                            ? 'text-cyan-400'
                            : 'text-amber-400'
                        }`}
                      >
                        {match.fit_score}%
                      </span>
                    </div>

                    {/* Radial or Visual Bar */}
                    <div className="w-12 h-12 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center">
                      <TrendingUp
                        className={`w-6 h-6 ${
                          match.fit_score >= 75
                            ? 'text-emerald-400'
                            : match.fit_score >= 50
                            ? 'text-cyan-400'
                            : 'text-amber-400'
                        }`}
                      />
                    </div>
                  </div>

                  {/* Buttons */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleTriggerWhatIf(match.job_id)}
                      className="px-3.5 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-bold flex items-center gap-1.5 transition-all"
                    >
                      <Zap className="w-3.5 h-3.5 text-cyan-400" />
                      <span>What if I learn...?</span>
                    </button>

                    <button
                      onClick={() => setExpandedJobId(isExpanded ? null : match.job_id)}
                      className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition-colors"
                      title="Toggle breakdown details"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>

              {/* Collapsible Breakdown Details */}
              {isExpanded && (
                <div className="mt-5 pt-5 border-t border-slate-800/80 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs animate-in fade-in duration-150">
                  {/* Subscores */}
                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                    <span className="font-semibold text-slate-300 block mb-2">Score Breakdown</span>
                    <div className="flex justify-between text-slate-400">
                      <span>Required Skills (40%)</span>
                      <span className="text-white font-medium">{match.required_skill_score}%</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Preferred Skills (15%)</span>
                      <span className="text-white font-medium">{match.preferred_skill_score}%</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Projects Alignment (15%)</span>
                      <span className="text-white font-medium">{match.project_score}%</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Experience Fit (15%)</span>
                      <span className="text-white font-medium">{match.experience_score}%</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>Education Fit (10%)</span>
                      <span className="text-white font-medium">{match.education_score}%</span>
                    </div>
                  </div>

                  {/* Narrative Strengths & Gaps */}
                  <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3">
                    {match.strengths.length > 0 && (
                      <div>
                        <span className="font-semibold text-emerald-400 block mb-1">Key Strengths</span>
                        <ul className="space-y-1 text-slate-300">
                          {match.strengths.map((st, i) => (
                            <li key={i}>• {st}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {match.gaps.length > 0 && (
                      <div>
                        <span className="font-semibold text-rose-400 block mb-1">Identified Gaps</span>
                        <ul className="space-y-1 text-slate-300">
                          {match.gaps.map((gp, i) => (
                            <li key={i}>• {gp}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
