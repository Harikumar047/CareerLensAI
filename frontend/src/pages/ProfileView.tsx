import React from 'react';
import {
  User,
  Mail,
  Phone,
  MapPin,
  GraduationCap,
  Briefcase,
  FolderGit2,
  Award,
  ArrowRight,
  Code2,
} from 'lucide-react';
import { useCareerLens } from '../context/CareerLensContext';

export const ProfileView: React.FC = () => {
  const { profile, setCurrentStep } = useCareerLens();

  if (!profile) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-400 mb-4">No resume profile extracted yet.</p>
        <button
          onClick={() => setCurrentStep('upload')}
          className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm font-semibold"
        >
          Upload Resume
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 sm:p-8 mb-8 shadow-xl backdrop-blur-md">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-brand-600 to-cyan-500 p-[1px]">
              <div className="w-full h-full bg-slate-950 rounded-[15px] flex items-center justify-center text-brand-400 font-bold text-2xl">
                {profile.name ? profile.name.charAt(0).toUpperCase() : <User className="w-7 h-7" />}
              </div>
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white">
                {profile.name || 'Candidate Profile'}
              </h1>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-2 text-xs sm:text-sm text-slate-400">
                {profile.email && (
                  <span className="flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5 text-brand-400" />
                    {profile.email}
                  </span>
                )}
                {profile.phone && (
                  <span className="flex items-center gap-1.5">
                    <Phone className="w-3.5 h-3.5 text-brand-400" />
                    {profile.phone}
                  </span>
                )}
                {profile.location && (
                  <span className="flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-brand-400" />
                    {profile.location}
                  </span>
                )}
                {profile.total_experience_years !== null && profile.total_experience_years !== undefined && (
                  <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-xs">
                    {profile.total_experience_years} Year{profile.total_experience_years === 1 ? '' : 's'} Exp
                  </span>
                )}
              </div>
            </div>
          </div>

          <button
            onClick={() => setCurrentStep('jobs')}
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-brand-500 to-cyan-500 hover:from-brand-600 hover:to-cyan-600 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-brand-500/25 transition-all hover:scale-[1.02]"
          >
            <span>Proceed to Find Jobs</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Skills & Certifications */}
        <div className="space-y-6">
          {/* Extracted Skills */}
          <div className="bg-slate-900/80 rounded-2xl border border-slate-800 p-6 shadow-md">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-brand-500/10 text-brand-400 flex items-center justify-center">
                <Code2 className="w-4 h-4" />
              </div>
              <h2 className="text-base font-bold text-white">
                Extracted Skills ({profile.skills.length})
              </h2>
            </div>

            {profile.skills.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {profile.skills.map((skill, i) => (
                  <span
                    key={i}
                    className="px-3 py-1.5 rounded-lg bg-brand-500/10 text-brand-300 border border-brand-500/20 text-xs font-semibold"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No specific skill keywords parsed.</p>
            )}
          </div>

          {/* Certifications */}
          {profile.certifications && profile.certifications.length > 0 && (
            <div className="bg-slate-900/80 rounded-2xl border border-slate-800 p-6 shadow-md">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center">
                  <Award className="w-4 h-4" />
                </div>
                <h2 className="text-base font-bold text-white">Certifications & Honors</h2>
              </div>
              <ul className="space-y-2">
                {profile.certifications.map((cert, i) => (
                  <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 shrink-0" />
                    <span>{cert}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right Column: Experience, Education, Projects */}
        <div className="lg:col-span-2 space-y-6">
          {/* Experience */}
          <div className="bg-slate-900/80 rounded-2xl border border-slate-800 p-6 shadow-md">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
                <Briefcase className="w-4 h-4" />
              </div>
              <h2 className="text-base font-bold text-white">Work Experience</h2>
            </div>

            {profile.experience && profile.experience.length > 0 ? (
              <div className="space-y-4">
                {profile.experience.map((exp, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1">
                      <h3 className="font-semibold text-white text-sm">
                        {exp.role || 'Role / Position'}
                      </h3>
                      <span className="text-xs text-slate-400">
                        {exp.start_date || ''} {exp.end_date ? `— ${exp.end_date}` : ''}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-brand-400 mb-2">
                      {exp.company || 'Company'}
                    </p>
                    {exp.description && (
                      <p className="text-xs text-slate-300 leading-relaxed mb-2">
                        {exp.description}
                      </p>
                    )}
                    {exp.skills && exp.skills.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {exp.skills.map((s, si) => (
                          <span
                            key={si}
                            className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px]"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No formal experience listed (fresher profile).</p>
            )}
          </div>

          {/* Education */}
          <div className="bg-slate-900/80 rounded-2xl border border-slate-800 p-6 shadow-md">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center">
                <GraduationCap className="w-4 h-4" />
              </div>
              <h2 className="text-base font-bold text-white">Education</h2>
            </div>

            {profile.education && profile.education.length > 0 ? (
              <div className="space-y-3">
                {profile.education.map((edu, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                    <div className="flex items-center justify-between mb-1">
                      <h3 className="font-semibold text-white text-sm">
                        {edu.degree || 'Degree'}
                      </h3>
                      {edu.graduation_year && (
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          Class of {edu.graduation_year}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400">{edu.institution || 'University / College'}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 italic">No education entries found.</p>
            )}
          </div>

          {/* Projects */}
          {profile.projects && profile.projects.length > 0 && (
            <div className="bg-slate-900/80 rounded-2xl border border-slate-800 p-6 shadow-md">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center">
                  <FolderGit2 className="w-4 h-4" />
                </div>
                <h2 className="text-base font-bold text-white">Key Projects</h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {profile.projects.map((proj, idx) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                    <h3 className="font-semibold text-white text-xs mb-1">
                      {proj.name || 'Project Name'}
                    </h3>
                    {proj.description && (
                      <p className="text-xs text-slate-400 mb-2 line-clamp-2">
                        {proj.description}
                      </p>
                    )}
                    {proj.technologies && proj.technologies.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-auto">
                        {proj.technologies.map((t, ti) => (
                          <span
                            key={ti}
                            className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px]"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
