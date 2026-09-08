import { useEffect, useState } from 'react'
import { MapPin, Search, Link2, Crosshair } from 'lucide-react'
import * as api from '../../api/instalacion'
import { Aviso, Boton, Campo, Entrada, Espacio, Mono, Pie, Titulo } from './Piezas'

// ─── 5 · Cronometraje ─────────────────────────────────────────

export function Cronometraje({ onSiguiente, onAtras }) {
  const [ruta, setRuta] = useState('')
  const [prueba, setPrueba] = useState(null)
  const [probando, setProbando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  // La ruta mapeada es el fallo más común de todos, y no da un error
  // evidente: el archivo se abre bien desde el Explorador y el servicio
  // de Windows no lo ve. Se avisa antes de que lo descubra en carrera.
  const esUnidadMapeada = /^[A-Za-z]:[\\/]/.test(ruta.trim())

  const probar = async (candidata = ruta) => {
    setError(''); setPrueba(null); setProbando(true)
    try {
      setPrueba(await api.verificarRuta(candidata))
    } catch (e) {
      setError(e.message)
    } finally {
      setProbando(false)
    }
  }

  const usarDemo = async () => {
    const demo = 'DEMO'
    setRuta(demo)
    await probar(demo)
  }

  const guardar = async () => {
    setError(''); setEnviando(true)
    try {
      await api.guardarCronometraje(ruta)
      onSiguiente()
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  const ok = prueba?.ok ?? prueba?.existe ?? false

  return (
    <>
      <Titulo sub={<>Race Core Studio lee el <Mono>current.xml</Mono> que MyLaps reescribe en vivo. Indica dónde está en la red.</>}>
        Cronometraje — MyLaps
      </Titulo>

      {error && <Aviso tipo="error">{error}</Aviso>}

      <Campo
        etiqueta="RUTA DEL CURRENT.XML"
        ayuda={<>Usa ruta de red completa (UNC). Una unidad mapeada como <Mono>W:\</Mono> no
               funciona: el servicio de Windows no las ve.</>}
      >
        <Entrada
          value={ruta}
          onChange={(e) => { setRuta(e.target.value); setPrueba(null) }}
          placeholder="\\TIMING-PC\MyLaps\current.xml"
          estado={prueba ? (ok ? 'ok' : 'error') : undefined}
          autoFocus
        />
      </Campo>

      {esUnidadMapeada && (
        <Aviso tipo="aviso" titulo="Eso parece una unidad de red mapeada">
          El servicio de Windows que ejecuta el backend no ve las unidades mapeadas, aunque
          el archivo se abra bien desde el Explorador. Usa la ruta completa:{' '}
          <Mono>{'\\\\NOMBRE-DEL-EQUIPO\\carpeta\\current.xml'}</Mono>
        </Aviso>
      )}

      <div className="flex gap-2.5 mb-4">
        <Boton variante="terciario" onClick={() => probar()} cargando={probando}
               disabled={!ruta.trim()}>
          Verificar ruta
        </Boton>
        <Boton variante="terciario" onClick={usarDemo}>
          Usar el XML de demostración
        </Boton>
      </div>

      {prueba && (
        <Aviso
          tipo={ok ? 'ok' : 'error'}
          titulo={ok ? 'Archivo leído correctamente' : 'No se pudo leer el archivo'}
        >
          {prueba.detalle || prueba.mensaje || prueba.error ||
            (ok ? 'El cronometraje se lee sin problemas.' : 'Revisa la ruta.')}
        </Aviso>
      )}

      {!prueba && (
        <Aviso tipo="info" titulo="¿MyLaps todavía no está encendido?">
          Puedes seguir con el XML de demostración y ajustar la ruta real más adelante,
          desde Ajustes.
        </Aviso>
      )}

      <Pie>
        <Boton variante="secundario" onClick={onAtras}>Atrás</Boton>
        <Espacio />
        <Boton onClick={guardar} disabled={!ruta.trim()} cargando={enviando}>Continuar</Boton>
      </Pie>
    </>
  )
}

// ─── 6 · Servidor de gráficos ─────────────────────────────────

export function Casparcg({ onSiguiente, onAtras }) {
  const [prueba, setPrueba] = useState(null)
  const [probando, setProbando] = useState(false)
  const [enviando, setEnviando] = useState(false)

  const probar = async () => {
    setProbando(true)
    try {
      setPrueba(await api.probarCasparcg())
    } catch (e) {
      setPrueba({ ok: false, error: e.message })
    } finally {
      setProbando(false)
    }
  }

  // Se prueba solo al entrar: es una comprobación, no una acción que
  // alguien tenga que pedir.
  useEffect(() => { probar() }, [])

  const seguir = async () => {
    setEnviando(true)
    try {
      await api.guardarCasparcg()
      onSiguiente()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <>
      <Titulo sub="Comprobación de que CasparCG está corriendo y responde.">
        Servidor de gráficos
      </Titulo>

      {probando && <Aviso tipo="info" titulo="Preguntando a CasparCG…" />}

      {prueba && !probando && (
        <Aviso
          tipo={prueba.ok ? 'ok' : 'aviso'}
          titulo={prueba.ok ? 'CasparCG respondió' : 'CasparCG no responde'}
        >
          {prueba.ok
            ? <>Versión {String(prueba.version).trim()} — AMCP en el puerto 5250</>
            : <>{prueba.error}<br />
                Se puede seguir e instalarlo después: el resto del sistema no depende
                de esto para configurarse.</>}
        </Aviso>
      )}

      <Pie>
        <Boton variante="secundario" onClick={onAtras}>Atrás</Boton>
        <Espacio />
        <Boton variante="terciario" onClick={probar} cargando={probando}>Probar de nuevo</Boton>
        <Boton onClick={seguir} cargando={enviando}>Continuar</Boton>
      </Pie>
    </>
  )
}

// ─── 7 · Ubicación del circuito ───────────────────────────────

const PESTANAS = [
  { id: 'buscar',      etiqueta: 'Buscar por nombre',   Icon: Search },
  { id: 'enlace',      etiqueta: 'Pegar enlace del mapa', Icon: Link2 },
  { id: 'coordenadas', etiqueta: 'Escribir coordenadas',  Icon: Crosshair },
]

export function Ubicacion({ onSiguiente, onAtras }) {
  const [pestana, setPestana] = useState('buscar')
  const [texto, setTexto] = useState('')
  const [resultados, setResultados] = useState([])
  const [sugerencia, setSugerencia] = useState('')
  const [elegido, setElegido] = useState(null)
  const [buscando, setBuscando] = useState(false)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const limpiar = () => { setResultados([]); setElegido(null); setError(''); setSugerencia('') }

  const buscar = async () => {
    limpiar(); setBuscando(true)
    try {
      const r = await api.buscarUbicacion(texto)
      setResultados(r.resultados)
      setSugerencia(r.sugerencia)
    } catch (e) {
      setError(e.message)
    } finally {
      setBuscando(false)
    }
  }

  const interpretar = async () => {
    limpiar(); setBuscando(true)
    try {
      const r = await api.interpretarUbicacion(texto)
      // Sin `nombre`: lo que se lee de unas coordenadas o de un enlace no
      // trae ciudad, y poner aquí la etiqueta de la interfaz la mandaba a
      // la base y de ahí al gráfico del clima, que acababa rotulando
      // «Leído del enlace del mapa» donde va el nombre del sitio.
      if (r.ok) setElegido({ lat: r.lat, lon: r.lon, origen: r.origen })
      else setError(r.error)
    } catch (e) {
      setError(e.message)
    } finally {
      setBuscando(false)
    }
  }

  const guardar = async () => {
    setEnviando(true)
    try {
      await api.guardarClima({
        lat: elegido.lat,
        lon: elegido.lon,
        ciudad: elegido.nombre,
        zona_horaria: elegido.zona_horaria,
      })
      onSiguiente()
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  const accion = pestana === 'buscar' ? buscar : interpretar

  return (
    <>
      <Titulo sub="Se usa para la plantilla del clima. Búscalo por su nombre, pega un enlace del mapa, o escribe las coordenadas.">
        ¿Dónde está el circuito?
      </Titulo>

      <div className="flex border-b border-neutral-800 mb-5 -mx-1">
        {PESTANAS.map(({ id, etiqueta, Icon }) => (
          <button
            key={id}
            onClick={() => { setPestana(id); setTexto(''); limpiar() }}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-bold -mb-px
                        border-b-2 transition-colors ${
              pestana === id
                ? 'text-red-500 border-red-600'
                : 'text-neutral-500 border-transparent hover:text-neutral-300'
            }`}
          >
            <Icon size={15} />
            <span className="hidden sm:inline">{etiqueta}</span>
          </button>
        ))}
      </div>

      {error && <Aviso tipo="error">{error}</Aviso>}

      <Campo
        ayuda={pestana === 'buscar'
          ? 'Un buscador de mapas encuentra ciudades, no circuitos. Si el nombre de tu pista no aparece, busca la ciudad más cercana: para el clima, unos kilómetros no cambian nada.'
          : pestana === 'enlace'
          ? 'Vale el enlace corto de compartir desde el móvil, el enlace largo del navegador, o las coordenadas que salen al hacer clic derecho sobre el mapa.'
          : 'Latitud y longitud separadas por coma. También se aceptan grados y minutos.'}
      >
        <Entrada
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && texto.trim() && accion()}
          placeholder={pestana === 'buscar' ? 'Monterrey'
            : pestana === 'enlace' ? 'https://maps.app.goo.gl/…'
            : '25.6866, -100.3161'}
          estado={elegido ? 'ok' : undefined}
          autoFocus
        />
      </Campo>

      <Boton variante="terciario" onClick={accion} cargando={buscando} disabled={!texto.trim()}>
        {pestana === 'buscar' ? 'Buscar' : 'Leer coordenadas'}
      </Boton>

      {sugerencia && <div className="mt-4"><Aviso tipo="info">{sugerencia}</Aviso></div>}

      {resultados.length > 0 && (
        <div className="mt-4 space-y-2 max-h-56 overflow-y-auto">
          {resultados.map((r, i) => {
            const activo = elegido?.lat === r.lat && elegido?.lon === r.lon
            return (
              <button
                key={i}
                onClick={() => setElegido(r)}
                className={`w-full flex items-center gap-3 text-left rounded-lg px-4 py-3
                            border transition-colors ${
                  activo
                    ? 'border-green-600 bg-green-600/10'
                    : 'border-neutral-700 bg-[#1c1c1f] hover:border-neutral-500'
                }`}
              >
                <MapPin size={16} className={activo ? 'text-green-500' : 'text-neutral-600'} />
                <div className="flex-1 min-w-0">
                  <p className="text-neutral-200 font-bold text-[15px] truncate">{r.nombre}</p>
                  <p className="text-neutral-500 text-[13px] truncate">{r.detalle}</p>
                </div>
                <code className="text-neutral-400 text-[12px] shrink-0 hidden sm:block">
                  {r.lat.toFixed(4)}, {r.lon.toFixed(4)}
                </code>
              </button>
            )
          })}
        </div>
      )}

      {elegido && (
        <div className="mt-4">
          <Aviso tipo="ok" titulo="Ubicación elegida">
            {elegido.nombre
              ? <>{elegido.nombre}{elegido.detalle ? ` · ${elegido.detalle}` : ''}</>
              : `Coordenadas leídas del ${elegido.origen}`}
            <br />
            Latitud <Mono>{elegido.lat.toFixed(6)}</Mono> ·
            Longitud <Mono>{elegido.lon.toFixed(6)}</Mono>
            {elegido.zona_horaria && <><br />Zona horaria detectada: <Mono>{elegido.zona_horaria}</Mono></>}
          </Aviso>
        </div>
      )}

      <Pie>
        <Boton variante="secundario" onClick={onAtras}>Atrás</Boton>
        <Espacio />
        <Boton onClick={guardar} disabled={!elegido} cargando={enviando}>Continuar</Boton>
      </Pie>
    </>
  )
}
