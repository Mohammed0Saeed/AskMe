import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Zap, Mail, Lock, AlertCircle, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import Button from '../components/ui/Button'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate   = useNavigate()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email.trim().toLowerCase(), password)
      navigate('/ask', { replace: true })
    } catch (err) {
      setError(err.data?.error || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  const DEMOS = [
    { email: 'mohammed_saeed@six.ch',  role: 'User' },
    { email: 'jacob_six@six.ch',       role: 'Expert' },
    { email: 'mirco_six@six.ch',       role: 'Admin' },
  ]

  return (
    <div className="min-h-screen bg-offwhite-100 flex">
      {/* Left brand panel */}
      <div className="hidden lg:flex flex-col justify-between w-96 bg-warm-900 p-10 text-white">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-brand-500 rounded-xl flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-lg font-bold">AskMe</div>
            <div className="text-[11px] text-warm-400 uppercase tracking-widest">SIX Group</div>
          </div>
        </div>

        <div>
          <h2 className="text-3xl font-bold leading-snug mb-4">
            Your internal<br />knowledge,<br />
            <span className="text-brand-400">instantly.</span>
          </h2>
          <p className="text-warm-400 text-sm leading-relaxed">
            Ask questions grounded in SIX Group's internal documents, policies, and procedures — with full citations.
          </p>
        </div>

        <div className="space-y-3">
          <p className="text-xs text-warm-500 uppercase tracking-wider font-medium">Demo accounts</p>
          {DEMOS.map((d) => (
            <button
              key={d.email}
              onClick={() => setEmail(d.email)}
              className="w-full text-left px-3 py-2 rounded-xl bg-warm-800 hover:bg-warm-700 transition-all"
            >
              <p className="text-xs font-medium text-white">{d.email}</p>
              <p className="text-[11px] text-warm-400">{d.role} · password: password</p>
            </button>
          ))}
        </div>
      </div>

      {/* Right login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-9 h-9 bg-brand-500 rounded-xl flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="font-bold text-warm-900">AskMe</div>
              <div className="text-[10px] text-warm-400 uppercase tracking-widest">SIX Group</div>
            </div>
          </div>

          <h1 className="text-2xl font-bold text-warm-900 mb-1">Welcome back</h1>
          <p className="text-sm text-warm-500 mb-8">Sign in to your account to continue</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label className="block text-xs font-medium text-warm-700">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-warm-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@six.ch"
                  required
                  className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-offwhite-300 bg-white text-sm text-warm-900 placeholder:text-warm-400 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="block text-xs font-medium text-warm-700">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-warm-400" />
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full pl-9 pr-10 py-2.5 rounded-xl border border-offwhite-300 bg-white text-sm text-warm-900 placeholder:text-warm-400 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-warm-400 hover:text-warm-700 transition-colors"
                  tabIndex={-1}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2 bg-brand-50 border border-brand-200 rounded-xl text-xs text-brand-700">
                <AlertCircle size={14} />
                {error}
              </div>
            )}

            <Button type="submit" loading={loading} className="w-full justify-center py-2.5">
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
