'use client';

import { useState, useEffect } from 'react';
import { X, Settings, Plus, X as XIcon } from 'lucide-react';
import { userAPI } from '@/lib/api';

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
      <div className="bg-white dark:bg-dark-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden flex flex-col animate-scale-in">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-dark-600">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white font-display">
            求职偏好
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-600 transition-colors"
          >
            <X className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-gray-500 dark:text-gray-400">加载中...</div>
            </div>
          ) : (
            <>
              {/* Intended Location */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
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
                    className="flex-1 px-4 py-2 border-2 border-gray-200 dark:border-dark-600 rounded-xl bg-white dark:bg-dark-700 text-gray-900 dark:text-white focus:border-primary-500 focus:outline-none"
                    placeholder="输入城市名称，按回车添加"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addItem('intended_location', newLocation);
                      setNewLocation('');
                    }}
                    className="p-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {preferences.intended_location.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-1 px-3 py-1 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded-full"
                    >
                      <span>{item}</span>
                      <button
                        onClick={() => removeItem('intended_location', index)}
                        className="p-0.5 rounded hover:bg-primary-200 dark:hover:bg-primary-800"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Intended Industry */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
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
                    className="flex-1 px-4 py-2 border-2 border-gray-200 dark:border-dark-600 rounded-xl bg-white dark:bg-dark-700 text-gray-900 dark:text-white focus:border-primary-500 focus:outline-none"
                    placeholder="输入行业名称，按回车添加"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addItem('intended_industry', newIndustry);
                      setNewIndustry('');
                    }}
                    className="p-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {preferences.intended_industry.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-1 px-3 py-1 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded-full"
                    >
                      <span>{item}</span>
                      <button
                        onClick={() => removeItem('intended_industry', index)}
                        className="p-0.5 rounded hover:bg-primary-200 dark:hover:bg-primary-800"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Intended Position */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
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
                    className="flex-1 px-4 py-2 border-2 border-gray-200 dark:border-dark-600 rounded-xl bg-white dark:bg-dark-700 text-gray-900 dark:text-white focus:border-primary-500 focus:outline-none"
                    placeholder="输入职位名称，按回车添加"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addItem('intended_position', newPosition);
                      setNewPosition('');
                    }}
                    className="p-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700 transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {preferences.intended_position.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-1 px-3 py-1 bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 rounded-full"
                    >
                      <span>{item}</span>
                      <button
                        onClick={() => removeItem('intended_position', index)}
                        className="p-0.5 rounded hover:bg-primary-200 dark:hover:bg-primary-800"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-600 dark:text-red-400">
                  {error}
                </div>
              )}

              {/* Success Message */}
              {success && (
                <div className="p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-600 dark:text-green-400">
                  保存成功！
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 dark:border-dark-600 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-6 py-3 bg-gray-200 dark:bg-dark-600 text-gray-700 dark:text-gray-300 rounded-xl hover:bg-gray-300 dark:hover:bg-dark-500 transition-all font-medium"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving || loading}
            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-xl hover:from-primary-700 hover:to-primary-600 transition-all font-medium disabled:opacity-50"
          >
            <Settings className="w-4 h-4" />
            {saving ? '保存中...' : '保存偏好'}
          </button>
        </div>
      </div>
    </div>
  );
}
