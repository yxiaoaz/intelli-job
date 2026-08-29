'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { FileText, Upload, CheckCircle, AlertCircle, Settings2 } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';

// ✅ 字段对齐 GET /api/v1/resumes/ 的真实响应结构
interface Resume {
  id: string;
  filename: string;
  status?: string;
  is_default?: boolean;
  manually_edited?: boolean;
  summary?: {
    latest_title: string | null;
    latest_company: string | null;
    highest_degree: string | null;
    skills_preview: string[];
    completeness: number | null;
    suggestion_count: number;
  } | null;
}

interface ResumeStatusCardProps {
  sessionId: string;
  onUploadSuccess?: (resumeId: string) => void;
}

export default function ResumeStatusCard({ sessionId, onUploadSuccess }: ResumeStatusCardProps) {
  const [resume, setResume] = useState<Resume | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 获取最新简历
  useEffect(() => {
    fetchLatestResume();
  }, []);

  // 如果简历正在解析中，自动轮询更新状态
  useEffect(() => {
    if (resume?.status === 'pending' || resume?.status === 'processing') {
      const interval = setInterval(fetchLatestResume, 3000); // 每3秒轮询
      return () => clearInterval(interval);
    }
  }, [resume?.status]);

  const fetchLatestResume = async () => {
    try {
      setLoading(true);
      // ✅ API 返回裸数组（旧代码误读 data.resumes），优先展示默认（使用中）简历
      const response = await fetchWithAuth('/api/v1/resumes/');

      if (response.ok) {
        const data = await response.json();
        const list: Resume[] = Array.isArray(data) ? data : data.resumes || [];
        const active = list.find((r) => r.is_default);
        setResume(active || list[0] || null);
      }
    } catch (err) {
      console.error('Failed to fetch resume:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // 验证文件类型
    const allowedTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!allowedTypes.includes(file.type)) {
      setError('只支持 PDF 和 Word 文档');
      return;
    }

    try {
      setUploading(true);
      setError(null);

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetchWithAuth('/api/v1/resumes/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        // 检查返回数据结构（兼容新旧格式）
        const resumeData = data.resume || data;
        if (resumeData && resumeData.id) {
          setResume(resumeData);
          onUploadSuccess?.(resumeData.id);
        } else {
          setError('上传成功但数据格式异常');
          console.error('Unexpected response structure:', data);
        }
      } else {
        const errorData = await response.json();
        setError(errorData.detail || '上传失败');
      }
    } catch (err) {
      setError('上传失败，请重试');
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <FileText className="w-5 h-5 text-yellow-500" />;
    }
  };

  const getStatusText = (status?: string) => {
    switch (status) {
      case 'completed':
        return '已解析';
      case 'processing':
        return '解析中...';
      case 'failed':
        return '解析失败';
      default:
        return '待解析';
    }
  };

  if (loading) {
    return (
      <div className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50">
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary-500 border-t-transparent"></div>
          加载中...
        </div>
      </div>
    );
  }

  return (
    <div className="glass rounded-xl p-4 border border-primary-200/50 dark:border-primary-700/50 shadow-md">
      {resume ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {getStatusIcon(resume.status)}
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {resume.filename}
              </span>
              {resume.is_default && (
                <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 rounded-full">
                  默认
                </span>
              )}
            </div>
            <span className={`text-xs px-2 py-1 rounded-full ${
              resume.status === 'completed' 
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : resume.status === 'failed'
                ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
            }`}>
              {getStatusText(resume.status)}
            </span>
          </div>
          
          {resume.status === 'completed' && (
            <p className="text-xs text-gray-600 dark:text-gray-400">
              ✓ 简历已解析，将用于智能匹配
            </p>
          )}

          {/* 简历画像摘要（对齐列表 API 的 summary） */}
          {resume.status === 'completed' && resume.summary && (
            <div className="mt-3 p-3 bg-gray-50 dark:bg-dark-700 rounded-lg space-y-1">
              {(resume.summary.latest_title || resume.summary.latest_company) && (
                <p className="text-xs text-gray-700 dark:text-gray-300">
                  💼 {resume.summary.latest_title}{resume.summary.latest_company ? ` @ ${resume.summary.latest_company}` : ''}
                </p>
              )}
              {resume.summary.highest_degree && (
                <p className="text-xs text-gray-700 dark:text-gray-300">
                  🎓 {resume.summary.highest_degree}
                </p>
              )}
              {resume.summary.skills_preview.length > 0 && (
                <p className="text-xs text-gray-700 dark:text-gray-300">
                  🛠️ {resume.summary.skills_preview.join(', ')}
                </p>
              )}
            </div>
          )}

          {resume.status === 'failed' && (
            <p className="text-xs text-red-600 dark:text-red-400">
              ✗ 解析失败，请重新上传
            </p>
          )}

          {/* 重新上传按钮 */}
          <label className="block mt-2">
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleUpload}
              disabled={uploading}
              className="hidden"
            />
            <span className="inline-flex items-center gap-1 text-xs text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 cursor-pointer transition-colors">
              <Upload className="w-3 h-3" />
              {uploading ? '上传中...' : '重新上传'}
            </span>
          </label>

          {/* 管理简历入口 */}
          <Link
            href="/resumes"
            className="mt-2 inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
          >
            <Settings2 className="w-3 h-3" />
            管理简历
          </Link>

          {/* 设为默认按钮 */}
          {!resume.is_default && resume.status === 'completed' && (
            <button
              onClick={async () => {
                try {
                  const response = await fetchWithAuth(`/api/v1/resumes/${resume.id}/set-default`, {
                    method: 'POST',
                  });
                  if (response.ok) {
                    await fetchLatestResume(); // 刷新状态
                  }
                } catch (err) {
                  console.error('Failed to set default resume:', err);
                }
              }}
              className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 cursor-pointer transition-colors"
            >
              ⭐ 设为默认简历
            </button>
          )}
        </div>
      ) : (
        <div className="text-center py-2">
          <FileText className="w-8 h-8 mx-auto mb-2 text-gray-400" />
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
            还没有简历？上传简历可以获得更精准的匹配
          </p>
          <label className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-primary-600 to-primary-500 text-white rounded-lg hover:from-primary-700 hover:to-primary-600 cursor-pointer transition-all shadow-md hover:shadow-lg">
            <Upload className="w-4 h-4" />
            上传简历
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
          {uploading && (
            <p className="text-xs text-gray-500 mt-2">上传中...</p>
          )}
        </div>
      )}

      {error && (
        <div className="mt-2 flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
          <AlertCircle className="w-3 h-3" />
          {error}
        </div>
      )}
    </div>
  );
}
