import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import { DisciplinaProvider } from './context/DisciplinaContext'
import { CarreraProvider } from './context/CarreraContext'
import { IdiomaProvider } from './context/IdiomaContext'
import ProtectedRoute from './components/auth/ProtectedRoute'
import RoleRoute from './components/auth/RoleRoute'
import DisciplinaGate from './components/shared/DisciplinaGate'
import GuardaInstalacion from './components/instalacion/GuardaInstalacion'
import LoginScreen from './components/auth/LoginScreen'
import InstalacionModule from './pages/Instalacion'
import MainLayout from './layouts/MainLayout'
import HomeModule from './pages/Home'
import EventosModule from './pages/Eventos'
import CategoriasModule from './pages/Categorias'
import PilotosModule from './pages/Pilotos'
import VehiculosModule from './pages/Vehiculos'
import GraficosModule from './pages/Graficos'
import UsuariosModule from './pages/Usuarios'
import AjustesModule from './pages/Ajustes'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/* Los avisos van por fuera de la guarda: un error de sesión
            expirada tiene que poder mostrarse también en el login. */}
        <IdiomaProvider>
        <ToastProvider>
          <DisciplinaProvider>
            <CarreraProvider>
            <Routes>
              {/* El asistente va fuera de toda guarda: cuando se usa
                  todavía no hay usuarios, así que exigir sesión aquí
                  sería pedir la llave de una puerta que aún no existe.
                  Se protege con el token que dejó el instalador. */}
              <Route path="/instalacion" element={<InstalacionModule />} />

              {/* Antes que la sesión: sin sistema configurado el login no
                  sirve de nada, y mandar ahí a quien acaba de instalar es
                  un callejón sin salida. */}
              <Route element={<GuardaInstalacion />}>
              <Route path="/login" element={<LoginScreen />} />

              {/* Primero sesión, después disciplina. En ese orden: la
                  pantalla de disciplina saluda por nombre, y filtrar la
                  base no tiene sentido antes de saber quién entra. */}
              <Route element={<ProtectedRoute />}>
                <Route element={<DisciplinaGate />}>
                  <Route element={<MainLayout />}>
                    <Route index             element={<HomeModule />} />
                    <Route path="eventos"    element={<EventosModule />} />
                    <Route path="categorias" element={<CategoriasModule />} />
                    <Route path="pilotos"    element={<PilotosModule />} />
                    <Route path="vehiculos"  element={<VehiculosModule />} />
                    <Route path="graficos"   element={<GraficosModule />} />

                    {/* Ajustes toca la configuración del cronometraje, que
                        cambia lo que sale al aire: owner y admin. */}
                    <Route element={<RoleRoute roles={['owner', 'admin']} />}>
                      <Route path="ajustes" element={<AjustesModule />} />
                    </Route>

                    {/* Solo el dueño. Un admin que escriba /usuarios a mano
                        rebota al inicio, y el backend le daría 403 igual. */}
                    <Route element={<RoleRoute roles={['owner']} />}>
                      <Route path="usuarios" element={<UsuariosModule />} />
                    </Route>
                  </Route>
                </Route>
              </Route>

              </Route>

              {/* Una URL escrita a mano que no existe cae en la raíz, y la
                  raíz vuelve a pasar por las guardas. */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </CarreraProvider>
          </DisciplinaProvider>
        </ToastProvider>
        </IdiomaProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
