import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Alertes from './pages/Alertes'
import AlerteDetail from './pages/AlerteDetail'
import Bulletins from './pages/Bulletins'
import BulletinDetail from './pages/BulletinDetail'
import Tiers from './pages/Tiers'
import Utilisateurs from './pages/Utilisateurs'
import NotFound from './pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/alertes" element={<Alertes />} />
        <Route path="/alertes/:id" element={<AlerteDetail />} />
        <Route path="/bulletins" element={<Bulletins />} />
        <Route path="/bulletins/:id" element={<BulletinDetail />} />
        <Route path="/tiers" element={<Tiers />} />
        <Route
          path="/utilisateurs"
          element={
            <ProtectedRoute adminOnly>
              <Utilisateurs />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="/404" element={<NotFound />} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>
  )
}
