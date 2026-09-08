import { t } from '../../i18n'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { User, Shield, Loader2 } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

export default function LoginScreen() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const { autenticado, cargando, iniciarSesion } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // Volver al login con sesión abierta no debe pedir credenciales otra vez.
  // Se espera a que termine de validarse el token guardado: si no, esto
  // deja pasar al login a alguien que sí tenía sesión.
  if (!cargando && autenticado) {
    return <Navigate to={location.state?.desde || '/'} replace />
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    setEnviando(true)

    try {
      await iniciarSesion(username, password)
      // Si la guarda lo mandó aquí, se vuelve a donde iba.
      navigate(location.state?.desde || '/', { replace: true })
    } catch (err) {
      // El backend distingue credenciales malas (401) de no poder
      // contactarlo (0), y son dos problemas muy distintos para el operador.
      setError(
        err.status === 0
          ? 'No se pudo contactar al backend. ¿Está corriendo en el 8080?'
          : err.message,
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div
      className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4"
      style={{ backgroundImage: 'linear-gradient(45deg, #0a0a0a 25%, #1a1a1a 100%)' }}
    >
      <div className="bg-[#141414] border border-red-600/30 p-8 rounded-xl w-full max-w-md shadow-[0_0_50px_rgba(220,38,38,0.15)]">
        
        {/* Logo */}
        <div className="text-center mb-8">
          <img
            src="/Logo.png"
            alt="Race Core Studio"
            className="w-64 mx-auto object-contain"
          />
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="block text-neutral-400 text-xs font-bold mb-2 uppercase tracking-wider">
              {t('Usuario')}
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-neutral-500 w-5 h-5" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={enviando}
                autoComplete="username"
                className="w-full bg-[#0a0a0a] border border-neutral-800 text-white pl-10 pr-4 py-3 rounded-lg focus:outline-none focus:border-red-600 transition-colors"
                placeholder="admin"
              />
            </div>
          </div>

          <div>
            <label className="block text-neutral-400 text-xs font-bold mb-2 uppercase tracking-wider">
              {t('Contraseña')}
            </label>
            <div className="relative">
              <Shield className="absolute left-3 top-1/2 transform -translate-y-1/2 text-neutral-500 w-5 h-5" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={enviando}
                autoComplete="current-password"
                className="w-full bg-[#0a0a0a] border border-neutral-800 text-white pl-10 pr-4 py-3 rounded-lg focus:outline-none focus:border-red-600 transition-colors"
                placeholder="admin"
              />
            </div>
          </div>

          {error && (
            <p className="text-red-500 text-sm text-center bg-red-500/10 py-2 rounded">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={enviando}
            className="w-full bg-red-600 hover:bg-red-700 disabled:bg-red-900 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-lg transition-colors flex justify-center items-center gap-2"
          >
            {enviando && <Loader2 size={18} className="animate-spin" />}
            {enviando ? 'VERIFICANDO...' : 'INGRESAR AL SISTEMA'}
          </button>
        </form>
      </div>
    </div>
  )
}
