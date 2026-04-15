import type { Metadata } from 'next';
import { MfaForm } from '@/components/auth/mfa-form';

export const metadata: Metadata = {
  title: 'Set up two-factor authentication',
};

export default function MfaSetupPage() {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/95 p-8 shadow-2xl backdrop-blur-md dark:bg-gray-900/95 dark:border-gray-700">
      <div className="mb-6 text-center">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
          Set up two-factor authentication
        </h1>
        <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
          Protect your account with an authenticator app
        </p>
      </div>

      <MfaForm mode="setup" />
    </div>
  );
}
