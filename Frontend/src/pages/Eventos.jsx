import { t } from '../i18n'
import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import {
  Pencil, Trash2, ChevronUp, ChevronDown, ChevronsUpDown, Loader2,
  CalendarDays, Car, ListOrdered, ArrowLeft, ArrowRight, Upload, X, ImageIcon,
}  from 'lucide-react'
import ModuleHeader from '../components/shared/ModuleHeader'
import Pagination from '../components/shared/Pagination'
import ConfirmDialog from '../components/shared/ConfirmDialog'
import SesionesEvento from '../components/events/SesionesEvento'
import SeleccionVehiculos from '../components/events/SeleccionVehiculos'
import {
  borrarImagenEvento, categoriasApi, eventosApi, subirImagenEvento,
  urlImagenEvento, vehiculosApi,
} from '../api/registro'
import { useListado } from '../hooks/useListado'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { useDisciplina } from '../context/DisciplinaContext'

const EMPTY_EVENT = {
  name: '', location: '', start_date: '', end_date: '',
  category_ids: [], inscritos: [],
}

function SortIcon({ columnKey, sortField, sortDirection, onSort }) {
  const isActive = sortField === columnKey
  return (
    <button onClick={() => onSort(columnKey)} className="inline-flex items-center hover:text-white transition-colors ml-1">
      {isActive
        ? sortDirection === 'asc' ? <ChevronUp size={13} className="text-red-400"/> : <ChevronDown size={13} className="text-red-400"/>
        : <ChevronsUpDown size={13} className="text-neutral-600"/>}
    </button>
  )
}

// Los días se cuentan con ambos extremos incluidos: un evento de sábado a
// domingo son dos días, no uno. El servidor calcula lo mismo; esto es solo
// para que el formulario lo muestre antes de guardar.
function contarDias(inicio, fin) {
  if (!inicio || !fin) return 0
  const a = new Date(`${inicio}T00:00:00`)
  const b = new Date(`${fin}T00:00:00`)
  if (b < a) return 0
  return Math.round((b - a) / 86400000) + 1
}

export default function EventosModule() {
  const toast = useToast()
  const { puedeEscribir } = useAuth()
  const { disciplina } = useDisciplina()

  const filtros = useMemo(() => ({ discipline: disciplina }), [disciplina])
  const lista = useListado(eventosApi, { ordenInicial: 'start_date', filtros })

  const [categorias,   setCategorias]   = useState([])
  const [vehiculos,    setVehiculos]    = useState([])
  const [isFormOpen,   setIsFormOpen]   = useState(false)
  const [currentEditId, setCurrentEditId] = useState(null)
  const [eventForm,    setEventForm]    = useState(EMPTY_EVENT)
  const [guardando,    setGuardando]    = useState(false)
  const [porBorrar,    setPorBorrar]    = useState(null)
  const [expandido,    setExpandido]    = useState(null)   // evento con el programa abierto
  const [paso,         setPaso]         = useState(1)      // 1 datos · 2 vehículos

  // Catálogos de la disciplina activa. Los vehículos traen sus pilotos ya
  // resueltos, que es lo que hace falta para elegir quién corre.
  useEffect(() => {
    Promise.all([
      categoriasApi.listar({ sort_by: 'category_name', discipline: disciplina }),
      vehiculosApi.listar({ sort_by: 'number', discipline: disciplina }),
    ])
      .then(([c, v]) => { setCategorias(c.items); setVehiculos(v.items) })
      .catch(err => toast.error('No se pudieron cargar los catálogos', err.message))
  }, [disciplina])   // eslint-disable-line react-hooks/exhaustive-deps

  const totalDias = contarDias(eventForm.start_date, eventForm.end_date)

  // Objetos completos de las categorías elegidas: el paso 2 necesita sus
  // subcategorías para agrupar. Se respeta el orden en que se marcaron.
  const categoriasElegidas = useMemo(
    () => eventForm.category_ids
      .map(id => categorias.find(c => c.category_id === id))
      .filter(Boolean),
    [eventForm.category_ids, categorias],
  )

  // La imagen no viaja en el JSON del evento sino como archivo, y en un
  // alta todavía no hay id al que asociarla: se guarda aquí y se sube en
  // cuanto el evento existe.
  const [imagen,       setImagen]       = useState(null)   // File sin subir
  const [imagenActual, setImagenActual] = useState(null)   // ruta ya guardada
  const inputImagen = useRef(null)

  // La previa de lo elegido se revoca al cambiar, para no ir dejando
  // URLs de objeto vivas en memoria.
  const [previaImagen, setPreviaImagen] = useState(null)
  useEffect(() => {
    if (!imagen) { setPreviaImagen(null); return }
    const url = URL.createObjectURL(imagen)
    setPreviaImagen(url)
    return () => URL.revokeObjectURL(url)
  }, [imagen])

  const vistaImagen = previaImagen || urlImagenEvento(imagenActual)

  const limpiarImagen = () => {
    setImagen(null); setImagenActual(null)
    if (inputImagen.current) inputImagen.current.value = ''
  }

  const quitarImagen = async () => {
    if (!currentEditId) { limpiarImagen(); return }
    try {
      await borrarImagenEvento(currentEditId)
      limpiarImagen()
      lista.recargar()
      toast.exito('Imagen quitada', 'El gráfico saldrá solo con el nombre')
    } catch (err) {
      toast.error('No se pudo quitar la imagen', err.message)
    }
  }

  const openAddForm = () => { setEventForm(EMPTY_EVENT); setCurrentEditId(null); setPaso(1); limpiarImagen(); setIsFormOpen(true) }
  const closeForm = () => { setIsFormOpen(false); setCurrentEditId(null); setEventForm(EMPTY_EVENT); setPaso(1); limpiarImagen() }
  const handleFormToggle = () => isFormOpen ? closeForm() : openAddForm()

  const openEditForm = (ev) => {
    setEventForm({
      name: ev.name,
      location: ev.location || '',
      start_date: ev.start_date,
      end_date: ev.end_date,
      category_ids: ev.category_ids,
      inscritos: ev.inscritos.map(i => ({ vehicle_id: i.vehicle_id, pilot_ids: i.pilot_ids })),
    })
    setCurrentEditId(ev.event_id)
    setPaso(1)

    setImagen(null)
    setImagenActual(ev.image_url || null)
    if (inputImagen.current) inputImagen.current.value = ''

    setIsFormOpen(true)
  }

  const alternarCategoria = (id) => {
    setEventForm(f => {
      const quitando = f.category_ids.includes(id)
      return {
        ...f,
        category_ids: quitando ? f.category_ids.filter(c => c !== id) : [...f.category_ids, id],
        // Al quitar una categoría se sacan sus carros: el backend rechaza
        // guardar inscritos de categorías que ya no corren.
        inscritos: quitando
          ? f.inscritos.filter(i => {
              const v = vehiculos.find(x => x.vehicle_id === i.vehicle_id)
              return v && v.category_id !== id
            })
          : f.inscritos,
      }
    })
  }

  const handleSave = async (e) => {
    e.preventDefault()

    // Guardia real, no cosmética. El paso 1 no puede guardar nada: si un
    // submit se cuela desde ahí, el evento se crearía sin inscritos y el
    // formulario se cerraría, que es justo lo que pasaba.
    if (paso !== 2) {
      setPaso(2)
      return
    }

    setGuardando(true)

    const cuerpo = {
      name: eventForm.name,
      location: eventForm.location || null,
      start_date: eventForm.start_date,
      end_date: eventForm.end_date,
      category_ids: eventForm.category_ids,
      inscritos: eventForm.inscritos,
    }

    try {
      let id = currentEditId

      if (currentEditId) {
        await eventosApi.actualizar(currentEditId, cuerpo)
        toast.exito('Evento actualizado', eventForm.name)
      } else {
        // Sin event_id: lo asigna el servidor, igual que en categorías.
        const creado = await eventosApi.crear({ ...cuerpo, discipline: disciplina })
        id = creado.event_id
        toast.exito('Evento creado', `${eventForm.name} · ${totalDias} día(s)`)
      }

      // Después de guardar porque en un alta el id no existe hasta ahora.
      if (imagen && id) {
        try {
          await subirImagenEvento(id, imagen)
        } catch (err) {
          toast.error('El evento se guardó, pero la imagen no', err.message)
        }
      }

      /* Se sigue en la ficha después de guardar, no se vuelve al listado.
         Al dar de alta hay cosas que solo se pueden hacer con el registro ya
         creado —subir su imagen, recortarle el fondo— y devolver a la lista
         obligaba a buscarlo otra vez para entrar a editarlo.

         El id se fija aquí: sin esto la ficha seguiría en modo alta y volver
         a guardar crearía un registro repetido. */
      setCurrentEditId(id)
      lista.recargar()
    } catch (err) {
      toast.error(currentEditId ? 'No se pudo actualizar' : 'No se pudo crear', err.message)
    } finally {
      setGuardando(false)
    }
  }

  const confirmarBorrado = async () => {
    const ev = porBorrar
    setPorBorrar(null)
    try {
      await eventosApi.eliminar(ev.event_id)
      toast.exito('Evento eliminado', ev.name)
      if (expandido?.event_id === ev.event_id) setExpandido(null)
      lista.recargar()
    } catch (err) {
      toast.error('No se pudo eliminar', err.message)
    }
  }

  // El programa devuelve el evento entero ya recalculado, así que se
  // refresca el panel abierto y la tabla con la misma respuesta.
  const alCambiarSesiones = (actualizado) => {
    setExpandido(actualizado)
    lista.recargar()
  }

  // Qué le falta al paso 1 para poder avanzar. Se calcula aquí y se
  // muestra al lado del botón: un botón apagado sin explicación deja al
  // operador pulsándolo sin entender por qué no pasa nada.
  const faltantes = []
  if (!eventForm.name.trim())            faltantes.push('el nombre')
  if (!eventForm.start_date)             faltantes.push('la fecha de inicio')
  if (!eventForm.end_date)               faltantes.push('la fecha final')
  if (eventForm.category_ids.length === 0) faltantes.push('al menos una categoría')

  const columnas = puedeEscribir ? 6 : 5

  return (
    <div className="w-full animate-fade-in">
      {/* El listado y la ficha no conviven: se ve uno u otro. Con los dos a
          la vez la ficha quedaba apretada arriba y en un teléfono ni se
          alcanzaba a ver entera. */}
      {!isFormOpen && (
      <ModuleHeader
        entityName="eventos"
        searchText={lista.texto}
        onSearchChange={lista.setTexto}
        isFormOpen={isFormOpen}
        onFormToggle={handleFormToggle}
        addButtonLabel="NUEVO EVENTO"
        puedeCrear={puedeEscribir}
        exportData={() => eventosApi.listar({ ...filtros, search: lista.texto || undefined, sort_by: lista.sortBy, sort_dir: lista.sortDir }).then(p => p.items)}
        onExportError={m => toast.error('No se pudo exportar', m)}
        exportFileName="eventos"
        exportColumnMap={{ name: 'Evento', start_date: 'Inicio', end_date: 'Fin', location: 'Sede' }}
      />
      )}

      {isFormOpen && (
      <>
        {/* Cabecera de la ficha. Sustituye a la del listado y da la vuelta
            atrás, que es lo único que se puede hacer desde aquí. */}
        <div className="flex items-center gap-3 mb-5">
          <button
            type="button" onClick={closeForm}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-800 text-neutral-400 hover:border-neutral-600 hover:text-white transition-colors font-bold text-xs"
          >
            <ArrowLeft size={15}/> {t('VOLVER')}
          </button>
          <h3 className="text-lg font-black italic text-white">
            {currentEditId ? t('Editar evento') : t('Nuevo evento')}
          </h3>
        </div>

        <form onSubmit={handleSave} className="bg-[#141414] p-6 rounded-xl border border-red-600/30 mb-6">
          {/* Dos pasos porque son dos decisiones distintas: primero qué
              categorías corren, y solo entonces tiene sentido preguntar
              qué carros de cada una. */}
          <div className="flex items-center gap-3 mb-5 pb-4 border-b border-neutral-800">
            {[
              { n: 1, titulo: 'Datos y categorías' },
              { n: 2, titulo: 'Vehículos que corren' },
            ].map(({ n, titulo }, i) => (
              <Fragment key={n}>
                {i > 0 && <span className="flex-1 h-px bg-neutral-800" />}
                <button
                  type="button"
                  onClick={() => n === 1 && setPaso(1)}
                  disabled={n === 2 && eventForm.category_ids.length === 0}
                  className={`flex items-center gap-2 text-xs font-bold transition-colors disabled:cursor-not-allowed ${
                    paso === n ? 'text-white' : 'text-neutral-600'
                  }`}
                >
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] ${
                    paso === n ? 'bg-red-600 text-white' : 'bg-neutral-800 text-neutral-500'
                  }`}>{n}</span>
                  <span className="hidden sm:inline uppercase tracking-wider">{titulo}</span>
                </button>
              </Fragment>
            ))}
          </div>

          {paso === 1 && (
          <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="md:col-span-2">
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Nombre del evento')}</label>
              <input required type="text" value={eventForm.name}
                onChange={e => setEventForm({ ...eventForm, name: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Fecha de inicio')}</label>
              <input required type="date" value={eventForm.start_date}
                onChange={e => setEventForm({ ...eventForm, start_date: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Fecha final')}</label>
              <input required type="date" value={eventForm.end_date}
                min={eventForm.start_date || undefined}
                onChange={e => setEventForm({ ...eventForm, end_date: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>
            <div className="md:col-span-2">
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Sede')}</label>
              <input type="text" value={eventForm.location} placeholder="Autódromo Panamá"
                onChange={e => setEventForm({ ...eventForm, location: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>

            {/* Logo del campeonato o imagen alusiva. En el gráfico sale a
                la derecha del nombre, con el logo del autódromo al otro
                lado: primero la casa, después la carrera. */}
            <div className="md:col-span-4 flex items-center gap-4 border-t border-neutral-800 pt-4">
              <div className="w-32 h-20 rounded-lg bg-[#0a0a0a] border border-neutral-800 overflow-hidden flex items-center justify-center flex-shrink-0">
                {vistaImagen
                  ? <img src={vistaImagen} alt="" className="w-full h-full object-contain"/>
                  : <ImageIcon size={22} className="text-neutral-700"/>}
              </div>

              <div className="min-w-0">
                <label className="block text-neutral-400 text-xs mb-2 uppercase">
                  {t('Imagen del evento')}
                </label>

                <input
                  type="file" accept="image/*" ref={inputImagen} className="hidden"
                  onChange={e => setImagen(e.target.files?.[0] || null)}
                />

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button" onClick={() => inputImagen.current?.click()}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-700 text-neutral-300 hover:border-blue-500 hover:text-blue-400 transition-colors font-bold text-xs"
                  >
                    <Upload size={14}/>
                    {vistaImagen ? 'CAMBIAR' : 'ELEGIR IMAGEN'}
                  </button>

                  {vistaImagen && (
                    <button
                      type="button" onClick={quitarImagen}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-800 text-neutral-500 hover:border-red-600 hover:text-red-500 transition-colors font-bold text-xs"
                    >
                      <X size={14}/> {t('QUITAR')}
                    </button>
                  )}
                </div>

                <p className="text-[11px] text-neutral-600 mt-2">
                  {imagen
                    ? 'Se sube al guardar el evento.'
                    : 'Sale en el gráfico de Evento, junto al nombre.'}
                </p>
              </div>
            </div>
            <div className="md:col-span-2 flex items-end">
              <p className="text-sm text-neutral-500">
                {totalDias > 0
                  ? <>{t('Duración:')} <span className="text-white font-bold">{totalDias} día{totalDias > 1 ? 's' : ''}</span></>
                  : 'Elige las dos fechas para ver la duración.'}
              </p>
            </div>
          </div>

          <div className="mt-5">
            <label className="block text-neutral-400 text-xs mb-2 uppercase">
              Categorías que corren ({eventForm.category_ids.length})
              {eventForm.category_ids.length === 0 && (
                <span className="ml-2 normal-case tracking-normal text-amber-400 font-normal">
                  · elige al menos una para continuar
                </span>
              )}
            </label>
            <div className="flex flex-wrap gap-2">
              {categorias.map(c => {
                const activa = eventForm.category_ids.includes(c.category_id)
                return (
                  <button
                    key={c.category_id} type="button"
                    onClick={() => alternarCategoria(c.category_id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${
                      activa
                        ? 'bg-red-600/15 border-red-600 text-red-400'
                        : 'border-neutral-800 text-neutral-500 hover:border-neutral-600 hover:text-neutral-300'
                    }`}
                  >
                    {c.category_name}
                  </button>
                )
              })}
              {categorias.length === 0 && (
                <p className="text-sm text-neutral-600">{t('No hay categorías en esta disciplina.')}</p>
              )}
            </div>
          </div>
          </>
          )}

          {paso === 2 && (
            <div>
              <div className="flex items-baseline justify-between mb-3">
                <label className="text-neutral-400 text-xs uppercase">
                  Vehículos que corren ({eventForm.inscritos.length})
                </label>
                <p className="text-xs text-neutral-600">
                  {t('Se elige categoría por categoría, y dentro por subcategoría.')}
                </p>
              </div>

              <SeleccionVehiculos
                categorias={categoriasElegidas}
                vehiculos={vehiculos}
                inscritos={eventForm.inscritos}
                onCambiar={inscritos => setEventForm(f => ({ ...f, inscritos }))}
              />
            </div>
          )}


          <div className="flex justify-between items-center gap-3 mt-6 pt-4 border-t border-neutral-800">
            <button type="button" onClick={closeForm}
              className="px-6 py-2 rounded border border-neutral-700 text-neutral-400 hover:text-white hover:border-neutral-500 transition-colors font-bold">
              {t('CANCELAR')}
            </button>

            <div className="flex items-center gap-3">
              {paso === 1 && faltantes.length > 0 && (
                <p className="text-xs text-amber-400 text-right max-w-xs">
                  Falta {faltantes.join(', ').replace(/, ([^,]*)$/, ' y $1')}.
                </p>
              )}

              {paso === 2 && (
                <button type="button" onClick={() => setPaso(1)}
                  className="flex items-center gap-2 px-5 py-2 rounded border border-neutral-700 text-neutral-400 hover:text-white hover:border-neutral-500 transition-colors font-bold text-sm">
                  <ArrowLeft size={15}/> {t('ATRÁS')}
                </button>
              )}

              {/* En el paso 1 el botón avanza, no guarda: sin type="button"
                  el submit del formulario se dispararía al pulsarlo. */}
              {paso === 1 ? (
                <button
                  // key distinta de la del botón de guardar: sin ella React
                  // reutiliza el mismo nodo del DOM y solo le cambia el
                  // type, que es el origen del submit accidental.
                  key="ir-al-paso-2"
                  type="button"
                  onClick={(e) => {
                    // React repinta de forma síncrona y este mismo nodo
                    // pasa a type="submit"; el navegador evalúa la acción
                    // por defecto después y enviaba el formulario.
                    e.preventDefault()
                    setPaso(2)
                  }}
                  disabled={faltantes.length > 0}
                  className="flex items-center gap-2 bg-white text-black font-bold py-2 px-6 rounded hover:bg-neutral-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  {t('SIGUIENTE')} <ArrowRight size={15}/>
                </button>
              ) : (
                <button key="guardar" type="submit" disabled={guardando}
                  className="bg-white text-black font-bold py-2 px-8 rounded hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2">
                  {guardando && <Loader2 size={16} className="animate-spin"/>}
                  {currentEditId ? 'ACTUALIZAR' : 'GUARDAR'}
                </button>
              )}
            </div>
          </div>
        </form>
      </>
      )}

      {!isFormOpen && (
      <div className="bg-[#141414] rounded-xl border border-neutral-800 overflow-hidden">
        {/* Desplaza en horizontal en pantallas estrechas. Antes el
            envoltorio recortaba y desde el móvil no se llegaba a las
            acciones, que van al final de la fila: se veía la tabla pero
            no se podía editar nada. */}
        <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left border-collapse">
          <thead>
            <tr className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 text-xs uppercase tracking-wider">
              <th className="p-4 font-bold"><span className="flex items-center">{t('Evento')} <SortIcon columnKey="name" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold"><span className="flex items-center">{t('Fechas')} <SortIcon columnKey="start_date" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold">{t('Categorías')}</th>
              <th className="p-4 font-bold text-right">{t('Inscritos')}</th>
              <th className="p-4 font-bold text-right">{t('Programa')}</th>
              {puedeEscribir && <th className="p-4 font-bold text-right">{t('Acciones')}</th>}
            </tr>
          </thead>
          <tbody>
            {lista.cargando && (
              <tr><td colSpan={columnas} className="p-10 text-center">
                <Loader2 className="w-6 h-6 animate-spin mx-auto text-red-600"/>
              </td></tr>
            )}

            {!lista.cargando && lista.error && (
              <tr><td colSpan={columnas} className="p-10 text-center text-red-500">{lista.error.message}</td></tr>
            )}

            {!lista.cargando && !lista.error && lista.items.length === 0 && (
              <tr><td colSpan={columnas} className="p-10 text-center text-neutral-500">
                {lista.texto ? `Sin resultados para "${lista.texto}".` : 'No hay eventos registrados.'}
              </td></tr>
            )}

            {!lista.cargando && !lista.error && lista.items.map(ev => (
              <Fragment key={ev.event_id}>
                <tr className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-4">
                    <p className="font-bold text-white italic">{ev.name}</p>
                    {ev.location && <p className="text-xs text-neutral-500 mt-0.5">{ev.location}</p>}
                  </td>
                  <td className="p-4 text-sm">
                    <span className="flex items-center gap-2 text-neutral-300">
                      <CalendarDays size={13} className="text-red-500"/>
                      {ev.start_date} → {ev.end_date}
                    </span>
                    <p className="text-xs text-neutral-600 mt-0.5 pl-5">{ev.total_dias} día{ev.total_dias > 1 ? 's' : ''}</p>
                  </td>
                  <td className="p-4">
                    <div className="flex flex-wrap gap-1">
                      {ev.categorias.length
                        ? ev.categorias.map(n => (
                            <span key={n} className="px-2 py-0.5 bg-neutral-800 text-neutral-300 text-[11px] rounded font-bold">{n}</span>
                          ))
                        : <span className="text-neutral-600">—</span>}
                    </div>
                  </td>
                  <td className="p-4 text-right">
                    <span className="inline-flex items-center gap-1.5 text-sm text-neutral-300">
                      <Car size={13} className="text-neutral-600"/>{ev.total_inscritos}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    <button
                      onClick={() => setExpandido(expandido?.event_id === ev.event_id ? null : ev)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-bold transition-colors ${
                        expandido?.event_id === ev.event_id
                          ? 'border-red-600 bg-red-600/10 text-red-400'
                          : 'border-neutral-800 text-neutral-400 hover:border-neutral-600 hover:text-white'
                      }`}
                    >
                      <ListOrdered size={13}/>{ev.total_sesiones}
                    </button>
                  </td>
                  {puedeEscribir && (
                    <td className="p-4 text-right whitespace-nowrap">
                      <button onClick={() => openEditForm(ev)} className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-700 transition-colors"><Pencil size={15}/></button>
                      <button onClick={() => setPorBorrar(ev)} className="p-2 rounded-lg text-neutral-400 hover:text-red-500 hover:bg-red-500/10 transition-colors"><Trash2 size={15}/></button>
                    </td>
                  )}
                </tr>

                {expandido?.event_id === ev.event_id && (
                  <tr className="border-b border-neutral-800/50">
                    <td colSpan={columnas} className="p-4 bg-[#0f0f0f]">
                      <p className="text-xs uppercase tracking-wider text-neutral-500 mb-3">
                        {t('Programa por día')}
                      </p>
                      <SesionesEvento
                        evento={expandido}
                        onCambio={alCambiarSesiones}
                        puedeEscribir={puedeEscribir}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        </div>

        {!lista.cargando && !lista.error && (
          <Pagination
            total={lista.total} skip={lista.skip} limit={lista.limit}
            onCambiarPagina={lista.setSkip} onCambiarTamano={lista.setLimit}
          />
        )}
      </div>
      )}

      <ConfirmDialog
        abierto={Boolean(porBorrar)}
        titulo={t('Eliminar evento')}
        mensaje={porBorrar ? `Se va a eliminar ${porBorrar.name} con sus ${porBorrar.total_sesiones} sesión(es).` : ''}
        onCancelar={() => setPorBorrar(null)}
        onConfirmar={confirmarBorrado}
      />
    </div>
  )
}
