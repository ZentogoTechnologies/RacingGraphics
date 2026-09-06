import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search, X } from 'lucide-react'
import { t, idiomaDeAhora } from '../../i18n'
import { PAISES, paisDe, urlBandera } from '../../data/paises'

/* ==========================================================================
   SELECTOR DE PAÍS

   Antes la nacionalidad se escribía a mano y en la base convivían
   "Panama", "Panamá" y "PANAMA" como si fueran tres países distintos.
   Ahora se elige de la lista y se guarda el código ISO, que además es el
   nombre del archivo de la bandera.

   No es un <select> normal: son 255 países y bajar por la lista con el
   ratón hasta Trinidad y Tobago es peor que teclearlo. Se abre, se
   escriben tres letras y se elige.

   Busca por el nombre en español y en inglés y por el código, sin tildes:
   quien escribe "panama" encuentra "Panamá".
========================================================================== */

const sinTildes = s => (s || '')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()

// El índice de búsqueda se arma una vez para todo el panel: es la misma
// tabla para todos los formularios y no cambia nunca.
const INDICE = PAISES.map(p => ({
  ...p,
  busca: `${sinTildes(p.nombre)} ${sinTildes(p.en)} ${p.codigo}`,
}))

export default function SelectorPais({ valor, onChange, id }) {
  const [abierto, setAbierto] = useState(false)
  const [busca,   setBusca]   = useState('')
  const caja  = useRef(null)
  const campo = useRef(null)

  const idioma = idiomaDeAhora()
  const elegido = paisDe(valor)

  // Cerrar al pulsar fuera. Sin esto la lista se queda abierta encima de
  // los campos de abajo y tapa el botón de guardar.
  useEffect(() => {
    if (!abierto) return
    const fuera = e => { if (caja.current && !caja.current.contains(e.target)) setAbierto(false) }
    document.addEventListener('mousedown', fuera)
    return () => document.removeEventListener('mousedown', fuera)
  }, [abierto])

  useEffect(() => { if (abierto) campo.current?.focus() }, [abierto])

  const resultados = useMemo(() => {
    const q = sinTildes(busca)
    if (!q) return INDICE
    // Los que empiezan por lo escrito van primero: quien teclea "pa"
    // busca Panamá o Pakistán, no Japón.
    const empiezan = [], contienen = []
    for (const p of INDICE) {
      const donde = p.busca.indexOf(q)
      if (donde === -1) continue
      ;(donde === 0 || p.busca[donde - 1] === ' ' ? empiezan : contienen).push(p)
    }
    return [...empiezan, ...contienen]
  }, [busca])

  const elegir = codigo => {
    onChange(codigo)
    setAbierto(false)
    setBusca('')
  }

  const nombreDe = p => (idioma === 'en' ? p.en : p.nombre)

  return (
    <div className="relative" ref={caja}>
      <button
        type="button" id={id}
        onClick={() => setAbierto(a => !a)}
        className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 flex items-center gap-2 text-left hover:border-neutral-700 focus:border-red-600 focus:outline-none transition-colors"
      >
        {elegido
          ? <>
              <img src={urlBandera(elegido.codigo)} alt="" className="w-6 h-4 object-cover rounded-[2px] border border-white/20 flex-shrink-0" />
              <span className="text-white truncate">{nombreDe(elegido)}</span>
            </>
          : <span className="text-neutral-600 truncate">{t('Sin nacionalidad')}</span>}

        {/* Quitar el país sin tener que abrir la lista para nada. */}
        {elegido && (
          <span
            role="button" tabIndex={-1}
            onClick={e => { e.stopPropagation(); elegir('') }}
            className="ml-auto text-neutral-600 hover:text-red-400 transition-colors"
            title={t('Quitar')}
          >
            <X size={14} />
          </span>
        )}
        <ChevronDown size={15} className={`text-neutral-600 flex-shrink-0 ${elegido ? '' : 'ml-auto'}`} />
      </button>

      {abierto && (
        <div className="absolute z-30 mt-1 w-full bg-[#0f0f0f] border border-neutral-700 rounded-lg shadow-2xl overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-2 border-b border-neutral-800">
            <Search size={14} className="text-neutral-600 flex-shrink-0" />
            <input
              ref={campo} value={busca} onChange={e => setBusca(e.target.value)}
              placeholder={t('Buscar país...')}
              className="w-full bg-transparent text-white text-sm focus:outline-none"
              onKeyDown={e => {
                if (e.key === 'Escape') setAbierto(false)
                // Enter con un solo resultado lo elige: teclear "urug" y
                // pulsar enter es lo que hace cualquiera.
                if (e.key === 'Enter') { e.preventDefault(); if (resultados.length) elegir(resultados[0].codigo) }
              }}
            />
          </div>

          <div className="max-h-60 overflow-y-auto">
            {resultados.length === 0 && (
              <p className="px-3 py-4 text-neutral-600 text-sm text-center">{t('Ningún país coincide')}</p>
            )}
            {resultados.map(p => (
              <button
                key={p.codigo} type="button" onClick={() => elegir(p.codigo)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors ${
                  p.codigo === valor
                    ? 'bg-red-600/15 text-white'
                    : 'text-neutral-300 hover:bg-neutral-800'}`}
              >
                <img src={urlBandera(p.codigo)} alt="" loading="lazy"
                     className="w-6 h-4 object-cover rounded-[2px] border border-white/20 flex-shrink-0" />
                <span className="truncate">{nombreDe(p)}</span>
                <span className="ml-auto text-[10px] uppercase text-neutral-600">{p.codigo}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* La bandera sola, para las tablas. Sin país no pinta nada: un hueco
   vacío se entiende mejor que un icono de imagen rota. */
export function Bandera({ codigo, tamano = 'w-7 h-5' }) {
  const p = paisDe(codigo)
  if (!p) return null
  return (
    <img
      src={urlBandera(p.codigo)} alt={p.nombre} title={p.nombre} loading="lazy"
      className={`${tamano} object-cover rounded-[2px] border border-white/20`}
    />
  )
}
