'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { 
  Upload, 
  FileText, 
  Trash2, 
  RefreshCw, 
  Download,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Filter,
  Star
} from 'lucide-react';
import ResumeUpload from '@/components/ResumeUpload';
import Navbar from '@/components/Navbar';
import { fetchWithAuth, resumeAPI, type ResumeSummary } from '@/lib/api';
import { toast } from 'sonner';
import { buttonClasses } from '@/components/ui/Button';

interface Resume {
  id: string;
  filename: string;
  file_size: number;
  content_type: string;
  uploaded_at: string;
  status?: string;
  score?: number;
  is_default?: boolean;
  manually_edited?: boolean;
  summary?: ResumeSummary | null;
}

export default function ResumesPage() {
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Check authentication and fetch resumes
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    fetchResumes();

    // Auto-refresh when there are pending/processing resumes
    const intervalId = setInterval(() => {
      const hasPendingResumes = resumes.some(r => 
        r.status === 'pending' || r.status === 'processing'
      );
      if (hasPendingResumes) {
        fetchResumes();
      }
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(intervalId);
  }, [router, resumes]);

  const fetchResumes = async () => {
    try {
      const response = await fetchWithAuth('/api/v1/resumes/');

      if (response.ok) {
        const data = await response.json();
        setResumes(data);
      } else {
        console.error('Failed to fetch resumes');
      }
    } catch (error) {
      console.error('Error fetching resumes:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUploadSuccess = () => {
    setShowUploadModal(false);
    fetchResumes();
  };

  const handleDelete = async (resumeId: string) => {
    if (!confirm('确定要删除这份简历吗？此操作不可恢复。')) {
      return;
    }

    try {
      const response = await fetchWithAuth(`/api/v1/resumes/${resumeId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setResumes(resumes.filter(r => r.id !== resumeId));
      } else {
        toast.error('删除失败');
      }
    } catch (error) {
      console.error('Error deleting resume:', error);
      toast.error('删除失败');
    }
  };

  const handleSetDefault = async (resumeId: string) => {
    try {
      const response = await resumeAPI.setDefault(resumeId);
      if (response.status === 200) {
        toast.success('已设为默认简历，AI 功能将基于此简历个性化');
        fetchResumes();
      } else {
        toast.error('设置默认简历失败');
      }
    } catch (error) {
      console.error('Error setting default resume:', error);
      toast.error('设置默认简历失败');
    }
  };

  const handleReparse = async (resumeId: string, manuallyEdited?: boolean) => {
    // 手动编辑过的画像会被重新解析覆盖，需要用户确认
    if (manuallyEdited && !confirm('重新解析将覆盖你手动编辑的画像内容，确定继续吗？')) {
      return;
    }
    try {
      const response = await fetchWithAuth(`/api/v1/resumes/${resumeId}/reparse`, {
        method: 'POST',
      });

      if (response.ok) {
        toast.success('重新解析任务已启动');
        fetchResumes();
      } else {
        toast.error('重新解析失败');
      }
    } catch (error) {
      console.error('Error reparsing resume:', error);
      toast.error('重新解析失败');
    }
  };

  const handleExport = async (resumeId: string) => {
    try {
      const response = await fetchWithAuth(`/api/v1/resumes/${resumeId}/export/json`);

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `resume_${resumeId}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        toast.error('导出失败');
      }
    } catch (error) {
      console.error('Error exporting resume:', error);
      toast.error('导出失败');
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-success-600" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-danger-600" />;
      case 'processing':
        return <Clock className="w-5 h-5 text-warning-400 animate-spin" />;
      default:
        return <Clock className="w-5 h-5 text-400" />;
    }
  };

  const getStatusText = (status?: string) => {
    switch (status) {
      case 'completed':
        return '解析完成';
      case 'failed':
        return '解析失败';
      case 'processing':
        return '解析中';
      default:
        return '待解析';
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Filter resumes
  const filteredResumes = resumes.filter(resume => {
    const matchesStatus = filterStatus === 'all' || resume.status === filterStatus;
    const matchesSearch = resume.filename.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base">
      {/* Header */}
      <Navbar currentPath="/resumes" />

      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-medium text-900 mb-2">
            我的简历
          </h1>
          <p className="text-700">
            上传和管理您的简历，获取智能分析和岗位推荐
          </p>
        </div>

        {/* Actions Bar */}
        <div className="bg-layer1 rounded-menu shadow-lv1 p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            {/* Search */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-400 w-5 h-5" />
              <input
                type="text"
                placeholder="搜索简历..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-l2 rounded-input focus:ring-2 focus:ring-primary-200 focus:border-transparent"
              />
            </div>

            {/* Filter */}
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-400" />
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="px-4 py-2 border border-l2 rounded-input focus:ring-2 focus:ring-primary-200"
              >
                <option value="all">全部状态</option>
                <option value="completed">解析完成</option>
                <option value="processing">解析中</option>
                <option value="failed">解析失败</option>
                <option value="pending">待解析</option>
              </select>
            </div>

            {/* Upload Button */}
            <button
              onClick={() => setShowUploadModal(true)}
              className={buttonClasses('primary', 'md')}
            >
              <Upload className="w-4 h-4" />
              上传简历
            </button>
          </div>
        </div>

        {/* Resume List */}
        {filteredResumes.length === 0 ? (
          <div className="bg-layer1 rounded-menu shadow-lv1 p-12 text-center">
            <FileText className="w-16 h-16 text-400 mx-auto mb-4" />
            <h3 className="text-xl font-medium text-900 mb-2">
              {resumes.length === 0 ? '暂无简历' : '未找到匹配的简历'}
            </h3>
            <p className="text-700 mb-6">
              {resumes.length === 0 
                ? '上传您的第一份简历，开始智能求职之旅' 
                : '尝试调整搜索条件或过滤器'}
            </p>
            {resumes.length === 0 && (
              <button
                onClick={() => setShowUploadModal(true)}
                className={buttonClasses('secondary', 'md', 'mx-auto')}
              >
                <Upload className="w-4 h-4" />
                上传简历
              </button>
            )}
          </div>
        ) : (
          <div className="grid gap-4">
            {filteredResumes.map((resume) => {
              const summary = resume.summary;
              const profileLine = summary
                ? [
                    summary.latest_title
                      ? `${summary.latest_title}${summary.latest_company ? ` @ ${summary.latest_company}` : ''}`
                      : null,
                    summary.highest_degree,
                  ]
                    .filter(Boolean)
                    .join(' · ')
                : '';

              return (
              <div
                key={resume.id}
                className="bg-layer1 rounded-menu shadow-lv1 p-6 hover:shadow-lv1 transition-shadow"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {/* Row 1: 默认徽章/切换按钮 + 画像一句话 + 状态 */}
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      {resume.is_default ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-tint-warning text-tint-warning">
                          <Star className="w-3.5 h-3.5 fill-current" />
                          使用中
                        </span>
                      ) : (
                        <button
                          onClick={() => handleSetDefault(resume.id)}
                          className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full border border-l2 text-700 hover:border-warning-400 hover:text-warning-600 transition-colors"
                        >
                          <Star className="w-3.5 h-3.5" />
                          设为默认
                        </button>
                      )}
                      {profileLine && (
                        <span className="text-sm font-medium text-900 truncate">
                          {profileLine}
                        </span>
                      )}
                      {getStatusIcon(resume.status)}
                      <span className="text-sm text-500">
                        {getStatusText(resume.status)}
                      </span>
                    </div>

                    {/* Row 2: 文件名（弱化）+ 总分 + completeness 进度条 */}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-500 mb-2">
                      <span className="truncate max-w-[220px]">{resume.filename}</span>
                      {resume.score !== undefined && resume.score !== null && (
                        <span className="font-medium text-tint-primary">
                          {resume.score} 分
                        </span>
                      )}
                      {summary?.completeness != null && (
                        <span className="flex items-center gap-2">
                          <span>完整度</span>
                          <span className="w-24 h-1.5 bg-layer2 rounded-full overflow-hidden">
                            <span
                              className="block h-full bg-primary-500 rounded-full"
                              style={{ width: `${Math.min(100, summary.completeness)}%` }}
                            />
                          </span>
                          <span>{summary.completeness}</span>
                        </span>
                      )}
                    </div>

                    {/* Row 3: 技能 chips + 优化建议数 */}
                    {summary && (summary.skills_preview.length > 0 || summary.suggestion_count > 0) && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        {summary.skills_preview.map((skill, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 text-xs rounded-full bg-tint-primary text-tint-primary"
                          >
                            {skill}
                          </span>
                        ))}
                        {summary.skills_preview.length > 0 && summary.suggestion_count > 0 && (
                          <span className="text-400">|</span>
                        )}
                        {summary.suggestion_count > 0 && (
                          <button
                            onClick={() => router.push(`/resumes/${resume.id}`)}
                            className="text-xs text-tint-primary hover:underline"
                          >
                            {summary.suggestion_count} 条优化建议 →
                          </button>
                        )}
                      </div>
                    )}

                    {/* 文件元数据（次要信息） */}
                    <div className="flex items-center gap-3 text-xs text-400 mt-2">
                      <span>{formatFileSize(resume.file_size)}</span>
                      <span>•</span>
                      <span>{formatDate(resume.uploaded_at)}</span>
                      {resume.manually_edited && (
                        <>
                          <span>•</span>
                          <span className="text-tint-success">已手动校准</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => router.push(`/resumes/${resume.id}`)}
                      className="px-4 py-2 text-sm bg-tint-primary text-tint-primary rounded-menu hover:bg-hover-primary transition-colors"
                    >
                      查看详情
                    </button>
                    
                    {resume.status === 'completed' && (
                      <button
                        onClick={() => handleExport(resume.id)}
                        className="p-2 text-700 hover:text-tint-primary transition-colors"
                        title="导出 JSON"
                      >
                        <Download className="w-5 h-5" />
                      </button>
                    )}
                    
                    <button
                      onClick={() => handleReparse(resume.id, resume.manually_edited)}
                      className="p-2 text-700 hover:text-tint-primary transition-colors"
                      title="重新解析"
                    >
                      <RefreshCw className="w-5 h-5" />
                    </button>
                    
                    <button
                      onClick={() => handleDelete(resume.id)}
                      className="p-2 text-700 hover:text-tint-danger transition-colors"
                      title="删除"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-layer1 rounded-dialog border border-l1 shadow-lv3 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-medium text-900">
                  上传简历
                </h2>
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="text-400 hover:text-700"
                >
                  <XCircle className="w-6 h-6" />
                </button>
              </div>
              
              <ResumeUpload onSuccess={handleUploadSuccess} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
