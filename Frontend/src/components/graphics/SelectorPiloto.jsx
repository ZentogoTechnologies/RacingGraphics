import { useState } from 'react'
import { Search } from 'lucide-react'
import { t } from '../../i18n'

/* ==========================================================================
   ELEGIR UN PILOTO PARA UN GRÁFICO

   Vive aparte de la página de Gráficos porque lo usan tres cosas: la carta
   del piloto, la carta VS y el duelo de drag. Tenerlo dentro de la página
   obligaba a que el formulario del duelo viviera también ahí, y esa página
   ya es demasiado larga.
========================================================================== */

// Clase de los campos de texto del panel. Vive fuera del componente porque
// la usan tanto el formulario como el selector de pilotos.
export const CLASE_CAMPO =
  'w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white'

// ─── Selector de piloto ───────────────────────────────────────
// Filtro por categoría, buscador y lista. Se usa tal cual en la carta del
// piloto y dos veces en la carta VS: con 117 pilotos, un desplegable suelto
// obliga a recorrer la lista entera, y acotar por categoría deja a mano los
// pocos que de verdad corren esa tanda.
export default function SelectorPiloto({
  etiqueta, pilotos, categorias, valor, onElegir, onQuitar, excluir = null,
}) {
  const [busqueda,  setBusqueda]  = useState('')
  const [categoria, setCategoria] = useState(null)   // null = todas

  // El que ya está en el otro lado no se ofrece: enfrentar a alguien
  // consigo mismo no dice nada.
  const disponibles = excluir === null
    ? pilotos
    : pilotos.filter(p => p.id !== excluir)

  // Solo las categorías que tienen pilotos: no sirve un filtro que deja la
  // lista vacía.
  const conPilotos = categorias.filter(c =>
    disponibles.some(p => p.categorias.includes(c.id))
  )

  const porCategoria = categoria === null
    ? disponibles
    : disponibles.filter(p => p.categorias.includes(categoria))

  const filtrados = porCategoria.filter(p =>
    `${p.nombre} ${p.apellido}`.toLowerCase().includes(busqueda.toLowerCase())
  )

  const elegido = pilotos.find(p => p.id === valor) || null

  return (
    <div>
      <label className="block text-neutral-400 text-xs mb-1 uppercase">
        {t(etiqueta)}
      </label>

      {elegido ? (
        <div className="flex items-center justify-between gap-3 bg-[#0a0a0a] border border-red-600/40 rounded p-2">
          <span className="text-white font-semibold text-sm truncate">
            {elegido.nombre} <span className="uppercase">{elegido.apellido}</span>
          </span>
          <button
            type="button"
            onClick={() => { onQuitar(); setBusqueda('') }}
            className="text-neutral-400 hover:text-white text-xs font-bold flex-shrink-0"
          >
            {t('CAMBIAR')}
          </button>
        </div>
      ) : (
        <>
          {/* Primero la categoría: acota la lista antes de buscar */}
          {conPilotos.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {[{ id: null, nombre: 'Todas' }, ...conPilotos].map(c => {
                const activa = categoria === c.id
                const cuantos = c.id === null
                  ? disponibles.length
                  : disponibles.filter(p => p.categorias.includes(c.id)).length
                return (
                  <button
                    key={c.id ?? 'todas'} type="button"
                    onClick={() => { setCategoria(c.id); setBusqueda('') }}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-bold transition-colors ${
                      activa
                        ? 'border-red-600 bg-red-600/15 text-white'
                        : 'border-neutral-800 bg-[#0a0a0a] text-neutral-400 hover:border-neutral-600 hover:text-neutral-200'
                    }`}
                  >
                    {c.nombre}
                    <span className={activa ? 'text-red-400' : 'text-neutral-600'}>
                      {cuantos}
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" size={16} />
            <input
              type="text" value={busqueda} placeholder={t('Buscar piloto...')}
              onChange={e => setBusqueda(e.target.value)}
              className={`${CLASE_CAMPO} pl-9`}
            />
          </div>

          <div className="mt-2 max-h-44 overflow-y-auto rounded border border-neutral-800 divide-y divide-neutral-800/60">
            {disponibles.length === 0 ? (
              <p className="p-3 text-neutral-500 text-sm">
                {t('No hay pilotos registrados todavía.')}
              </p>
            ) : filtrados.length === 0 ? (
              <p className="p-3 text-neutral-500 text-sm">{t('Sin coincidencias.')}</p>
            ) : (
              filtrados.map(p => (
                <button
                  key={p.id} type="button"
                  onClick={() => onElegir(p)}
                  className="w-full text-left px-3 py-2 text-sm text-neutral-300 hover:bg-neutral-800 hover:text-white transition-colors"
                >
                  {p.nombre} <span className="uppercase">{p.apellido}</span>
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}
