'use client';

/**
 * ui-redesign 决策 7：按钮三档体系的唯一入口。
 * primary / secondary / ghost × md(36) / sm(28)。
 *
 * 全站禁止再内联写渐变按钮类；少数挂在 <a>/Next.js <Link> 上的 CTA
 * 可直接复用导出的 buttonClasses()，不必强塞进 <button>。
 */

import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';
export type ButtonSize = 'md' | 'sm';

const BASE_CLASSES =
  'inline-flex items-center justify-center gap-2 font-medium rounded-btn ' +
  'transition-colors duration-base ease-ds ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-200 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'bg-primary-500 text-white hover:bg-primary-600 active:bg-primary-800',
  secondary:
    'bg-transparent border border-l2 text-900 hover:bg-hover-neutral',
  ghost:
    'bg-transparent text-900 hover:bg-hover-primary',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  md: 'h-9 px-3.5 text-sm',
  sm: 'h-7 px-2.5 text-xs',
};

export function buttonClasses(
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  extra?: string
): string {
  return [BASE_CLASSES, VARIANT_CLASSES[variant], SIZE_CLASSES[size], extra]
    .filter(Boolean)
    .join(' ');
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button type={type} className={buttonClasses(variant, size, className)} {...rest}>
      {children}
    </button>
  );
}
