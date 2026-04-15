'use client';

import * as React from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ShieldCheck, Download, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/store/auth-store';
import * as authApi from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import { cn } from '@/lib/utils';

// ────────────────────────────────────────────────────────────────
// Shared OTP input (6 individual digit inputs with auto-advance)
// ────────────────────────────────────────────────────────────────

interface OtpInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

function OtpInput({ value, onChange, disabled }: OtpInputProps) {
  const digits = value.split('').concat(Array(6).fill('')).slice(0, 6);
  const inputRefs = Array.from({ length: 6 }, () => React.createRef<HTMLInputElement>());

  const handleInput = (index: number, char: string) => {
    const digit = char.replace(/\D/g, '').slice(-1);
    const next = [...digits];
    next[index] = digit;
    onChange(next.join(''));
    if (digit && index < 5) {
      inputRefs[index + 1].current?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace') {
      if (!digits[index] && index > 0) {
        inputRefs[index - 1].current?.focus();
        const next = [...digits];
        next[index - 1] = '';
        onChange(next.join(''));
      } else {
        const next = [...digits];
        next[index] = '';
        onChange(next.join(''));
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs[index - 1].current?.focus();
    } else if (e.key === 'ArrowRight' && index < 5) {
      inputRefs[index + 1].current?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    onChange(pasted.padEnd(6, '').slice(0, 6));
    const focusIdx = Math.min(pasted.length, 5);
    inputRefs[focusIdx].current?.focus();
  };

  return (
    <div className="flex gap-2 justify-center" onPaste={handlePaste}>
      {digits.map((digit, i) => (
        <input
          key={i}
          ref={inputRefs[i]}
          type="text"
          inputMode="numeric"
          pattern="[0-9]"
          maxLength={1}
          value={digit}
          disabled={disabled}
          onChange={(e) => handleInput(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          aria-label={`Digit ${i + 1}`}
          className={cn(
            'h-12 w-10 rounded-lg border text-center text-xl font-semibold',
            'text-gray-900 dark:text-gray-100',
            'bg-white dark:bg-gray-800',
            'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            'transition-colors',
            digit
              ? 'border-primary-400 dark:border-primary-500'
              : 'border-gray-300 dark:border-gray-600',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        />
      ))}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Verify MFA during login (re-posts /auth/login with mfaCode)
// ────────────────────────────────────────────────────────────────

interface MfaVerifyProps {
  email: string;
  password: string;
}

function MfaVerify({ email, password }: MfaVerifyProps) {
  const router = useRouter();
  const [otp, setOtp] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const { setUser, setTokens } = useAuthStore();

  const handleVerify = async () => {
    if (otp.length !== 6) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await authApi.verifyMfa({ email, password, mfaCode: otp });

      const payload = authApi.decodeTokenPayload(res.accessToken);
      if (!payload) {
        setError('Invalid token received.');
        return;
      }

      setTokens(res.accessToken);
      setUser({
        id: payload.sub,
        name: payload.email.split('@')[0],
        email: payload.email,
        role: payload.role,
      });

      router.push('/dashboard');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'INVALID_MFA_CODE') {
          setError('Incorrect code. Please try again.');
        } else {
          setError(err.message ?? 'Verification failed. Please try again.');
        }
      } else {
        setError('Verification failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-5"
    >
      <div className="text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/40">
          <ShieldCheck size={24} className="text-primary-600 dark:text-primary-400" />
        </div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Two-factor authentication
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Enter the 6-digit code from your authenticator app
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/50" role="alert">
          <AlertCircle size={15} className="text-red-600 dark:text-red-400 shrink-0" />
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      <OtpInput value={otp} onChange={setOtp} disabled={isLoading} />

      <Button
        className="w-full"
        size="lg"
        isLoading={isLoading}
        disabled={otp.length !== 6}
        onClick={handleVerify}
      >
        Verify
      </Button>
    </motion.div>
  );
}

// ────────────────────────────────────────────────────────────────
// MFA Setup wizard (3 steps)
// ────────────────────────────────────────────────────────────────

function MfaSetup() {
  const [step, setStep] = React.useState<1 | 2 | 3>(1);
  const [setupData, setSetupData] = React.useState<authApi.MfaSetupResponse | null>(null);
  const [otp, setOtp] = React.useState('');
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const router = useRouter();

  const initSetup = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await authApi.setupMfa();
      setSetupData(data);
    } catch (err) {
      const e = err as { message?: string };
      setError(e.message ?? 'Failed to initialize MFA setup.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    initSetup();
  }, [initSetup]);

  const handleVerify = async () => {
    if (otp.length !== 6 || !setupData) return;
    setIsLoading(true);
    setError(null);
    try {
      await authApi.verifyMfaSetup({ token: otp });
      setStep(3);
    } catch {
      setError('Incorrect code. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const downloadBackupCodes = () => {
    const codes = setupData?.backupCodes ?? [];
    const content = `AnjalArivaan — MFA Backup Codes\nGenerated: ${new Date().toISOString()}\n\n${codes.join('\n')}\n\nKeep these codes safe. Each can only be used once.`;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'anjalarivaan-backup-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const stepLabels = ['Scan QR', 'Verify', 'Backup codes'];

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {stepLabels.map((label, i) => {
          const s = i + 1;
          const isComplete = step > s;
          const isCurrent = step === s;
          return (
            <React.Fragment key={s}>
              <div className="flex items-center gap-1.5">
                <div
                  className={cn(
                    'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold',
                    isComplete
                      ? 'bg-primary-600 text-white'
                      : isCurrent
                      ? 'border-2 border-primary-600 text-primary-600'
                      : 'border-2 border-gray-300 text-gray-400'
                  )}
                >
                  {isComplete ? <CheckCircle2 size={14} /> : s}
                </div>
                <span
                  className={cn(
                    'text-xs font-medium hidden sm:block',
                    isCurrent ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400'
                  )}
                >
                  {label}
                </span>
              </div>
              {i < stepLabels.length - 1 && (
                <div className={cn('flex-1 h-px', step > s ? 'bg-primary-600' : 'bg-gray-200 dark:bg-gray-700')} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/50" role="alert">
          <AlertCircle size={15} className="text-red-600 shrink-0" />
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      {step === 1 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4 text-center">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Scan this QR code with Google Authenticator, Authy, or any TOTP app.
          </p>
          {isLoading || !setupData ? (
            <div className="mx-auto h-48 w-48 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-700" />
          ) : (
            <div className="mx-auto inline-block rounded-xl border border-gray-200 p-3 dark:border-gray-700">
              <Image
                src={setupData.qrCodeUri}
                alt="MFA QR Code"
                width={180}
                height={180}
                unoptimized
              />
            </div>
          )}
          <p className="text-xs text-gray-500">
            Or enter the secret manually: <code className="font-mono bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">{setupData?.secret ?? '…'}</code>
          </p>
          <Button className="w-full" size="lg" onClick={() => setStep(2)} disabled={!setupData}>
            I&apos;ve scanned the code
          </Button>
        </motion.div>
      )}

      {step === 2 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
          <p className="text-center text-sm text-gray-600 dark:text-gray-400">
            Enter the 6-digit code shown in your authenticator app to confirm setup.
          </p>
          <OtpInput value={otp} onChange={setOtp} disabled={isLoading} />
          <Button
            className="w-full"
            size="lg"
            isLoading={isLoading}
            disabled={otp.length !== 6}
            onClick={handleVerify}
          >
            Confirm
          </Button>
        </motion.div>
      )}

      {step === 3 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          <div className="text-center">
            <CheckCircle2 size={40} className="mx-auto mb-2 text-emerald-500" />
            <p className="font-semibold text-gray-900 dark:text-gray-100">MFA enabled successfully</p>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Save these backup codes. Each can only be used once.
            </p>
          </div>
          <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800">
            <div className="grid grid-cols-2 gap-2">
              {(setupData?.backupCodes ?? []).map((code) => (
                <code
                  key={code}
                  className="rounded bg-white px-2 py-1 text-center font-mono text-sm dark:bg-gray-900"
                >
                  {code}
                </code>
              ))}
            </div>
          </div>
          <Button
            variant="secondary"
            className="w-full"
            onClick={downloadBackupCodes}
          >
            <Download size={16} />
            Download backup codes
          </Button>
          <Button className="w-full" size="lg" onClick={() => router.push('/dashboard')}>
            Continue to dashboard
          </Button>
        </motion.div>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Exported component
// ────────────────────────────────────────────────────────────────

interface MfaFormProps {
  mode: 'verify' | 'setup';
  email?: string;
  password?: string;
}

export function MfaForm({ mode, email, password }: MfaFormProps) {
  if (mode === 'verify' && email && password) {
    return <MfaVerify email={email} password={password} />;
  }
  return <MfaSetup />;
}
