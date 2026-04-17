'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Mail, Lock, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuthStore } from '@/store/auth-store';
import * as authApi from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import { MfaForm } from './mfa-form';

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const router = useRouter();
  const [showPassword, setShowPassword] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [mfaState, setMfaState] = React.useState<{
    required: boolean;
    email: string;
    password: string;
  } | null>(null);

  const { setUser, setTokens } = useAuthStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (values: LoginFormValues) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await authApi.login(values);

      // Decode user info from JWT
      const payload = authApi.decodeTokenPayload(res.accessToken);
      if (!payload) {
        setError('Invalid token received. Please try again.');
        return;
      }

      // Store tokens and user in zustand (refreshToken enables silent
      // re-issue of the 15-min access token so the user isn't bounced to
      // /login mid-session).
      setTokens(res.accessToken, res.refreshToken);
      setUser({
        id: payload.sub,
        name: payload.email.split('@')[0], // fallback name from email
        email: payload.email,
        role: payload.role,
      });

      // Navigate to dashboard
      router.push('/dashboard');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'MFA_REQUIRED') {
          // MFA is required — show the MFA form
          setMfaState({
            required: true,
            email: values.email,
            password: values.password,
          });
        } else if (err.status === 401) {
          setError('Invalid email or password. Please try again.');
        } else {
          setError(err.message ?? 'Something went wrong. Please try again.');
        }
      } else if (err instanceof Error) {
        setError(err.message ?? 'Something went wrong. Please try again.');
      } else {
        setError('Unable to connect. Please check your connection.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (mfaState?.required) {
    return (
      <MfaForm
        mode="verify"
        email={mfaState.email}
        password={mfaState.password}
      />
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/50"
            role="alert"
          >
            <AlertCircle size={16} className="text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
          </motion.div>
        )}

        <Input
          label="Email address"
          type="email"
          autoComplete="email"
          placeholder="admin@takshashilauniv.ac.in"
          error={errors.email?.message}
          leftIcon={<Mail size={16} />}
          {...register('email')}
        />

        <Input
          label="Password"
          type={showPassword ? 'text' : 'password'}
          autoComplete="current-password"
          placeholder="Enter your password"
          error={errors.password?.message}
          leftIcon={<Lock size={16} />}
          rightIcon={
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 focus:outline-none"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          }
          {...register('password')}
        />

        <Button type="submit" className="w-full" size="lg" isLoading={isLoading}>
          Sign in
        </Button>
      </form>
    </motion.div>
  );
}
