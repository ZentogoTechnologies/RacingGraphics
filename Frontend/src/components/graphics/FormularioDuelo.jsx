import { useEffect, useMemo, useState } from 'react'
import { Eye, EyeOff, Loader2, Trophy } from 'lucide-react'
import { t } from '../../i18n'
import SelectorPiloto, { CLASE_CAMPO } from './SelectorPiloto'

/* ==========================================================================
   UN DUELO DE DRAG

   Dos carros, uno por carril, y quién ganó. Es el único gráfico de la
   disciplina y sirve para los dos momentos: antes de que salgan, con los
   carriles puestos y sin ganador, y después con las cifras y el ganador
   marcado. No hace falta cambiar de gráfico, basta con actualizarlo.

   Los pilotos se eligen con el mismo buscador que la carta VS: filtro por
   categoría y búsqueda por nombre. Con 117 pilotos un desplegable suelto
   obliga a recorrer la lista entera.

   Las cifras se escriben a mano. Race America no está conectado todavía y
   hasta que lo esté esto tiene que funcionar solo: son dos carros y tres
   cifras cada uno, teclearlo es viable. Cuando el cronometraje exporte, se
   rellenan estos mismos campos y el arte no cambia.

   Dos modalidades:

     · DragWar es libre. No hay llaves ni premiación y se enfrenta
       cualquiera contra cualquiera, así que no se pregunta ni categoría
       ni ronda: la cabecera dice "DRAG WAR" y ya.

     · Competencia va por categorías de índice y por rondas, y las dos
       cosas se dicen en la cabecera porque son lo que sitúa la pasada.
========================================================================== */

const CARRIL_VACIO = { rt: '', et: '', speed: '' }

const RONDAS = [
  'Clasificación', 'Octavos de final', 'Cuartos de final',
  'Semifinal', 'Final',
]

export default function FormularioDuelo({
  item, modalidad, pilotos, categorias, carrera,
  alAire, ocupado, onMostrar, onOcultar,
}) {
  const esDragWar = modalidad === 'dragwar'

  const [izquierda, setIzquierda] = useState(null)
  const [derecha,   setDerecha]   = useState(null)

  const [cifras, setCifras] = useState([{ ...CARRIL_VACIO }, { ...CARRIL_VACIO }])
  const [unidad, setUnidad] = useState('km/h')

  // null = todavía no ha corrido. La carta sale igual, presentando el
  // enfrentamiento, y se marca el ganador al terminar con un UPDATE.
  const [gana, setGana] = useState(null)

  const [categoria, setCategoria] = useState(null)
  const [ronda,     setRonda]     = useState(RONDAS[0])

  // Solo las categorías de la jornada. La disciplina ya las acota a las de
  // drag; esto las acota además a las que de verdad están corriendo.
  const categoriasDelEvento = useMemo(() => {
    const nombres = carrera?.categorias || []
    if (nombres.length === 0) return categorias
    return categorias.filter(c => nombres.includes(c.nombre))
  }, [categorias, carrera])

  // Si la categoría elegida deja de estar en la jornada —se cambió de
  // evento— se suelta, o la cabecera saldría con una que no se corre.
  useEffect(() => {
    if (categoria !== null && !categoriasDelEvento.some(c => c.id === categoria)) {
      setCategoria(null)
    }
  }, [categoria, categoriasDelEvento])

  const cambiar = (i, campo, valor) =>
    setCifras(prev => prev.map((c, n) => (n === i ? { ...c, [campo]: valor } : c)))

  /* Con los dos tiempos escritos se propone el menor. Se propone y no se
     impone porque en drag no siempre gana el más rápido: una salida
     quemada descalifica aunque el tiempo sea mejor. */
  const sugerido = useMemo(() => {
    const a = parseFloat(cifras[0].et)
    const b = parseFloat(cifras[1].et)
    if (Number.isNaN(a) || Number.isNaN(b)) return null
    return a <= b ? 0 : 1
  }, [cifras])

  const ganador = gana !== null ? gana : sugerido

  const nombreCategoria = categoriasDelEvento.find(c => c.id === categoria)?.nombre || ''

  /* Lo que dice la banda de arriba. En DragWar es fijo: no hay categorías
     que valgan, cualquiera corre contra cualquiera. */
  const cabecera = esDragWar
    ? 'DRAG WAR'
    : [nombreCategoria, ronda].filter(Boolean).join(' · ')

  const datos = {
    header: cabecera,
    winner: ganador === 0 ? 'a' : ganador === 1 ? 'b' : '',
    // La velocidad lleva su unidad pegada: el arte la pinta tal cual y así
    // no hay que decidir en la plantilla si son km/h o mph.
    ...cifras.reduce((acc, c, i) => {
      const s = i === 0 ? 'a' : 'b'
      acc[`rt_${s}`]    = c.rt.trim()
      acc[`et_${s}`]    = c.et.trim()
      acc[`speed_${s}`] = c.speed.trim() ? `${c.speed.trim()} ${unidad}` : ''
      return acc
    }, {}),
  }

  const listo = izquierda !== null && derecha !== null

  const campoCifra = (i, campo, etiqueta, ayuda) => (
    <div>
      <label className="block text-neutral-500 text-[10px] mb-1 uppercase tracking-wider">
        {t(etiqueta)}
      </label>
      <input
        value={cifras[i][campo]} inputMode="decimal" placeholder={ayuda}
        onChange={e => cambiar(i, campo, e.target.value)}
        className={`${CLASE_CAMPO} tabular-nums`}
      />
    </div>
  )

  return (
    <div className="bg-[#141414] p-6 rounded-xl border border-red-600/30 mt-4">
      <p className="text-white font-bold text-sm uppercase tracking-wider mb-4">
        {t(item.nombre)}
      </p>

      {/* En competencia hay categoría y ronda; en DragWar no hay ni lo uno
          ni lo otro, así que la fila entera desaparece en vez de quedarse
          con campos que no aplican. */}
      {!esDragWar && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
          <div>
            <label className="block text-neutral-400 text-xs mb-2 uppercase">
              {t('Categoría')}
            </label>
            {categoriasDelEvento.length === 0 ? (
              <p className="text-sm text-neutral-600">
                {t('No hay categorías de drag en el evento seleccionado.')}
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {categoriasDelEvento.map(c => (
                  <button
                    key={c.id} type="button"
                    onClick={() => setCategoria(categoria === c.id ? null : c.id)}
                    className={`px-3 py-1.5 rounded-full border text-xs font-bold transition-colors ${
                      categoria === c.id
                        ? 'border-red-600 bg-red-600/15 text-white'
                        : 'border-neutral-800 bg-[#0a0a0a] text-neutral-400 hover:border-neutral-600 hover:text-neutral-200'
                    }`}
                  >
                    {c.nombre}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-neutral-400 text-xs mb-2 uppercase">{t('Ronda')}</label>
            <select value={ronda} onChange={e => setRonda(e.target.value)} className={CLASE_CAMPO}>
              {RONDAS.map(r => <option key={r} value={r}>{t(r)}</option>)}
            </select>
          </div>
        </div>
      )}

      {/* Lo que va a salir arriba del arte, escrito tal cual saldrá. Sin
          esto hay que sacar el gráfico para saber qué dice la banda. */}
      <p className="text-[11px] text-neutral-600 mb-5">
        {t('Cabecera')}: <span className="text-neutral-400">{cabecera || '—'}</span>
      </p>

      {/* Los dos carriles, uno al lado del otro y en el mismo orden en que
          salen en pantalla: el izquierdo a la izquierda. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {[0, 1].map(i => {
          const valor    = i === 0 ? izquierda : derecha
          const otro     = i === 0 ? derecha   : izquierda
          const fijar    = i === 0 ? setIzquierda : setDerecha
          const esGanador = ganador === i

          return (
            <div
              key={i}
              className={`rounded-lg border p-4 transition-colors ${
                esGanador ? 'border-green-600/60 bg-green-600/5' : 'border-neutral-800'
              }`}
            >
              <div className="flex items-center justify-between gap-3 mb-3">
                <p className="text-neutral-300 font-bold text-xs uppercase tracking-wider">
                  {i === 0 ? t('Carril izquierdo') : t('Carril derecho')}
                </p>
                <button
                  type="button"
                  onClick={() => setGana(ganador === i ? null : i)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-bold uppercase transition-colors flex-shrink-0 ${
                    esGanador
                      ? 'border-green-600 bg-green-600/15 text-green-400'
                      : 'border-neutral-700 text-neutral-500 hover:text-neutral-300'
                  }`}
                >
                  <Trophy size={11} /> {t('Ganó')}
                </button>
              </div>

              <SelectorPiloto
                etiqueta={i === 0 ? 'Piloto del carril izquierdo' : 'Piloto del carril derecho'}
                pilotos={pilotos} categorias={categorias}
                valor={valor} excluir={otro}
                onElegir={p => fijar(p.id)}
                onQuitar={() => fijar(null)}
              />

              <div className="grid grid-cols-3 gap-2 mt-4">
                {/* La reacción admite signo: negativa es salida quemada, y
                    el arte la pinta en rojo porque significa que pierde
                    aunque su tiempo sea el mejor. */}
                {campoCifra(i, 'rt',    'Reacción',  '0.045')}
                {campoCifra(i, 'et',    'Tiempo',    '12.348')}
                {campoCifra(i, 'speed', 'Velocidad', '180.4')}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center gap-4 mt-4">
        <div className="flex items-center gap-2">
          <span className="text-neutral-500 text-[11px] uppercase tracking-wider">
            {t('Velocidad en')}
          </span>
          {['km/h', 'mph'].map(u => (
            <button
              key={u} type="button" onClick={() => setUnidad(u)}
              className={`px-2.5 py-1 rounded border text-[11px] font-bold transition-colors ${
                unidad === u
                  ? 'border-red-600 bg-red-600/15 text-white'
                  : 'border-neutral-800 text-neutral-500 hover:text-neutral-300'
              }`}
            >
              {u}
            </button>
          ))}
        </div>

        {sugerido !== null && gana === null && (
          <p className="text-[11px] text-neutral-600">
            {t('Gana el del tiempo menor. Márcalo a mano si hubo salida quemada o descalificación.')}
          </p>
        )}
        {ganador === null && listo && (
          <p className="text-[11px] text-neutral-600">
            {t('Sin ganador marcado sale el enfrentamiento; márcalo y actualiza para dar el resultado.')}
          </p>
        )}
      </div>

      <div className="flex justify-end gap-3 mt-6">
        <button
          type="button" onClick={onOcultar} disabled={!alAire || ocupado}
          className="flex items-center gap-2 px-5 py-2 rounded border border-neutral-700 text-neutral-300 hover:border-red-600 hover:text-red-400 transition-all font-bold text-sm disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <EyeOff size={16} />
          {t('OCULTAR')}
        </button>
        <button
          type="button"
          onClick={() => onMostrar({ pilotId: izquierda, pilotId2: derecha, data: datos })}
          disabled={!listo || ocupado}
          className="flex items-center gap-2 bg-white text-black font-bold py-2 px-6 rounded hover:bg-neutral-200 transition-colors text-sm disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {ocupado ? <Loader2 size={16} className="animate-spin" /> : <Eye size={16} />}
          {alAire ? t('ACTUALIZAR DATOS') : t('MOSTRAR GRÁFICO')}
        </button>
      </div>
    </div>
  )
}
