import React, { createContext, useContext, useState } from 'react';
import {
  AppStep,
  CandidateProfile,
  Job,
  SearchMatchSummary,
  SkillGapItem,
} from '../types';

interface CareerLensContextType {
  currentStep: AppStep;
  setCurrentStep: (step: AppStep) => void;
  
  resumeId: string | null;
  setResumeId: (id: string | null) => void;
  
  profile: CandidateProfile | null;
  setProfile: (profile: CandidateProfile | null) => void;
  
  searchId: string | null;
  setSearchId: (id: string | null) => void;
  
  jobs: Job[];
  setJobs: (jobs: Job[]) => void;
  
  searchQuery: { role: string; location: string };
  setSearchQuery: (q: { role: string; location: string }) => void;
  
  matchSummary: SearchMatchSummary | null;
  setMatchSummary: (summary: SearchMatchSummary | null) => void;
  
  skillGaps: SkillGapItem[];
  setSkillGaps: (gaps: SkillGapItem[]) => void;
  
  selectedJobForWhatIf: Job | null;
  setSelectedJobForWhatIf: (job: Job | null) => void;

  resetSession: () => void;
}

const CareerLensContext = createContext<CareerLensContextType | undefined>(undefined);

export const CareerLensProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentStep, setCurrentStep] = useState<AppStep>('upload');
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [searchQuery, setSearchQuery] = useState<{ role: string; location: string }>({
    role: 'Software Engineer',
    location: 'Bangalore',
  });
  const [matchSummary, setMatchSummary] = useState<SearchMatchSummary | null>(null);
  const [skillGaps, setSkillGaps] = useState<SkillGapItem[]>([]);
  const [selectedJobForWhatIf, setSelectedJobForWhatIf] = useState<Job | null>(null);

  const resetSession = () => {
    setCurrentStep('upload');
    setResumeId(null);
    setProfile(null);
    setSearchId(null);
    setJobs([]);
    setMatchSummary(null);
    setSkillGaps([]);
    setSelectedJobForWhatIf(null);
  };

  return (
    <CareerLensContext.Provider
      value={{
        currentStep,
        setCurrentStep,
        resumeId,
        setResumeId,
        profile,
        setProfile,
        searchId,
        setSearchId,
        jobs,
        setJobs,
        searchQuery,
        setSearchQuery,
        matchSummary,
        setMatchSummary,
        skillGaps,
        setSkillGaps,
        selectedJobForWhatIf,
        setSelectedJobForWhatIf,
        resetSession,
      }}
    >
      {children}
    </CareerLensContext.Provider>
  );
};

export const useCareerLens = (): CareerLensContextType => {
  const context = useContext(CareerLensContext);
  if (!context) {
    throw new Error('useCareerLens must be used within a CareerLensProvider');
  }
  return context;
};
