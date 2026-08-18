import React, { useEffect, useState } from 'react';
import {
  GraduationCap,
  Play,
  ExternalLink,
  BookOpen,
  Loader2,
} from 'lucide-react';
import { useCareerLens } from '../context/CareerLensContext';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';
import { LearningResourceItem } from '../types';

export const LearningHub: React.FC = () => {
  const { resumeId, searchId, skillGaps } = useCareerLens();
  const [resources, setResources] = useState<LearningResourceItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [freeOnly, setFreeOnly] = useState(false);
  const [activeSkillFilter, setActiveSkillFilter] = useState<string>('all');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRecommendations();
  }, [resumeId, searchId, freeOnly]);

  const fetchRecommendations = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Gather top skills from skill gaps if available
      const targetSkills = skillGaps.length > 0 ? skillGaps.map((g) => g.skill) : undefined;
      const res = await api.getCourseRecommendations(
        resumeId || undefined,
        searchId || undefined,
        targetSkills,
        freeOnly,
        3
      );
      setResources(res.recommendations || []);
    } catch (err: any) {
      setError(err.message || 'Failed to discover dynamic learning resources.');
    } finally {
      setIsLoading(false);
    }
  };

  // Distinct skill list for filter tabs
  const distinctSkills = Array.from(new Set(resources.map((r) => r.skill)));

  const filteredResources =
    activeSkillFilter === 'all'
      ? resources
      : resources.filter((r) => r.skill.toLowerCase() === activeSkillFilter.toLowerCase());

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 mb-8 shadow-xl backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-emerald-300 text-xs font-semibold uppercase tracking-wider mb-2">
              <GraduationCap className="w-3.5 h-3.5 text-emerald-400" />
              Dynamic Learning Resource Hub
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white mb-1">
              Curated Courses for Your Skill Gaps
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 max-w-xl">
              Real tutorials, official playlists, and verified courses discovered directly for your high-priority missing skills.
            </p>
          </div>

          {/* Free-Only Filter Toggle */}
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer bg-slate-950 px-4 py-2 rounded-xl border border-slate-800 text-xs text-slate-300 hover:border-slate-700 transition-colors">
              <input
                type="checkbox"
                checked={freeOnly}
                onChange={(e) => setFreeOnly(e.target.checked)}
                className="w-4 h-4 rounded text-emerald-500 bg-slate-900 border-slate-700 focus:ring-emerald-500"
              />
              <span className="font-semibold">Free Resources Only</span>
            </label>
          </div>
        </div>

        {/* Skill Filter Tabs */}
        {distinctSkills.length > 1 && (
          <div className="flex flex-wrap items-center gap-2 mt-6 pt-5 border-t border-slate-800/80">
            <button
              onClick={() => setActiveSkillFilter('all')}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                activeSkillFilter === 'all'
                  ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/25'
                  : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              All Skills ({resources.length})
            </button>
            {distinctSkills.map((skill) => (
              <button
                key={skill}
                onClick={() => setActiveSkillFilter(skill)}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                  activeSkillFilter === skill
                    ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/25'
                    : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                {skill}
              </button>
            ))}
          </div>
        )}
      </div>

      <ErrorAlert message={error} onDismiss={() => setError(null)} />

      {/* Loading state */}
      {isLoading ? (
        <div className="text-center py-24">
          <Loader2 className="w-10 h-10 text-emerald-400 animate-spin mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Discovering verified learning resources...</p>
        </div>
      ) : filteredResources.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredResources.map((res, idx) => {
            const isYouTube = res.resource_type?.toLowerCase() === 'youtube';

            return (
              <div
                key={idx}
                className="bg-slate-900/85 hover:bg-slate-900 rounded-2xl border border-slate-800 p-5 flex flex-col justify-between transition-all hover:border-slate-700 shadow-md group relative overflow-hidden"
              >
                <div>
                  {/* Top Badges */}
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-extrabold">
                      {res.skill}
                    </span>

                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-semibold uppercase">
                        {res.level || 'Beginner'}
                      </span>
                      {res.free ? (
                        <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-extrabold">
                          FREE
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-semibold">
                          PAID
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Thumbnail if available */}
                  {res.thumbnail && (
                    <div className="w-full h-36 rounded-xl bg-slate-950 overflow-hidden mb-3 border border-slate-800/80 relative">
                      <img
                        src={res.thumbnail}
                        alt={res.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = 'none';
                        }}
                      />
                      {isYouTube && (
                        <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/80 text-[10px] font-bold text-white flex items-center gap-1">
                          <Play className="w-3 h-3 text-red-500 fill-red-500" />
                          YouTube
                        </div>
                      )}
                    </div>
                  )}

                  {/* Title & Provider */}
                  <h3 className="font-bold text-white text-sm leading-snug group-hover:text-emerald-300 transition-colors mb-1 line-clamp-2">
                    {res.title}
                  </h3>
                  <p className="text-xs text-slate-400 font-medium mb-3">
                    by <span className="text-slate-300">{res.provider}</span>
                  </p>

                  <p className="text-xs text-slate-400 leading-relaxed line-clamp-2 mb-4">
                    {res.description}
                  </p>
                </div>

                {/* Open URL Button */}
                <div className="pt-3 border-t border-slate-800/80">
                  <a
                    href={res.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`w-full py-2.5 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-md ${
                      isYouTube
                        ? 'bg-red-600/90 hover:bg-red-600 text-white shadow-red-600/20'
                        : 'bg-brand-600/90 hover:bg-brand-600 text-white shadow-brand-600/20'
                    }`}
                  >
                    {isYouTube ? (
                      <>
                        <Play className="w-3.5 h-3.5 fill-current" />
                        <span>WATCH ON YOUTUBE</span>
                      </>
                    ) : (
                      <>
                        <GraduationCap className="w-3.5 h-3.5" />
                        <span>VIEW ON COURSERA</span>
                      </>
                    )}
                    <ExternalLink className="w-3.5 h-3.5 ml-auto opacity-70" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-20 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
          <BookOpen className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white mb-1">No learning resources found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto mb-4">
            Try turning off the "Free Resources Only" filter or search across more job opportunities.
          </p>
          <button
            onClick={() => {
              setFreeOnly(false);
              fetchRecommendations();
            }}
            className="px-4 py-2 rounded-xl bg-emerald-500 text-white text-xs font-bold shadow"
          >
            Reset Filters
          </button>
        </div>
      )}
    </div>
  );
};
