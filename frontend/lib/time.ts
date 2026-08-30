/**
 * 解析后端时间戳：naive UTC 字符串（无时区标记）补 'Z' 后再转本地时区，
 * 避免 new Date() 按本地时区解析导致差 8 小时（晚间操作日期跨天）。
 * 已带时区（以 z/Z 结尾或 ±HH:MM、±HHMM 结尾）的时间戳原样解析。
 */
export function parseUtc(dateStr: string): Date {
  if (!dateStr) return new Date(NaN);
  const hasTimezone = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(dateStr);
  return new Date(hasTimezone ? dateStr : dateStr + 'Z');
}

/** 格式化为 MM-DD（本地时区），非法时间戳返回空串 */
export function formatMonthDay(dateStr: string): string {
  const d = parseUtc(dateStr);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

/** Format a date string to relative time like "2小时前", "3天前" */
export function formatRelativeTime(dateStr: string): string {
  if (!dateStr) return '';
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diff = now - date;
  if (diff < 0) return '刚刚';
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}天前`;
  if (days < 30) return `${Math.floor(days / 7)}周前`;
  return new Date(dateStr).toLocaleDateString('zh-CN');
}
