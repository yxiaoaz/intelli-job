'use client';

import { useState, useEffect, useMemo, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { jobAPI, authAPI } from '@/lib/api';
import JobCard from '@/components/JobCard';
import Navbar from '@/components/Navbar';
import SearchHistoryModal from '@/components/SearchHistoryModal';
import { exportJobsToExcel } from '@/lib/export';
import { Search, Clock, Download, ArrowUpDown, Loader2, MapPin, DollarSign, Sparkles } from 'lucide-react';
import { recruitmentTypeLabels } from '@/lib/constants';
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

type SortOption = 'match' | 'newest' | 'salary_high';

const loadingTexts = ['正在分析你的需求...', '正在匹配职位...', '正在生成推荐...'];

/** Parse salary string like "30-50k" to max numeric value (50) */
function parseSalaryMax(salary: string): number {
  if (!salary) return 0;
  const matches = Array.from(salary.matchAll(/(\d+)/g));
  if (matches.length === 0) return 0;
  const last = parseInt(matches[matches.length - 1][1]);
  return salary.includes('万') ? last * 1000 : last;
}

interface SearchRecord {
  keyword: string;
  mode: string;
  topK: number;
  timestamp: string;
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
  
  const [userId, setUserId] = useState<string>('');
  
  const [keyword, setKeyword] = useState('');
  const [searchMode, setSearchMode] = useState<'hybrid' | 'keyword' | 'vector'>('hybrid');
  const [topK, setTopK] = useState<number>(50);
  
  // Hard Filter 状态
  const [recruitmentType, setRecruitmentType] = useState<string[]>([]);
  const [educationLevel, setEducationLevel] = useState<string>('');
  const [updateTimeAfter, setUpdateTimeAfter] = useState<string>('');
  
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);

  // Sort & pagination
  const [sortBy, setSortBy] = useState<SortOption>('match');
  const [displayCount, setDisplayCount] = useState(20);

  // Modals
  const [showSecurityQuestionModal, setShowSecurityQuestionModal] = useState(false);
  const [showSearchHistory, setShowSearchHistory] = useState(false);

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }
    
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUserId(payload.sub || '');
    } catch (error) {
      console.error('Failed to decode token:', error);
    }

    checkSecurityQuestionStatus();
  }, [router]);

  const checkSecurityQuestionStatus = async () => {
    try {
      const response = await authAPI.getSecurityQuestionStatus();
      if (!response.data.has_security_question) {
        setShowSecurityQuestionModal(true);
      }
    } catch (error) {
      console.error('Failed to check security question status:', error);
    }
  };

  // Restore state from URL/localStorage
  useEffect(() => {
    const urlKeyword = searchParams.get('q');
    const urlMode = searchParams.get('mode') as any;
    const urlTopK = searchParams.get('topK');
    
    if (urlKeyword) setKeyword(decodeURIComponent(urlKeyword));
    if (urlMode && ['hybrid', 'keyword', 'vector'].includes(urlMode)) setSearchMode(urlMode);
    if (urlTopK) setTopK(parseInt(urlTopK));
    
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
    
    const currentKeyword = urlKeyword ? decodeURIComponent(urlKeyword) : (localStorage.getItem(`dashboard_search_${userId}_keyword`) || '');
    const currentMode = urlMode || (localStorage.getItem(`dashboard_search_${userId}_mode`) || 'hybrid');
    const currentTopK = urlTopK ? parseInt(urlTopK) : parseInt(localStorage.getItem(`dashboard_search_${userId}_topK`) || '50');
    
    if (currentKeyword && userId) {
      const cacheKey = `dashboard_jobs_${userId}_${currentKeyword}_${currentMode}_${currentTopK}`;
      const cachedJobs = localStorage.getItem(cacheKey);
      if (cachedJobs) {
        try {
          const parsed = JSON.parse(cachedJobs);
          setJobs(parsed.jobs || parsed);
        } catch (err) {
          console.error('Failed to parse cached jobs:', err);
        }
      }
    }
    
    cleanupExpiredCache();
  }, [userId, searchParams]);

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
          // ignore
        }
      }
    }
    
    keysToRemove.forEach(key => localStorage.removeItem(key));
  };

  // Save search to history
  const saveSearchToHistory = (kw: string, mode: string, k: number) => {
    if (!userId) return;
    try {
      const historyKey = `search_history_${userId}`;
      const history: SearchRecord[] = JSON.parse(localStorage.getItem(historyKey) || '[]');
      
      // Deduplicate: remove existing entry with same keyword
      const filtered = history.filter(r => r.keyword !== kw);
      
      // Add new record at the beginning
      filtered.unshift({
        keyword: kw,
        mode,
        topK: k,
        timestamp: new Date().toISOString(),
      });
      
      // Keep max 20
      const trimmed = filtered.slice(0, 20);
      localStorage.setItem(historyKey, JSON.stringify(trimmed));
    } catch (err) {
      console.error('Failed to save search history:', err);
    }
  };

  const handleSearch = async () => {
    if (!keyword.trim()) {
      toast.error('请输入搜索关键词');
      return;
    }

    setLoading(true);
    setLoadingStep(0);
    setDisplayCount(20);

    // Simulate loading steps
    const stepTimer = setTimeout(() => setLoadingStep(1), 600);
    const stepTimer2 = setTimeout(() => setLoadingStep(2), 1200);

    try {
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

      clearTimeout(stepTimer);
      clearTimeout(stepTimer2);

      if (response.data.status === 'success') {
        const results = response.data.data;
        setJobs(results);
        
        const cacheKey = `dashboard_jobs_${userId}_${keyword}_${searchMode}_${topK}`;
        const cacheData = {
          jobs: results,
          timestamp: Date.now(),
          expiresAt: Date.now() + 24 * 60 * 60 * 1000,
        };
        localStorage.setItem(cacheKey, JSON.stringify(cacheData));
        
        localStorage.setItem(`dashboard_search_${userId}_keyword`, keyword);
        localStorage.setItem(`dashboard_search_${userId}_mode`, searchMode);
        localStorage.setItem(`dashboard_search_${userId}_topK`, topK.toString());
        
        // Save to search history
        saveSearchToHistory(keyword, searchMode, topK);
        
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
      setLoadingStep(0);
    }
  };

  const displayedJobs = useMemo(() => {
    let sorted = [...jobs];
    switch (sortBy) {
      case 'newest':
        sorted.sort((a, b) => new Date(b.update_time).getTime() - new Date(a.update_time).getTime());
        break;
      case 'salary_high':
        sorted.sort((a, b) => parseSalaryMax(b.salary) - parseSalaryMax(a.salary));
        break;
      case 'match':
      default:
        sorted.sort((a, b) => b.score - a.score);
        break;
    }
    return sorted.slice(0, displayCount);
  }, [jobs, sortBy, displayCount]);

  // Stats
  const stats = useMemo(() => {
    if (jobs.length === 0) return null;
    const scores = jobs.map(j => j.score ?? 0);
    const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
    const maxSalary = Math.max(...jobs.map(j => parseSalaryMax(j.salary)));
    const cityMap = new Map<string, number>();
    jobs.forEach(j => {
      const city = j.location?.split('/')[0]?.trim() || '未知';
      cityMap.set(city, (cityMap.get(city) || 0) + 1);
    });
    const topCities = Array.from(cityMap.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([city, count]) => `${city} ${count}`)
      .join('、');
    return { avgScore, maxSalary, topCities };
  }, [jobs]);

  // Query bar helpers
  const hasActiveFilters = keyword || recruitmentType.length > 0 || educationLevel || updateTimeAfter;

  const removeFilter = (filter: string) => {
    switch (filter) {
      case 'keyword':
        setKeyword('');
        break;
      case 'education':
        setEducationLevel('');
        break;
      case 'time':
        setUpdateTimeAfter('');
        break;
      default:
        if (filter.startsWith('type:')) {
          setRecruitmentType(prev => prev.filter(t => t !== filter.replace('type:', '')));
        }
        break;
    }
  };

  const clearAllFilters = () => {
    setKeyword('');
    setRecruitmentType([]);
    setEducationLevel('');
    setUpdateTimeAfter('');
  };

  const eduLabels: Record<string, string> = {
    ASSOCIATE: '专科',
    UNDERGRADUATE: '本科',
    MASTERS: '硕士',
    DOCTOR: '博士',
  };

  const typeLabels = recruitmentTypeLabels;

  return (
    <div className="min-h-screen bg-gradient-to-br from-dark-50 via-white to-primary-50 dark:from-dark-900 dark:via-dark-800 dark:to-dark-900 animate-fade-in">
      <Navbar currentPath="/dashboard" />

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Search Section */}
        <div className="glass rounded-2xl shadow-lg p-6 mb-6 border border-primary-200/50 dark:border-primary-700/50 card-hover">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white font-display">职位搜索</h2>
          
          {/* Keyword search - responsive */}
          <div className="flex flex-col md:flex-row gap-3 mb-4">
            <div className="flex-1 flex gap-2">
              {/* Search history button */}
              <button
                onClick={() => setShowSearchHistory(true)}
                className="px-3 py-3 border-2 border-gray-300 dark:border-dark-500 rounded-xl
                           bg-white dark:bg-dark-600 text-gray-500 dark:text-gray-400
                           hover:border-primary-400 hover:text-primary-500 dark:hover:border-primary-600
                           transition-all duration-200"
                title="搜索历史"
              >
                <Clock className="w-5 h-5" />
              </button>
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-primary-400 dark:text-primary-500 w-5 h-5" />
                <input
                  type="text"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="输入职位关键词，如：产品经理、Java开发..."
                  className="w-full pl-10 pr-4 py-3 border-2 border-gray-300 dark:border-dark-500
                             bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                             rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent
                             transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
                />
              </div>
            </div>
            
            <div className="flex gap-2 flex-wrap">
              <select
                value={searchMode}
                onChange={(e) => setSearchMode(e.target.value as any)}
                className="px-3 py-3 border-2 border-gray-300 dark:border-dark-500
                           bg-white dark:bg-dark-600 text-gray-900 dark:text-white text-sm
                           rounded-xl focus:ring-2 focus:ring-primary-500
                           transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
              >
                <option value="hybrid">混合搜索</option>
                <option value="keyword">关键词搜索</option>
                <option value="vector">向量搜索</option>
              </select>

              <button
                onClick={handleSearch}
                disabled={loading}
                className="px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600
                           disabled:opacity-50 disabled:cursor-not-allowed font-semibold shadow-lg hover:shadow-glow
                           transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]
                           flex items-center gap-2 min-w-[100px] justify-center"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    搜索中
                  </>
                ) : '搜索'}
              </button>
            </div>
          </div>
          
          {/* Hard Filter */}
          <div className="border-t border-gray-200 dark:border-dark-600 pt-4 mt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2">
                <svg className="w-4 h-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                </svg>
                高级筛选
              </h3>
              
              {(recruitmentType.length > 0 || educationLevel || updateTimeAfter) && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 dark:bg-primary-900/30 text-primary-800 dark:text-primary-300">
                  {recruitmentType.length + (educationLevel ? 1 : 0) + (updateTimeAfter ? 1 : 0)} 个筛选条件
                </span>
              )}
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Recruitment type */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">招聘类型</label>
                <div className="flex flex-wrap gap-2">
                  {['EXPERIENCED', 'GRADUATE', 'INTERN'].map((type) => {
                    const isSelected = recruitmentType.includes(type);
                    return (
                      <button
                        key={type}
                        onClick={() => {
                          setRecruitmentType(prev => 
                            prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
                          );
                        }}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                          isSelected
                            ? 'bg-primary-500 text-white shadow-md hover:bg-primary-600'
                            : 'bg-gray-100 dark:bg-dark-500 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-400'
                        }`}
                      >
                        {typeLabels[type]}
                        {isSelected && <span className="ml-1">✓</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
              
              {/* Education */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">最低学历要求</label>
                <select
                  value={educationLevel}
                  onChange={(e) => setEducationLevel(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-dark-500
                             bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                             rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm"
                >
                  <option value="">不限</option>
                  <option value="ASSOCIATE">专科</option>
                  <option value="UNDERGRADUATE">本科</option>
                  <option value="MASTERS">硕士</option>
                  <option value="DOCTOR">博士</option>
                </select>
              </div>
              
              {/* Update time */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">最近发布</label>
                <select
                  value={updateTimeAfter}
                  onChange={(e) => setUpdateTimeAfter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-dark-500
                             bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                             rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm"
                >
                  <option value="">不限时间</option>
                  <option value={new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()}>最近7天</option>
                  <option value={new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString()}>最近14天</option>
                  <option value={new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()}>最近30天</option>
                  <option value={new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString()}>最近3个月</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Query Bar */}
        {hasActiveFilters && jobs.length > 0 && (
          <div className="glass rounded-xl border border-gray-200 dark:border-dark-600 px-4 py-3 mb-6 animate-fade-in">
            <div className="flex items-center flex-wrap gap-2">
              {keyword && (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-primary-100 dark:bg-primary-900/30 text-primary-800 dark:text-primary-300">
                  {keyword}
                  <button onClick={() => removeFilter('keyword')} className="ml-1 hover:text-primary-900">×</button>
                </span>
              )}
              {recruitmentType.map(type => (
                <span key={type} className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300">
                  {typeLabels[type]}
                  <button onClick={() => removeFilter(`type:${type}`)} className="ml-1 hover:text-blue-900">×</button>
                </span>
              ))}
              {educationLevel && (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300">
                  {eduLabels[educationLevel]}
                  <button onClick={() => removeFilter('education')} className="ml-1 hover:text-purple-900">×</button>
                </span>
              )}
              {updateTimeAfter && (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                  最近发布
                  <button onClick={() => removeFilter('time')} className="ml-1 hover:text-green-900">×</button>
                </span>
              )}
              <button
                onClick={clearAllFilters}
                className="ml-auto text-xs text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 font-medium"
              >
                清空全部
              </button>
            </div>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="space-y-4 mb-6 animate-fade-in">
            <div className="text-center py-8">
              <div className="inline-flex items-center gap-3 px-6 py-3 rounded-xl bg-white dark:bg-dark-700 shadow-lg border border-gray-200 dark:border-dark-600">
                <Loader2 className="w-5 h-5 animate-spin text-primary-500" />
                <span className="text-sm text-gray-700 dark:text-gray-300 font-medium">
                  {loadingTexts[loadingStep] || loadingTexts[0]}
                </span>
              </div>
            </div>
            {/* Skeleton cards */}
            <div className="grid grid-cols-1 gap-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="rounded-xl border border-gray-200 dark:border-dark-600 bg-white dark:bg-dark-700 p-4 animate-pulse" style={{ animationDelay: `${i * 150}ms` }}>
                  <div className="flex justify-between mb-3">
                    <div className="space-y-2 flex-1">
                      <div className="h-4 bg-gray-200 dark:bg-dark-500 rounded w-1/3"></div>
                      <div className="h-3 bg-gray-100 dark:bg-dark-600 rounded w-1/4"></div>
                    </div>
                    <div className="h-5 w-12 bg-gray-200 dark:bg-dark-500 rounded"></div>
                  </div>
                  <div className="flex gap-3 mb-3">
                    <div className="h-3 w-16 bg-gray-100 dark:bg-dark-600 rounded"></div>
                    <div className="h-3 w-16 bg-gray-100 dark:bg-dark-600 rounded"></div>
                    <div className="h-3 w-16 bg-gray-100 dark:bg-dark-600 rounded"></div>
                  </div>
                  <div className="flex gap-2">
                    <div className="h-7 w-20 bg-gray-100 dark:bg-dark-600 rounded-md"></div>
                    <div className="h-7 w-16 bg-gray-100 dark:bg-dark-600 rounded-md"></div>
                    <div className="h-7 w-20 bg-gray-200 dark:bg-dark-500 rounded-md"></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results Section */}
        {!loading && jobs.length > 0 && (
          <div className="space-y-4">
            {/* Stats + Sort row */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              {/* Stats */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                <div className="flex items-center gap-1.5 font-semibold text-gray-900 dark:text-white">
                  <Sparkles className="w-4 h-4 text-primary-500" />
                  <span>共 {jobs.length} 个职位</span>
                </div>
                {stats && (
                  <>
                    <span className="text-gray-300 dark:text-gray-600 hidden sm:inline">·</span>
                    <div className="flex items-center gap-1 text-gray-600 dark:text-gray-400">
                      <span>平均匹配度</span>
                      <span className={`font-semibold ${stats.avgScore >= 0.7 ? 'text-emerald-600 dark:text-emerald-400' : stats.avgScore >= 0.3 ? 'text-amber-600 dark:text-amber-400' : 'text-red-500 dark:text-red-400'}`}>
                        {(stats.avgScore * 100).toFixed(0)}%
                      </span>
                    </div>
                    {stats.maxSalary > 0 && (
                      <>
                        <span className="text-gray-300 dark:text-gray-600 hidden sm:inline">·</span>
                        <div className="flex items-center gap-1 text-gray-600 dark:text-gray-400">
                          <DollarSign className="w-3.5 h-3.5" />
                          <span>最高 <strong className="text-green-600 dark:text-green-400">{stats.maxSalary}k</strong></span>
                        </div>
                      </>
                    )}
                    {stats.topCities && (
                      <>
                        <span className="text-gray-300 dark:text-gray-600 hidden sm:inline">·</span>
                        <div className="flex items-center gap-1 text-gray-600 dark:text-gray-400">
                          <MapPin className="w-3.5 h-3.5" />
                          <span>{stats.topCities}</span>
                        </div>
                      </>
                    )}
                  </>
                )}
              </div>

              {/* Sort + Export */}
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
                  <ArrowUpDown className="w-4 h-4" />
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as SortOption)}
                    className="px-2 py-1 border border-gray-300 dark:border-dark-500 bg-white dark:bg-dark-600
                               text-gray-900 dark:text-white rounded-lg text-sm focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="match">AI匹配度</option>
                    <option value="newest">最新发布</option>
                    <option value="salary_high">薪资最高</option>
                  </select>
                </div>
                <button
                  onClick={() => exportJobsToExcel(jobs, `职位搜索_${keyword}`)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg
                             border border-gray-300 dark:border-dark-500 text-gray-600 dark:text-gray-400
                             hover:border-primary-400 hover:text-primary-600 dark:hover:border-primary-500
                             dark:hover:text-primary-400 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  导出 Excel
                </button>
              </div>
            </div>

            {/* Job cards */}
            <div className="grid grid-cols-1 gap-4">
              {displayedJobs.map((job, idx) => (
                <JobCard
                  key={job.id}
                  job={{
                    ...job,
                    match_score: job.score * 100,
                    truncated_description: job.description,
                  }}
                  index={idx}
                  onViewDetail={() => router.push(`/jobs/${job.id}?from=dashboard`)}
                  isBookmarked={job.is_bookmarked}
                />
              ))}
            </div>

            {/* Load more */}
            {displayCount < jobs.length && (
              <div className="text-center pt-2">
                <button
                  onClick={() => setDisplayCount(prev => prev + 20)}
                  className="px-8 py-3 text-sm font-medium rounded-xl border-2 border-gray-300 dark:border-dark-500
                             text-gray-700 dark:text-gray-300 bg-white dark:bg-dark-700
                             hover:border-primary-400 hover:text-primary-600 dark:hover:border-primary-500
                             transition-all duration-200"
                >
                  加载更多（还有 {jobs.length - displayCount} 个）
                </button>
              </div>
            )}
            {jobs.length > 20 && (
              <p className="text-center text-xs text-gray-400 dark:text-gray-500">
                共 {jobs.length} 个职位，已显示 {Math.min(displayCount, jobs.length)} 个
              </p>
            )}
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

      {/* Search History Modal */}
      <SearchHistoryModal
        isOpen={showSearchHistory}
        onClose={() => setShowSearchHistory(false)}
        onSelect={(record) => {
          setKeyword(record.keyword);
          if (record.mode) setSearchMode(record.mode as any);
          setShowSearchHistory(false);
        }}
      />

      {/* Security Question Modal */}
      <SecurityQuestionModal
        isOpen={showSecurityQuestionModal}
        onClose={() => setShowSecurityQuestionModal(false)}
      />
    </div>
  );
}
