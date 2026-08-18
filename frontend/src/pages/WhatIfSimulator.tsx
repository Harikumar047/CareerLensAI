import React, { useState, useEffect } from 'react';
import {
  Zap,
  TrendingUp,
  Plus,
  Check,
  ArrowRight,
  Loader2,
  Sparkles,
  GraduationCap,
} from 'lucide-react';
import { useCareerLens } from '../context/CareerLensContext';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';
import { Job, WhatIfResponse } from '../types';

export const WhatIfSimulator: React.FC = () => {
  const {
    resumeId,
    jobs,
    matchSummary,
    selectedJobForWhatIf,
    setSelectedJobForWhatIf,
    setCurrentStep,
  } = useCareerLens();

  const [selectedJob, setSelectedJob] = useState<Job | null>(
    selectedJobForWhatIf || (jobs.length > 0 ? jobs[0] : null)
  );

  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [customSkill, setCustomSkill] = useState('');
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState<WhatIfResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Get missing skills for currently selected job from matchSummary
  const currentMatch = matchSummary?.matches.find((m) => m.job_id === selectedJob?.id);
  const availableMissingSkills = currentMatch
    ? Array.from(
        new Set([...currentMatch.missing_required_skills, ...currentMatch.missing_preferred_skills])
      )
    : ['AWS', 'Docker', 'Kubernetes', 'FastAPI', 'React', 'SQL'];

  useEffect(() => {
    if (selectedJobForWhatIf) {
      setSelectedJob(selectedJobForWhatIf);
    }
  }, [selectedJobForWhatIf]);

  // When job changes, clear simulation
  const handleJobChange = (jobId: string) => {
    const job = jobs.find((j) => j.id === jobId) || null;
    setSelectedJob(job);
    setSelectedJobForWhatIf(job);
    setSelectedSkills([]);
    setSimulationResult(null);
  };

  const toggleSkill = (skill: string) => {
    if (selectedSkills.includes(skill)) {
      setSelectedSkills(selectedSkills.filter((s) => s !== skill));
    } else {
      setSelectedSkills([...selectedSkills, skill]);
    }
  };

  const handleAddCustomSkill = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = customSkill.trim();
    if (clean && !selectedSkills.includes(clean)) {
      setSelectedSkills([...selectedSkills, clean]);
      setCustomSkill('');
    }
  };

  const handleRunSimulation = async () => {
    if (!resumeId || !selectedJob) {
      setError('Please select an active resume and target job first.');
      return;
    }

    setIsSimulating(true);
    setError(null);

    try {
      const res = await api.simulateWhatIf({
        resume_id: resumeId,
        job_id: selectedJob.id,
        skills_to_add: selectedSkills,
      });
      setSimulationResult(res);
    } catch (err: any) {
      setError(err.message || 'Simulation failed. Please try again.');
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 mb-8 shadow-xl backdrop-blur-md relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/25 text-cyan-300 text-xs font-semibold uppercase tracking-wider mb-3 w-fit">
          <Zap className="w-3.5 h-3.5 text-cyan-400" />
          Headline Feature • What-If Simulator
        </div>

        <h1 className="text-2xl sm:text-4xl font-extrabold text-white mb-2">
          Simulate Skill Acquisition
        </h1>
        <p className="text-sm text-slate-300 max-w-2xl">
          See the exact mathematical increase in your <strong>Job Fit Score</strong> before spending weeks learning a new skill.
          Stored resume remains 100% untouched.
        </p>
      </div>

      <ErrorAlert message={error} onDismiss={() => setError(null)} />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Job Selector & Skill Toggles */}
        <div className="lg:col-span-5 space-y-6">
          {/* Target Job Picker */}
          <div className="bg-slate-900/80 rounded-2xl border border-slate-800 p-5 shadow-md">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              1. Select Target Job
            </label>

            {jobs.length > 0 ? (
              <select
                value={selectedJob?.id || ''}
                onChange={(e) => handleJobChange(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
              >
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title} — {j.company} ({j.location})
                  </option>
                ))}
              </select>
            ) : (
              <p className="text-xs text-slate-400">No jobs loaded. Search jobs in Step 3 first.</p>
            )}

            {selectedJob && (
              <div className="mt-3 p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs space-y-1">
                <span className="font-semibold text-white block">{selectedJob.title}</span>
                <span className="text-slate-400 block">{selectedJob.company} • {selectedJob.location}</span>
                {currentMatch && (
                  <span className="inline-block mt-1 font-bold text-cyan-400">
                    Current Baseline Fit: {currentMatch.fit_score}%
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Skill Selector */}
          <div className="bg-slate-900/80 rounded-2xl border border-slate-800 p-5 shadow-md">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
              2. Choose Skills to Learn & Simulate
            </label>
            <p className="text-xs text-slate-400 mb-4">
              Toggle missing requirements or add any custom technology.
            </p>

            <div className="flex flex-wrap gap-2 mb-4">
              {availableMissingSkills.map((skill) => {
                const isSelected = selectedSkills.includes(skill);
                return (
                  <button
                    key={skill}
                    type="button"
                    onClick={() => toggleSkill(skill)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                      isSelected
                        ? 'bg-cyan-500 text-white shadow-md shadow-cyan-500/25 ring-2 ring-cyan-400/30'
                        : 'bg-slate-950 text-slate-300 border border-slate-700 hover:border-slate-500'
                    }`}
                  >
                    {isSelected ? <Check className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5 text-slate-500" />}
                    <span>{skill}</span>
                  </button>
                );
              })}
            </div>

            {/* Custom Skill Input */}
            <form onSubmit={handleAddCustomSkill} className="flex gap-2">
              <input
                type="text"
                value={customSkill}
                onChange={(e) => setCustomSkill(e.target.value)}
                placeholder="Add other skill (e.g. Next.js)..."
                className="flex-1 bg-slate-950 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <button
                type="submit"
                className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold"
              >
                Add
              </button>
            </form>

            {/* Run Button */}
            <button
              onClick={handleRunSimulation}
              disabled={isSimulating || !selectedJob}
              className="w-full mt-5 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-brand-500 hover:from-cyan-600 hover:to-brand-600 text-white font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/25 transition-all disabled:opacity-50"
            >
              {isSimulating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Computing Live Multi-Factor Score...</span>
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  <span>Run Simulation ({selectedSkills.length} selected)</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Column: Simulation Result Display */}
        <div className="lg:col-span-7">
          {simulationResult ? (
            <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 sm:p-8 shadow-2xl backdrop-blur-md animate-in fade-in zoom-in-95 duration-200">
              <div className="flex items-center justify-between pb-6 border-b border-slate-800 mb-6">
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 block mb-1">
                    Simulation Complete
                  </span>
                  <h3 className="text-xl font-bold text-white">Projected Score Impact</h3>
                </div>

                {simulationResult.improvement > 0 && (
                  <div className="px-3.5 py-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-extrabold text-sm flex items-center gap-1 shadow-sm">
                    <TrendingUp className="w-4 h-4" />
                    <span>+{simulationResult.improvement} Points</span>
                  </div>
                )}
              </div>

              {/* Big Score Cards */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="p-5 rounded-2xl bg-slate-950/80 border border-slate-800 text-center">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Current Fit
                  </span>
                  <span className="text-4xl font-extrabold text-slate-300">
                    {simulationResult.current_score}%
                  </span>
                </div>

                <div className="p-5 rounded-2xl bg-cyan-950/20 border border-cyan-500/40 text-center relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-tr from-cyan-500/10 to-transparent pointer-events-none" />
                  <span className="text-xs font-semibold text-cyan-300 uppercase tracking-wider block mb-1">
                    Simulated Fit
                  </span>
                  <span className="text-4xl font-extrabold text-cyan-400">
                    {simulationResult.simulated_score}%
                  </span>
                </div>
              </div>

              {/* Explanation Banner */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs sm:text-sm text-slate-300 mb-6 leading-relaxed flex items-start gap-3">
                <Sparkles className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-white block mb-0.5">Analysis Insight</span>
                  {simulationResult.explanation}
                </div>
              </div>

              {/* Skills Breakdown */}
              <div className="space-y-4 mb-8 text-xs">
                {simulationResult.newly_matched_skills.length > 0 && (
                  <div>
                    <span className="font-bold text-emerald-400 block mb-2">
                      ✓ Newly Matched Requirements ({simulationResult.newly_matched_skills.length})
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {simulationResult.newly_matched_skills.map((s, i) => (
                        <span
                          key={i}
                          className="px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/25 font-semibold"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {simulationResult.remaining_gaps.length > 0 && (
                  <div>
                    <span className="font-bold text-rose-400 block mb-2">
                      ✗ Remaining Skill Gaps ({simulationResult.remaining_gaps.length})
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {simulationResult.remaining_gaps.map((s, i) => (
                        <span
                          key={i}
                          className="px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-300 border border-rose-500/20 font-medium"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Learning CTA */}
              <button
                onClick={() => setCurrentStep('learning')}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/25 transition-all hover:scale-[1.01]"
              >
                <GraduationCap className="w-4 h-4" />
                <span>Start Learning These Skills Now</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="h-full min-h-[380px] rounded-2xl border-2 border-dashed border-slate-800 bg-slate-900/30 flex flex-col items-center justify-center p-8 text-center">
              <Zap className="w-12 h-12 text-slate-600 mb-3" />
              <h3 className="text-base font-bold text-slate-300 mb-1">
                No Simulation Executed Yet
              </h3>
              <p className="text-xs text-slate-500 max-w-sm">
                Select your target job on the left, pick the missing skills you're interested in learning, and hit <strong>Run Simulation</strong>.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
