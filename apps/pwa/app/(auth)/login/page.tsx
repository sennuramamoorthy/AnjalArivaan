import type { Metadata } from 'next';
import { Sparkles } from 'lucide-react';
import { LoginForm } from '@/components/auth/login-form';

export const metadata: Metadata = {
  title: 'Sign in',
};

export default function LoginPage() {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/95 p-8 shadow-2xl backdrop-blur-md dark:bg-gray-900/95 dark:border-gray-700">
      {/* Logo */}
      <div className="mb-6 flex flex-col items-center text-center">
        <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-600 shadow-lg shadow-primary-900/30">
          <Sparkles size={28} className="text-white" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">AnjalArivaan</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Smart Assistant for Takshashila University
        </p>
      </div>

      {/* Divider */}
      <div className="mb-6 h-px bg-gray-200 dark:bg-gray-700" />

      {/* Form */}
      <LoginForm />

      {/* Footer */}
      <p className="mt-8 text-center text-xs text-gray-400 dark:text-gray-500">
        Powered by{' '}
        <span className="font-medium text-gray-500 dark:text-gray-400">AnjalArivaan</span>
        {' '}·{' '}
        <span>Takshashila University</span>
      </p>
    </div>
  );
}
