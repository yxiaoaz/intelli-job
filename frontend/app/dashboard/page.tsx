'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { jobAPI, authAPI } from '@/lib/api';
import JobCard from '@/components/JobCard';
import Navbar from '@/components/Navbar';
import { Search, MapPin, Building2, DollarSign, Calendar } from 'lucide-react';
import { toast } from 'sonner';
import SecurityQuestionModal from '@/components/SecurityQuestionModal';

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

  // Security Question Setup Modal
  const [showSecurityQuestionModal, setShowSecurityQuestionModal] = useState(false);

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
      toast.error('请输入搜索关键词');
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
      toast.error(error.response?.data?.detail || '搜索失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900 animate-fade-in">
      {/* Header */}
      <Navbar currentPath="/dashboard" />

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
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2">
                <svg className="w-4 h-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                </svg>
                高级筛选
              </h3>
              
              {/* 已选条件计数徽章 */}
              {(recruitmentType.length > 0 || educationLevel || updateTimeAfter) && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 dark:bg-primary-900/30 text-primary-800 dark:text-primary-300">
                  {recruitmentType.length + (educationLevel ? 1 : 0) + (updateTimeAfter ? 1 : 0)} 个筛选条件
                </span>
              )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* 招聘类型 - Tag 形式 */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  招聘类型
                </label>
                <div className="space-y-2">
                  <div className="flex flex-wrap gap-2">
                    {['EXPERIENCED', 'GRADUATE', 'INTERN'].map((type) => {
                      const labels = { EXPERIENCED: '社招', GRADUATE: '校招', INTERN: '实习' };
                      const isSelected = recruitmentType.includes(type);
                      return (
                        <button
                          key={type}
                          onClick={() => {
                            setRecruitmentType(prev => 
                              prev.includes(type) 
                                ? prev.filter(t => t !== type)
                                : [...prev, type]
                            );
                          }}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                            isSelected
                              ? 'bg-primary-500 text-white shadow-md hover:bg-primary-600'
                              : 'bg-gray-100 dark:bg-dark-500 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-400'
                          }`}
                          aria-pressed={isSelected}
                        >
                          {labels[type as keyof typeof labels]}
                          {isSelected && (
                            <span className="ml-1 inline-block">✓</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
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
            
            {/* 已选条件展示 + 清除按钮 */}
            {(recruitmentType.length > 0 || educationLevel || updateTimeAfter) && (
              <div className="mt-4 pt-3 border-t border-gray-200 dark:border-dark-600">
                <div className="flex items-center justify-between">
                  <div className="flex flex-wrap gap-2 flex-1">
                    {/* 招聘类型 Tags */}
                    {recruitmentType.map((type) => {
                      const labels = { EXPERIENCED: '社招', GRADUATE: '校招', INTERN: '实习' };
                      return (
                        <span
                          key={type}
                          className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-primary-100 dark:bg-primary-900/30 text-primary-800 dark:text-primary-300"
                        >
                          {labels[type as keyof typeof labels]}
                          <button
                            onClick={() => setRecruitmentType(prev => prev.filter(t => t !== type))}
                            className="ml-1 hover:text-primary-900 dark:hover:text-primary-100 focus:outline-none"
                            aria-label={`移除${labels[type as keyof typeof labels]}筛选`}
                          >
                            ×
                          </button>
                        </span>
                      );
                    })}
                    
                    {/* 学历要求 Tag */}
                    {educationLevel && (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300">
                        {(() => {
                          const eduLabels: Record<string, string> = {
                            ASSOCIATE: '专科',
                            UNDERGRADUATE: '本科',
                            MASTERS: '硕士',
                            DOCTOR: '博士'
                          };
                          return `学历: ${eduLabels[educationLevel]}`;
                        })()}
                        <button
                          onClick={() => setEducationLevel('')}
                          className="ml-1 hover:text-purple-900 dark:hover:text-purple-100 focus:outline-none"
                          aria-label="移除学历要求筛选"
                        >
                          ×
                        </button>
                      </span>
                    )}
                    
                    {/* 更新时间 Tag */}
                    {updateTimeAfter && (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                        最近发布
                        <button
                          onClick={() => setUpdateTimeAfter('')}
                          className="ml-1 hover:text-green-900 dark:hover:text-green-100 focus:outline-none"
                          aria-label="移除时间筛选"
                        >
                          ×
                        </button>
                      </span>
                    )}
                  </div>
                  
                  {/* 一键清除所有 */}
                  <button
                    onClick={() => {
                      setRecruitmentType([]);
                      setEducationLevel('');
                      setUpdateTimeAfter('');
                    }}
                    className="ml-3 px-3 py-1 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-red-500"
                    aria-label="清除所有筛选条件"
                  >
                    清除全部
                  </button>
                </div>
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

            <div className="grid grid-cols-1 gap-4">
              {jobs.map((job, idx) => (
                <JobCard
                  key={job.id}
                  job={{
                    ...job,
                    match_score: job.score * 100,
                    truncated_description: job.description,
                  }}
                  index={idx}
                  onClick={() => router.push(`/jobs/${job.id}?from=dashboard`)}
                  isBookmarked={job.is_bookmarked}
                />
              ))}
            </div>
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

      {/* Security Question Setup Modal */}
      <SecurityQuestionModal
        isOpen={showSecurityQuestionModal}
        onClose={() => setShowSecurityQuestionModal(false)}
      />
    </div>
  );
}
