// ─── El asistente de instalación ──────────────────────────────
//
// Siete pasos y una pantalla final. El estado del paso vive aquí y no en
// la dirección a propósito: recargar a mitad de una instalación no debe
// repetir un paso que ya se guardó en el backend, y el backend es quien
// sabe por dónde iba.

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

import * as api from '../api/instalacion'
import { Aviso, Boton, Espacio, Marco, Mono, Pie, Titulo } from '../components/instalacion/Piezas'
import { Bienvenida, Logo, Organizacion, Usuarios } from '../components/instalacion/Pasos1a4'
import { Casparcg, Cronometraje, Ubicacion } from '../components/instalacion/Pasos5a7'

const TOTAL = 7

// El orden es el mismo que PASOS en instalacion_model.py. Si uno cambia,
// el otro también: el backend guarda por nombre de paso.
const PASOS = ['bienvenida', 'organizacion', 'logo', 'usuarios',
               'cronometraje', 'casparcg', 'clima', 'listo']

const ORGANIZACION_VACIA = {
  organizacion: '', circuito: '', pais: '', ciudad: '',
  idioma: 'es', zona_horaria: 'UTC',
}

export default function Instalacion() {
  const navigate = useNavigate()

  const [indice, setIndice] = useState(0)
  const [organizacion, setOrganizacion] = useState(ORGANIZACION_VACIA)
  const [cargando, setCargando] = useState(true)
  const [bloqueo, setBloqueo] = useState('')

  useEffect(() => {
    // El token viene en la dirección con la que el instalador abrió el
    // navegador. Se recoge y se limpia la barra antes de nada.
    api.recogerTokenDeLaUrl()

    api.estado()
      .then(e => {
        if (e.configurado) {
          setBloqueo('Este sistema ya está configurado. Los cambios se hacen desde Ajustes.')
          return
        }
        if (!api.leerToken()) {
          setBloqueo('Falta el token de instalación. Abre el asistente desde el enlace '
                   + 'que mostró el instalador, o vuelve a ejecutarlo.')
          return
        }
        // Se retoma donde lo dejó, no desde el principio: cerrar el
        // navegador a media instalación no puede obligar a repetirlo todo.
        const guardado = PASOS.indexOf(e.paso)
        if (guardado > 0) setIndice(guardado)
      })
      .catch(e => setBloqueo(e.message))
      .finally(() => setCargando(false))
  }, [])

  const siguiente = () => setIndice(i => Math.min(i + 1, PASOS.length - 1))
  const atras     = () => setIndice(i => Math.max(i - 1, 0))

  if (cargando) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 size={30} className="animate-spin text-red-600" />
      </div>
    )
  }

  if (bloqueo) {
    return (
      <Marco>
        <Titulo>No se puede continuar</Titulo>
        <Aviso tipo="aviso">{bloqueo}</Aviso>
        <Pie>
          <Espacio />
          <Boton onClick={() => navigate('/login', { replace: true })}>Ir al panel</Boton>
          <Espacio />
        </Pie>
      </Marco>
    )
  }

  const paso = PASOS[indice]

  // La bienvenida sí cuenta como paso —es la primera pantalla que se ve—
  // y la final no: cuando se llega, ya terminó. Sin contar la bienvenida
  // la barra se quedaba a un segmento del final y el número iba corrido.
  const numero = paso === 'listo' ? null : indice + 1

  const contenido = {
    bienvenida:   <Bienvenida onSiguiente={siguiente} />,
    organizacion: <Organizacion datos={organizacion} onCambio={setOrganizacion}
                                onSiguiente={siguiente} onAtras={atras} />,
    logo:         <Logo onSiguiente={siguiente} onAtras={atras} />,
    usuarios:     <Usuarios onSiguiente={siguiente} onAtras={atras} />,
    cronometraje: <Cronometraje onSiguiente={siguiente} onAtras={atras} />,
    casparcg:     <Casparcg onSiguiente={siguiente} onAtras={atras} />,
    clima:        <Ubicacion onSiguiente={siguiente} onAtras={atras} />,
    listo:        <Listo organizacion={organizacion} />,
  }[paso]

  return (
    <Marco paso={numero} total={TOTAL} ancho={paso === 'usuarios' ? 'max-w-4xl' : 'max-w-3xl'}>
      {contenido}
    </Marco>
  )
}

// ─── La pantalla final ────────────────────────────────────────

function Listo({ organizacion }) {
  const navigate = useNavigate()
  const [red, setRed] = useState(null)
  const [cerrando, setCerrando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { api.red().then(setRed).catch(() => {}) }, [])

  const terminar = async () => {
    setError(''); setCerrando(true)
    try {
      await api.completar()
      // Recarga completa y no navigate: al completarse, el backend borra
      // el token y cierra el asistente, así que la app tiene que volver a
      // preguntar su estado desde cero para no quedarse con el viejo.
      window.location.href = '/login'
    } catch (e) {
      setError(e.message)
      setCerrando(false)
    }
  }

  return (
    <>
      <div className="text-center text-5xl mb-4">🏁</div>
      <div className="text-center">
        <Titulo>Todo listo</Titulo>
      </div>
      <p className="text-neutral-400 text-center -mt-4 mb-6">
        {organizacion.organizacion || 'Race Core Studio'}
        {organizacion.ciudad && ` · ${organizacion.ciudad}`}
        {organizacion.pais && `, ${organizacion.pais}`}
      </p>

      {error && <Aviso tipo="error">{error}</Aviso>}

      {red && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          <Tarjeta titulo="DESDE ESTE EQUIPO" valor={red.local} />
          {red.red && <Tarjeta titulo="DESDE UN IPAD U OTRO PC" valor={red.red} />}
        </div>
      )}

      <Aviso tipo="aviso" titulo="Este asistente no se vuelve a abrir">
        Todo cambio posterior se hace desde Ajustes, entrando con una cuenta.
      </Aviso>

      <Pie>
        <Espacio />
        <Boton variante="verde" onClick={terminar} cargando={cerrando}>
          Terminar y entrar al panel
        </Boton>
        <Espacio />
      </Pie>
    </>
  )
}

function Tarjeta({ titulo, valor }) {
  return (
    <div className="bg-[#1c1c1f] border border-neutral-700 rounded-xl px-4 py-3">
      <p className="text-[11px] text-neutral-500 font-bold tracking-wider">{titulo}</p>
      <p className="text-neutral-200 font-bold mt-1 break-all"><Mono>{valor}</Mono></p>
    </div>
  )
}
