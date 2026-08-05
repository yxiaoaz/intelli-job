import * as XLSX from 'xlsx';

interface Job {
  title: string;
  company: string;
  location?: string;
  salary?: string;
  score?: number;
  recruitment_type?: string;
  update_time?: string;
  url?: string;
  education?: string;
  experience?: string;
}

const recruitmentTypeLabels: Record<string, string> = {
  EXPERIENCED: '社招',
  GRADUATE: '校招',
  INTERN: '实习',
};

export function exportJobsToExcel(jobs: Job[], filename = '职位列表') {
  const data = jobs.map((job) => ({
    职位: job.title || '',
    公司: job.company || '',
    地点: job.location || '',
    薪资: job.salary || '面议',
    匹配度: job.score != null ? `${(job.score * 100).toFixed(0)}%` : '',
    招聘类型: recruitmentTypeLabels[job.recruitment_type || ''] || job.recruitment_type || '',
    学历要求: job.education || '',
    经验要求: job.experience || '',
    发布时间: job.update_time ? new Date(job.update_time).toLocaleDateString('zh-CN') : '',
    链接: job.url || '',
  }));

  const ws = XLSX.utils.json_to_sheet(data);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, '职位列表');

  // Auto column width
  const colWidths = Object.keys(data[0] || {}).map((key) => ({
    wch: Math.max(key.length * 2, ...data.map((row) => (row as any)[key]?.toString().length || 0)) + 2,
  }));
  ws['!cols'] = colWidths;

  XLSX.writeFile(wb, `${filename}.xlsx`);
}
