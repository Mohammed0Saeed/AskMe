import React from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth, isAdmin, isExpert } from './context/AuthContext'
import Layout from './components/layout/Layout'
import LoginPage      from './pages/LoginPage'
import AskPage        from './pages/AskPage'
import IngestPage     from './pages/IngestPage'
import AuditPage      from './pages/AuditPage'
import TrainingPage   from './pages/TrainingPage'
import AdminPage      from './pages/AdminPage'
import TicketsPage    from './pages/TicketsPage'
import InsightsPage   from './pages/InsightsPage'
import KBPage         from './pages/KBPage'

function PrivateRoute({ children, require: role }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  if (role === 'expert' && !isExpert(user)) return <Navigate to="/ask" replace />
  if (role === 'admin'  && !isAdmin(user))  return <Navigate to="/ask" replace />
  return children
}

function AppRoutes() {
  const { user, loading } = useAuth()
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-offwhite-100">
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/ask" replace /> : <LoginPage />} />

      <Route element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route index                   element={<Navigate to="/ask" replace />} />
        <Route path="/ask"             element={<AskPage />} />
        <Route path="/audit"           element={<AuditPage />} />
        <Route path="/training"        element={<TrainingPage />} />
        <Route path="/ingest"          element={<PrivateRoute require="expert"><IngestPage /></PrivateRoute>} />
        <Route path="/tickets"         element={<PrivateRoute require="expert"><TicketsPage /></PrivateRoute>} />
        <Route path="/insights"        element={<PrivateRoute require="expert"><InsightsPage /></PrivateRoute>} />
        <Route path="/kb"              element={<PrivateRoute require="expert"><KBPage /></PrivateRoute>} />
        <Route path="/admin"           element={<PrivateRoute require="admin"><AdminPage /></PrivateRoute>} />
      </Route>

      <Route path="*" element={<Navigate to="/ask" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
