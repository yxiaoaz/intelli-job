'use client';

import { useState, useRef } from 'react';
import { Upload, X, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';
import { buttonClasses } from '@/components/ui/Button';

interface ResumeUploadProps {
  onSuccess?: () => void;
}

export default function ResumeUpload({ onSuccess }: ResumeUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    // Check file type
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];
    
    if (!allowedTypes.includes(file.type)) {
      return '仅支持 PDF 和 DOCX 格式的文件';
    }

    // Check file size (10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      return '文件大小不能超过 10MB';
    }

    return null;
  };

  const handleFileSelect = (selectedFile: File) => {
    setError('');
    setSuccess(false);
    
    const validationError = validateFile(selectedFile);
    if (validationError) {
      setError(validationError);
      return;
    }

    setFile(selectedFile);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError('');
    setProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + 10;
        });
      }, 200);

      const response = await fetchWithAuth('/api/v1/resumes/upload', {
        method: 'POST',
        body: formData,
      });

      clearInterval(progressInterval);
      setProgress(100);

      if (response.ok) {
        const data = await response.json();
        setSuccess(true);
        
        // Wait a bit then call success callback
        setTimeout(() => {
          if (onSuccess) {
            onSuccess();
          }
        }, 1500);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || '上传失败');
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError('网络错误，请重试');
    } finally {
      setUploading(false);
    }
  };

  const removeFile = () => {
    setFile(null);
    setError('');
    setSuccess(false);
    setProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  if (success) {
    return (
      <div className="text-center py-8">
        <CheckCircle className="w-16 h-16 text-success-600 mx-auto mb-4" />
        <h3 className="text-xl font-medium text-900 mb-2">
          上传成功！
        </h3>
        <p className="text-700">
          简历正在后台解析中，请稍后查看分析结果
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Drop Zone */}
      {!file && (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-l2 rounded-menu p-8 text-center cursor-pointer hover:border-tint-primary transition-colors bg-layer1"
        >
          <Upload className="w-12 h-12 text-400 mx-auto mb-4" />
          <p className="text-lg font-medium text-700 mb-2">
            拖拽文件到此处或点击上传
          </p>
          <p className="text-sm text-500">
            支持 PDF、DOCX 格式，最大 10MB
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
              }
            }}
            className="hidden"
          />
        </div>
      )}

      {/* File Selected */}
      {file && !success && (
        <div className="bg-layer1 rounded-menu p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <FileText className="w-8 h-8 text-primary-600" />
              <div>
                <p className="font-medium text-900">
                  {file.name}
                </p>
                <p className="text-sm text-500">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
            <button
              onClick={removeFile}
              className="text-400 hover:text-danger-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Progress Bar */}
          {uploading && (
            <div className="mb-4">
              <div className="flex justify-between text-sm text-700 mb-2">
                <span>上传中...</span>
                <span>{progress}%</span>
              </div>
              <div className="w-full bg-layer2 rounded-full h-2">
                <div
                  className="bg-primary-500 h-2 rounded-full transition-colors duration-slow"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-2 text-tint-danger mb-4 p-3 bg-tint-danger rounded-menu">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {/* Upload Button */}
          <button
            onClick={handleUpload}
            disabled={uploading}
            className={buttonClasses('primary', 'md', 'w-full')}
          >
            {uploading ? '上传中...' : '开始上传'}
          </button>
        </div>
      )}

      {/* Instructions */}
      <div className="mt-6 p-4 bg-tint-primary rounded-menu">
        <h4 className="font-medium text-tint-primary mb-2">
          温馨提示
        </h4>
        <ul className="text-sm text-tint-primary space-y-1">
          <li>• 上传后系统将自动解析简历内容</li>
          <li>• 解析完成后会生成质量评分和改进建议</li>
          <li>• 您可以随时重新解析或导出分析结果</li>
        </ul>
      </div>
    </div>
  );
}
