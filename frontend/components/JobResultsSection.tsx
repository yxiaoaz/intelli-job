'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import JobCard from './JobCard';
import JobSummaryBar from './JobSummaryBar';
import JobDetailModal from './JobDetailModal';
import QuickActions from './QuickActions';
import { toast } from 'sonner';

interface JobResultsSectionProps {
  jobs: any[];
  onQuickAction: (actionText: string) => void;
}

export default function JobResultsSection({ jobs, onQuickAction }: JobResultsSectionProps) {
  const router = useRouter();
  const [selectedJob, setSelectedJob] = useState<any | null>(null);

  if (!jobs || jobs.length === 0) return null;

  const displayJobs = jobs.slice(0, 5);
  const hasMore = jobs.length > 5;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Summary bar */}
      <JobSummaryBar jobs={jobs} />

      {/* Job cards grid */}
      <div className="grid grid-cols-1 gap-3">
        {displayJobs.map((job: any, idx: number) => {
          const enhancedJob = {
            ...job,
            description: job.description || '',
            full_description: job.description || '',
            recruitment_type: job.recruitment_type || '未知',
            education: job.education || '不限',
            update_time: job.update_time || '',
            score: job.match_score || 0,
            is_bookmarked: false,
          };

          return (
            <JobCard
              key={job.id || idx}
              job={enhancedJob}
              index={idx}
              onViewDetail={() => setSelectedJob(enhancedJob)}
              onBookmark={() => toast.success('已收藏')}
              onApply={() => toast.success(`准备投递: ${enhancedJob.title}`)}
            />
          );
        })}
      </div>

      {/* View all button */}
      {hasMore && (
        <div className="text-center">
          <button
            onClick={() => router.push('/dashboard')}
            className="px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl
                       hover:from-primary-700 hover:to-primary-600 transition-all shadow-lg hover:shadow-xl
                       font-semibold text-sm"
          >
            查看全部 {jobs.length} 个岗位
          </button>
        </div>
      )}

      {/* Quick action buttons */}
      <QuickActions jobs={jobs} onAction={onQuickAction} />

      {/* Job Detail Modal */}
      <JobDetailModal
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        onApply={() => toast.success(`准备投递: ${selectedJob?.title}`)}
        onBookmark={() => toast.success('已收藏')}
      />
    </div>
  );
}
