import { t } from '../i18n'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Flag, Pencil, Trash2, ChevronUp, ChevronDown, ChevronsUpDown, Users, Loader2, ImagePlus, Scissors, X } from 'lucide-react'
import ModuleHeader from '../components/shared/ModuleHeader'
import Pagination from '../components/shared/Pagination'
import ConfirmDialog from '../components/shared/ConfirmDialog'
import {
  borrarFotoVehiculo, categoriasApi, pilotosApi, quitarFondoVehiculo,
  subirFotoVehiculo,
  urlFotoVehiculo, vehiculosApi,
} from '../api/registro'
import { useListado } from '../hooks/useListado'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { useDisciplina } from '../context/DisciplinaContext'

const EMPTY_VEHICLE = {
  vehicle_id: '', number: '', display_number: '',
  brand: '', model: '', color: '',
  category_id: '', sub_category_id: '', pilot_ids: [],
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

export default function VehiculosModule() {
  const toast = useToast()
  const { puedeEscribir } = useAuth()
  const { disciplina } = useDisciplina()

  const [categoriaFiltro, setCategoriaFiltro] = useState('')
  const [subFiltro,       setSubFiltro]       = useState('')
  const [pilotoFiltro,    setPilotoFiltro]    = useState('')

  // Se escribe con retardo: sin esto cada tecla dispara una consulta y la
  // tabla parpadea mientras se teclea un apellido.
  const [pilotoDebounce, setPilotoDebounce] = useState('')
  useEffect(() => {
    const id = setTimeout(() => setPilotoDebounce(pilotoFiltro.trim()), 350)
    return () => clearTimeout(id)
  }, [pilotoFiltro])

  // La disciplina viaja siempre; lo demás solo si se eligió.
  const filtros = useMemo(
    () => ({
      discipline: disciplina,
      ...(categoriaFiltro ? { category_id: categoriaFiltro } : {}),
      ...(subFiltro ? { sub_category_id: subFiltro } : {}),
      ...(pilotoDebounce ? { pilot: pilotoDebounce } : {}),
    }),
    [disciplina, categoriaFiltro, subFiltro, pilotoDebounce],
  )

  const lista = useListado(vehiculosApi, { ordenInicial: 'number', filtros })

  const [categorias,    setCategorias]    = useState([])
  const [pilotos,       setPilotos]       = useState([])
  const [isFormOpen,    setIsFormOpen]    = useState(false)
  const [currentEditId, setCurrentEditId] = useState(null)
  const [vehicleForm,   setVehicleForm]   = useState(EMPTY_VEHICLE)
  const [buscaPiloto,   setBuscaPiloto]   = useState('')
  const [guardando,     setGuardando]     = useState(false)
  const [porBorrar,     setPorBorrar]     = useState(null)

  // Catálogos completos para los selectores del formulario. Van sin
  // `limit` a propósito: aquí sí hace falta la lista entera.
  useEffect(() => {
    Promise.all([
      categoriasApi.listar({ sort_by: 'category_name', discipline: disciplina }),
      pilotosApi.listar({ sort_by: 'last_name' }),
    ])
      .then(([cats, pils]) => { setCategorias(cats.items); setPilotos(pils.items) })
      .catch(err => toast.error('No se pudieron cargar los catálogos', err.message))
  }, [disciplina])   // eslint-disable-line react-hooks/exhaustive-deps

  // Las subcategorías van embebidas en la categoría elegida.
  const subcategorias = useMemo(() => {
    const cat = categorias.find(c => String(c.category_id) === String(vehicleForm.category_id))
    return cat?.sub_categories || []
  }, [categorias, vehicleForm.category_id])

  // Las de la categoría elegida en el filtro. Son otras que las del
  // formulario, que dependen de la categoría del vehículo que se edita.
  const subcategoriasFiltro = useMemo(() => {
    const cat = categorias.find(c => String(c.category_id) === String(categoriaFiltro))
    return cat?.sub_categories || []
  }, [categorias, categoriaFiltro])

  // Cambiar de categoría deja huérfana la subcategoría elegida: pertenece
  // a la anterior y filtraría por un id que ya no existe en esta.
  useEffect(() => { setSubFiltro('') }, [categoriaFiltro])

  const pilotosFiltrados = useMemo(() => {
    const busca = buscaPiloto.trim().toLowerCase()
    if (!busca) return pilotos
    return pilotos.filter(p => `${p.name} ${p.last_name}`.toLowerCase().includes(busca))
  }, [pilotos, buscaPiloto])

  // Las fotos no viajan en el JSON del vehículo sino como archivos, y en
  // un alta todavía no hay id al que asociarlas: se guardan aquí y se
  // suben en cuanto el vehículo existe.
  const [fotos,  setFotos]  = useState([])   // ya guardadas: [{archivo, url}]
  const [nuevas, setNuevas] = useState([])   // File elegidos, sin subir
  const inputFoto = useRef(null)

  // Dos: una de frente y una de perfil, que es lo que usan los gráficos.
  // Tiene que coincidir con TOPE_FOTOS del backend, que es quien manda.
  const TOPE_FOTOS = 2

  // Una foto ya guardada se borra en el acto, no al guardar: el vehículo
  // ya existe y el archivo está en el servidor.
  // Cuál se está recortando, para poder marcarla mientras trabaja: son
  // dos segundos y sin aviso parece que no pasó nada.
  const [recortando, setRecortando] = useState(null)

  const recortarFoto = async (archivo) => {
    setRecortando(archivo)
    try {
      const v = await quitarFondoVehiculo(currentEditId, archivo)
      setFotos((v.photos || []).map((a, i) => ({
        archivo: a,
        url: urlFotoVehiculo((v.photo_urls || [])[i]),
      })))
      lista.recargar()
      toast.exito('Fondo quitado', 'La foto queda recortada sobre transparente')
    } catch (err) {
      toast.error('No se pudo quitar el fondo', err.message)
    } finally {
      setRecortando(null)
    }
  }

  const quitarFotoGuardada = async (archivo) => {
    try {
      const v = await borrarFotoVehiculo(currentEditId, archivo)
      setFotos((v.photos || []).map((a, i) => ({
        archivo: a,
        url: urlFotoVehiculo((v.photo_urls || [])[i]),
      })))
      lista.recargar()
    } catch (err) {
      toast.error('No se pudo quitar la foto', err.message)
    }
  }

  const limpiarFotos = () => {
    setFotos([]); setNuevas([])
    if (inputFoto.current) inputFoto.current.value = ''
  }

  const openAddForm = () => {
    setVehicleForm(EMPTY_VEHICLE); setCurrentEditId(null)
    setBuscaPiloto(''); limpiarFotos(); setIsFormOpen(true)
  }
  const closeForm = () => {
    setIsFormOpen(false); setCurrentEditId(null)
    setVehicleForm(EMPTY_VEHICLE); setBuscaPiloto(''); limpiarFotos()
  }
  const handleFormToggle = () => isFormOpen ? closeForm() : openAddForm()

  const openEditForm = (vehiculo) => {
    setVehicleForm({
      vehicle_id: vehiculo.vehicle_id,
      number: vehiculo.number,
      display_number: vehiculo.display_number || '',
      brand: vehiculo.brand || '',
      model: vehiculo.model || '',
      color: vehiculo.color || '',
      category_id: vehiculo.category_id,
      sub_category_id: vehiculo.sub_category_id ?? '',
      pilot_ids: (vehiculo.pilots || []).map(p => p.pilot_id),
    })
    setCurrentEditId(vehiculo.vehicle_id)
    setBuscaPiloto('')

    setFotos((vehiculo.photos || []).map((archivo, i) => ({
      archivo,
      url: urlFotoVehiculo((vehiculo.photo_urls || [])[i]),
    })))
    setNuevas([])
    if (inputFoto.current) inputFoto.current.value = ''

    setIsFormOpen(true)
  }

  const alternarPiloto = (pilotId) => {
    setVehicleForm(f => {
      if (f.pilot_ids.includes(pilotId)) {
        return { ...f, pilot_ids: f.pilot_ids.filter(id => id !== pilotId) }
      }
      // El backend rechaza más de dos; se avisa aquí para no gastar un
      // viaje al servidor con un error que ya sabemos.
      if (f.pilot_ids.length >= 2) {
        toast.info('Máximo dos pilotos', 'Quita uno antes de agregar otro.')
        return f
      }
      return { ...f, pilot_ids: [...f.pilot_ids, pilotId] }
    })
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setGuardando(true)

    const cuerpo = {
      number: Number(vehicleForm.number),
      // Si se deja vacío, el backend lo rellena con el número. Importa
      // porque los ceros a la izquierda distinguen carros ('044' != '44').
      display_number: vehicleForm.display_number || null,
      brand: vehicleForm.brand || null,
      model: vehicleForm.model || null,
      color: vehicleForm.color || null,
      category_id: Number(vehicleForm.category_id),
      sub_category_id: vehicleForm.sub_category_id === '' ? null : Number(vehicleForm.sub_category_id),
      pilot_ids: vehicleForm.pilot_ids,
    }

    const etiqueta = `#${vehicleForm.number} ${vehicleForm.brand} ${vehicleForm.model}`.trim()

    try {
      let id = currentEditId

      if (currentEditId) {
        await vehiculosApi.actualizar(currentEditId, cuerpo)
        toast.exito('Vehículo actualizado', etiqueta)
      } else {
        // Sin vehicle_id: lo asigna el backend. El dorsal (`number`) sí
        // lo escribe quien inscribe; esto era solo la clave interna.
        const creado = await vehiculosApi.crear(cuerpo)
        id = creado.vehicle_id
        toast.exito('Vehículo creado', etiqueta)
      }

      // Después de guardar porque en un alta el id no existe hasta ahora.
      // Si falla una foto no se deshace el vehículo: se avisa y ya.
      for (const archivo of nuevas) {
        try {
          await subirFotoVehiculo(id, archivo)
        } catch (err) {
          toast.error(`No se pudo subir ${archivo.name}`, err.message)
        }
      }

      /* Se sigue en la ficha después de guardar, no se vuelve al listado.
         Al dar de alta hay cosas que solo se pueden hacer con el registro ya
         creado —subir su imagen, recortarle el fondo— y devolver a la lista
         obligaba a buscarlo otra vez para entrar a editarlo.

         El id se fija aquí: sin esto la ficha seguiría en modo alta y volver
         a guardar crearía un registro repetido. */
      setCurrentEditId(id)

      // Las fotos ya subieron; se sueltan para que no vuelvan a mandarse.
      setNuevas([])
      lista.recargar()
    } catch (err) {
      toast.error(currentEditId ? 'No se pudo actualizar' : 'No se pudo crear', err.message)
    } finally {
      setGuardando(false)
    }
  }

  const confirmarBorrado = async () => {
    const vehiculo = porBorrar
    setPorBorrar(null)

    try {
      await vehiculosApi.eliminar(vehiculo.vehicle_id)
      toast.exito('Vehículo eliminado', `#${vehiculo.number} ${vehiculo.brand || ''}`.trim())
      lista.recargar()
    } catch (err) {
      toast.error('No se pudo eliminar', err.message)
    }
  }

  return (
    <div className="w-full animate-fade-in">
      {/* El listado y la ficha no conviven: se ve uno u otro. Con los dos a
          la vez la ficha quedaba apretada arriba y en un teléfono ni se
          alcanzaba a ver entera. */}
      {!isFormOpen && (
      <ModuleHeader
        entityName="vehículos"
        searchText={lista.texto}
        onSearchChange={lista.setTexto}
        isFormOpen={isFormOpen}
        onFormToggle={handleFormToggle}
        addButtonLabel="NUEVO VEHÍCULO"
        puedeCrear={puedeEscribir}
        exportData={() => vehiculosApi.listar({ ...filtros, search: lista.texto || undefined, sort_by: lista.sortBy, sort_dir: lista.sortDir }).then(p => p.items)}
        onExportError={m => toast.error('No se pudo exportar', m)}
        exportFileName="vehiculos"
        exportColumnMap={{ vehicle_id: 'ID', number: 'Dorsal', brand: 'Marca', model: 'Modelo', category_name: 'Categoría' }}
      />
      )}

      {!isFormOpen && (
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <label className="text-xs uppercase tracking-wider text-neutral-500">{t('Categoría')}</label>
        <select
          value={categoriaFiltro}
          onChange={e => setCategoriaFiltro(e.target.value)}
          className="bg-[#141414] border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-300 focus:outline-none focus:border-red-600"
        >
          <option value="">{t('Todas')}</option>
          {categorias.map(c => (
            <option key={c.category_id} value={c.category_id}>{c.category_name}</option>
          ))}
        </select>

        {/* Solo aparece si la categoría elegida tiene subcategorías: un
            desplegable con una única opción vacía no dice nada. */}
        {subcategoriasFiltro.length > 0 && (
          <>
            <label className="text-xs uppercase tracking-wider text-neutral-500">{t('Subcategoría')}</label>
            <select
              value={subFiltro}
              onChange={e => setSubFiltro(e.target.value)}
              className="bg-[#141414] border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-300 focus:outline-none focus:border-red-600"
            >
              <option value="">{t('Todas')}</option>
              {subcategoriasFiltro.map(sc => (
                <option key={sc.sub_category_id} value={sc.sub_category_id}>
                  {sc.sub_category_name}
                </option>
              ))}
            </select>
          </>
        )}

        {/* Buscar por piloto: se quiere saber qué corre alguien, y de paso
            se ven sus categorías y subcategorías en la propia tabla. */}
        <label className="text-xs uppercase tracking-wider text-neutral-500">{t('Piloto')}</label>
        <div className="relative">
          <input
            type="text"
            value={pilotoFiltro}
            onChange={e => setPilotoFiltro(e.target.value)}
            placeholder={t('Nombre o apellido...')}
            className="bg-[#141414] border border-neutral-800 rounded-lg pl-3 pr-8 py-2 text-sm text-neutral-300 focus:outline-none focus:border-red-600 w-52"
          />
          {pilotoFiltro && (
            <button
              type="button"
              onClick={() => setPilotoFiltro('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-white"
              title={t('Quitar el filtro')}
            >
              <X size={14}/>
            </button>
          )}
        </div>
      </div>
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
            {currentEditId ? t('Editar vehículo') : t('Nuevo vehículo')}
          </h3>
        </div>

        <form onSubmit={handleSave} className="bg-[#141414] p-6 rounded-xl border border-red-600/30 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Dorsal')}</label>
              <input required type="number" min="0" value={vehicleForm.number}
                onChange={e => setVehicleForm({ ...vehicleForm, number: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Dorsal en pantalla')}</label>
              <input type="text" value={vehicleForm.display_number} placeholder={vehicleForm.number || 'igual al dorsal'}
                onChange={e => setVehicleForm({ ...vehicleForm, display_number: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Color')}</label>
              <input type="text" value={vehicleForm.color}
                onChange={e => setVehicleForm({ ...vehicleForm, color: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Marca')}</label>
              <input required type="text" value={vehicleForm.brand}
                onChange={e => setVehicleForm({ ...vehicleForm, brand: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Modelo')}</label>
              <input type="text" value={vehicleForm.model}
                onChange={e => setVehicleForm({ ...vehicleForm, model: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
            </div>
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Categoría')}</label>
              <select required value={vehicleForm.category_id}
                onChange={e => setVehicleForm({ ...vehicleForm, category_id: e.target.value, sub_category_id: '' })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white">
                <option value="">{t('Seleccionar...')}</option>
                {categorias.map(c => <option key={c.category_id} value={c.category_id}>{c.category_name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Subcategoría')}</label>
              <select value={vehicleForm.sub_category_id}
                disabled={subcategorias.length === 0}
                onChange={e => setVehicleForm({ ...vehicleForm, sub_category_id: e.target.value })}
                className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white disabled:opacity-40">
                <option value="">{subcategorias.length ? 'Ninguna' : 'Sin subcategorías'}</option>
                {subcategorias.map(s => (
                  <option key={s.sub_category_id} value={s.sub_category_id}>{s.sub_category_name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Fotos del carro. Dos: una de frente y una de perfil. Cuál se
              saca al aire se decide
              al graficar, así que aquí no hay principal ni secundaria: es
              una lista y el orden es el de subida. */}
          <div className="mt-5 border-t border-neutral-800 pt-4">
            <label className="block text-neutral-400 text-xs mb-2 uppercase">
              Fotos del vehículo ({fotos.length + nuevas.length}/{TOPE_FOTOS})
            </label>

            <div className="flex flex-wrap gap-3 mb-3">
              {fotos.map(f => (
                <div key={f.archivo} className="relative w-28 h-20 rounded-lg overflow-hidden border border-neutral-800 bg-[#0a0a0a]">
                  <img src={f.url} alt="" className="w-full h-full object-cover"/>
                  <button
                    type="button" onClick={() => recortarFoto(f.archivo)}
                    disabled={recortando !== null}
                    className="absolute top-1 left-1 bg-black/70 rounded p-1 text-neutral-300 hover:text-green-400 disabled:opacity-40 transition-colors"
                    title="Quitar el fondo de esta foto"
                  >
                    {recortando === f.archivo
                      ? <Loader2 size={12} className="animate-spin"/>
                      : <Scissors size={12}/>}
                  </button>
                  <button
                    type="button" onClick={() => quitarFotoGuardada(f.archivo)}
                    className="absolute top-1 right-1 bg-black/70 rounded p-1 text-neutral-300 hover:text-red-500 transition-colors"
                    title={t('Quitar esta foto')}
                  >
                    <X size={12}/>
                  </button>
                </div>
              ))}

              {nuevas.map((archivo, i) => (
                <div key={`nueva-${i}`} className="relative w-28 h-20 rounded-lg overflow-hidden border border-blue-600/50 bg-[#0a0a0a]">
                  <img src={URL.createObjectURL(archivo)} alt="" className="w-full h-full object-cover"/>
                  <span className="absolute bottom-0 inset-x-0 bg-blue-600/80 text-white text-[10px] font-bold text-center py-0.5">
                    {t('AL GUARDAR')}
                  </span>
                  <button
                    type="button" onClick={() => setNuevas(n => n.filter((_, j) => j !== i))}
                    className="absolute top-1 right-1 bg-black/70 rounded p-1 text-neutral-300 hover:text-red-500 transition-colors"
                  >
                    <X size={12}/>
                  </button>
                </div>
              ))}

              {fotos.length + nuevas.length < TOPE_FOTOS && (
                <button
                  type="button" onClick={() => inputFoto.current?.click()}
                  className="w-28 h-20 rounded-lg border border-dashed border-neutral-700 text-neutral-500 hover:border-blue-500 hover:text-blue-400 transition-colors flex flex-col items-center justify-center gap-1"
                >
                  <ImagePlus size={18}/>
                  <span className="text-[11px] font-bold">{t('AÑADIR')}</span>
                </button>
              )}
            </div>

            <input
              type="file" accept="image/*" multiple ref={inputFoto} className="hidden"
              onChange={e => {
                // Los archivos se leen aquí y no dentro del actualizador de
                // estado. React ejecuta el actualizador más tarde, y para
                // entonces la línea que limpia el input ya vació
                // e.target.files: la lista llegaba vacía y no se subía nada.
                const elegidos = Array.from(e.target.files || [])

                // Se limpia para poder volver a elegir el mismo archivo:
                // sin esto el onChange no se dispara la segunda vez.
                e.target.value = ''

                setNuevas(n => [
                  ...n,
                  ...elegidos.slice(0, TOPE_FOTOS - fotos.length - n.length),
                ])
              }}
            />
          </div>

          <div className="mt-5">
            <label className="block text-neutral-400 text-xs mb-2 uppercase">
              Pilotos ({vehicleForm.pilot_ids.length}/2)
            </label>
            <input
              type="text" value={buscaPiloto} placeholder={t('Filtrar pilotos...')}
              onChange={e => setBuscaPiloto(e.target.value)}
              className="w-full md:w-72 mb-3 bg-[#0a0a0a] border border-neutral-800 rounded p-2 text-sm focus:border-red-600 focus:outline-none text-white"
            />
            {/* Son más de cien pilotos: la caja se limita en alto y se
                desplaza, si no el formulario se vuelve una lista infinita. */}
            <div className="max-h-52 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 p-1">
              {pilotosFiltrados.map(piloto => {
                const asignado = vehicleForm.pilot_ids.includes(piloto.pilot_id)
                return (
                  <button
                    key={piloto.pilot_id} type="button"
                    onClick={() => alternarPiloto(piloto.pilot_id)}
                    className={`px-3 py-2 rounded-lg text-xs font-bold border text-left min-w-0 transition-colors ${
                      asignado
                        ? 'bg-red-600/15 border-red-600 text-red-400'
                        : 'border-neutral-800 text-neutral-500 hover:border-neutral-600 hover:text-neutral-300'
                    }`}
                  >
                    {/* Nombre y apellido, no solo el nombre: escribiendo
                        "roberto" salían cuatro botones idénticos y no había
                        forma de saber cuál era cuál. */}
                    <span className="block truncate">{piloto.name}</span>
                    <span className={`block truncate uppercase text-[11px] font-black tracking-wide ${
                      asignado ? 'text-red-300' : 'text-neutral-400'
                    }`}>
                      {piloto.last_name}
                    </span>
                  </button>
                )
              })}
              {pilotosFiltrados.length === 0 && (
                <p className="col-span-full text-sm text-neutral-600 py-3">{t('Ningún piloto coincide.')}</p>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-3 mt-5">
            <button type="button" onClick={closeForm} className="px-6 py-2 rounded border border-neutral-700 text-neutral-400 hover:text-white hover:border-neutral-500 transition-colors font-bold">{t('CANCELAR')}</button>
            <button type="submit" disabled={guardando}
              className="bg-white text-black font-bold py-2 px-8 rounded hover:bg-neutral-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2">
              {guardando && <Loader2 size={16} className="animate-spin"/>}
              {currentEditId ? 'ACTUALIZAR' : 'GUARDAR'}
            </button>
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
        <table className="w-full min-w-[820px] text-left border-collapse">
          <thead>
            <tr className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 text-xs uppercase tracking-wider">
              <th className="p-4 font-bold"><span className="flex items-center">{t('Dorsal')} <SortIcon columnKey="number" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold"><span className="flex items-center">{t('Vehículo')} <SortIcon columnKey="brand" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold"><span className="flex items-center">{t('Categoría')} <SortIcon columnKey="category_id" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold">{t('Pilotos')}</th>
              {puedeEscribir && <th className="p-4 font-bold text-right">{t('Acciones')}</th>}
            </tr>
          </thead>
          <tbody>
            {lista.cargando && (
              <tr><td colSpan={puedeEscribir ? 5 : 4} className="p-10 text-center">
                <Loader2 className="w-6 h-6 animate-spin mx-auto text-red-600"/>
              </td></tr>
            )}

            {!lista.cargando && lista.error && (
              <tr><td colSpan={puedeEscribir ? 5 : 4} className="p-10 text-center text-red-500">{lista.error.message}</td></tr>
            )}

            {!lista.cargando && !lista.error && lista.items.length === 0 && (
              <tr><td colSpan={puedeEscribir ? 5 : 4} className="p-10 text-center text-neutral-500">
                {lista.texto ? `Sin resultados para "${lista.texto}".` : 'No hay vehículos registrados.'}
              </td></tr>
            )}

            {!lista.cargando && !lista.error && lista.items.map(vehiculo => (
              <tr key={vehiculo.vehicle_id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                <td className="p-4">
                  <span className="inline-flex items-center justify-center min-w-[42px] h-9 px-2 rounded bg-neutral-800 text-white font-black font-mono">
                    {vehiculo.display_number || vehiculo.number}
                  </span>
                </td>
                <td className="p-4">
                  <p className="font-bold text-white">{vehiculo.brand || <span className="text-neutral-600">{t('Sin marca')}</span>}</p>
                  <p className="text-xs text-neutral-500">{vehiculo.model || '—'}{vehiculo.color ? ` · ${vehiculo.color}` : ''}</p>
                </td>
                <td className="p-4 text-neutral-300 text-sm">
                  <span className="flex items-center gap-2"><Flag size={13} className="text-red-500"/>{vehiculo.category_name || `#${vehiculo.category_id}`}</span>
                  {vehiculo.sub_category_name && <p className="text-xs text-neutral-600 mt-0.5 pl-5">{vehiculo.sub_category_name}</p>}
                </td>
                <td className="p-4">
                  {vehiculo.pilots?.length
                    ? (
                      <div className="flex flex-col gap-0.5">
                        {vehiculo.pilots.map(p => (
                          <span key={p.pilot_id} className="text-sm text-neutral-300 flex items-center gap-2">
                            <Users size={12} className="text-neutral-600"/>{p.name}
                          </span>
                        ))}
                      </div>
                    )
                    : <span className="text-neutral-600">{t('Sin piloto')}</span>}
                </td>
                {puedeEscribir && (
                  <td className="p-4 text-right whitespace-nowrap">
                    <button onClick={() => openEditForm(vehiculo)} className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-700 transition-colors"><Pencil size={15}/></button>
                    <button onClick={() => setPorBorrar(vehiculo)} className="p-2 rounded-lg text-neutral-400 hover:text-red-500 hover:bg-red-500/10 transition-colors"><Trash2 size={15}/></button>
                  </td>
                )}
              </tr>
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
        titulo={t('Eliminar vehículo')}
        mensaje={porBorrar ? `Se va a eliminar el #${porBorrar.number} ${porBorrar.brand || ''}.` : ''}
        onCancelar={() => setPorBorrar(null)}
        onConfirmar={confirmarBorrado}
      />
    </div>
  )
}
