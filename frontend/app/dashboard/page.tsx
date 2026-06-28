'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { jobAPI, authAPI } from '@/lib/api';
import JobDetailModal from '@/components/JobDetailModal';
import { Search, MapPin, Building2, DollarSign, Calendar } from 'lucide-react';

interface Job {
  id: string;
  company: string;
  title: string;
  recruitment_type: string;
  location: string;
  salary: string;
  education: string;
  update_time: string;
  description: string;
  full_description: string;
  url: string;
  score: number;
  is_bookmarked: boolean;
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><p className="text-gray-500">加载中...</p></div>}>
      <DashboardContent />
    </Suspense>
  );
}

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // 用户 ID（用于缓存隔离）
  const [userId, setUserId] = useState<string>('');
  
  // ✅ 修复 SSR 问题：使用简单初始化，在 useEffect 中恢复 localStorage 状态
  const [keyword, setKeyword] = useState('');
  const [searchMode, setSearchMode] = useState<'hybrid' | 'keyword' | 'vector'>('hybrid');
  const [topK, setTopK] = useState<number>(10);
  
  // Hard Filter 状态
  const [recruitmentType, setRecruitmentType] = useState<string[]>([]); // ['EXPERIENCED', 'GRADUATE']
  const [educationLevel, setEducationLevel] = useState<string>(''); // 'UNDERGRADUATE'
  const [updateTimeAfter, setUpdateTimeAfter] = useState<string>(''); // ISO date string
  
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Job Detail Modal State
  const [selectedJob, setSelectedJob] = useState<any>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Security Question Setup Modal
  const [showSecurityQuestionModal, setShowSecurityQuestionModal] = useState(false);
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [settingSecurityQuestion, setSettingSecurityQuestion] = useState(false);
  const [securityQuestionError, setSecurityQuestionError] = useState('');

  const securityQuestions = [
    '你的小学母校名称是什么？',
    '你最喜欢的电影是什么？',
    '你的宠物名字是什么？',
    '你出生的城市是哪里？',
    '你最喜欢的食物是什么？',
  ];

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }
    
    // 解析 token 获取用户 ID
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUserId(payload.sub || '');
    } catch (error) {
      console.error('Failed to decode token:', error);
    }

    // 检查是否已设置安全问题
    checkSecurityQuestionStatus();
  }, [router]);

  const checkSecurityQuestionStatus = async () => {
    try {
      const response = await authAPI.getSecurityQuestionStatus();
      if (!response.data.has_security_question) {
        // 已有用户未设置安全问题，显示引导弹窗
        setShowSecurityQuestionModal(true);
      }
    } catch (error) {
      console.error('Failed to check security question status:', error);
    }
  };

  // 页面加载时，从 localStorage 恢复搜索结果
  // ✅ 客户端挂载后，从 URL 和 localStorage 恢复状态
  useEffect(() => {
    // 1. 优先从 URL 恢复
    const urlKeyword = searchParams.get('q');
    const urlMode = searchParams.get('mode') as any;
    const urlTopK = searchParams.get('topK');
    
    if (urlKeyword) setKeyword(decodeURIComponent(urlKeyword));
    if (urlMode && ['hybrid', 'keyword', 'vector'].includes(urlMode)) setSearchMode(urlMode);
    if (urlTopK) setTopK(parseInt(urlTopK));
    
    // 2. 如果 URL 没有，则从 localStorage 恢复
    if (!urlKeyword) {
      const savedKeyword = localStorage.getItem(`dashboard_search_${userId}_keyword`);
      if (savedKeyword) setKeyword(savedKeyword);
    }
    if (!urlMode) {
      const savedMode = localStorage.getItem(`dashboard_search_${userId}_mode`);
      if (savedMode && ['hybrid', 'keyword', 'vector'].includes(savedMode)) {
        setSearchMode(savedMode as any);
      }
    }
    if (!urlTopK) {
      const savedTopK = localStorage.getItem(`dashboard_search_${userId}_topK`);
      if (savedTopK) setTopK(parseInt(savedTopK));
    }
    
    // 3. 如果有搜索关键词但没有结果，尝试从 localStorage 恢复搜索结果
    const currentKeyword = urlKeyword ? decodeURIComponent(urlKeyword) : (localStorage.getItem(`dashboard_search_${userId}_keyword`) || '');
    const currentMode = urlMode || (localStorage.getItem(`dashboard_search_${userId}_mode`) || 'hybrid');
    const currentTopK = urlTopK ? parseInt(urlTopK) : parseInt(localStorage.getItem(`dashboard_search_${userId}_topK`) || '10');
    
    if (currentKeyword && userId) {
      const cacheKey = `dashboard_jobs_${userId}_${currentKeyword}_${currentMode}_${currentTopK}`;
      const cachedJobs = localStorage.getItem(cacheKey);
      if (cachedJobs) {
        try {
          const parsed = JSON.parse(cachedJobs);
          setJobs(parsed);
          console.log('从缓存恢复搜索结果:', parsed.length, '条');
        } catch (err) {
          console.error('Failed to parse cached jobs:', err);
        }
      }
    }
    
    // 4. 清理过期的缓存（超过24小时）
    cleanupExpiredCache();
  }, [userId, searchParams]);

  // 清理过期缓存
  const cleanupExpiredCache = () => {
    const now = Date.now();
    const keysToRemove: string[] = [];
    
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith('dashboard_jobs_')) {
        try {
          const data = JSON.parse(localStorage.getItem(key) || '{}');
          if (data.expiresAt && now > data.expiresAt) {
            keysToRemove.push(key);
          }
        } catch (err) {
          // 忽略解析错误
        }
      }
    }
    
    keysToRemove.forEach(key => localStorage.removeItem(key));
    if (keysToRemove.length > 0) {
      console.log('清理过期缓存:', keysToRemove.length, '条');
    }
  };

  const handleSearch = async () => {
    if (!keyword.trim()) {
      alert('请输入搜索关键词');
      return;
    }

    setLoading(true);
    try {
      // 构建 hard_filters
      const hardFilters: any = {};
      
      if (recruitmentType.length > 0) {
        hardFilters.recruitment_type = recruitmentType;
      }
      
      if (educationLevel) {
        hardFilters.education_level = educationLevel;
      }
      
      if (updateTimeAfter) {
        hardFilters.update_time_after = updateTimeAfter;
      }
      
      const response = await jobAPI.search({
        user_query_preference: { keywords: keyword },
        search_mode: searchMode,
        top_k: topK,
        hard_filters: Object.keys(hardFilters).length > 0 ? hardFilters : undefined,
      });

      if (response.data.status === 'success') {
        const results = response.data.data;
        setJobs(results);
        
        // ✅ 保存到 localStorage（带过期时间，按用户隔离）
        const cacheKey = `dashboard_jobs_${userId}_${keyword}_${searchMode}_${topK}`;
        const cacheData = {
          jobs: results,
          timestamp: Date.now(),
          expiresAt: Date.now() + 24 * 60 * 60 * 1000, // 24小时过期
        };
        localStorage.setItem(cacheKey, JSON.stringify(results));
        
        // ✅ 保存搜索参数（按用户隔离）
        localStorage.setItem(`dashboard_search_${userId}_keyword`, keyword);
        localStorage.setItem(`dashboard_search_${userId}_mode`, searchMode);
        localStorage.setItem(`dashboard_search_${userId}_topK`, topK.toString());
        
        // ✅ 更新 URL（方便分享和刷新）
        const params = new URLSearchParams();
        params.set('q', encodeURIComponent(keyword));
        params.set('mode', searchMode);
        params.set('topK', topK.toString());
        router.push(`/dashboard?${params.toString()}`);
      }
    } catch (error: any) {
      console.error('Search failed:', error);
      alert(error.response?.data?.detail || '搜索失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetail = (job: Job) => {
    // 打开 Job Detail Modal
    setSelectedJob(job);
    setIsModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900 animate-fade-in">
      {/* Header - 玻璃态 */}
      <header className="glass shadow-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold gradient-text font-display">Intelli-Job</h1>
          <nav className="space-x-6">
            <button
              onClick={() => router.push('/dashboard')}
              className="text-primary-600 dark:text-primary-400 font-semibold"
            >
              职位搜索
            </button>
            <button
              onClick={() => router.push('/resumes')}
              className="text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
            >
              我的简历
            </button>
            <button
              onClick={() => router.push('/chat')}
              className="text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
            >
              AI助手
            </button>
            <button
              onClick={() => router.push('/profile')}
              className="text-gray-700 dark:text-gray-300 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
            >
              我的资料
            </button>
            <button
              onClick={() => {
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                router.push('/login');
              }}
              className="text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 transition-colors"
            >
              退出
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Search Section - 玻璃态卡片 */}
        <div className="glass rounded-2xl shadow-lg p-6 mb-8 border border-primary-200/50 dark:border-primary-700/50 card-hover">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white font-display">职位搜索</h2>
          
          {/* 关键词搜索 */}
          <div className="flex gap-4 mb-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-primary-400 dark:text-primary-500 w-5 h-5" />
              <input
                type="text"
                value={keyword}
                onChange={(e) => {
                  const newKeyword = e.target.value;
                  setKeyword(newKeyword);
                  localStorage.setItem('dashboard_search_keyword', newKeyword);
                }}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="输入职位关键词，如：产品经理、Java开发..."
                className="w-full pl-10 pr-4 py-3 border-2 border-gray-300 dark:border-dark-500
                           bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                           rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent
                           transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
              />
            </div>
            
            <select
              value={searchMode}
              onChange={(e) => {
                const newMode = e.target.value as any;
                setSearchMode(newMode);
                localStorage.setItem('dashboard_search_mode', newMode);
              }}
              className="px-4 py-3 border-2 border-gray-300 dark:border-dark-500
                         bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                         rounded-xl focus:ring-2 focus:ring-primary-500
                         transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
            >
              <option value="hybrid">混合搜索</option>
              <option value="keyword">关键词搜索</option>
              <option value="vector">向量搜索</option>
            </select>

            <select
              value={topK}
              onChange={(e) => {
                const newTopK = Number(e.target.value);
                setTopK(newTopK);
                localStorage.setItem('dashboard_search_topK', newTopK.toString());
              }}
              className="px-4 py-3 border-2 border-gray-300 dark:border-dark-500
                         bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                         rounded-xl focus:ring-2 focus:ring-primary-500
                         transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
            >
              <option value={5}>显示5条</option>
              <option value={10}>显示10条</option>
              <option value={20}>显示20条</option>
              <option value={50}>显示50条</option>
            </select>

            <button
              onClick={handleSearch}
              disabled={loading}
              className="px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600
                         disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-lg hover:shadow-glow
                         transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
            >
              {loading ? '搜索中...' : '搜索'}
            </button>
          </div>
          
          {/* Hard Filter 筛选栏 */}
          <div className="border-t border-gray-200 dark:border-dark-600 pt-4 mt-4">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              高级筛选（可选）
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* 招聘类型 */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  招聘类型
                </label>
                <select
                  multiple
                  value={recruitmentType}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions).map(opt => opt.value);
                    setRecruitmentType(selected);
                  }}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-dark-500
                             bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                             rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             text-sm"
                  size={3}
                >
                  <option value="EXPERIENCED">社招</option>
                  <option value="GRADUATE">校招</option>
                  <option value="INTERN">实习</option>
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                  按住 Ctrl/Cmd 多选
                </p>
              </div>
              
              {/* 学历要求 */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  最低学历要求
                </label>
                <select
                  value={educationLevel}
                  onChange={(e) => setEducationLevel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-dark-500
                             bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                             rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             text-sm"
                >
                  <option value="">不限</option>
                  <option value="ASSOCIATE">专科</option>
                  <option value="UNDERGRADUATE">本科</option>
                  <option value="MASTERS">硕士</option>
                  <option value="DOCTOR">博士</option>
                </select>
              </div>
              
              {/* 更新时间 */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  最近发布
                </label>
                <select
                  value={updateTimeAfter}
                  onChange={(e) => setUpdateTimeAfter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-dark-500
                             bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                             rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             text-sm"
                >
                  <option value="">不限时间</option>
                  <option value={new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()}>最近7天</option>
                  <option value={new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString()}>最近14天</option>
                  <option value={new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()}>最近30天</option>
                  <option value={new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString()}>最近3个月</option>
                </select>
              </div>
            </div>
            
            {/* 清除筛选按钮 */}
            {(recruitmentType.length > 0 || educationLevel || updateTimeAfter) && (
              <div className="mt-3 flex justify-end">
                <button
                  onClick={() => {
                    setRecruitmentType([]);
                    setEducationLevel('');
                    setUpdateTimeAfter('');
                  }}
                  className="text-xs text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 transition-colors"
                >
                  清除所有筛选
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Results Section */}
        {jobs.length > 0 && (
          <div className="space-y-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white font-display">
                找到 {jobs.length} 个职位
              </h3>
            </div>

            {jobs.map((job) => (
              <div
                key={job.id}
                className="glass rounded-2xl shadow-md p-6 hover:shadow-glow-lg transition-all cursor-pointer
                           border border-primary-200/50 dark:border-primary-700/50 card-hover"
                onClick={() => handleViewDetail(job)}
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h4 className="text-xl font-semibold text-gray-900 dark:text-white mb-1 font-display">
                      {job.title}
                    </h4>
                    <div className="flex items-center gap-4 text-sm text-gray-700 dark:text-gray-300">
                      <div className="flex items-center gap-1">
                        <Building2 className="w-4 h-4 text-primary-500" />
                        <span>{job.company}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <MapPin className="w-4 h-4 text-primary-500" />
                        <span>{job.location}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <DollarSign className="w-4 h-4 text-primary-500" />
                        <span>{job.salary}</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                      匹配度: {(job.score * 100).toFixed(1)}%
                    </div>
                    {job.is_bookmarked && (
                      <span className="inline-block px-2 py-1 bg-accent-cyan/20 dark:bg-accent-cyan/30 text-accent-cyan dark:text-accent-teal text-xs rounded-lg font-semibold">
                        已收藏
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-4 text-sm text-gray-700 dark:text-gray-300 mb-3">
                  <span className="px-3 py-1 bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded-lg font-medium">
                    {job.recruitment_type}
                  </span>
                  <span className="px-3 py-1 bg-accent-cyan/20 dark:bg-accent-cyan/30 text-accent-cyan dark:text-accent-teal rounded-lg font-medium">
                    {job.education}
                  </span>
                  <div className="flex items-center gap-1">
                    <Calendar className="w-4 h-4 text-primary-500" />
                    <span>{job.update_time}</span>
                  </div>
                </div>

                <p className="text-gray-700 dark:text-gray-300 text-sm line-clamp-2">
                  {job.description}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && jobs.length === 0 && keyword && (
          <div className="text-center py-12 animate-fade-in">
            <div className="text-primary-400 text-6xl mb-4">🔍</div>
            <p className="text-gray-700 dark:text-gray-300 text-lg">暂无搜索结果</p>
            <p className="text-gray-600 dark:text-gray-400 text-sm mt-2">尝试更换关键词或调整搜索模式</p>
          </div>
        )}

        {/* Initial State */}
        {!loading && jobs.length === 0 && !keyword && (
          <div className="text-center py-12 animate-fade-in">
            <div className="text-primary-400 text-6xl mb-4">💼</div>
            <p className="text-gray-700 dark:text-gray-300 text-lg">开始你的求职之旅</p>
            <p className="text-gray-600 dark:text-gray-400 text-sm mt-2">输入关键词搜索心仪的职位</p>
          </div>
        )}
      </main>
      
      {/* Job Detail Modal */}
      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          isOpen={isModalOpen}
          onClose={() => {
            setIsModalOpen(false);
            setSelectedJob(null);
          }}
          source="dashboard"
        />
      )}

      {/* Security Question Setup Modal */}
      {showSecurityQuestionModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="glass rounded-3xl shadow-2xl p-8 max-w-md w-full border border-primary-200/50 dark:border-primary-700/50">
            <div className="text-center mb-6">
              <div className="mx-auto h-16 w-16 bg-gradient-to-br from-primary-500 via-accent-cyan to-primary-600 rounded-2xl flex items-center justify-center shadow-glow-lg mb-4">
                <svg className="h-9 w-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold gradient-text mb-2">设置安全问题</h3>
              <p className="text-sm text-gray-700 dark:text-gray-300">
                为了保障你的账号安全，请设置一个安全问题用于找回密码
              </p>
            </div>

            {securityQuestionError && (
              <div className="bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg text-sm mb-4 animate-fade-in">
                {securityQuestionError}
              </div>
            )}

            <form onSubmit={async (e) => {
              e.preventDefault();
              setSecurityQuestionError('');

              if (!securityQuestion) {
                setSecurityQuestionError('请选择一个安全问题');
                return;
              }

              if (!securityAnswer || securityAnswer.trim().length === 0) {
                setSecurityQuestionError('请填写答案');
                return;
              }

              setSettingSecurityQuestion(true);
              try {
                await authAPI.setSecurityQuestion(securityQuestion, securityAnswer.trim().toLowerCase());
                setShowSecurityQuestionModal(false);
              } catch (err: any) {
                setSecurityQuestionError(err.response?.data?.detail || '设置失败，请稍后重试');
              } finally {
                setSettingSecurityQuestion(false);
              }
            }} className="space-y-4">
              <div>
                <label htmlFor="sq" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  选择一个安全问题
                </label>
                <select
                  id="sq"
                  value={securityQuestion}
                  onChange={(e) => setSecurityQuestion(e.target.value)}
                  required
                  className="w-full px-4 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                             text-gray-900 dark:text-white
                             bg-white dark:bg-dark-600
                             focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
                >
                  <option value="">选择一个安全问题</option>
                  {securityQuestions.map((q, idx) => (
                    <option key={idx} value={q}>{q}</option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="sa" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  问题答案
                </label>
                <input
                  id="sa"
                  name="dash_answer_field" // 使用不同的 name 避免浏览器自动填充
                  type="text"
                  required
                  value={securityAnswer}
                  onChange={(e) => setSecurityAnswer(e.target.value)}
                  autoComplete="off" // 禁用自动填充
                  className="w-full px-4 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                             placeholder-gray-400 dark:placeholder-gray-500 text-gray-900 dark:text-white
                             bg-white dark:bg-dark-600
                             focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
                  placeholder="请输入答案"
                />
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowSecurityQuestionModal(false)}
                  className="flex-1 py-3 px-4 border-2 border-gray-300 dark:border-dark-500 text-gray-700 dark:text-gray-300
                             font-semibold rounded-xl hover:bg-gray-50 dark:hover:bg-dark-700
                             transition-all duration-200"
                >
                  稍后设置
                </button>
                <button
                  type="submit"
                  disabled={settingSecurityQuestion}
                  className="flex-1 py-3 px-4 bg-gradient-to-r from-primary-600 via-primary-500 to-accent-cyan hover:from-primary-700 hover:via-primary-600 hover:to-accent-teal
                             text-white font-bold rounded-xl shadow-lg hover:shadow-glow
                             disabled:opacity-50 disabled:cursor-not-allowed
                             transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
                >
                  {settingSecurityQuestion ? (
                    <span className="flex items-center justify-center">
                      <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      设置中...
                    </span>
                  ) : (
                    '确认设置'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
