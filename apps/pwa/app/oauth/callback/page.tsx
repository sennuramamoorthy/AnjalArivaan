'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import * as authApi from '@/lib/api/auth';
import { useAuthStore } from '@/store/auth-store';

type CallbackStatus = 'processing' | 'success' | 'error';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const setLinkedAccounts = useAuthStore((s) => s.setLinkedAccounts);

  const [status, setStatus] = React.useState<CallbackStatus>('processing');
  const [errorMessage, setErrorMessage] = React.useState('');
  const processedRef = React.useRef(false);

  React.useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;

    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const oauthError = searchParams.get('error');

    if (oauthError) {
      setStatus('error');
      setErrorMessage(
        oauthError === 'access_denied'
          ? 'You declined the permission request. Please try again.'
          : `Google returned an error: ${oauthError}`,
      );
      return;
    }
    if (!code || !state) {
      setStatus('error');
      setErrorMessage('Missing authorization code or state.');
      return;
    }

    (async () => {
      try {
        // eslint-disable-next-line no-console
        console.log('[oauth/callback] POST complete', { code: code.slice(0, 8), state: state.slice(0, 8) });
        const account = await authApi.completeAccountLink(code, state);
        // eslint-disable-next-line no-console
        console.log('[oauth/callback] linked', account);
        setStatus('success');
        // Refresh store in background — non-fatal
        authApi
          .getLinkedAccounts()
          .then((accs) => setLinkedAccounts(accs))
          .catch(() => undefined);
        setTimeout(() => router.push('/settings'), 1500);
      } catch (err: any) {
        // eslint-disable-next-line no-console
        console.error('[oauth/callback] failed', err);
        setStatus('error');
        setErrorMessage(err?.message ?? 'Failed to complete account linking.');
      }
    })();
  }, [searchParams, router, setLinkedAccounts]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-950 px-4">
      <div className="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-8 text-center shadow-sm dark:border-gray-700 dark:bg-gray-900">
        {status === 'processing' && (
          <>
            <div className="flex justify-center mb-4">
              <Loader2 size={40} className="animate-spin text-primary-600" />
            </div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Linking Account</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              Completing the connection to your Google account...
            </p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="flex justify-center mb-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                <CheckCircle2 size={28} className="text-green-600 dark:text-green-400" />
              </div>
            </div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Account Linked</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              Your Google account has been linked successfully. Redirecting to settings...
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="flex justify-center mb-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
                <XCircle size={28} className="text-red-600 dark:text-red-400" />
              </div>
            </div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Linking Failed</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">{errorMessage}</p>
            <div className="mt-6">
              <Button variant="primary" onClick={() => router.push('/settings')}>
                Back to Settings
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 size={40} className="animate-spin text-primary-600" />
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}
