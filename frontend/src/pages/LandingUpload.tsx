import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  Sparkles,
  ArrowRight,
  Shield,
  Briefcase,
  Zap,
  GraduationCap,
  Loader2,
  CheckCircle,
} from 'lucide-react';
import { useCareerLens } from '../context/CareerLensContext';
import { api } from '../services/api';
import { ErrorAlert } from '../components/ErrorAlert';

export const LandingUpload: React.FC = () => {
  const { setResumeId, setProfile, setCurrentStep } = useCareerLens();
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    setError(null);
    if (selectedFile.type !== 'application/pdf' && !selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a valid PDF document (.pdf). Other formats are not supported.');
      return;
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError('The resume PDF file is too large (maximum allowed size is 10 MB).');
      return;
    }
    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select or drop a PDF resume first.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await api.uploadResume(file);
      setResumeId(response.resume_id);
      setProfile(response.profile);
      setCurrentStep('profile');
    } catch (err: any) {
      setError(err.message || 'Failed to extract structured details from resume. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-8 lg:py-12 px-4">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mx-auto mb-10 lg:mb-14">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-500/10 border border-brand-500/25 text-brand-300 text-xs font-semibold uppercase tracking-wider mb-6 shadow-sm">
          <Sparkles className="w-4 h-4 text-brand-400" />
          AI-Powered Student Career Intelligence
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-[1.15] mb-6">
          Know which jobs you can{' '}
          <span className="bg-gradient-to-r from-brand-400 via-cyan-400 to-emerald-400 bg-clip-text text-transparent">
            actually target.
          </span>
        </h1>

        <p className="text-lg sm:text-xl text-slate-300 font-normal leading-relaxed mb-4">
          Upload your resume. Discover real opportunities. See what skills could improve your chances.
        </p>

        <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto">
          AI evaluates your candidate profile against live job postings with honest, transparent fit scores — no false hype, just real actionable paths.
        </p>
      </div>

      <ErrorAlert message={error} onDismiss={() => setError(null)} />

      {/* Main Upload Box */}
      <div className="max-w-2xl mx-auto bg-slate-900/90 rounded-2xl border border-slate-800 p-6 sm:p-8 shadow-2xl backdrop-blur-md relative overflow-hidden">
        {/* Glow accent */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-brand-500/20 rounded-full blur-3xl pointer-events-none" />

        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isLoading && fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 sm:p-12 text-center transition-all cursor-pointer relative ${
            isDragging
              ? 'border-brand-400 bg-brand-500/10 scale-[1.01]'
              : file
              ? 'border-emerald-500/60 bg-emerald-950/20'
              : 'border-slate-700/80 hover:border-brand-500/50 hover:bg-slate-800/40'
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileInput}
            accept=".pdf,application/pdf"
            className="hidden"
          />

          {isLoading ? (
            <div className="flex flex-col items-center py-4">
              <div className="relative">
                <Loader2 className="w-14 h-14 text-brand-400 animate-spin mb-4" />
                <Sparkles className="w-5 h-5 text-cyan-300 absolute -top-1 -right-1 animate-pulse" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">Analyzing Resume with AI...</h3>
              <p className="text-sm text-slate-400 max-w-sm">
                Parsing education, work experience, projects, and extracting technical skills using our specialized model.
              </p>
            </div>
          ) : file ? (
            <div className="flex flex-col items-center py-2">
              <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 mb-4">
                <CheckCircle className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-bold text-white mb-1">{file.name}</h3>
              <p className="text-xs text-slate-400 mb-4">
                {(file.size / (1024 * 1024)).toFixed(2)} MB PDF • Ready to parse
              </p>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
                className="text-xs text-rose-400 hover:text-rose-300 underline"
              >
                Change PDF
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <div className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400 mb-5 shadow-inner">
                <UploadCloud className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">
                Click to upload or drag & drop resume PDF
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 mb-4 max-w-sm">
                Supports all standard student and professional PDF resumes up to 10 MB.
              </p>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-slate-800 text-slate-300 text-xs font-medium border border-slate-700">
                <FileText className="w-3.5 h-3.5 text-brand-400" />
                Select PDF File
              </span>
            </div>
          )}
        </div>

        {/* Action Button */}
        <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Shield className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Private & secure: analyzed in temporary memory</span>
          </div>

          <button
            type="button"
            disabled={!file || isLoading}
            onClick={handleUpload}
            className={`w-full sm:w-auto px-6 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all shadow-lg ${
              file && !isLoading
                ? 'bg-gradient-to-r from-brand-500 to-cyan-500 hover:from-brand-600 hover:to-cyan-600 text-white shadow-brand-500/25 hover:shadow-brand-500/40 scale-[1.02]'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
            }`}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Extracting Profile...</span>
              </>
            ) : (
              <>
                <span>Extract Profile & Continue</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Feature highlights grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto mt-14">
        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80">
          <div className="w-9 h-9 rounded-lg bg-brand-500/10 text-brand-400 flex items-center justify-center mb-3">
            <Briefcase className="w-5 h-5" />
          </div>
          <h4 className="font-semibold text-white text-sm mb-1">Live Adzuna Jobs</h4>
          <p className="text-xs text-slate-400 leading-relaxed">
            Search live job postings in your city or remote, normalized with real employer requirements.
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80">
          <div className="w-9 h-9 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center mb-3">
            <Zap className="w-5 h-5" />
          </div>
          <h4 className="font-semibold text-white text-sm mb-1">What-If Skill Simulator</h4>
          <p className="text-xs text-slate-400 leading-relaxed">
            Simulate how learning missing skills immediately increases your fit score before applying.
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-3">
            <GraduationCap className="w-5 h-5" />
          </div>
          <h4 className="font-semibold text-white text-sm mb-1">Dynamic Learning Hub</h4>
          <p className="text-xs text-slate-400 leading-relaxed">
            Discovers real, verified YouTube and Coursera courses mapped directly to your missing skills.
          </p>
        </div>
      </div>
    </div>
  );
};
