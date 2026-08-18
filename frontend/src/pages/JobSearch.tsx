import React, { useState } from 'react';
import {
  Search,
  MapPin,
  Briefcase,
  ExternalLink,
  DollarSign,
  Loader2,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { useCareerLens } from '../context/CareerLensContext';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';

export const JobSearch: React.FC = () => {
  const {
    resumeId,
    searchQuery,
    setSearchQuery,
    jobs,
    setJobs,
    setSearchId,
    setMatchSummary,
    setCurrentStep,
  } = useCareerLens();

  const [role, setRole] = useState(searchQuery.role);
  const [location, setLocation] = useState(searchQuery.location);
  const [isSearching, setIsSearching] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!role.trim()) {
      setError('Please enter a target role or keyword.');
      return;
    }

    setIsSearching(true);
    setError(null);

    try {
      setSearchQuery({ role, location });
      const res = await api.searchJobs(role, location, 1);
      setJobs(res.jobs);
      if (res.search_id) {
        setSearchId(res.search_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch live job search results. Please check parameters and try again.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleAnalyzeMatch = async () => {
    if (!resumeId) {
      setError('No active resume found. Please upload a resume first.');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      // Perform search analysis
      const res = await api.searchJobs(role, location, 1);
      setJobs(res.jobs);
      if (res.search_id) {
        setSearchId(res.search_id);
        const matchRes = await api.analyzeSearch(resumeId, res.search_id);
        setMatchSummary(matchRes);
        setCurrentStep('matches');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to analyze matching scores for these jobs.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const formatSalary = (min?: number | null, max?: number | null): string | null => {
    if (!min && !max) return null;
    if (min && max) return `₹${min.toLocaleString()} – ₹${max.toLocaleString()}`;
    if (min) return `From ₹${min.toLocaleString()}`;
    if (max) return `Up to ₹${max.toLocaleString()}`;
    return null;
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 animate-in fade-in duration-200">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto mb-8">
        <h1 className="text-3xl font-extrabold text-white mb-2">
          Discover Live Opportunities
        </h1>
        <p className="text-sm text-slate-400">
          Query real-time job openings from Adzuna across Indian tech hubs or remote roles.
        </p>
      </div>

      <ErrorAlert message={error} onDismiss={() => setError(null)} />

      {/* Search Form */}
      <form
        onSubmit={handleSearch}
        className="bg-slate-900/90 rounded-2xl border border-slate-800 p-4 sm:p-6 mb-8 shadow-xl backdrop-blur-md"
      >
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-4">
          <div className="sm:col-span-6 relative">
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Target Job Role / Keywords
            </label>
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. Software Engineer, Backend Developer, Python"
                className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
              />
            </div>
          </div>

          <div className="sm:col-span-4 relative">
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              Location / City
            </label>
            <div className="relative">
              <MapPin className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Bangalore, Chennai, Hyderabad, Remote"
                className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
              />
            </div>
          </div>

          <div className="sm:col-span-2 flex items-end">
            <button
              type="submit"
              disabled={isSearching || isAnalyzing}
              className="w-full bg-brand-500 hover:bg-brand-600 text-white font-bold text-sm py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-brand-500/25 transition-all disabled:opacity-50"
            >
              {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              <span>Search</span>
            </button>
          </div>
        </div>
      </form>

      {/* Results Header with Match Action */}
      {jobs.length > 0 && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6 p-4 rounded-xl bg-brand-950/40 border border-brand-800/40">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-brand-400 block mb-0.5">
              Live Results
            </span>
            <p className="text-sm text-slate-200">
              Found <strong className="text-white">{jobs.length}</strong> active postings matching "
              {searchQuery.role}" in "{searchQuery.location}".
            </p>
          </div>

          <button
            onClick={handleAnalyzeMatch}
            disabled={isAnalyzing}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-brand-500 to-cyan-500 hover:from-brand-600 hover:to-cyan-600 text-white font-bold text-xs sm:text-sm flex items-center gap-2 shadow-lg shadow-brand-500/25 transition-all hover:scale-[1.02] disabled:opacity-50"
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Calculating Fit Scores...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Analyze Alignment with My Resume</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      )}

      {/* Job Cards */}
      {isSearching ? (
        <div className="text-center py-16">
          <Loader2 className="w-10 h-10 text-brand-400 animate-spin mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Querying live Adzuna job listings...</p>
        </div>
      ) : jobs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {jobs.map((job) => {
            const salaryText = formatSalary(job.salary_min, job.salary_max);

            return (
              <div
                key={job.id}
                className="bg-slate-900/80 hover:bg-slate-900 rounded-2xl border border-slate-800/90 p-5 flex flex-col justify-between transition-all hover:border-slate-700 shadow-md group"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <h3 className="font-bold text-white text-base leading-snug group-hover:text-brand-300 transition-colors">
                      {job.title}
                    </h3>
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white hover:bg-brand-600 transition-all shrink-0"
                      title="Open job posting"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-400 mb-3">
                    <span className="font-medium text-slate-300 flex items-center gap-1">
                      <Briefcase className="w-3 h-3 text-brand-400" />
                      {job.company || 'Direct Employer'}
                    </span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3 h-3 text-slate-400" />
                      {job.location}
                    </span>
                    {salaryText && (
                      <>
                        <span>•</span>
                        <span className="flex items-center gap-1 text-emerald-400 font-medium">
                          <DollarSign className="w-3 h-3" />
                          {salaryText}
                        </span>
                      </>
                    )}
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed line-clamp-3 mb-4">
                    {job.description}
                  </p>
                </div>

                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-slate-500">
                    Source: {job.source.toUpperCase()}
                  </span>

                  <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors"
                  >
                    <span>Apply</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-16 bg-slate-900/40 rounded-2xl border border-slate-800/60 p-8">
          <Briefcase className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-300 mb-1">No jobs searched yet</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mb-4">
            Enter your preferred role and city above to pull live postings from our job index.
          </p>
          <button
            onClick={() => handleSearch()}
            className="px-4 py-2 rounded-xl bg-brand-500 text-white text-xs font-bold shadow"
          >
            Search Example Software Engineer Jobs
          </button>
        </div>
      )}
    </div>
  );
};
