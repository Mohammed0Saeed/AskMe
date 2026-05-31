import React, { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  MessageSquare, Upload, ClipboardList, GraduationCap,
  Users, Ticket, BarChart2, Database, LogOut,
  ChevronLeft, ChevronRight, Zap,
} from 'lucide-react'
import { useAuth, isAdmin, isExpert } from '../../context/AuthContext'
import clsx from 'clsx'

const SIXLogo = () => (
  <svg viewBox="0 0 82 30" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-10 h-auto">
    <text x="0" y="24" fontFamily="Inter, sans-serif" fontWeight="700" fontSize="28" fill="currentColor">SIX</text>
  </svg>
)

const NAV_ITEMS = [
  { to: '/ask',      icon: MessageSquare, label: 'Ask',      role: null },
  { to: '/audit',    icon: ClipboardList, label: 'Audit',    role: null },
  { to: '/training', icon: GraduationCap, label: 'Training', role: null },
  { to: '/ingest',   icon: Upload,        label: 'Ingest',   role: 'expert' },
  { to: '/tickets',  icon: Ticket,        label: 'Tickets',  role: 'expert' },
  { to: '/insights', icon: BarChart2,     label: 'Insights', role: 'expert' },
  { to: '/kb',       icon: Database,      label: 'KB',       role: 'expert' },
  { to: '/admin',    icon: Users,         label: 'Admin',    role: 'admin' },
]

const ROLE_COLORS = {
  admin:  'bg-brand-500 text-white',
  expert: 'bg-brand-100 text-brand-700',
  user:   'bg-offwhite-200 text-warm-600',
}

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const visible = NAV_ITEMS.filter(({ role }) => {
    if (!role) return true
    if (role === 'expert') return isExpert(user)
    if (role === 'admin')  return isAdmin(user)
    return false
  })

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <aside
      className={clsx(
        'relative flex flex-col h-screen bg-warm-900 text-white transition-all duration-300 ease-in-out flex-shrink-0',
        collapsed ? 'w-16' : 'w-56'
      )}
    >
      {/* Logo */}
      <div className={clsx('flex items-center gap-3 px-4 py-5 border-b border-warm-800', collapsed && 'justify-center px-0')}>
        <div className="flex-shrink-0 w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
          <Zap className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <div>
            <div className="text-sm font-bold tracking-wide text-white">AskMe</div>
            <div className="text-[10px] text-warm-400 uppercase tracking-widest">SIX Group</div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 scrollbar-hide">
        <ul className="space-y-0.5 px-2">
          {visible.map(({ to, icon: Icon, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150',
                    isActive
                      ? 'bg-brand-500 text-white shadow-md'
                      : 'text-warm-300 hover:bg-warm-800 hover:text-white',
                    collapsed && 'justify-center px-0'
                  )
                }
                title={collapsed ? label : undefined}
              >
                <Icon className="w-4.5 h-4.5 flex-shrink-0" size={18} />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* User footer */}
      <div className={clsx('border-t border-warm-800 p-3', collapsed && 'flex flex-col items-center gap-2')}>
        {!collapsed && (
          <div className="flex items-center gap-2 mb-2 px-1">
            <div className="w-7 h-7 rounded-full bg-brand-500 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
              {user?.name?.[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-white truncate">{user?.name}</p>
              <span className={clsx('text-[10px] px-1.5 py-0.5 rounded-full font-medium', ROLE_COLORS[user?.role] || ROLE_COLORS.user)}>
                {user?.role}
              </span>
            </div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className={clsx(
            'w-full flex items-center gap-2 rounded-xl px-3 py-2 text-xs text-warm-400 hover:text-white hover:bg-warm-800 transition-all',
            collapsed && 'justify-center px-0'
          )}
          title="Sign out"
        >
          <LogOut size={15} />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="absolute -right-3 top-6 w-6 h-6 bg-warm-700 border border-warm-600 rounded-full flex items-center justify-center text-warm-300 hover:text-white hover:bg-warm-600 transition-all z-10"
        title={collapsed ? 'Expand' : 'Collapse'}
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  )
}
