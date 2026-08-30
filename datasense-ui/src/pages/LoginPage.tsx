import React, { useState } from 'react'
import { LogIn, Mail, KeyRound, Loader2, ShieldCheck } from 'lucide-react'
import { useAppStore } from '../store/appStore'
import { login, verifyOtp, requestPasswordReset, resetPassword } from '../api/auth'

type Flow = 'login' | 'forgot_password'

export function LoginPage() {
  const { loginUser } = useAppStore()
  const [flow, setFlow] = useState<Flow>('login')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [forgotEmail, setForgotEmail] = useState('')
  const [resetCode, setResetCode] = useState('')
  const [resetDemoCode, setResetDemoCode] = useState('')
  const [resetCodeSent, setResetCodeSent] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [newPassword2, setNewPassword2] = useState('')

  const [otpUserId, setOtpUserId] = useState<number | null>(null)
  const [demoOtp, setDemoOtp] = useState('')
  const [otpCode, setOtpCode] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(email.trim().toLowerCase(), password)
      if ('otp_required' in res) {
        setOtpUserId(res.user_id)
        setDemoOtp(res.demo_otp ?? '')
      } else {
        loginUser(res.user, res.token)
      }
    } catch (err) {
      setError((err as Error).message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    if (otpUserId === null) return
    setError('')
    setLoading(true)
    try {
      const res = await verifyOtp(otpUserId, otpCode.trim())
      loginUser(res.user, res.token)
    } catch (err) {
      setError((err as Error).message || 'Invalid code')
    } finally {
      setLoading(false)
    }
  }

  const handleRequestPasswordReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      const res = await requestPasswordReset(forgotEmail.trim().toLowerCase())
      setResetCodeSent(true)
      setResetDemoCode(res.demo_code ?? '')
    } catch (err) {
      setError((err as Error).message || 'Failed to request password reset.')
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (newPassword !== newPassword2) { setError('Passwords do not match.'); return }
    if (newPassword.length < 8) { setError('Password must be at least 8 characters.'); return }
    setLoading(true)
    try {
      await resetPassword(forgotEmail.trim().toLowerCase(), resetCode.trim(), newPassword)
      setSuccess('Password reset successfully. You can now sign in.')
      setFlow('login')
      setEmail(forgotEmail)
      setPassword('')
    } catch (err) {
      setError((err as Error).message || 'Failed to reset password.')
    } finally {
      setLoading(false)
    }
  }

  const switchFlow = (f: Flow) => {
    setFlow(f)
    setError('')
    setSuccess('')
    setOtpUserId(null)
    setOtpCode('')
    setDemoOtp('')
    setResetCodeSent(false)
    setResetCode('')
    setResetDemoCode('')
    setNewPassword('')
    setNewPassword2('')
    if (f === 'forgot_password' && email) setForgotEmail(email)
  }

  return (
    <div className="min-h-screen flex bg-bg">
      {/* Left branding panel — hidden on small screens */}
      <div className="hidden lg:flex flex-col justify-between p-12 w-[45%] bg-surface border-r border-line">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-accent rounded-lg flex items-center justify-center">
            <span className="font-display font-extrabold text-bg text-sm">SL</span>
          </div>
          <span className="font-display font-bold text-xl text-tx">QC Central</span>
        </div>

        <div className="space-y-5">
          <h1 className="font-display font-extrabold text-4xl text-tx leading-tight">
            Survey Quality Control,<br />simplified.
          </h1>
          <p className="text-muted text-base leading-relaxed">
            Run QC checks, catch fabrication, track quotas, and compare waves — all in one place.
          </p>
          <ul className="space-y-2 text-sm text-muted">
            {[
              'Missing values, range violations & duplicates',
              'Custom logic rule engine',
              'Straightlining & interviewer anomaly detection',
              'Wave-over-wave comparison',
            ].map(f => (
              <li key={f} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                {f}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-muted">© {new Date().getFullYear()} QC Central</p>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        {/* Mobile logo */}
        <div className="flex items-center gap-2 mb-10 lg:hidden">
          <div className="w-8 h-8 bg-accent rounded-lg flex items-center justify-center">
            <span className="font-display font-extrabold text-bg text-xs">SL</span>
          </div>
          <span className="font-display font-bold text-lg text-tx">QC Central</span>
        </div>

        <div className="w-full max-w-sm">
          {/* OTP step */}
          {otpUserId !== null && (
            <div className="space-y-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <ShieldCheck size={18} className="text-accent" />
                  <h2 className="font-display font-bold text-2xl text-tx">Check your email</h2>
                </div>
                <p className="text-sm text-muted">
                  A 6-digit verification code has been sent to your email address.
                </p>
                {demoOtp && (
                  <p className="mt-2 text-sm text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2">
                    Email not configured — your code is:{' '}
                    <span className="font-mono font-bold tracking-widest">{demoOtp}</span>
                  </p>
                )}
              </div>
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div>
                  <label className="label mb-1 block">Verification code</label>
                  <input
                    type="text"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    placeholder="000000"
                    inputMode="numeric"
                    maxLength={6}
                    required
                    autoFocus
                    className="w-full bg-surface border border-line rounded-lg px-3 py-2.5 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors tracking-widest"
                  />
                </div>
                {error && <p className="text-xs text-critical bg-critical/10 border border-critical/30 rounded-lg px-3 py-2">{error}</p>}
                <button type="submit" disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2 py-2.5">
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
                  {loading ? 'Verifying…' : 'Verify'}
                </button>
                <button type="button" onClick={() => { setOtpUserId(null); setOtpCode(''); setDemoOtp(''); setError(''); setFlow('login') }} className="text-[11px] text-muted text-center w-full underline underline-offset-2">
                  Back to sign in
                </button>
              </form>
            </div>
          )}

          {/* Login */}
          {otpUserId === null && flow === 'login' && (
            <div className="space-y-6">
              <div>
                <h2 className="font-display font-bold text-2xl text-tx">Sign in</h2>
                <p className="text-sm text-muted mt-1">Use your QC Central account credentials.</p>
              </div>
              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="label mb-1 block">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    autoFocus
                    className="w-full bg-surface border border-line rounded-lg px-3 py-2.5 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                  />
                </div>
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <label className="label block">Password</label>
                    <button type="button" onClick={() => switchFlow('forgot_password')} className="text-[11px] text-accent hover:underline underline-offset-2">
                      Forgot password?
                    </button>
                  </div>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full bg-surface border border-line rounded-lg px-3 py-2.5 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                  />
                </div>
                {error && <p className="text-xs text-critical bg-critical/10 border border-critical/30 rounded-lg px-3 py-2">{error}</p>}
                <button type="submit" disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2 py-2.5">
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <LogIn size={14} />}
                  {loading ? 'Signing in…' : 'Sign in'}
                </button>
              </form>
            </div>
          )}

          {/* Forgot password — email step */}
          {otpUserId === null && flow === 'forgot_password' && !resetCodeSent && (
            <div className="space-y-6">
              <div>
                <h2 className="font-display font-bold text-2xl text-tx">Forgot password?</h2>
                <p className="text-sm text-muted mt-1">Enter your email and we'll send you a reset code.</p>
              </div>
              <form onSubmit={handleRequestPasswordReset} className="space-y-4">
                <div>
                  <label className="label mb-1 block">Email</label>
                  <input
                    type="email"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    autoFocus
                    className="w-full bg-surface border border-line rounded-lg px-3 py-2.5 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                  />
                </div>
                {error && <p className="text-xs text-critical bg-critical/10 border border-critical/30 rounded-lg px-3 py-2">{error}</p>}
                <button type="submit" disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2 py-2.5">
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <Mail size={14} />}
                  {loading ? 'Sending…' : 'Send reset code'}
                </button>
                <button type="button" onClick={() => switchFlow('login')} className="text-[11px] text-muted text-center w-full underline underline-offset-2">
                  Back to sign in
                </button>
              </form>
            </div>
          )}

          {/* Forgot password — code + new password step */}
          {otpUserId === null && flow === 'forgot_password' && resetCodeSent && (
            <div className="space-y-6">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <ShieldCheck size={18} className="text-accent" />
                  <h2 className="font-display font-bold text-2xl text-tx">Check your email</h2>
                </div>
                <p className="text-sm text-muted">Enter the 6-digit code sent to {forgotEmail} and choose a new password.</p>
                {resetDemoCode && (
                  <p className="mt-2 text-xs text-accent bg-accent/10 border border-accent/30 rounded-lg px-3 py-2">
                    Dev fallback — code: <span className="font-mono font-bold">{resetDemoCode}</span>
                  </p>
                )}
              </div>
              <form onSubmit={handleResetPassword} className="space-y-4">
                <div>
                  <label className="label mb-1 block">Reset code</label>
                  <input
                    type="text"
                    value={resetCode}
                    onChange={(e) => setResetCode(e.target.value)}
                    placeholder="000000"
                    inputMode="numeric"
                    maxLength={6}
                    required
                    autoFocus
                    className="w-full bg-surface border border-line rounded-lg px-3 py-2.5 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors tracking-widest"
                  />
                </div>
                <div>
                  <label className="label mb-1 block">New password</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Min. 8 characters"
                    required
                    className="w-full bg-surface border border-line rounded-lg px-3 py-2.5 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                  />
                </div>
                <div>
                  <label className="label mb-1 block">Confirm new password</label>
                  <input
                    type="password"
                    value={newPassword2}
                    onChange={(e) => setNewPassword2(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="w-full bg-surface border border-line rounded-lg px-3 py-2.5 text-sm text-tx placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
                  />
                </div>
                {error && <p className="text-xs text-critical bg-critical/10 border border-critical/30 rounded-lg px-3 py-2">{error}</p>}
                {success && <p className="text-xs text-accent bg-accent/10 border border-accent/30 rounded-lg px-3 py-2">{success}</p>}
                <button type="submit" disabled={loading} className="w-full btn-primary flex items-center justify-center gap-2 py-2.5">
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />}
                  {loading ? 'Resetting…' : 'Reset password'}
                </button>
                <button type="button" onClick={() => switchFlow('login')} className="text-[11px] text-muted text-center w-full underline underline-offset-2">
                  Back to sign in
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
