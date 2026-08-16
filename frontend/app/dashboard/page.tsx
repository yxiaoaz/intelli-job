'use client';

import { useState, useEffect, useMemo, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { jobAPI, authAPI, QueryEnhancement } from '@/lib/api';
import JobCard from '@/components/JobCard';
import { useBookmark } from '@/hooks/useBookmark';
import Navbar from '@/components/Navbar';
import SearchHistoryModal from '@/components/SearchHistoryModal';
import { exportJobsToExcel } from '@/lib/export';
import { Search, Clock, Download, ArrowUpDown, Loader2, MapPin, Sparkles } from 'lucide-react';
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

type SortOption = 'match' | 'newest';

const vectorSearchTexts = ['正在分析你的需求...', '正在匹配职位...', '正在生成推荐...'];
const fieldSearchTexts = ['正在搜索...', '正在筛选职位...', '正在整理结果...'];

/** 本地时区日期格式化为 YYYY-MM-DD（避免 toISOString 的 UTC 偏移导致边界日偏差） */
function formatLocalDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

interface SearchRecord {
  keyword: string;
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
  const [topK, setTopK] = useState<number>(50);
  
  // Hard Filter 状态
  const [recruitmentType, setRecruitmentType] = useState<string[]>([]);
  const [educationLevel, setEducationLevel] = useState<string>('');
  const [updateTimeAfter, setUpdateTimeAfter] = useState<string>('');   // YYYY-MM-DD
  const [updateTimeBefore, setUpdateTimeBefore] = useState<string>(''); // YYYY-MM-DD
  const [filterCompany, setFilterCompany] = useState('');
  const [filterCity, setFilterCity] = useState('');
  
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [isFieldOnlySearch, setIsFieldOnlySearch] = useState(false);
  const [enhancement, setEnhancement] = useState<QueryEnhancement | null>(null);

  // Sort & pagination
  const [sortBy, setSortBy] = useState<SortOption>('match');
  const [pageSize, setPageSize] = useState<number>(10);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // 收藏统一管理（挂载时从后端同步收藏列表）
  const { toggleBookmark } = useBookmark();

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

  // 收藏切换：委托 useBookmark，成功后同步 jobs state
  const handleToggleBookmark = (job: Job) => {
    toggleBookmark(job.id, (_id, newState) => {
      setJobs(prev => prev.map(j => j.id === job.id ? { ...j, is_bookmarked: newState } : j));
    });
  };

  // Restore state from URL/localStorage
  useEffect(() => {
    const urlKeyword = searchParams.get('q');
    const urlTopK = searchParams.get('topK');

    if (urlKeyword) setKeyword(decodeURIComponent(urlKeyword));
    if (urlTopK) setTopK(parseInt(urlTopK));

    // 恢复筛选/排序状态
    const urlType = searchParams.get('type');
    const urlEdu = searchParams.get('edu');
    const urlAfter = searchParams.get('after');
    const urlBefore = searchParams.get('before');
    const urlSort = searchParams.get('sort');
    if (urlType) setRecruitmentType(urlType.split(',').filter(t => ['EXPERIENCED', 'GRADUATE', 'INTERN'].includes(t)));
    if (urlEdu) setEducationLevel(urlEdu);
    if (urlAfter) setUpdateTimeAfter(urlAfter);
    if (urlBefore) setUpdateTimeBefore(urlBefore);
    if (urlSort && ['match', 'newest'].includes(urlSort)) setSortBy(urlSort as SortOption);

    if (!urlKeyword) {
      const savedKeyword = localStorage.getItem(`dashboard_search_${userId}_keyword`);
      if (savedKeyword) setKeyword(savedKeyword);
    }
    if (!urlTopK) {
      const savedTopK = localStorage.getItem(`dashboard_search_${userId}_topK`);
      if (savedTopK) setTopK(parseInt(savedTopK));
    }

    const currentKeyword = urlKeyword ? decodeURIComponent(urlKeyword) : (localStorage.getItem(`dashboard_search_${userId}_keyword`) || '');
    const currentTopK = urlTopK ? parseInt(urlTopK) : parseInt(localStorage.getItem(`dashboard_search_${userId}_topK`) || '50');

    if (currentKeyword && userId) {
      const cacheKey = `dashboard_jobs_${userId}_${currentKeyword}_hybrid_${currentTopK}`;
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
  const saveSearchToHistory = (kw: string, k: number) => {
    if (!userId) return;
    try {
      const historyKey = `search_history_${userId}`;
      const history: SearchRecord[] = JSON.parse(localStorage.getItem(historyKey) || '[]');

      // Deduplicate: remove existing entry with same keyword
      const filtered = history.filter(r => r.keyword !== kw);

      // Add new record at the beginning
      filtered.unshift({
        keyword: kw,
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

  const handleSearch = async (kwOverride?: string) => {
    const kw = (kwOverride ?? keyword).trim();
    const hasExactFilter = filterCompany.trim() || filterCity.trim();
    if (!kw && !hasExactFilter) {
      toast.error('请输入搜索关键词或筛选条件');
      return;
    }
    if (kwOverride) setKeyword(kwOverride);

    setLoading(true);
    setLoadingStep(0);
    setCurrentPage(1);
    setIsFieldOnlySearch(!kw && !!hasExactFilter);

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
        hardFilters.update_time_after = `${updateTimeAfter}T00:00:00`;
      }
      if (updateTimeBefore) {
        hardFilters.update_time_before = `${updateTimeBefore}T23:59:59`;
      }
      if (filterCompany.trim()) {
        hardFilters.company = filterCompany.trim();
      }
      if (filterCity.trim()) {
        hardFilters.city = filterCity.trim();
      }
      
      const response = await jobAPI.search({
        user_query_preference: kw ? { keywords: kw } : {},
        search_mode: 'hybrid',
        top_k: topK,
        hard_filters: Object.keys(hardFilters).length > 0 ? hardFilters : undefined,
      });

      clearTimeout(stepTimer);
      clearTimeout(stepTimer2);

      if (response.data.status === 'success') {
        const results = response.data.data;
        setJobs(results);
        
        // Store enhancement info for display
        if (response.data.enhancement) {
          setEnhancement(response.data.enhancement as QueryEnhancement);
        } else {
          setEnhancement(null);
        }
        
        const cacheKey = `dashboard_jobs_${userId}_${kw}_hybrid_${topK}`;
        const cacheData = {
          jobs: results,
          timestamp: Date.now(),
          expiresAt: Date.now() + 24 * 60 * 60 * 1000,
        };
        localStorage.setItem(cacheKey, JSON.stringify(cacheData));

        localStorage.setItem(`dashboard_search_${userId}_keyword`, kw);
        localStorage.setItem(`dashboard_search_${userId}_topK`, topK.toString());

        // Save to search history
        saveSearchToHistory(kw, topK);

        const params = new URLSearchParams();
        params.set('q', encodeURIComponent(kw));
        params.set('topK', topK.toString());
        if (recruitmentType.length > 0) params.set('type', recruitmentType.join(','));
        if (educationLevel) params.set('edu', educationLevel);
        if (updateTimeAfter) params.set('after', updateTimeAfter);
        if (updateTimeBefore) params.set('before', updateTimeBefore);
        params.set('sort', sortBy);
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

  const totalPages = Math.max(1, Math.ceil(jobs.length / pageSize));

  const displayedJobs = useMemo(() => {
    let sorted = [...jobs];
    switch (sortBy) {
      case 'newest':
        sorted.sort((a, b) => new Date(b.update_time).getTime() - new Date(a.update_time).getTime());
        break;
      case 'match':
      default:
        sorted.sort((a, b) => b.score - a.score);
        break;
    }
    return sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  }, [jobs, sortBy, currentPage, pageSize]);

  // 页码列表（带省略号逻辑）
  const pageNumbers = useMemo(() => {
    const pages: (number | '...')[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (currentPage > 3) pages.push('...');
      for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) pages.push(i);
      if (currentPage < totalPages - 2) pages.push('...');
      pages.push(totalPages);
    }
    return pages;
  }, [currentPage, totalPages]);

  // Stats
  const stats = useMemo(() => {
    if (jobs.length === 0) return null;
    const scores = jobs.map(j => j.score ?? 0);
    const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
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
    return { avgScore, topCities };
  }, [jobs]);

  // Query bar helpers
  const hasActiveFilters = keyword || recruitmentType.length > 0 || educationLevel || updateTimeAfter || updateTimeBefore || filterCompany || filterCity;

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
        setUpdateTimeBefore('');
        break;
      case 'company':
        setFilterCompany('');
        break;
      case 'city':
        setFilterCity('');
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
    setUpdateTimeBefore('');
    setFilterCompany('');
    setFilterCity('');
  };

  // 更新时间区间快捷预设
  const applyTimePreset = (days: number | null) => {
    if (!days) {
      setUpdateTimeAfter('');
      setUpdateTimeBefore('');
      return;
    }
    setUpdateTimeAfter(formatLocalDate(new Date(Date.now() - days * 24 * 60 * 60 * 1000)));
    setUpdateTimeBefore(formatLocalDate(new Date()));
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
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                title="单次返回数量上限"
                className="px-3 py-3 border-2 border-gray-300 dark:border-dark-500
                           bg-white dark:bg-dark-600 text-gray-900 dark:text-white text-sm
                           rounded-xl focus:ring-2 focus:ring-primary-500
                           transition-all duration-200 hover:border-primary-400 dark:hover:border-primary-600"
              >
                <option value={50}>返回 50 个</option>
                <option value={100}>返回 100 个</option>
                <option value={200}>返回 200 个</option>
              </select>

              <button
                onClick={() => handleSearch()}
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
              
              {(recruitmentType.length > 0 || educationLevel || updateTimeAfter || updateTimeBefore || filterCompany || filterCity) && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 dark:bg-primary-900/30 text-primary-800 dark:text-primary-300">
                  {recruitmentType.length + (educationLevel ? 1 : 0) + (updateTimeAfter || updateTimeBefore ? 1 : 0) + (filterCompany ? 1 : 0) + (filterCity ? 1 : 0)} 个筛选条件
                </span>
              )}
            </div>
            
            {/* 精确字段：公司 + 城市 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">公司名称</label>
                <input
                  type="text"
                  value={filterCompany}
                  onChange={(e) => setFilterCompany(e.target.value)}
                  placeholder="如：腾讯、字节跳动"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-dark-500
                             bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                             rounded-lg focus:ring-2 focus:ring-primary-500 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5">城市</label>
                <input
                  type="text"
                  value={filterCity}
                  onChange={(e) => setFilterCity(e.target.value)}
                  placeholder="如：深圳、北京"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-dark-500
                             bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                             rounded-lg focus:ring-2 focus:ring-primary-500 text-sm"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
              
              {/* Update time range */}
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">更新时间区间</label>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {([
                    { label: '不限', days: null },
                    { label: '最近7天', days: 7 },
                    { label: '最近30天', days: 30 },
                    { label: '最近3个月', days: 90 },
                  ] as { label: string; days: number | null }[]).map((preset) => {
                    const active = preset.days === null
                      ? !updateTimeAfter && !updateTimeBefore
                      : updateTimeAfter === formatLocalDate(new Date(Date.now() - preset.days * 24 * 60 * 60 * 1000));
                    return (
                      <button
                        key={preset.label}
                        onClick={() => applyTimePreset(preset.days)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all duration-200 ${
                          active
                            ? 'bg-primary-500 text-white shadow-md hover:bg-primary-600'
                            : 'bg-gray-100 dark:bg-dark-500 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-dark-400'
                        }`}
                      >
                        {preset.label}
                      </button>
                    );
                  })}
                </div>
                <div className="flex items-center gap-1.5">
                  <input
                    type="date"
                    value={updateTimeAfter}
                    onChange={(e) => setUpdateTimeAfter(e.target.value)}
                    className="flex-1 min-w-0 px-2 py-1.5 border border-gray-300 dark:border-dark-500
                               bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                               rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent text-xs"
                  />
                  <span className="text-xs text-gray-400 dark:text-gray-500 shrink-0">至</span>
                  <input
                    type="date"
                    value={updateTimeBefore}
                    onChange={(e) => setUpdateTimeBefore(e.target.value)}
                    className="flex-1 min-w-0 px-2 py-1.5 border border-gray-300 dark:border-dark-500
                               bg-white dark:bg-dark-600 text-gray-900 dark:text-white
                               rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent text-xs"
                  />
                </div>
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
              {(updateTimeAfter || updateTimeBefore) && (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300">
                  {updateTimeAfter && updateTimeBefore
                    ? `${updateTimeAfter} ~ ${updateTimeBefore}`
                    : updateTimeAfter
                      ? `${updateTimeAfter} 之后`
                      : `${updateTimeBefore} 之前`}
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
                  {(isFieldOnlySearch ? fieldSearchTexts : vectorSearchTexts)[loadingStep] || (isFieldOnlySearch ? fieldSearchTexts : vectorSearchTexts)[0]}
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

        {/* Search Intelligence Bar */}
        {enhancement && enhancement.synonyms.length > 0 && jobs.length > 0 && !loading && (
          <div className="rounded-xl border border-primary-200 dark:border-primary-700/50 bg-primary-50/60 dark:bg-primary-900/20 px-5 py-4 mb-4 animate-fade-in">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-2 min-w-0">
                {/* 叙事头 + 结果数 */}
                <div className="flex items-center flex-wrap gap-2">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-primary-700 dark:text-primary-300">
                    <Sparkles className="w-4 h-4" />
                    AI 已优化你的搜索
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">找到 {jobs.length} 个匹配职位</span>
                </div>
                {/* 原始需求 → 扩展方向（点击 chip 直接重新搜索） */}
                <div className="flex items-center flex-wrap gap-1.5 text-xs">
                  <span className="text-gray-600 dark:text-gray-400 font-medium">{enhancement.original_keywords}</span>
                  <span className="text-gray-400 dark:text-gray-500">→</span>
                  {enhancement.synonyms.map((syn, i) => (
                    <button
                      key={i}
                      onClick={() => handleSearch(syn)}
                      title={`以“${syn}”重新搜索`}
                      className="px-2 py-0.5 rounded-full font-medium bg-primary-100 dark:bg-primary-800/40
                                 text-primary-700 dark:text-primary-300
                                 hover:bg-primary-200 dark:hover:bg-primary-700/50 transition-colors"
                    >
                      {syn}
                    </button>
                  ))}
                </div>
                {/* 简历上下文 */}
                {enhancement.resume_context && (() => {
                  const parts = [enhancement.resume_context.latest_title, ...(enhancement.resume_context.skills || [])].filter(Boolean);
                  return parts.length > 0 ? (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      基于你的简历：{parts.join(' · ')}
                    </div>
                  ) : null;
                })()}
              </div>
              <button
                onClick={() => setEnhancement(null)}
                className="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors shrink-0"
                title="关闭 AI 扩展提示"
              >
                ×
              </button>
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
                  </select>
                </div>
                <button
                  onClick={() => exportJobsToExcel(jobs, `职位搜索_${keyword}`, {
                    keyword,
                    synonyms: enhancement?.synonyms,
                    filters: [
                      recruitmentType.length > 0 ? recruitmentType.map(t => typeLabels[t]).join('/') : null,
                      educationLevel ? `学历≥${eduLabels[educationLevel] || educationLevel}` : null,
                      updateTimeAfter || updateTimeBefore ? `${updateTimeAfter || '不限'} ~ ${updateTimeBefore || '不限'}` : null,
                    ].filter(Boolean).join('；') || undefined,
                  })}
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
                  onBookmark={() => handleToggleBookmark(job)}
                  onApply={() => job.url ? window.open(job.url, '_blank') : toast.error('该职位暂无原始链接')}
                />
              ))}
            </div>

            {/* Pagination */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
              {/* 每页条数 */}
              <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <span>每页</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setCurrentPage(1); }}
                  className="px-2 py-1 border border-gray-300 dark:border-dark-500 bg-white dark:bg-dark-600
                             text-gray-900 dark:text-white rounded-lg text-sm focus:ring-2 focus:ring-primary-500"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                </select>
                <span>条</span>
              </div>

              {/* 页码 */}
              <div className="flex items-center gap-1">
                <button
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-dark-500
                             text-gray-600 dark:text-gray-400 bg-white dark:bg-dark-700
                             disabled:opacity-40 disabled:cursor-not-allowed
                             hover:border-primary-400 hover:text-primary-600 transition-colors"
                >
                  上一页
                </button>
                {pageNumbers.map((p, i) =>
                  p === '...' ? (
                    <span key={`ellipsis-${i}`} className="px-1 text-gray-400 dark:text-gray-500 text-sm">…</span>
                  ) : (
                    <button
                      key={p}
                      onClick={() => setCurrentPage(p)}
                      className={`min-w-[2rem] px-2 py-1.5 text-sm rounded-lg border transition-colors ${
                        p === currentPage
                          ? 'bg-primary-500 text-white border-primary-500 font-semibold'
                          : 'border-gray-300 dark:border-dark-500 text-gray-600 dark:text-gray-400 bg-white dark:bg-dark-700 hover:border-primary-400 hover:text-primary-600'
                      }`}
                    >
                      {p}
                    </button>
                  )
                )}
                <button
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-dark-500
                             text-gray-600 dark:text-gray-400 bg-white dark:bg-dark-700
                             disabled:opacity-40 disabled:cursor-not-allowed
                             hover:border-primary-400 hover:text-primary-600 transition-colors"
                >
                  下一页
                </button>
              </div>

              {/* 数量信息 */}
              <span className="text-xs text-gray-400 dark:text-gray-500">
                第 {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, jobs.length)} 条，共 {jobs.length} 个
              </span>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!loading && jobs.length === 0 && keyword && (
          <div className="text-center py-12 animate-fade-in">
            <div className="text-primary-400 text-6xl mb-4">🔍</div>
            <p className="text-gray-700 dark:text-gray-300 text-lg">没有找到匹配岗位</p>
            <p className="text-gray-600 dark:text-gray-400 text-sm mt-2">尝试更换关键词或调整筛选条件</p>
            {enhancement && enhancement.synonyms.length > 0 && (
              <div className="mt-6">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">猜你想找：</p>
                <div className="flex justify-center flex-wrap gap-2">
                  {enhancement.synonyms.map((syn, i) => (
                    <button
                      key={i}
                      onClick={() => handleSearch(syn)}
                      className="px-4 py-1.5 rounded-full text-sm font-medium bg-primary-100 dark:bg-primary-900/30
                                 text-primary-700 dark:text-primary-300
                                 hover:bg-primary-200 dark:hover:bg-primary-800/40 transition-colors"
                    >
                      {syn}
                    </button>
                  ))}
                </div>
              </div>
            )}
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
