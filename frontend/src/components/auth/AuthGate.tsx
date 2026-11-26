import React, { useState } from 'react';
import { Sun, Lock, Mail, User, Home, ArrowRight, Loader2, ShieldCheck } from 'lucide-react';
import { api, type AuthMeResponse } from '../../lib/api';

interface AuthGateProps {
  onAuthenticated: (auth: AuthMeResponse) => void;
  bannerMessage?: string | null;
}

export const AuthGate: React.FC<AuthGateProps> = ({ onAuthenticated, bannerMessage }) => {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [installationName, setInstallationName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError('Enter your email address and password.');
      return;
    }
    if (mode === 'register' && password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    setSubmitting(true);
    try {
      const res =
        mode === 'login'
          ? await api.login({ email: email.trim(), password })
          : await api.register({
              email: email.trim(),
              password,
              display_name: displayName.trim() || undefined,
              installation_name: installationName.trim() || undefined
            });
      onAuthenticated(res);
    } catch (err: any) {
      const msg = String(err?.message || 'Authentication failed.');
      const jsonStart = msg.indexOf('{');
      if (jsonStart !== -1) {
        try {
          const parsed = JSON.parse(msg.slice(jsonStart));
          setError(parsed.detail || msg);
        } catch {
          setError(msg);
        }
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-dvh bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm p-6 sm:p-8 space-y-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-lg bg-amber-600 flex items-center justify-center text-white shrink-0">
              <Sun className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-slate-900 dark:text-slate-100">
                SolarScope
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Solar &amp; Utility Intelligence Workspace
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 text-[11px] font-medium border border-emerald-200 dark:border-emerald-800">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Isolated</span>
          </span>
        </div>

        <div className="grid grid-cols-2 p-1 rounded-lg bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700">
          <button
            type="button"
            onClick={() => {
              setMode('login');
              setError(null);
            }}
            className={`py-1.5 text-xs font-semibold rounded-md transition-colors ${
              mode === 'login'
                ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('register');
              setError(null);
            }}
            className={`py-1.5 text-xs font-semibold rounded-md transition-colors ${
              mode === 'register'
                ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
            }`}
          >
            Create Account
          </button>
        </div>

        {bannerMessage && (
          <div className="px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-200">
            {bannerMessage}
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="px-3 py-2.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block">
                  Your Name
                </label>
                <div className="relative">
                  <User className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="e.g. Household Owner"
                    autoComplete="name"
                    className="w-full h-10 pl-9 pr-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block">
                  First Installation Name
                </label>
                <div className="relative">
                  <Home className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
                  <input
                    type="text"
                    value={installationName}
                    onChange={(e) => setInstallationName(e.target.value)}
                    placeholder="e.g. Main Residence Solar"
                    className="w-full h-10 pl-9 pr-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
              </div>
            </>
          )}

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block">
              Email Address
            </label>
            <div className="relative">
              <Mail className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@household.com"
                autoComplete="email"
                className="w-full h-10 pl-9 pr-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block">
              Password
            </label>
            <div className="relative">
              <Lock className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'register' ? 'Minimum 8 characters' : 'Enter password'}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                className="w-full h-10 pl-9 pr-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full h-10 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 text-white dark:text-slate-900 text-xs font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                <span>{mode === 'login' ? 'Signing in...' : 'Creating workspace...'}</span>
              </>
            ) : (
              <>
                <span>{mode === 'login' ? 'Sign In to Workspace' : 'Create Household Workspace'}</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </>
            )}
          </button>
        </form>

        <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-4">
          Each household workspace stores its solar datasets, electricity bills, and encrypted Deye Cloud credentials in strict project isolation.
        </p>
      </div>
    </div>
  );
};
