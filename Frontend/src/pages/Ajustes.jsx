import { t } from '../i18n'
import { useEffect, useRef, useState } from 'react'
import {
  Loader2, CheckCircle2, AlertCircle, FolderSearch, Save, FlaskConical,
  Upload, X, ImageIcon, Plug, Radio, Sliders, Languages, Type,
} from 'lucide-react'
import {
  elegirFuente, guardarRutaXml, leerAjustes, listarFuentes, probarRutaXml,
  quitarLogoCliente, subirLogoCliente, urlFuente, urlLogoCliente,
} from '../api/registro'
import { reconectarCasparcg } from '../api/graphics'
import Trazados from '../components/settings/Trazados'
import { useToast } from '../context/ToastContext'
import { useIdioma } from '../context/IdiomaContext'
import ExploradorXml from '../components/settings/ExploradorXml'


// ─── Pestañas ─────────────────────────────────────────────────
const PESTANAS = [
  { id: 'generales',  nombre: 'Generales',  Icon: Sliders  },
  { id: 'conexiones', nombre: 'Conexiones', Icon: Plug     },
  { id: 'imagenes',   nombre: 'Imágenes',   Icon: ImageIcon },
]

// ─── Generales ────────────────────────────────────────────────
function Generales() {

  const toast = useToast()

  const { idioma, idiomas, cambiar: cambiarIdioma } = useIdioma()

  const [fuentes,  setFuentes]  = useState([])
  const [actual,   setActual]   = useState(null)
  const [guardando, setGuardando] = useState(null)

  useEffect(() => {
    listarFuentes()
      .then(r => { setFuentes(r.fuentes || []); setActual(r.actual) })
      .catch(() => {})
  }, [])

  /* Cada tipografía se declara en el propio panel apuntando a los mismos
     archivos que usan las plantillas. Sin esto los cinco botones saldrían
     con la letra de la interfaz y elegir sería adivinar. */
  useEffect(() => {
    if (!fuentes.length) return

    const estilo = document.createElement('style')
    estilo.textContent = fuentes.map(f => `
      @font-face{
        font-family:"${f.nombre}";
        src:url("${urlFuente(f.url)}") format("woff2");
        font-weight:700;
        font-display:swap;
      }`).join('')

    document.head.appendChild(estilo)
    return () => { document.head.removeChild(estilo) }
  }, [fuentes])

  const cambiar = async (id) => {
    setGuardando(id)
    try {
      await elegirFuente(id)
      setActual(id)
      toast('Tipografía cambiada. Los gráficos que ya estén al aire la toman al volver a sacarlos.')
    } catch (e) {
      toast(e.message || 'No se pudo cambiar la tipografía', 'error')
    } finally {
      setGuardando(null)
    }
  }

  return (
    <>
      <div className="bg-[#141414] rounded-xl border border-neutral-800 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Languages size={17} className="text-neutral-500"/>
          <h3 className="text-lg font-black italic text-white">{t('IDIOMA')}</h3>
        </div>
        <p className="text-neutral-500 text-sm mb-5">
          Cambia la interfaz y los rótulos de los gráficos a la vez. Los datos
          —nombres, equipos, marcas— no se traducen: son nombres propios.
          El inglés está traducido pero apagado; se enciende cuando haga falta.
        </p>

        <select
          value={idioma}
          onChange={async e => {
            try { await cambiarIdioma(e.target.value) }
            catch (err) { toast(err.message || 'No se pudo cambiar el idioma', 'error') }
          }}
          className="w-full sm:w-72 bg-[#0a0a0a] border border-neutral-800 rounded p-2.5 focus:border-red-600 focus:outline-none text-white"
        >
          {idiomas.map(l => (
            <option key={l.id} value={l.id} disabled={!l.listo}>
              {t(l.nombre)}{l.listo ? '' : t(' — desactivado')}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-[#141414] rounded-xl border border-neutral-800 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Type size={17} className="text-neutral-500"/>
          <h3 className="text-lg font-black italic text-white">{t('TIPOGRAFÍA DE LOS GRÁFICOS')}</h3>
        </div>
        <p className="text-neutral-500 text-sm mb-5">
          La letra con la que salen al aire los tótems, las banderas, las cartas y
          la grilla. Van empaquetadas con el software, así que el arte se ve igual
          en cualquier máquina sin instalar nada.
        </p>

        <div className="space-y-2.5">
          {fuentes.map(f => {
            const activa = actual === f.id
            const ocupado = guardando === f.id
            return (
              <button
                key={f.id} type="button"
                onClick={() => cambiar(f.id)}
                disabled={guardando !== null}
                className={`w-full text-left rounded-lg border p-4 transition-colors disabled:cursor-not-allowed ${
                  activa
                    ? 'border-red-600 bg-red-600/10'
                    : 'border-neutral-800 bg-[#0a0a0a] hover:border-neutral-600'
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    {/* La muestra va en la propia letra: es lo único que
                        deja comparar cinco tipografías de un vistazo. */}
                    <p
                      className="text-white text-2xl leading-tight truncate"
                      style={{ fontFamily: `"${f.nombre}", sans-serif`, fontWeight: 700 }}
                    >
                      {f.nombre}
                    </p>
                    <p
                      className="text-neutral-400 text-lg leading-tight truncate"
                      style={{ fontFamily: `"${f.nombre}", sans-serif`, fontWeight: 700 }}
                    >
                      DE GRACIA · #24 · 1:23.456
                    </p>
                  </div>

                  <span className={`flex-shrink-0 text-xs font-bold uppercase tracking-wider ${
                    activa ? 'text-red-400' : 'text-neutral-600'
                  }`}>
                    {ocupado ? 'Guardando…' : activa ? 'En uso' : 'Usar'}
                  </span>
                </div>

                <p className="text-neutral-500 text-sm mt-2.5 leading-relaxed">
                  {f.nota}
                </p>
              </button>
            )
          })}
        </div>
      </div>
    </>
  )
}

export default function AjustesModule() {
  const toast = useToast()

  const [pestana,   setPestana]   = useState('generales')
  const [cargando,  setCargando]  = useState(true)
  const [ruta,      setRuta]      = useState('')
  const [aplicada,  setAplicada]  = useState('')
  const [estado,    setEstado]    = useState(null)   // estado de la ruta aplicada
  const [explorando, setExplorando] = useState(false)
  const [prueba,    setPrueba]    = useState(null)   // resultado de "probar"
  const [detectados, setDetectados] = useState([])

  // Logo del cliente. Se sube y se ve al momento: cambia en los 22
  // gráficos a la vez porque todas las plantillas miran el mismo archivo.
  const [logoUrl,   setLogoUrl]   = useState(null)
  const [logoPropio, setLogoPropio] = useState(null)
  const [subiendo,  setSubiendo]  = useState(false)
  const inputLogo = useRef(null)

  // Reconexión con CasparCG
  const [reconectando, setReconectando] = useState(false)
  const [conexion,     setConexion]     = useState(null)
  const [probando,  setProbando]  = useState(false)
  const [guardando, setGuardando] = useState(false)

  const cargar = () => {
    setCargando(true)
    leerAjustes()
      .then(a => {
        setRuta(a.timing_xml_path || '')
        setAplicada(a.timing_xml_path || '')
        setEstado(a.estado)
        setDetectados(a.detectados || [])
        setLogoUrl(a.client_logo_url || null)
        setLogoPropio(a.client_logo || null)
      })
      .catch(err => toast.error('No se pudieron cargar los ajustes', err.message))
      .finally(() => setCargando(false))
  }

  useEffect(cargar, [])   // eslint-disable-line react-hooks/exhaustive-deps

  const probar = async () => {
    setProbando(true)
    setPrueba(null)
    try {
      setPrueba(await probarRutaXml(ruta))
    } catch (err) {
      setPrueba({ ok: false, detalle: err.message })
    } finally {
      setProbando(false)
    }
  }

  const guardar = async () => {
    setGuardando(true)
    try {
      const r = await guardarRutaXml(ruta)
      setAplicada(r.timing_xml_path)
      setEstado(r.estado)
      setPrueba(null)
      toast.exito(
        'Ruta aplicada',
        r.estado?.ok ? `${r.estado.evento || 'archivo leído'} · ${r.estado.tanda || ''}`.trim()
                     : 'guardada, pero el archivo no se pudo leer',
      )
    } catch (err) {
      toast.error('No se pudo guardar', err.message)
    } finally {
      setGuardando(false)
    }
  }

  const subirLogo = async (archivo) => {
    if (!archivo) return
    setSubiendo(true)
    try {
      const r = await subirLogoCliente(archivo)
      setLogoUrl(r.client_logo_url)
      setLogoPropio(archivo.name)
      toast.exito('Logo actualizado', 'Sale en todos los gráficos')
    } catch (err) {
      toast.error('No se pudo subir el logo', err.message)
    } finally {
      setSubiendo(false)
      if (inputLogo.current) inputLogo.current.value = ''
    }
  }

  const restaurarLogo = async () => {
    setSubiendo(true)
    try {
      const r = await quitarLogoCliente()
      setLogoUrl(r.client_logo_url)
      setLogoPropio(null)
      toast.exito('Logo restaurado', 'Vuelve el que trae el software')
    } catch (err) {
      toast.error('No se pudo restaurar', err.message)
    } finally {
      setSubiendo(false)
    }
  }

  const reconectar = async () => {
    setReconectando(true)
    setConexion(null)
    try {
      setConexion(await reconectarCasparcg())
    } catch (err) {
      setConexion({ ok: false, detalle: err.message })
    } finally {
      setReconectando(false)
    }
  }

  const sinCambios = ruta.trim() === (aplicada || '').trim()

  const Diagnostico = ({ r, titulo }) => {
    if (!r) return null
    return (
      <div className={`flex items-start gap-3 rounded-lg px-4 py-3 border ${
        r.ok ? 'border-green-600/40 bg-green-600/5' : 'border-red-600/40 bg-red-600/5'
      }`}>
        {r.ok
          ? <CheckCircle2 size={18} className="text-green-500 flex-shrink-0 mt-0.5"/>
          : <AlertCircle size={18} className="text-red-500 flex-shrink-0 mt-0.5"/>}
        <div className="min-w-0">
          {titulo && <p className="text-xs uppercase tracking-wider text-neutral-500 mb-0.5">{titulo}</p>}
          <p className={`text-sm font-bold ${r.ok ? 'text-green-400' : 'text-red-400'}`}>{r.detalle}</p>
          {r.ok && (
            <p className="text-xs text-neutral-500 mt-1">
              {[r.evento, r.tanda, r.grupo].filter(Boolean).join(' · ')}
              {r.filas != null && ` · ${r.filas} líneas`}
            </p>
          )}
        </div>
      </div>
    )
  }

  if (cargando) {
    return (
      <div className="w-full py-20 text-center">
        <Loader2 className="w-6 h-6 animate-spin mx-auto text-red-600"/>
      </div>
    )
  }

  return (
    <div className="w-full max-w-3xl animate-fade-in">

      {/* Ajustes eran una sola columna de tarjetas sueltas y ya no cabian
          de un vistazo. Repartidas por pestañas, cada una agrupa cosas que
          se tocan juntas: lo que conecta con el exterior, lo que se ve, y
          lo que define el sistema. */}
      <div className="flex gap-2 mb-6 border-b border-neutral-800">
        {PESTANAS.map(({ id, nombre, Icon }) => {
          const activa = pestana === id
          return (
            <button
              key={id} type="button"
              onClick={() => setPestana(id)}
              className={`flex items-center gap-2 px-4 py-3 -mb-px border-b-2 font-bold text-sm uppercase tracking-wide transition-colors ${
                activa
                  ? 'border-red-600 text-white'
                  : 'border-transparent text-neutral-500 hover:text-neutral-300'
              }`}
            >
              <Icon size={16} />
              {t(nombre)}
            </button>
          )
        })}
      </div>

      <div className="space-y-6">

        {pestana === 'generales' && <Generales />}

        {pestana === 'conexiones' && (
          <>
      <div className="bg-[#141414] rounded-xl border border-neutral-800 p-6">
        <h3 className="text-lg font-black italic text-white mb-1">{t('CRONOMETRAJE')}</h3>
        <p className="text-neutral-500 text-sm mb-5">
          Archivo que MyLaps reescribe con la clasificación en vivo. El backend lo relee
          varias veces por segundo mientras hay una tanda en pista.
        </p>

        <label className="block text-neutral-400 text-xs mb-2 uppercase">
          {t('Ruta del current.xml')}
        </label>
        <div className="flex flex-col sm:flex-row gap-2 mb-3">
          <input
            type="text" value={ruta}
            onChange={e => { setRuta(e.target.value); setPrueba(null) }}
            placeholder="W:/XML/current.xml"
            spellCheck={false}
            className="flex-1 bg-[#0a0a0a] border border-neutral-800 rounded p-2.5 font-mono text-sm focus:border-red-600 focus:outline-none text-white"
          />
          {/* Examinar el disco DEL SERVIDOR. El selector de archivos del
              navegador no vale: entrega el archivo pero nunca su ruta, y
              es la ruta lo que hay que guardar. */}
          <button
            onClick={() => setExplorando(v => !v)}
            className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border transition-colors font-bold text-sm whitespace-nowrap ${
              explorando
                ? 'border-red-600 bg-red-600/10 text-red-400'
                : 'border-neutral-700 text-neutral-300 hover:border-neutral-500 hover:text-white'}`}
          >
            <FolderSearch size={16}/>
            {t('EXAMINAR')}
          </button>
          <button
            onClick={probar} disabled={probando || !ruta.trim()}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-neutral-700 text-neutral-300 hover:border-blue-500 hover:text-blue-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-bold text-sm whitespace-nowrap"
          >
            {probando ? <Loader2 size={16} className="animate-spin"/> : <FlaskConical size={16}/>}
            {t('PROBAR')}
          </button>
          <button
            onClick={guardar} disabled={guardando || sinCambios}
            className="flex items-center justify-center gap-2 bg-white text-black font-bold py-2.5 px-5 rounded-lg hover:bg-neutral-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm whitespace-nowrap"
          >
            {guardando ? <Loader2 size={16} className="animate-spin"/> : <Save size={16}/>}
            {t('APLICAR')}
          </button>
        </div>

        {explorando && (
          <ExploradorXml
            rutaInicial={ruta}
            onElegir={r => { setRuta(r); setPrueba(null); setExplorando(false) }}
            onCerrar={() => setExplorando(false)}
          />
        )}

        {/* Se navega el disco del servidor, no el de quien mira el panel:
            el XML lo lee el backend, que puede estar en otra máquina. */}
        <p className="text-xs text-neutral-600 mt-3 mb-5">
          {t('Es una ruta del servidor donde corre el backend, no de tu equipo.')}
        </p>

        <div className="space-y-3">
          <Diagnostico r={prueba} titulo={t('Prueba (sin aplicar)')} />
          {!prueba && <Diagnostico r={estado} titulo={t('Ruta en uso')} />}
        </div>
      </div>

      <div className="bg-[#141414] rounded-xl border border-neutral-800 p-6">
        <div className="flex items-center gap-2 mb-1">
          <FolderSearch size={17} className="text-neutral-500"/>
          <h3 className="text-lg font-black italic text-white">{t('ARCHIVOS DETECTADOS')}</h3>
        </div>
        <p className="text-neutral-500 text-sm mb-4">
          {t('XML que el servidor alcanza ahora mismo. Pulsa uno para ponerlo en el campo de arriba.')}
        </p>

        <div className="flex flex-col gap-2">
          {detectados.map(d => {
            const enUso = d.ruta === aplicada
            return (
              <button
                key={d.ruta}
                onClick={() => { setRuta(d.ruta); setPrueba(null) }}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-colors ${
                  enUso ? 'border-red-600/60 bg-red-600/5' : 'border-neutral-800 hover:border-neutral-600'
                }`}
              >
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${d.existe ? 'bg-green-500' : 'bg-red-600'}`}/>
                <span className="flex-1 min-w-0">
                  <span className="block text-sm font-bold text-white">{t(d.nombre)}</span>
                  <span className="block text-[11px] text-neutral-600 font-mono truncate">{d.ruta}</span>
                </span>
                {enUso && (
                  <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-red-600/15 text-red-400 flex-shrink-0">
                    {t('EN USO')}
                  </span>
                )}
                {!d.existe && (
                  <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-neutral-700/30 text-neutral-500 flex-shrink-0">
                    {t('NO ALCANZABLE')}
                  </span>
                )}
              </button>
            )
          })}
          {detectados.length === 0 && (
            <p className="text-sm text-neutral-600">{t('El servidor no encuentra ningún XML.')}</p>
          )}
        </div>
      </div>

      {/* Reconexión con CasparCG. Hace falta porque el cliente solo se da
          cuenta de que la conexión murió al mandar el siguiente comando:
          si CasparCG se cerró y se abrió, parece viva y no lo está. */}
      <div className="bg-[#141414] rounded-xl border border-neutral-800 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Plug size={17} className="text-neutral-500"/>
          <h3 className="text-lg font-black italic text-white">{t('CONEXIÓN CON CASPARCG')}</h3>
        </div>
        <p className="text-neutral-500 text-sm mb-5">
          Si cerraste y volviste a abrir CasparCG, la conexión anterior se queda
          colgada y el primer gráfico falla. Esto la fuerza sin reiniciar nada.
        </p>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button" onClick={reconectar} disabled={reconectando}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg border border-neutral-700 text-neutral-300 hover:border-green-500 hover:text-green-400 disabled:opacity-40 transition-colors font-bold text-sm"
          >
            {reconectando ? <Loader2 size={16} className="animate-spin"/> : <Radio size={16}/>}
            {t('RECONECTAR')}
          </button>

          {conexion && (
            <span className={`flex items-center gap-2 text-sm font-bold ${
              conexion.ok ? 'text-green-400' : 'text-red-400'
            }`}>
              {conexion.ok
                ? <CheckCircle2 size={16}/>
                : <AlertCircle size={16}/>}
              {conexion.ok
                ? `Conectado a ${conexion.host}:${conexion.port}`
                : conexion.detalle}
            </span>
          )}
        </div>
      </div>
          </>
        )}

        {pestana === 'imagenes' && (
          <>
      {/* Logo del cliente. Va aquí y no en cada plantilla porque las 22
          apuntan al mismo archivo: cambiarlo lo cambia en todos los
          gráficos de una vez. */}
      <div className="bg-[#141414] rounded-xl border border-neutral-800 p-6">
        <div className="flex items-center gap-2 mb-1">
          <ImageIcon size={17} className="text-neutral-500"/>
          <h3 className="text-lg font-black italic text-white">{t('LOGO DEL AUTÓDROMO')}</h3>
        </div>
        <p className="text-neutral-500 text-sm mb-5">
          Sale en todos los gráficos: tótems, banderas, fichas y cartas. Se guarda
          en PNG con transparencia, para que no salga con un recuadro blanco sobre
          los paneles oscuros.
        </p>

        <div className="flex items-center gap-5">
          {/* Fondo a cuadros para ver la transparencia del logo. */}
          <div
            className="w-32 h-24 rounded-lg border border-neutral-800 flex items-center justify-center overflow-hidden flex-shrink-0"
            style={{
              backgroundImage:
                'linear-gradient(45deg,#1a1a1a 25%,transparent 25%),' +
                'linear-gradient(-45deg,#1a1a1a 25%,transparent 25%),' +
                'linear-gradient(45deg,transparent 75%,#1a1a1a 75%),' +
                'linear-gradient(-45deg,transparent 75%,#1a1a1a 75%)',
              backgroundSize: '14px 14px',
              backgroundPosition: '0 0, 0 7px, 7px -7px, -7px 0',
              backgroundColor: '#0a0a0a',
            }}
          >
            {logoUrl
              ? <img src={urlLogoCliente(logoUrl)} alt="" className="max-w-full max-h-full object-contain"/>
              : <ImageIcon size={22} className="text-neutral-700"/>}
          </div>

          <div className="min-w-0">
            <input
              type="file" accept="image/*" ref={inputLogo} className="hidden"
              onChange={e => {
                const elegido = e.target.files?.[0] || null
                subirLogo(elegido)
              }}
            />

            <div className="flex flex-wrap gap-2">
              <button
                type="button" disabled={subiendo}
                onClick={() => inputLogo.current?.click()}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-neutral-700 text-neutral-300 hover:border-blue-500 hover:text-blue-400 disabled:opacity-40 transition-colors font-bold text-sm"
              >
                {subiendo ? <Loader2 size={16} className="animate-spin"/> : <Upload size={16}/>}
                {t('CAMBIAR LOGO')}
              </button>

              {logoPropio && (
                <button
                  type="button" onClick={restaurarLogo} disabled={subiendo}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-neutral-800 text-neutral-500 hover:border-red-600 hover:text-red-500 disabled:opacity-40 transition-colors font-bold text-sm"
                >
                  <X size={16}/> {t('RESTAURAR')}
                </button>
              )}
            </div>

            <p className="text-xs text-neutral-600 mt-2">
              {logoPropio
                ? `En uso: ${logoPropio}`
                : 'Ahora mismo está el que trae el software.'}
            </p>
          </div>
        </div>
      </div>

      <Trazados />
          </>
        )}

      </div>

    </div>
  )
}
