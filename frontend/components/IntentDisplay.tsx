'use client';

import { useState, useEffect } from 'react';
import { Edit2, Save, X, MapPin, Briefcase, DollarSign, Code, GraduationCap, TrendingUp } from 'lucide-react';
import Button from '@/components/ui/Button';

interface SalaryRange {
  min: number;
  max?: number;
  currency: string;
}

interface ExperienceFilter {
  preferred_min_years?: number;
  preferred_max_years?: number;
  avoid_above_years?: number;
}

interface SessionIntent {
  thread_id: string;
  intent: {
    target_roles: string[];
    locations: string[];
    salary: SalaryRange | null;
    experience: ExperienceFilter | null;
    recruitment_types: string[];
    industries: string[];
    filters: Record<string, any>;
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

  const formatSalary = (salary: SalaryRange | null) => {
    if (!salary) return '未设置';
    const min = salary.min / 1000;
    const max = salary.max ? `${salary.max / 1000}k` : '以上';
    return `${min}-${max}/${salary.currency}`;
  };

  const renderTagList = (items: string[] | undefined, icon: React.ReactNode) => (
    <div className="flex flex-wrap gap-1">
      {icon}
      {items && items.length > 0 ? (
        items.map((item, idx) => (
          <span key={idx} className="text-xs px-2 py-0.5 bg-tint-primary text-tint-primary rounded-input">
            {item}
          </span>
        ))
      ) : (
        <span className="text-xs text-400">未设置</span>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="bg-layer1 border border-l1 rounded-menu p-4">
        <div className="flex items-center gap-2 text-sm text-500">
          <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary-500 border-t-transparent"></div>
          加载意图...
        </div>
      </div>
    );
  }

  if (!intent || !intent.intent) {
    return (
      <div className="bg-layer1 border border-l1 rounded-menu p-4">
        <p className="text-sm text-500">
          暂无求职意向，在对话中告诉我你的想法吧
        </p>
      </div>
    );
  }

  const { target_roles, locations, salary, experience, filters } = intent.intent;

  return (
    <div className="bg-layer1 border border-l1 rounded-menu shadow-lv1 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-900 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-primary-500" />
          当前求职意向
        </h3>
        {!editing && (
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)} className="text-primary-600 hover:text-primary-800 flex items-center gap-1">
            <Edit2 className="w-3 h-3" />
            编辑
          </Button>
        )}
      </div>

      {/* Content */}
      {editing ? (
        <div className="space-y-3">
          {/* 城市 */}
          <div>
            <label className="block text-xs font-medium text-700 mb-1">
              意向城市（用逗号分隔）
            </label>
            <input
              type="text"
              value={editForm.locations?.join(', ') || ''}
              onChange={(e) => setEditForm({ ...editForm, locations: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
              className="w-full px-3 py-2 text-sm rounded-input border border-l2 bg-base text-900 focus:outline-none focus:ring-2 focus:ring-primary-200 focus:border-transparent"
              placeholder="北京, 上海, 深圳"
            />
          </div>

          {/* 岗位 */}
          <div>
            <label className="block text-xs font-medium text-700 mb-1">
              意向岗位（用逗号分隔）
            </label>
            <input
              type="text"
              value={editForm.target_roles?.join(', ') || ''}
              onChange={(e) => setEditForm({ ...editForm, target_roles: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
              className="w-full px-3 py-2 text-sm rounded-input border border-l2 bg-base text-900 focus:outline-none focus:ring-2 focus:ring-primary-200 focus:border-transparent"
              placeholder="产品经理, 运营"
            />
          </div>

          {/* Buttons */}
          <div className="flex gap-2 pt-2">
            <Button onClick={handleSave} disabled={saving} variant="primary" size="sm" className="flex-1">
              <Save className="w-4 h-4" />
              {saving ? '保存中...' : '保存'}
            </Button>
            <Button onClick={handleCancel} variant="secondary" size="sm" className="flex-1">
              <X className="w-4 h-4" />
              取消
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          {/* 城市 */}
          <div className="flex items-start gap-2">
            <MapPin className="w-4 h-4 text-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-500">城市：</span>
              {renderTagList(locations, null)}
            </div>
          </div>

          {/* 岗位 */}
          <div className="flex items-start gap-2">
            <Briefcase className="w-4 h-4 text-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-500">岗位：</span>
              {renderTagList(target_roles, null)}
            </div>
          </div>

          {/* 薪资 */}
          <div className="flex items-start gap-2">
            <DollarSign className="w-4 h-4 text-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-xs text-500">薪资期望：</span>
              <span className="text-900">{formatSalary(salary)}</span>
            </div>
          </div>

          {/* 经验要求 */}
          {experience && (
            <div className="flex items-start gap-2">
              <GraduationCap className="w-4 h-4 text-400 flex-shrink-0 mt-0.5" />
              <div>
                <span className="text-xs text-500">经验要求：</span>
                <span className="text-900">
                  {experience.preferred_min_years}-{experience.preferred_max_years}年
                  {experience.avoid_above_years ? ` (不看${experience.avoid_above_years}年以上)` : ''}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
