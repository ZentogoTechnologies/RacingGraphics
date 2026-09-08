import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

import { estado } from '../../api/instalacion'

/**
 * Manda al asistente cuando el sistema todavía no está configurado.
 *
 * Va por fuera de la guarda de sesión y por encima de ella: mientras no
 * exista ningún usuario, el login no sirve de nada —no hay con qué entrar—
 * y mandar ahí a quien acaba de instalar es un callejón sin salida.
 *
 * Si el backend no contesta se deja pasar en vez de bloquear. Un corte de
 * red no puede dejar a un operador fuera del panel en mitad de una
 * transmisión: el backend volverá a exigir sesión por su cuenta, que es
 * quien de verdad manda.
 */
export default function GuardaInstalacion() {
  const [estadoSetup, setEstadoSetup] = useState(null)
  const location = useLocation()

  useEffect(() => {
    estado()
      .then(setEstadoSetup)
      .catch(() => setEstadoSetup({ configurado: true }))
  }, [])

  if (estadoSetup === null) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 size={30} className="animate-spin text-red-600" />
      </div>
    )
  }

  // Solo se desvía si además queda token: sin él el asistente no se puede
  // usar, y mandar ahí a alguien sería enseñarle una pantalla de error en
  // vez del login.
  const hayQueInstalar = !estadoSetup.configurado && estadoSetup.asistente_disponible

  if (hayQueInstalar && location.pathname !== '/instalacion') {
    return <Navigate to="/instalacion" replace />
  }

  return <Outlet />
}
