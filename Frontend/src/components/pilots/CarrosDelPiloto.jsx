import { useEffect, useMemo, useState } from 'react'
import { Car, ExternalLink, LayoutGrid, List, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { urlFotoVehiculo, vehiculosApi } from '../../api/registro'
import { useDisciplina } from '../../context/DisciplinaContext'

/* ==========================================================================
   LOS CARROS DE UN PILOTO

   Van debajo de su ficha, agrupados por disciplina. Separados y no en una
   sola lista porque un piloto que corre en las dos tendría mezclados el
   carro de circuito y el de drag, que no se parecen en nada ni compiten
   entre sí.

   Dos vistas: tarjetas, que enseñan la foto y sirven para reconocer el
   carro de un vistazo, y tabla, que cabe más y compara mejor cuando son
   varios. La elección se recuerda porque es preferencia de quien trabaja,
   no algo propio de este piloto.

   No se editan aquí: un carro puede llevar dos pilotos, y editarlo desde
   la ficha de uno haría fácil pisar lo que puso el otro sin enterarse.
   Vehículos sigue siendo el único sitio donde se cambia un carro, pero se
   llega de un clic: la tarjeta o la fila abre ese carro ya cargado.
========================================================================== */

const NOMBRE_DISCIPLINA = { circuito: 'Circuito', drag: 'Drag' }
const CLAVE_VISTA = 'rcs.carrosPiloto.vista'

function leerVista() {
  try {
    return localStorage.getItem(CLAVE_VISTA) === 'tabla' ? 'tabla' : 'tarjetas'
  } catch {
    return 'tarjetas'
  }
}

const nombresDe = (vehiculo, pilotId) => (vehiculo.pilots || [])
  .filter(p => p.pilot_id !== pilotId)
  .map(p => `${p.name || ''} ${p.last_name || ''}`.trim())
  .join(', ')

const marcaYModelo = v => [v.brand, v.model].filter(Boolean).join(' ') || '—'

const categoriaDe = v =>
  (v.category_name || '—') + (v.sub_category_name ? ` · ${v.sub_category_name}` : '')

export default function CarrosDelPiloto({ pilotId, disciplinas }) {
  const navegar = useNavigate()
  const { disciplina: disciplinaActiva, elegir } = useDisciplina()

  const [porDisciplina, setPorDisciplina] = useState({})
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

  const [vista,  setVista]  = useState(leerVista)
  const [filtro, setFiltro] = useState('')   // '' = todas

  useEffect(() => {
    try { localStorage.setItem(CLAVE_VISTA, vista) } catch { /* bloqueado */ }
  }, [vista])

  useEffect(() => {
    if (!pilotId || !disciplinas?.length) { setCargando(false); return }

    let vigente = true
    setCargando(true)
    setError(null)

    /* Una consulta por disciplina en vez de una sola y agrupar aquí: el
       backend ya sabe qué categorías son de cada una, y el carro no lleva
       la disciplina encima —la hereda de su categoría—, así que agruparlo
       en el navegador obligaría a traerse el catálogo entero. */
    Promise.all(
      disciplinas.map(d =>
        vehiculosApi.listar({ pilot_id: pilotId, discipline: d, limit: 50 })
          .then(p => [d, p.items]),
      ),
    )
      .then(pares => { if (vigente) setPorDisciplina(Object.fromEntries(pares)) })
      .catch(err => { if (vigente) setError(err.message) })
      .finally(() => { if (vigente) setCargando(false) })

    return () => { vigente = false }
  }, [pilotId, disciplinas])

  // Solo las que tienen algún carro: dejar filtrar por una disciplina vacía
  // deja la lista en blanco sin explicar por qué.
  const conCarros = useMemo(
    () => (disciplinas || []).filter(d => (porDisciplina[d] || []).length > 0),
    [disciplinas, porDisciplina],
  )

  // Si el filtro apunta a una disciplina que se quedó sin carros, se cae
  // solo en vez de dejar la sección vacía.
  useEffect(() => {
    if (filtro && !conCarros.includes(filtro)) setFiltro('')
  }, [filtro, conCarros])

  const visibles = filtro ? [filtro] : conCarros
  const total    = conCarros.reduce((n, d) => n + porDisciplina[d].length, 0)

  /* Abre el carro en Vehículos, ya cargado. La disciplina se cambia antes
     de saltar si hace falta: Vehículos filtra por la activa, y con la otra
     puesta el selector de categoría del formulario saldría vacío. */
  const abrirCarro = (vehiculo, disciplinaDelCarro) => {
    if (disciplinaDelCarro && disciplinaDelCarro !== disciplinaActiva) {
      elegir(disciplinaDelCarro)
    }
    navegar('/vehiculos', { state: { editarVehiculo: vehiculo.vehicle_id } })
  }

  if (!pilotId) return null

  const botonVista = (valor, Icono, titulo) => (
    <button
      type="button" onClick={() => setVista(valor)} title={titulo}
      className={`p-2 rounded-lg transition-colors ${
        vista === valor
          ? 'bg-red-600 text-white'
          : 'text-neutral-500 hover:text-white hover:bg-neutral-800'}`}
    >
      <Icono size={15} />
    </button>
  )

  const botonFiltro = (valor, etiqueta) => (
    <button
      key={valor || 'todas'} type="button" onClick={() => setFiltro(valor)}
      className={`px-3 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wide transition-colors ${
        filtro === valor
          ? 'bg-neutral-700 text-white'
          : 'text-neutral-500 hover:text-white'}`}
    >
      {etiqueta}
    </button>
  )

  return (
    <div className="mt-6">
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <Car size={17} className="text-neutral-500" />
        <h3 className="text-lg font-black italic text-white">{t('SUS VEHÍCULOS')}</h3>
        {!cargando && (
          <span className="text-neutral-600 text-sm">
            {total === 0 ? t('ninguno') : total}
          </span>
        )}

        {!cargando && total > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            {/* El filtro solo cuando de verdad hay que elegir: con carros
                en una sola disciplina no filtraría nada. */}
            {conCarros.length > 1 && (
              <div className="flex items-center bg-[#141414] rounded-lg border border-neutral-800 p-0.5">
                {botonFiltro('', t('Todas'))}
                {conCarros.map(d => botonFiltro(d, t(NOMBRE_DISCIPLINA[d] || d)))}
              </div>
            )}

            <div className="flex items-center bg-[#141414] rounded-lg border border-neutral-800 p-0.5">
              {botonVista('tarjetas', LayoutGrid, t('Tarjetas'))}
              {botonVista('tabla',    List,       t('Tabla'))}
            </div>
          </div>
        )}
      </div>

      {cargando && (
        <div className="py-8 text-center">
          <Loader2 className="w-5 h-5 animate-spin mx-auto text-red-600" />
        </div>
      )}

      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      {!cargando && !error && total === 0 && (
        <div className="bg-[#141414] rounded-xl border border-neutral-800 p-6">
          <p className="text-neutral-500 text-sm mb-4">
            Este piloto no tiene ningún vehículo asignado. Los carros se dan de
            alta en Vehículos y ahí se les asigna quién los maneja.
          </p>
          <button
            type="button" onClick={() => navegar('/vehiculos')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-neutral-700 text-neutral-300 hover:border-red-600 hover:text-red-400 transition-colors font-bold text-xs"
          >
            <ExternalLink size={14} /> {t('IR A VEHÍCULOS')}
          </button>
        </div>
      )}

      {!cargando && !error && total > 0 && vista === 'tarjetas' && (
        <div className="space-y-5">
          {visibles.map(d => (
            <div key={d}>
              {/* El rótulo de la disciplina solo cuando se ven las dos: con
                  una sola sobra y solo añade ruido. */}
              {visibles.length > 1 && (
                <p className="text-[11px] font-bold uppercase tracking-widest text-neutral-500 mb-2">
                  {t(NOMBRE_DISCIPLINA[d] || d)}
                </p>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {porDisciplina[d].map(v => (
                  <button
                    key={v.vehicle_id}
                    type="button" onClick={() => abrirCarro(v, d)}
                    title={t('Editar en Vehículos')}
                    className="bg-[#141414] rounded-xl border border-neutral-800 overflow-hidden flex text-left hover:border-red-600/60 transition-colors group"
                  >
                    <div className="w-28 flex-shrink-0 bg-[#0a0a0a] flex items-center justify-center">
                      {v.photo_urls?.[0]
                        ? <img src={urlFotoVehiculo(v.photo_urls[0])} alt=""
                               className="w-full h-full object-cover" />
                        : <Car size={22} className="text-neutral-700" />}
                    </div>

                    <div className="flex-1 min-w-0 p-3">
                      <div className="flex items-baseline gap-2 mb-0.5">
                        <span className="text-red-500 font-black text-lg">
                          #{v.display_number || v.number}
                        </span>
                        <span className="text-white font-bold text-sm truncate">
                          {marcaYModelo(v)}
                        </span>
                      </div>

                      <p className="text-neutral-500 text-xs truncate">{categoriaDe(v)}</p>

                      {/* Un carro puede llevar dos pilotos. Se dice quién
                          más lo maneja: es lo que explica por qué aparece
                          aquí un cambio que este piloto no hizo. */}
                      {v.pilots?.length > 1 && (
                        <p className="text-neutral-600 text-[11px] mt-1 truncate">
                          {t('Compartido con')} {nombresDe(v, pilotId)}
                        </p>
                      )}

                      <span className="flex items-center gap-1.5 mt-2 text-[11px] font-bold uppercase text-neutral-500 group-hover:text-red-400 transition-colors">
                        <ExternalLink size={12} /> {t('Editar en Vehículos')}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!cargando && !error && total > 0 && vista === 'tabla' && (
        /* Con desplazamiento propio: en un teléfono la tabla no cabe y sin
           esto se estira la página entera. */
        <div className="bg-[#141414] rounded-xl border border-neutral-800 overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-widest text-neutral-500 border-b border-neutral-800">
                <th className="text-left font-bold px-4 py-3 w-16">#</th>
                <th className="text-left font-bold px-4 py-3">{t('Vehículo')}</th>
                <th className="text-left font-bold px-4 py-3">{t('Categoría')}</th>
                {visibles.length > 1 && (
                  <th className="text-left font-bold px-4 py-3">{t('Disciplina')}</th>
                )}
                <th className="text-left font-bold px-4 py-3">{t('Compartido con')}</th>
                <th className="px-4 py-3 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {visibles.flatMap(d => porDisciplina[d].map(v => (
                <tr
                  key={`${d}-${v.vehicle_id}`}
                  onClick={() => abrirCarro(v, d)}
                  title={t('Editar en Vehículos')}
                  className="border-b border-neutral-800/60 last:border-0 hover:bg-neutral-800/40 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-red-500 font-black">
                    #{v.display_number || v.number}
                  </td>
                  <td className="px-4 py-3 text-white font-bold whitespace-nowrap">
                    {marcaYModelo(v)}
                  </td>
                  <td className="px-4 py-3 text-neutral-400 whitespace-nowrap">
                    {categoriaDe(v)}
                  </td>
                  {visibles.length > 1 && (
                    <td className="px-4 py-3 text-neutral-400 whitespace-nowrap">
                      {t(NOMBRE_DISCIPLINA[d] || d)}
                    </td>
                  )}
                  <td className="px-4 py-3 text-neutral-500 whitespace-nowrap">
                    {v.pilots?.length > 1 ? nombresDe(v, pilotId) : '—'}
                  </td>
                  <td className="px-4 py-3 text-neutral-600">
                    <ExternalLink size={14} />
                  </td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
