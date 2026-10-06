'use client';

import { useState, useEffect } from 'react';
import { X, Settings, Plus, X as XIcon } from 'lucide-react';
import { userAPI } from '@/lib/api';
import Button, { buttonClasses } from '@/components/ui/Button';

interface PreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Preferences {
  intended_company: string[];
  intended_company_type: string[];
  intended_location: string[];
  intended_industry: string[];
  intended_position: string[];
  job_type: string[];
}

export default function PreferencesModal({ isOpen, onClose }: PreferencesModalProps) {
  const [preferences, setPreferences] = useState<Preferences>({
    intended_company: [],
    intended_company_type: [],
    intended_location: [],
    intended_industry: [],
    intended_position: [],
    job_type: [],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  // Input states for adding items
  const [newCompany, setNewCompany] = useState('');
  const [newLocation, setNewLocation] = useState('');
  const [newIndustry, setNewIndustry] = useState('');
  const [newPosition, setNewPosition] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadPreferences();
    }
  }, [isOpen]);

  const loadPreferences = async () => {
    try {
      setLoading(true);
      const response = await userAPI.getPreferences();
      setPreferences(response.data || {
        intended_company: [],
        intended_company_type: [],
        intended_location: [],
        intended_industry: [],
        intended_position: [],
        job_type: [],
      });
    } catch (error) {
      console.error('加载偏好失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      await userAPI.updatePreferences(preferences);
      setSuccess(true);
      
      setTimeout(() => {
        setSuccess(false);
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  const addItem = (field: keyof Preferences, value: string) => {
    if (!value.trim()) return;
    if (preferences[field].includes(value)) return;
    
    setPreferences({
      ...preferences,
      [field]: [...preferences[field], value],
    });
  };

  const removeItem = (field: keyof Preferences, index: number) => {
    setPreferences({
      ...preferences,
      [field]: preferences[field].filter((_, i) => i !== index),
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-layer1 rounded-dialog border border-l1 shadow-lv3 max-w-4xl w-full max-h-[85vh] overflow-hidden flex flex-col animate-fade-in">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-l2">
          <h2 className="text-2xl font-medium text-900">
            求职偏好
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-menu hover:bg-hover-neutral transition-colors"
          >
            <X className="w-5 h-5 text-700" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-500">加载中...</div>
            </div>
          ) : (
            <>
              {/* Intended Location */}
              <div>
                <label className="block text-sm font-medium text-700 mb-3">
                  期望城市
                </label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={newLocation}
                    onChange={(e) => setNewLocation(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addItem('intended_location', newLocation);
                        setNewLocation('');
                      }
                    }}
                    className="flex-1 px-4 py-2 rounded-input border border-l2 bg-base text-900 focus:outline-none focus:ring-2 focus:ring-primary-200"
                    placeholder="输入城市名称，按回车添加"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addItem('intended_location', newLocation);
                      setNewLocation('');
                    }}
                    className={buttonClasses('secondary', 'md', 'w-9 px-0 flex-shrink-0')}
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {preferences.intended_location.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-1 px-3 py-1 bg-tint-primary text-tint-primary rounded-full"
                    >
                      <span>{item}</span>
                      <button
                        onClick={() => removeItem('intended_location', index)}
                        className="p-0.5 rounded-input hover:bg-primary-200"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Intended Industry */}
              <div>
                <label className="block text-sm font-medium text-700 mb-3">
                  期望行业
                </label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={newIndustry}
                    onChange={(e) => setNewIndustry(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addItem('intended_industry', newIndustry);
                        setNewIndustry('');
                      }
                    }}
                    className="flex-1 px-4 py-2 rounded-input border border-l2 bg-base text-900 focus:outline-none focus:ring-2 focus:ring-primary-200"
                    placeholder="输入行业名称，按回车添加"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addItem('intended_industry', newIndustry);
                      setNewIndustry('');
                    }}
                    className={buttonClasses('secondary', 'md', 'w-9 px-0 flex-shrink-0')}
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {preferences.intended_industry.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-1 px-3 py-1 bg-tint-primary text-tint-primary rounded-full"
                    >
                      <span>{item}</span>
                      <button
                        onClick={() => removeItem('intended_industry', index)}
                        className="p-0.5 rounded-input hover:bg-primary-200"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Intended Position */}
              <div>
                <label className="block text-sm font-medium text-700 mb-3">
                  期望职位
                </label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={newPosition}
                    onChange={(e) => setNewPosition(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addItem('intended_position', newPosition);
                        setNewPosition('');
                      }
                    }}
                    className="flex-1 px-4 py-2 rounded-input border border-l2 bg-base text-900 focus:outline-none focus:ring-2 focus:ring-primary-200"
                    placeholder="输入职位名称，按回车添加"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addItem('intended_position', newPosition);
                      setNewPosition('');
                    }}
                    className={buttonClasses('secondary', 'md', 'w-9 px-0 flex-shrink-0')}
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {preferences.intended_position.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-1 px-3 py-1 bg-tint-primary text-tint-primary rounded-full"
                    >
                      <span>{item}</span>
                      <button
                        onClick={() => removeItem('intended_position', index)}
                        className="p-0.5 rounded-input hover:bg-primary-200"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="p-3 bg-tint-danger border border-tint-danger rounded-menu text-sm text-tint-danger">
                  {error}
                </div>
              )}

              {/* Success Message */}
              {success && (
                <div className="p-3 bg-tint-success border border-tint-success rounded-menu text-sm text-tint-success">
                  保存成功！
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-l2 flex gap-3">
          <Button onClick={onClose} variant="secondary" className="flex-1 px-6">
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving || loading} variant="primary" className="flex-1 px-6">
            <Settings className="w-4 h-4" />
            {saving ? '保存中...' : '保存偏好'}
          </Button>
        </div>
      </div>
    </div>
  );
}
