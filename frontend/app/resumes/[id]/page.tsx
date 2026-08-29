'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Briefcase,
  GraduationCap,
  Code,
  Star,
  TrendingUp,
  AlertCircle,
  Trash2,
  ExternalLink,
  MapPin,
  Building2,
  DollarSign,
  Pencil,
  Save,
  X,
  Plus
} from 'lucide-react';
import { fetchWithAuth, resumeAPI } from '@/lib/api';
import { toast } from 'sonner';

interface ParsedData {
  personal_info?: {
    name?: string;
    email?: string;
    phone?: string;
    location?: string;
  };
  education?: Array<{
    school?: string;
    degree?: string;
    major?: string;
    start_date?: string;
    end_date?: string;
  }>;
  work_experience?: Array<{
    company?: string;
    position?: string;
    start_date?: string;
    end_date?: string;
    description?: string;
  }>;
  skills?: string[];
  projects?: Array<{
    name?: string;
    description?: string;
    technologies?: string[];
  }>;
}

interface Evaluation {
  overall_score?: number;
  dimension_scores?: {
    completeness?: number;
    professionalism?: number;
    relevance?: number;
    formatting?: number;
  };
  summary?: string;
  suggestions?: Array<{
    category?: string;
    issue?: string;
    recommendation?: string;
  }>;
  strengths?: string[];
}

interface Analysis {
  id?: string;
  parsed_data?: ParsedData;
  evaluation?: Evaluation;
  status?: string;
  error_message?: string;
}

interface MatchedJob {
  id: string;
  title: string;
  company: string;
  location?: string;
  salary_min?: number;
  salary_max?: number;
  match_score: number;
  url?: string;
}

export default function ResumeDetailPage() {
  const router = useRouter();
  const params = useParams();
  const resumeId = params.id as string;

  const [loading, setLoading] = useState(true);
  const [resume, setResume] = useState<any>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [matchedJobs, setMatchedJobs] = useState<MatchedJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);

  // 画像校准（编辑模式）
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editForm, setEditForm] = useState<{
    personal_info: { name?: string; email?: string; phone?: string; location?: string };
    skills: string[];
    education: Array<{ school?: string; degree?: string; major?: string; start_date?: string; end_date?: string }>;
    work_experience: Array<{ company?: string; position?: string; start_date?: string; end_date?: string; description?: string }>;
  } | null>(null);
  const [skillInput, setSkillInput] = useState('');
  const [newEdu, setNewEdu] = useState({ school: '', degree: '', major: '' });
  const [newWork, setNewWork] = useState({ company: '', position: '' });

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    fetchResumeDetail();
    fetchMatchedJobs();

    // Auto-refresh when status is pending or processing
    const intervalId = setInterval(() => {
      if (analysis && (analysis.status === 'pending' || analysis.status === 'processing')) {
        fetchResumeDetail();
        // Also refresh matched jobs if status becomes completed
        if (analysis.status === 'processing') {
          fetchMatchedJobs();
        }
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(intervalId);
  }, [resumeId, router, analysis?.status]);

  const fetchResumeDetail = async () => {
    try {
      const response = await fetchWithAuth(`/api/v1/resumes/${resumeId}`);

      if (response.ok) {
        const data = await response.json();
        setResume(data.resume);
        setAnalysis(data.analysis);
      } else {
        toast.error('获取简历详情失败');
        router.push('/resumes');
      }
    } catch (error) {
      console.error('Error fetching resume detail:', error);
      toast.error('网络错误');
    } finally {
      setLoading(false);
    }
  };

  const fetchMatchedJobs = async () => {
    setLoadingJobs(true);
    try {
      const response = await fetchWithAuth(`/api/v1/resumes/${resumeId}/matches`);

      if (response.ok) {
        const data = await response.json();
        setMatchedJobs(data.matches || []);
      }
    } catch (error) {
      console.error('Error fetching matched jobs:', error);
    } finally {
      setLoadingJobs(false);
    }
  };

  const handleReparse = async () => {
    // 手动编辑过的画像会被重新解析覆盖，需要用户确认
    if (resume?.manually_edited && !confirm('重新解析将覆盖你手动编辑的画像内容，确定继续吗？')) {
      return;
    }
    try {
      const response = await fetchWithAuth(`/api/v1/resumes/${resumeId}/reparse`, {
        method: 'POST',
      });

      if (response.ok) {
        toast.success('重新解析任务已启动');
        fetchResumeDetail();
      } else {
        toast.error('重新解析失败');
      }
    } catch (error) {
      console.error('Error reparsing:', error);
      toast.error('重新解析失败');
    }
  };

  const handleExport = async () => {
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
      console.error('Error exporting:', error);
      toast.error('导出失败');
    }
  };

  const handleDelete = async () => {
    if (!confirm('确定要删除这份简历吗？此操作不可恢复。')) {
      return;
    }

    try {
      const response = await fetchWithAuth(`/api/v1/resumes/${resumeId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        toast.success('简历已删除');
        router.push('/resumes');
      } else {
        toast.error('删除失败');
      }
    } catch (error) {
      console.error('Error deleting resume:', error);
      toast.error('删除失败');
    }
  };

  const handleApplyJob = (jobUrl?: string) => {
    if (jobUrl) {
      window.open(jobUrl, '_blank');
    } else {
      toast.error('该职位暂无申请链接');
    }
  };

  // ── 画像校准（编辑模式）──
  const startEdit = () => {
    const pd = analysis?.parsed_data || {};
    setEditForm({
      personal_info: { ...(pd.personal_info || {}) },
      skills: [...(pd.skills || [])],
      education: (pd.education || []).map((e) => ({ ...e })),
      work_experience: (pd.work_experience || []).map((e) => ({ ...e })),
    });
    setSkillInput('');
    setNewEdu({ school: '', degree: '', major: '' });
    setNewWork({ company: '', position: '' });
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditForm(null);
    setSkillInput('');
  };

  const addSkill = () => {
    const v = skillInput.trim();
    if (!v || !editForm) return;
    if (!editForm.skills.includes(v)) {
      setEditForm({ ...editForm, skills: [...editForm.skills, v] });
    }
    setSkillInput('');
  };

  const addEduEntry = () => {
    if (!editForm || !newEdu.school.trim()) return;
    setEditForm({
      ...editForm,
      education: [...editForm.education, { school: newEdu.school.trim(), degree: newEdu.degree.trim(), major: newEdu.major.trim() }],
    });
    setNewEdu({ school: '', degree: '', major: '' });
  };

  const addWorkEntry = () => {
    if (!editForm || (!newWork.company.trim() && !newWork.position.trim())) return;
    setEditForm({
      ...editForm,
      work_experience: [...editForm.work_experience, { company: newWork.company.trim(), position: newWork.position.trim() }],
    });
    setNewWork({ company: '', position: '' });
  };

  const saveEdit = async () => {
    if (!editForm) return;
    setSaving(true);
    try {
      const response = await resumeAPI.updateProfile(resumeId, {
        personal_info: editForm.personal_info,
        skills: editForm.skills,
        education: editForm.education,
        work_experience: editForm.work_experience,
      });

      if (response.status === 200) {
        // 用返回的 merged extracted_content 刷新本地展示（去掉内部标记）
        const merged = response.data?.extracted_content || {};
        const { manually_edited: _ignored, ...parsed } = merged;
        setAnalysis((prev) => (prev ? { ...prev, parsed_data: parsed } : prev));
        if (resume) setResume({ ...resume, manually_edited: true });
        toast.success('画像已保存');
        setEditing(false);
        setEditForm(null);
      } else {
        toast.error(response.data?.detail || '保存失败');
      }
    } catch (err: any) {
      console.error('Error saving profile:', err);
      toast.error(err.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!resume || !analysis) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
            无法加载简历
          </h2>
          <button
            onClick={() => router.push('/resumes')}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            返回列表
          </button>
        </div>
      </div>
    );
  }

  const parsedData = analysis.parsed_data;
  const evaluation = analysis.evaluation;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
      {/* Header */}
      <header className="bg-white/80 dark:bg-slate-800/80 backdrop-blur-md shadow-sm sticky top-0 z-50 border-b border-slate-200 dark:border-slate-700">
        <div className="container mx-auto px-4 py-4 max-w-7xl flex justify-between items-center">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
            Intelli-Job
          </h1>
          <nav className="space-x-6 flex items-center">
            <button
              onClick={() => router.push('/dashboard')}
              className="text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              职位搜索
            </button>
            <button
              onClick={() => router.push('/resumes')}
              className="text-blue-600 dark:text-blue-400 font-semibold"
            >
              我的简历
            </button>
            <button
              onClick={() => router.push('/chat')}
              className="text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              AI助手
            </button>
            <button
              onClick={() => router.push('/profile')}
              className="text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              我的资料
            </button>
          </nav>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push('/resumes')}
            className="flex items-center gap-2 text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 mb-4"
          >
            <ArrowLeft className="w-5 h-5" />
            返回简历列表
          </button>
          
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2">
                {parsedData?.personal_info?.name || resume.filename}
              </h1>
              <p className="text-slate-600 dark:text-slate-400">
                上传时间: {new Date(resume.uploaded_at).toLocaleDateString('zh-CN')}
              </p>
            </div>
            
            <div className="flex gap-2">
              {editing ? (
                <>
                  <button
                    onClick={saveEdit}
                    disabled={saving}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    <Save className="w-5 h-5" />
                    {saving ? '保存中...' : '保存'}
                  </button>
                  <button
                    onClick={cancelEdit}
                    disabled={saving}
                    className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                  >
                    <X className="w-5 h-5" />
                    取消
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={startEdit}
                    disabled={analysis.status !== 'completed'}
                    title={analysis.status !== 'completed' ? '简历尚未完成解析' : '修正解析错误的画像'}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <Pencil className="w-5 h-5" />
                    编辑画像
                  </button>
                  <button
                    onClick={handleExport}
                    className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                  >
                    <Download className="w-5 h-5" />
                    导出 JSON
                  </button>
                  <button
                    onClick={handleReparse}
                    className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                  >
                    <RefreshCw className="w-5 h-5" />
                    重新解析
                  </button>
                  <button
                    onClick={handleDelete}
                    className="flex items-center gap-2 px-4 py-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                  >
                    <Trash2 className="w-5 h-5" />
                    删除
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Status Banner */}
        {analysis.status !== 'completed' && (
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-xl p-4 mb-6">
            <div className="flex items-center gap-2 text-yellow-800 dark:text-yellow-300">
              <AlertCircle className="w-5 h-5" />
              <span>
                {analysis.status === 'processing' ? '正在解析中，请稍候...' : 
                 analysis.status === 'failed' ? `解析失败: ${analysis.error_message}` : 
                 '等待解析，即将开始处理...'}
              </span>
              {(analysis.status === 'pending' || analysis.status === 'processing') && (
                <div className="ml-2 animate-spin rounded-full h-4 w-4 border-2 border-yellow-600 border-t-transparent"></div>
              )}
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Personal Info */}
            {(editing || parsedData?.personal_info) && (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">
                  个人信息
                </h2>
                {editing ? (
                  <div className="grid md:grid-cols-2 gap-4">
                    {(['name', 'phone', 'email', 'location'] as const).map((field) => (
                      <div key={field}>
                        <label className="text-sm text-slate-500 dark:text-slate-400">
                          {field === 'name' ? '姓名' : field === 'phone' ? '电话' : field === 'email' ? '邮箱' : '城市'}
                        </label>
                        <input
                          type="text"
                          value={editForm?.personal_info?.[field] || ''}
                          onChange={(e) =>
                            setEditForm((prev) =>
                              prev
                                ? { ...prev, personal_info: { ...prev.personal_info, [field]: e.target.value } }
                                : prev
                            )
                          }
                          className="w-full px-3 py-2 border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="grid md:grid-cols-2 gap-4">
                    {parsedData?.personal_info?.name && (
                      <div>
                        <label className="text-sm text-slate-500 dark:text-slate-400">姓名</label>
                        <p className="font-medium text-slate-900 dark:text-white">{parsedData.personal_info.name}</p>
                      </div>
                    )}
                    {parsedData?.personal_info?.email && (
                      <div>
                        <label className="text-sm text-slate-500 dark:text-slate-400">邮箱</label>
                        <p className="font-medium text-slate-900 dark:text-white">{parsedData.personal_info.email}</p>
                      </div>
                    )}
                    {parsedData?.personal_info?.phone && (
                      <div>
                        <label className="text-sm text-slate-500 dark:text-slate-400">电话</label>
                        <p className="font-medium text-slate-900 dark:text-white">{parsedData.personal_info.phone}</p>
                      </div>
                    )}
                    {parsedData?.personal_info?.location && (
                      <div>
                        <label className="text-sm text-slate-500 dark:text-slate-400">地点</label>
                        <p className="font-medium text-slate-900 dark:text-white">{parsedData.personal_info.location}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Education */}
            {(editing || (parsedData?.education && parsedData.education.length > 0)) && (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <GraduationCap className="w-6 h-6 text-blue-600" />
                  教育背景
                </h2>
                <div className="space-y-4">
                  {(editing ? editForm?.education ?? [] : parsedData?.education ?? []).map((edu, index) => (
                    <div key={index} className="border-l-2 border-blue-200 dark:border-blue-800 pl-4 flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-medium text-slate-900 dark:text-white">{edu.school}</h3>
                        <p className="text-slate-600 dark:text-slate-400">
                          {[edu.degree, edu.major].filter(Boolean).join(' · ')}
                        </p>
                        {(edu.start_date || edu.end_date) && (
                          <p className="text-sm text-slate-500 dark:text-slate-500">
                            {edu.start_date} - {edu.end_date || '至今'}
                          </p>
                        )}
                      </div>
                      {editing && (
                        <button
                          onClick={() =>
                            setEditForm((prev) =>
                              prev ? { ...prev, education: prev.education.filter((_, i) => i !== index) } : prev
                            )
                          }
                          className="p-1 text-slate-400 hover:text-red-600 transition-colors"
                          title="删除该条目"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                {editing && (
                  <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                    <div className="grid md:grid-cols-3 gap-2 mb-2">
                      <input
                        type="text"
                        value={newEdu.school}
                        onChange={(e) => setNewEdu({ ...newEdu, school: e.target.value })}
                        placeholder="学校 *"
                        className="px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                      />
                      <input
                        type="text"
                        value={newEdu.degree}
                        onChange={(e) => setNewEdu({ ...newEdu, degree: e.target.value })}
                        placeholder="学历"
                        className="px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                      />
                      <input
                        type="text"
                        value={newEdu.major}
                        onChange={(e) => setNewEdu({ ...newEdu, major: e.target.value })}
                        placeholder="专业"
                        className="px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <button
                      onClick={addEduEntry}
                      className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      <Plus className="w-4 h-4" />
                      添加教育经历
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Work Experience */}
            {(editing || (parsedData?.work_experience && parsedData.work_experience.length > 0)) && (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <Briefcase className="w-6 h-6 text-blue-600" />
                  工作经历
                </h2>
                <div className="space-y-6">
                  {(editing ? editForm?.work_experience ?? [] : parsedData?.work_experience ?? []).map((exp, index) => (
                    <div key={index} className="border-l-2 border-blue-200 dark:border-blue-800 pl-4 flex items-start justify-between gap-2">
                      <div>
                        <h3 className="font-medium text-slate-900 dark:text-white">{exp.position}</h3>
                        <p className="text-slate-600 dark:text-slate-400">{exp.company}</p>
                        {(exp.start_date || exp.end_date) && (
                          <p className="text-sm text-slate-500 dark:text-slate-500 mb-2">
                            {exp.start_date} - {exp.end_date || '至今'}
                          </p>
                        )}
                        {exp.description && (
                          <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-line">
                            {exp.description}
                          </p>
                        )}
                      </div>
                      {editing && (
                        <button
                          onClick={() =>
                            setEditForm((prev) =>
                              prev ? { ...prev, work_experience: prev.work_experience.filter((_, i) => i !== index) } : prev
                            )
                          }
                          className="p-1 text-slate-400 hover:text-red-600 transition-colors"
                          title="删除该条目"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                {editing && (
                  <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                    <div className="grid md:grid-cols-2 gap-2 mb-2">
                      <input
                        type="text"
                        value={newWork.company}
                        onChange={(e) => setNewWork({ ...newWork, company: e.target.value })}
                        placeholder="公司"
                        className="px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                      />
                      <input
                        type="text"
                        value={newWork.position}
                        onChange={(e) => setNewWork({ ...newWork, position: e.target.value })}
                        placeholder="职位"
                        className="px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <button
                      onClick={addWorkEntry}
                      className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      <Plus className="w-4 h-4" />
                      添加工作经历
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Skills */}
            {(editing || (parsedData?.skills && parsedData.skills.length > 0)) && (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <Code className="w-6 h-6 text-blue-600" />
                  技能清单
                </h2>
                <div className="flex flex-wrap gap-2">
                  {(editing ? editForm?.skills ?? [] : parsedData?.skills ?? []).map((skill, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded-full text-sm"
                    >
                      {skill}
                      {editing && (
                        <button
                          onClick={() =>
                            setEditForm((prev) =>
                              prev ? { ...prev, skills: prev.skills.filter((_, i) => i !== index) } : prev
                            )
                          }
                          className="text-blue-400 hover:text-red-600 transition-colors"
                          title="删除该技能"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </span>
                  ))}
                </div>
                {editing && (
                  <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700 flex gap-2">
                    <input
                      type="text"
                      value={skillInput}
                      onChange={(e) => setSkillInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && addSkill()}
                      placeholder="输入技能名后回车"
                      className="flex-1 px-3 py-2 text-sm border border-slate-200 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={addSkill}
                      className="inline-flex items-center gap-1 px-3 py-2 text-sm bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                      添加
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Projects（只读，第一期不做编辑） */}
            {!editing && parsedData?.projects && parsedData.projects.length > 0 && (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="w-6 h-6 text-indigo-600" />
                  项目经历
                </h2>
                <div className="space-y-4">
                  {parsedData.projects.map((proj, index) => (
                    <div key={index} className="border-l-2 border-indigo-200 dark:border-indigo-800 pl-4">
                      <h3 className="font-medium text-slate-900 dark:text-white">{proj.name}</h3>
                      {proj.description && (
                        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1 whitespace-pre-line">
                          {proj.description}
                        </p>
                      )}
                      {proj.technologies && proj.technologies.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {proj.technologies.map((tech, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 text-xs rounded-full bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400"
                            >
                              {tech}
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

          {/* Sidebar - Evaluation */}
          <div className="space-y-6">
            {/* Score Card */}
            {evaluation && (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <Star className="w-6 h-6 text-yellow-500" />
                  质量评分
                </h2>
                
                <div className="text-center mb-6">
                  <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-3xl font-bold mb-2">
                    {evaluation.overall_score}
                  </div>
                  <p className="text-sm text-slate-600 dark:text-slate-400">综合评分</p>
                </div>

                {/* Dimension Scores */}
                {evaluation.dimension_scores && (
                  <div className="space-y-3">
                    {Object.entries(evaluation.dimension_scores).map(([key, value]) => (
                      <div key={key}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-slate-600 dark:text-slate-400">
                            {key === 'completeness' ? '完整性' :
                             key === 'professionalism' ? '专业性' :
                             key === 'relevance' ? '相关性' : '格式规范'}
                          </span>
                          <span className="font-medium text-slate-900 dark:text-white">{value}</span>
                        </div>
                        <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2">
                          <div
                            className="bg-gradient-to-r from-blue-600 to-indigo-600 h-2 rounded-full transition-all"
                            style={{ width: `${value}%` }}
                          ></div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Strengths */}
            {evaluation?.strengths && evaluation.strengths.length > 0 && (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="w-6 h-6 text-green-500" />
                  优势亮点
                </h2>
                <ul className="space-y-2">
                  {evaluation.strengths.map((strength, index) => (
                    <li key={index} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                      <span className="text-green-500 mt-1">•</span>
                      {strength}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Suggestions */}
            {evaluation?.suggestions && evaluation.suggestions.length > 0 && (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <AlertCircle className="w-6 h-6 text-orange-500" />
                  改进建议
                </h2>
                <div className="space-y-4">
                  {evaluation.suggestions.map((suggestion, index) => (
                    <div key={index} className="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
                      <h4 className="font-medium text-orange-900 dark:text-orange-300 text-sm mb-1">
                        {suggestion.category}
                      </h4>
                      <p className="text-xs text-orange-700 dark:text-orange-400 mb-2">
                        {suggestion.issue}
                      </p>
                      <p className="text-sm text-slate-700 dark:text-slate-300">
                        {suggestion.recommendation}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Matched Jobs Section */}
        <div className="mt-8">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-6">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
              <Briefcase className="w-7 h-7 text-blue-600" />
              推荐职位
            </h2>

            {loadingJobs ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : matchedJobs.length === 0 ? (
              <div className="text-center py-8 text-slate-600 dark:text-slate-400">
                <p>暂无匹配职位，请稍后再试</p>
              </div>
            ) : (
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {matchedJobs.map((job) => (
                  <div
                    key={job.id}
                    className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="font-semibold text-slate-900 dark:text-white line-clamp-2">
                        {job.title}
                      </h3>
                      <span className="ml-2 px-2 py-1 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 text-xs font-medium rounded-full">
                        {job.match_score}%
                      </span>
                    </div>

                    <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400 mb-4">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4" />
                        <span className="truncate">{job.company}</span>
                      </div>
                      {job.location && (
                        <div className="flex items-center gap-2">
                          <MapPin className="w-4 h-4" />
                          <span>{job.location}</span>
                        </div>
                      )}
                      {(job.salary_min || job.salary_max) && (
                        <div className="flex items-center gap-2">
                          <DollarSign className="w-4 h-4" />
                          <span>
                            {job.salary_min && `¥${job.salary_min.toLocaleString()}`}
                            {job.salary_min && job.salary_max && ' - '}
                            {job.salary_max && `¥${job.salary_max.toLocaleString()}`}
                          </span>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => handleApplyJob(job.url)}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:from-blue-700 hover:to-indigo-700 transition-all text-sm font-medium"
                    >
                      <ExternalLink className="w-4 h-4" />
                      申请职位
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
