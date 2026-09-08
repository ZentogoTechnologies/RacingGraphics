import { useEffect, useRef, useState } from 'react'
import { Flag, Upload } from 'lucide-react'
import * as api from '../../api/instalacion'
import { Aviso, Boton, Campo, Entrada, Espacio, Mono, Pie, Titulo } from './Piezas'

// ─── 1 · Bienvenida ───────────────────────────────────────────

export function Bienvenida({ onSiguiente }) {
  const [licencia, setLicencia] = useState(null)
  const [red, setRed] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    // Las dos a la vez: son independientes y esperar una detrás de otra
    // solo alarga la primera pantalla que ve el técnico.
    Promise.all([api.licencia(), api.red()])
      .then(([lic, r]) => { setLicencia(lic); setRed(r) })
      .catch(e => setError(e.message))
  }, [])

  return (
    <>
      <Titulo sub="Falta configurar el sistema para este autódromo. Son siete pasos y toma unos minutos.">
        Todo quedó instalado
      </Titulo>

      {error && <Aviso tipo="error" titulo="No se pudo leer el estado">{error}</Aviso>}

      {licencia && (
        <Aviso
          tipo={licencia.opera ? 'ok' : 'error'}
          titulo={licencia.opera
            ? `Licencia ${licencia.estado} — ${licencia.cliente || 'sin cliente'}`
            : 'Problema con la licencia'}
        >
          {licencia.opera
            ? <>Plan {licencia.plan} · vence el{' '}
                {licencia.vence ? new Date(licencia.vence).toLocaleDateString('es') : '—'}
                {licencia.dias_restantes != null && ` · quedan ${licencia.dias_restantes} días`}</>
            : licencia.mensaje}
        </Aviso>
      )}

      {red?.red && (
        <Aviso tipo="info" titulo="Para operar desde otro equipo o un iPad">
          Escribe esta dirección en el navegador: <Mono>{red.red}</Mono>
          <br />
          Desde este mismo equipo: <Mono>{red.local}</Mono>
        </Aviso>
      )}

      <Pie>
        <Boton onClick={onSiguiente} disabled={!licencia}>Comenzar</Boton>
        <Espacio />
      </Pie>
    </>
  )
}

// ─── 2 · Datos del cliente ────────────────────────────────────

export function Organizacion({ datos, onCambio, onSiguiente, onAtras }) {
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  const listo = datos.organizacion.trim().length >= 2 && datos.pais.trim().length >= 2

  const guardar = async () => {
    setError(''); setEnviando(true)
    try {
      await api.guardarOrganizacion(datos)
      onSiguiente()
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  const campo = (clave) => ({
    value: datos[clave],
    onChange: (e) => onCambio({ ...datos, [clave]: e.target.value }),
  })

  return (
    <>
      <Titulo sub="Estos datos aparecen en el panel y en los gráficos que salen al aire.">
        ¿Quién es el cliente?
      </Titulo>

      {error && <Aviso tipo="error">{error}</Aviso>}

      <Campo etiqueta="AUTÓDROMO, CLUB O PROMOTORA *">
        <Entrada {...campo('organizacion')} placeholder="Autódromo Internacional del Norte" autoFocus />
      </Campo>

      <Campo etiqueta="NOMBRE DEL CIRCUITO"
             ayuda="Si el autódromo tiene varios trazados con nombre propio.">
        <Entrada {...campo('circuito')} placeholder="Circuito Principal" />
      </Campo>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Campo etiqueta="PAÍS *">
          <Entrada {...campo('pais')} placeholder="México" />
        </Campo>
        <Campo etiqueta="CIUDAD">
          <Entrada {...campo('ciudad')} placeholder="Monterrey" />
        </Campo>
        <Campo etiqueta="IDIOMA">
          <select
            {...campo('idioma')}
            className="w-full bg-[#1c1c1f] border border-neutral-700 rounded-lg px-3.5 py-2.5
                       text-neutral-200 text-[15px] outline-none focus:border-red-600"
          >
            <option value="es">Español</option>
            <option value="en">English</option>
          </select>
        </Campo>
      </div>

      <Pie>
        <Boton variante="secundario" onClick={onAtras}>Atrás</Boton>
        <Espacio />
        <Boton onClick={guardar} disabled={!listo} cargando={enviando}>Continuar</Boton>
      </Pie>
    </>
  )
}

// ─── 3 · Logo ─────────────────────────────────────────────────

export function Logo({ onSiguiente, onAtras }) {
  const [subiendo, setSubiendo] = useState(false)
  const [subido, setSubido] = useState(null)
  const [error, setError] = useState('')
  const entrada = useRef(null)

  const subir = async (archivo) => {
    if (!archivo) return
    setError(''); setSubiendo(true)
    try {
      const r = await api.subirLogo(archivo)
      setSubido({ nombre: archivo.name, url: r.url })
    } catch (e) {
      setError(e.message)
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <>
      <Titulo sub="Es el que sale al aire en las plantillas de gráficos. Puedes cambiarlo después desde Ajustes.">
        Logo del autódromo
      </Titulo>

      {error && <Aviso tipo="error">{error}</Aviso>}

      <button
        onClick={() => entrada.current?.click()}
        disabled={subiendo}
        className="w-full border-2 border-dashed border-neutral-700 hover:border-red-600
                   rounded-xl p-8 text-center bg-[#1c1c1f] transition-colors
                   disabled:opacity-50"
      >
        {subido ? (
          <>
            <img src={subido.url} alt="" className="h-20 mx-auto object-contain mb-3" />
            <p className="text-neutral-200 font-bold">{subido.nombre}</p>
            <p className="text-neutral-500 text-sm mt-1">Haz clic para cambiarlo</p>
          </>
        ) : (
          <>
            <Upload size={30} className="mx-auto text-neutral-600 mb-3" />
            <p className="text-neutral-200 font-bold">
              {subiendo ? 'Subiendo…' : 'Haz clic para elegir el logo'}
            </p>
            <p className="text-neutral-500 text-sm mt-1.5">
              PNG con fondo transparente · máximo 4 MB · se recomienda 800 × 400 px
            </p>
          </>
        )}
      </button>

      <input
        ref={entrada}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => subir(e.target.files?.[0])}
      />

      <div className="mt-4">
        <Aviso tipo="info" titulo="Este paso se puede omitir">
          Sin logo, las plantillas salen sin marca. Se puede subir más adelante.
        </Aviso>
      </div>

      <Pie>
        <Boton variante="secundario" onClick={onAtras}>Atrás</Boton>
        <Espacio />
        {!subido && <Boton variante="terciario" onClick={onSiguiente}>Omitir</Boton>}
        <Boton onClick={onSiguiente} disabled={subiendo}>Continuar</Boton>
      </Pie>
    </>
  )
}

// ─── 4 · Las tres cuentas ─────────────────────────────────────

const ROLES = [
  { clave: 'owner',    etiqueta: 'OWNER',    color: 'bg-red-600',
    detalle: 'Administra las cuentas del sistema' },
  { clave: 'admin',    etiqueta: 'ADMIN',    color: 'bg-blue-600',
    detalle: 'Crea y edita pilotos, vehículos y eventos' },
  { clave: 'standard', etiqueta: 'STANDARD', color: 'bg-green-600',
    detalle: 'Opera los gráficos, sin modificar registros' },
]

const CUENTAS_VACIAS = {
  owner:    { username: '', password: '' },
  admin:    { username: '', password: '' },
  standard: { username: '', password: '' },
}

export function Usuarios({ onSiguiente, onAtras }) {
  const [cuentas, setCuentas] = useState(CUENTAS_VACIAS)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  const cambiar = (rol, campo, valor) =>
    setCuentas(c => ({ ...c, [rol]: { ...c[rol], [campo]: valor } }))

  // El backend valida esto también, y es él quien manda. Aquí solo se
  // adelanta para no dejar pulsar un botón que ya se sabe que va a fallar.
  const completas = ROLES.every(({ clave }) =>
    cuentas[clave].username.trim().length >= 3 && cuentas[clave].password.length >= 8)

  const nombres = ROLES.map(r => cuentas[r.clave].username.trim().toLowerCase())
  const repetidos = new Set(nombres.filter(Boolean)).size !== nombres.filter(Boolean).length

  const crear = async () => {
    setError(''); setEnviando(true)
    try {
      await api.crearUsuarios(cuentas)
      onSiguiente()
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <>
      <Titulo sub="Las tres son obligatorias. Si solo existiera el dueño, todos operarían con esa cuenta y los roles no separarían nada.">
        Las tres cuentas del sistema
      </Titulo>

      {error && <Aviso tipo="error">{error}</Aviso>}
      {repetidos && (
        <Aviso tipo="aviso">Los tres usuarios deben tener nombres distintos.</Aviso>
      )}

      {ROLES.map(({ clave, etiqueta, color, detalle }) => (
        <div key={clave} className="bg-[#1c1c1f] border border-neutral-700 rounded-xl p-4 mb-3">
          <div className="flex items-center gap-2.5 mb-3">
            <span className={`${color} text-white text-[11px] font-bold px-2.5 py-0.5
                              rounded-full tracking-wider`}>
              {etiqueta}
            </span>
            <span className="text-neutral-400 text-[13px]">{detalle}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Entrada
              placeholder="usuario"
              autoComplete="off"
              value={cuentas[clave].username}
              onChange={(e) => cambiar(clave, 'username', e.target.value)}
            />
            <Entrada
              type="password"
              placeholder="contraseña (mínimo 8)"
              autoComplete="new-password"
              value={cuentas[clave].password}
              onChange={(e) => cambiar(clave, 'password', e.target.value)}
            />
          </div>
        </div>
      ))}

      <Aviso tipo="aviso" titulo="Anota estas contraseñas antes de continuar">
        No hay contraseñas por defecto y no se pueden recuperar desde aquí.
      </Aviso>

      <Pie>
        <Boton variante="secundario" onClick={onAtras}>Atrás</Boton>
        <Espacio />
        <Boton onClick={crear} disabled={!completas || repetidos} cargando={enviando}>
          Crear las tres cuentas
        </Boton>
      </Pie>
    </>
  )
}

export { Flag }
