'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { jobAPI } from '@/lib/api';
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
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // 用户 ID（用于缓存隔离）
  const [userId, setUserId] = useState<string>('');
  
  // ✅ 修复 SSR 问题：使用简单初始化，在 useEffect 中恢复 localStorage 状态
  const [keyword, setKeyword] = useState('');
  const [searchMode, setSearchMode] = useState<'hybrid' | 'keyword' | 'vector'>('hybrid');
  const [topK, setTopK] = useState<number>(10);
  
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Job Detail Modal State
  const [selectedJob, setSelectedJob] = useState<any>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

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
  }, [router]);

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
      const response = await jobAPI.search({
        user_query_preference: { keywords: keyword },
        search_mode: searchMode,
        top_k: topK,
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
    </div>
  );
}
