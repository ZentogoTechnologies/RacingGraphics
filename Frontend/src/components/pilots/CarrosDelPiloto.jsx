import { useEffect, useState } from 'react'
import { Car, ExternalLink, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { t } from '../../i18n'
import { urlFotoVehiculo, vehiculosApi } from '../../api/registro'

/* ==========================================================================
   LOS CARROS DE UN PILOTO

   Van debajo de su ficha, agrupados por disciplina. Separados y no en una
   sola lista porque un piloto que corre en las dos tendría mezclados el
   carro de circuito y el de drag, que no se parecen en nada ni compiten
   entre sí.

   Se muestran, no se editan. Un carro puede llevar dos pilotos, y dejarlo
   editar desde la ficha de uno haría fácil pisar lo que puso el otro sin
   enterarse. Vehículos es el único sitio donde se cambia un carro; desde
   aquí solo se salta allá.
========================================================================== */

const NOMBRE_DISCIPLINA = { circuito: 'Circuito', drag: 'Drag' }

export default function CarrosDelPiloto({ pilotId, disciplinas }) {
  const navegar = useNavigate()

  const [porDisciplina, setPorDisciplina] = useState({})
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)

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

  if (!pilotId) return null

  const total = Object.values(porDisciplina).reduce((n, v) => n + v.length, 0)

  return (
    <div className="mt-6">
      <div className="flex items-center gap-2 mb-4">
        <Car size={17} className="text-neutral-500" />
        <h3 className="text-lg font-black italic text-white">{t('SUS VEHÍCULOS')}</h3>
        {!cargando && (
          <span className="text-neutral-600 text-sm">
            {total === 0 ? t('ninguno') : total}
          </span>
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

      {!cargando && !error && total > 0 && (
        <div className="space-y-5">
          {disciplinas.map(d => {
            const carros = porDisciplina[d] || []
            if (carros.length === 0) return null

            return (
              <div key={d}>
                {/* El rótulo de la disciplina solo cuando corre en las dos:
                    con una sola sobra y solo añade ruido. */}
                {disciplinas.length > 1 && (
                  <p className="text-[11px] font-bold uppercase tracking-widest text-neutral-500 mb-2">
                    {t(NOMBRE_DISCIPLINA[d] || d)}
                  </p>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                  {carros.map(v => (
                    <div
                      key={v.vehicle_id}
                      className="bg-[#141414] rounded-xl border border-neutral-800 overflow-hidden flex"
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
                            {[v.brand, v.model].filter(Boolean).join(' ') || '—'}
                          </span>
                        </div>

                        <p className="text-neutral-500 text-xs truncate">
                          {v.category_name || '—'}
                          {v.sub_category_name ? ` · ${v.sub_category_name}` : ''}
                        </p>

                        {/* Un carro puede llevar dos pilotos. Se dice quién
                            más lo maneja: es lo que explica por qué aparece
                            aquí un cambio que este piloto no hizo. */}
                        {v.pilots?.length > 1 && (
                          <p className="text-neutral-600 text-[11px] mt-1 truncate">
                            {t('Compartido con')}{' '}
                            {v.pilots
                              .filter(p => p.pilot_id !== pilotId)
                              .map(p => `${p.name || ''} ${p.last_name || ''}`.trim())
                              .join(', ')}
                          </p>
                        )}

                        <button
                          type="button" onClick={() => navegar('/vehiculos')}
                          className="flex items-center gap-1.5 mt-2 text-[11px] font-bold uppercase text-neutral-500 hover:text-red-400 transition-colors"
                        >
                          <ExternalLink size={12} /> {t('Editar en Vehículos')}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
