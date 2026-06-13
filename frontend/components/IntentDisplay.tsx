'use client';

import { useState, useEffect } from 'react';
import { Edit2, Save, X, MapPin, Briefcase, DollarSign, Code, GraduationCap, TrendingUp } from 'lucide-react';

interface SalaryExpectation {
  min: number;
  max: number;
  currency: string;
}

interface SessionIntent {
  thread_id: string;
  intent: {
    preferred_city: string[];
    preferred_job_titles: string[];
    salary_expectation: SalaryExpectation | null;
    skills: string[];
    education_level: string | null;
    work_experience_years: number | null;
    search_direction: string | null;
    resume_id: string | null;
    include_resume_in_search: boolean;
  };
}

interface IntentDisplayProps {
  sessionId: string;
  onIntentChange?: (intent: SessionIntent['intent']) => void;
}

export default function IntentDisplay({ sessionId, onIntentChange }: IntentDisplayProps) {
  const [intent, setIntent] = useState<SessionIntent | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Partial<SessionIntent['intent']>>({});
  const [saving, setSaving] = useState(false);

  // 获取意图数据
  useEffect(() => {
    fetchIntent();
  }, [sessionId]);

  const fetchIntent = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/chat/sessions/${sessionId}/intent`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setIntent(data);
        setEditForm(data.intent || {});
      }
    } catch (err) {
      console.error('Failed to fetch intent:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/chat/sessions/${sessionId}/intent`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(editForm),
      });

      if (response.ok) {
        const updated = await response.json();
        setIntent(updated);
        setEditing(false);
        onIntentChange?.(updated.intent);
      }
    } catch (err) {
      console.error('Failed to save intent:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditForm(intent?.intent || {});
    setEditing(false);
  };

  const formatSalary = (salary: SalaryExpectation | null) => {
    if (!salary) return '未设置';
    return `${salary.min / 1000}-${salary.max / 1000}k/${salary.currency}`;
  };

  const renderTagList = (items: string[], icon: React.ReactNode) => (
    <div className="flex flex-wrap gap-1">
      {icon}
      {items.length > 0 ? (
        items.map((item, idx) => (
          <span key={idx} className="text-xs px-2 py-1 bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 rounded-full">
            {item}
          </span>
        ))
      ) : (
        <span className="text-xs text-gray-400">未设置</span>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50">
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary-500 border-t-transparent"></div>
          加载意图...
        </div>
      </div>
    );
  }

  if (!intent || !intent.intent) {
    return (
      <div className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          暂无求职意向，在对话中告诉我你的想法吧
        </p>
      </div>
    );
  }

  const { preferred_city, preferred_job_titles, salary_expectation, skills, education_level, work_experience_years, search_direction } = intent.intent;

  return (
    <div className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50 shadow-md">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-primary-600 dark:text-primary-400" />
          当前求职意向
        </h3>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 flex items-center gap-1 transition-colors"
          >
            <Edit2 className="w-3 h-3" />
            编辑
          </button>
        )}
      </div>

      {/* Content */}
      {editing ? (
        <div className="space-y-3">
          {/* 城市 */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              意向城市（用逗号分隔）
            </label>
            <input
              type="text"
              value={editForm.preferred_city?.join(', ') || ''}
              onChange={(e) => setEditForm({ ...editForm, preferred_city: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-dark-500 rounded-lg bg-white dark:bg-dark-600 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="北京, 上海, 深圳"
            />
          </div>

          {/* 岗位 */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              意向岗位（用逗号分隔）
            </label>
            <input
              type="text"
              value={editForm.preferred_job_titles?.join(', ') || ''}
              onChange={(e) => setEditForm({ ...editForm, preferred_job_titles: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-dark-500 rounded-lg bg-white dark:bg-dark-600 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="产品经理, 运营"
            />
          </div>

          {/* 技能 */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              技能（用逗号分隔）
            </label>
            <input
              type="text"
              value={editForm.skills?.join(', ') || ''}
              onChange={(e) => setEditForm({ ...editForm, skills: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-dark-500 rounded-lg bg-white dark:bg-dark-600 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="Python, 数据分析"
            />
          </div>

          {/* 工作经验 */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              工作年限
            </label>
            <input
              type="number"
              value={editForm.work_experience_years || ''}
              onChange={(e) => setEditForm({ ...editForm, work_experience_years: parseInt(e.target.value) || null })}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-dark-500 rounded-lg bg-white dark:bg-dark-600 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="2"
            />
          </div>

          {/* Buttons */}
          <div className="flex gap-2 pt-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-lg hover:from-primary-700 hover:to-primary-600 disabled:opacity-50 transition-all text-sm font-medium"
            >
              <Save className="w-4 h-4" />
              {saving ? '保存中...' : '保存'}
            </button>
            <button
              onClick={handleCancel}
              className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-gray-200 dark:bg-dark-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-dark-500 transition-all text-sm font-medium"
            >
              <X className="w-4 h-4" />
              取消
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          {/* 城市 */}
          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-gray-600 dark:text-gray-400">城市：</span>
              {renderTagList(preferred_city, null)}
            </div>
          </div>

          {/* 岗位 */}
          <div className="flex items-start gap-2">
            <Briefcase className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-gray-600 dark:text-gray-400">岗位：</span>
              {renderTagList(preferred_job_titles, null)}
            </div>
          </div>

          {/* 薪资 */}
          <div className="flex items-start gap-2">
            <DollarSign className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-gray-600 dark:text-gray-400">薪资期望：</span>
              <span className="text-gray-900 dark:text-white">{formatSalary(salary_expectation)}</span>
            </div>
          </div>

          {/* 技能 */}
          <div className="flex items-start gap-2">
            <Code className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-gray-600 dark:text-gray-400">技能：</span>
              {renderTagList(skills, null)}
            </div>
          </div>

          {/* 学历 */}
          {(education_level || work_experience_years) && (
            <div className="flex items-start gap-2">
              <GraduationCap className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
              <div>
                <span className="text-xs text-gray-600 dark:text-gray-400">背景：</span>
                <span className="text-gray-900 dark:text-white">
                  {education_level}{work_experience_years ? ` · ${work_experience_years}年经验` : ''}
                </span>
              </div>
            </div>
          )}

          {/* 求职方向 */}
          {search_direction && (
            <div className="flex items-start gap-2">
              <TrendingUp className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
              <div>
                <span className="text-xs text-gray-600 dark:text-gray-400">方向：</span>
                <span className="text-xs px-2 py-1 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded-full">
                  {search_direction}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
