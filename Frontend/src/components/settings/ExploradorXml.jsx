import { useCallback, useEffect, useState } from 'react'
import {
  ArrowUp, FileCode2, Folder, HardDrive, Loader2, RotateCw, X,
} from 'lucide-react'
import { t } from '../../i18n'
import { explorarRutaXml } from '../../api/registro'

/* ==========================================================================
   EXAMINAR LA RUTA DEL CURRENT.XML

   Navega por las carpetas del SERVIDOR, no por las de quien mira el panel.
   No es un capricho: el archivo lo lee el backend, que puede estar en otra
   máquina, y lo que hay que guardar es su ruta en ese disco. Un selector de
   archivos del navegador entrega el archivo y su nombre pero jamás su ruta
   —lo prohíbe el propio navegador—, así que con él no se puede configurar
   esto. Por eso el servidor enseña sus carpetas y aquí solo se navega.

   Solo llegan carpetas y archivos .xml, nunca el contenido de ninguno:
   esto sirve para encontrar el current.xml, no para leer el disco del
   servidor desde el navegador.
========================================================================== */

const kilobytes = bytes =>
  bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`

const cuando = (segundos) => {
  if (!segundos) return ''
  const fecha = new Date(segundos * 1000)
  return fecha.toLocaleString(undefined, {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

export default function ExploradorXml({ rutaInicial, onElegir, onCerrar }) {
  const [datos,    setDatos]    = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error,    setError]    = useState(null)

  const ir = useCallback(async (ruta) => {
    setCargando(true)
    setError(null)
    try {
      setDatos(await explorarRutaXml(ruta || ''))
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }, [])

  // Se abre donde apunta la ruta que ya está escrita: si dice
  // W:/XML/current.xml, se entra directo en W:/XML en vez de obligar a
  // bajar desde la unidad cada vez.
  useEffect(() => { ir(rutaInicial) }, [ir, rutaInicial])

  const unidades = datos?.unidades || []
  const carpetas = datos?.carpetas || []
  const archivos = datos?.archivos || []

  return (
    <div className="mt-3 bg-[#0f0f0f] border border-neutral-700 rounded-lg overflow-hidden">

      <div className="flex items-center gap-2 px-3 py-2 border-b border-neutral-800">
        <button
          type="button" onClick={() => ir(datos?.padre)} disabled={!datos?.padre || cargando}
          title={t('Subir una carpeta')}
          className="p-1.5 rounded text-neutral-400 hover:text-white hover:bg-neutral-800 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
        >
          <ArrowUp size={15} />
        </button>

        {/* La ruta actual también se puede escribir a mano: con una carpeta
            de miles de archivos, teclearla es más rápido que bajar. */}
        <input
          value={datos?.ruta || ''}
          onChange={e => setDatos(d => ({ ...d, ruta: e.target.value }))}
          onKeyDown={e => { if (e.key === 'Enter') ir(datos?.ruta) }}
          placeholder={t('Elige una unidad o escribe una ruta')}
          spellCheck={false}
          className="flex-1 min-w-0 bg-transparent text-white text-xs font-mono focus:outline-none"
        />

        <button
          type="button" onClick={() => ir(datos?.ruta)} disabled={cargando}
          title={t('Volver a leer')}
          className="p-1.5 rounded text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
        >
          {cargando ? <Loader2 size={15} className="animate-spin" /> : <RotateCw size={15} />}
        </button>

        <button
          type="button" onClick={onCerrar} title={t('Cerrar')}
          className="p-1.5 rounded text-neutral-500 hover:text-red-400 transition-colors"
        >
          <X size={15} />
        </button>
      </div>

      {/* Las unidades siempre a la vista: es el único punto de partida
          seguro cuando no se sabe dónde está el archivo. */}
      {unidades.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-3 py-2 border-b border-neutral-800">
          {unidades.map(u => (
            <button
              key={u.ruta} type="button" onClick={() => ir(u.ruta)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded border text-xs font-bold transition-colors ${
                datos?.ruta === u.ruta
                  ? 'border-red-600 bg-red-600/15 text-white'
                  : 'border-neutral-800 text-neutral-400 hover:border-neutral-600 hover:text-white'}`}
            >
              <HardDrive size={12} /> {u.nombre}
            </button>
          ))}
        </div>
      )}

      {error && <p className="px-3 py-3 text-sm text-red-400">{error}</p>}

      {datos?.detalle && (
        <p className="px-3 py-2 text-[11px] text-amber-400/80 border-b border-neutral-800">
          {datos.detalle}
        </p>
      )}

      <div className="max-h-72 overflow-y-auto">
        {!cargando && !error && !datos?.ruta && (
          <p className="px-3 py-6 text-sm text-neutral-600 text-center">
            {t('Elige una unidad para empezar.')}
          </p>
        )}

        {carpetas.map(c => (
          <button
            key={c.ruta} type="button" onClick={() => ir(c.ruta)}
            className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-sm text-neutral-300 hover:bg-neutral-800 transition-colors"
          >
            <Folder size={15} className="text-neutral-600 flex-shrink-0" />
            <span className="truncate">{c.nombre}</span>
          </button>
        ))}

        {/* Los XML al final y marcados: son lo que se viene a buscar, y
            entre veinte carpetas se pierden si van mezclados. */}
        {archivos.map(a => (
          <button
            key={a.ruta} type="button" onClick={() => onElegir(a.ruta)}
            className="w-full flex items-center gap-2.5 px-3 py-2 text-left text-sm hover:bg-red-600/10 transition-colors group"
          >
            <FileCode2 size={15} className="text-red-500/70 flex-shrink-0" />
            <span className="text-white group-hover:text-red-300 truncate">{a.nombre}</span>
            <span className="ml-auto text-[11px] text-neutral-600 flex-shrink-0 tabular-nums">
              {kilobytes(a.tamano)} · {cuando(a.modificado)}
            </span>
          </button>
        ))}

        {!cargando && !error && datos?.ruta
          && carpetas.length === 0 && archivos.length === 0 && (
          <p className="px-3 py-6 text-sm text-neutral-600 text-center">
            {t('Aquí no hay carpetas ni archivos XML.')}
          </p>
        )}
      </div>
    </div>
  )
}
