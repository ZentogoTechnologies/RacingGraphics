import { t } from '../i18n'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Pencil, Trash2, ChevronUp, ChevronDown, ChevronsUpDown, Loader2, Scissors, Upload, User, X } from 'lucide-react'
import ModuleHeader from '../components/shared/ModuleHeader'
import Pagination from '../components/shared/Pagination'
import ConfirmDialog from '../components/shared/ConfirmDialog'
import {
  borrarFotoPiloto, categoriasApi, pilotosApi, quitarFondoPiloto,
  subirFotoPiloto, urlFotoPiloto,
} from '../api/registro'
import { useListado } from '../hooks/useListado'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { useDisciplina } from '../context/DisciplinaContext'

// Sin discipline: la hereda del selector global. Si el formulario dejara
// elegirla, crear un piloto de la otra disciplina solo serviría para que
// desapareciera de la lista al guardarlo.
const EMPTY_PILOT = {
  name: '', last_name: '', nationality: '',
  team_brand: '', category_ids: [],
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

export default function PilotosModule() {
  const toast = useToast()
  const { puedeEscribir } = useAuth()
  const { disciplina } = useDisciplina()

  // El filtro por categoría se manda al backend, no se aplica sobre la
  // página visible: filtrar aquí dejaría el total y las páginas mintiendo.
  const [categoriaFiltro, setCategoriaFiltro] = useState('')

  // '' = todos, 'true' = activos, 'false' = inactivos. Se guarda como
  // texto porque sale de un <select>, y se manda tal cual: el backend lo
  // interpreta y distingue false de "sin filtro".
  const [estadoFiltro, setEstadoFiltro] = useState('')

  // La disciplina viaja siempre; la categoría y el estado solo si se
  // eligieron.
  const filtros = useMemo(
    () => ({
      discipline: disciplina,
      ...(categoriaFiltro ? { category_id: categoriaFiltro } : {}),
      ...(estadoFiltro ? { is_active: estadoFiltro } : {}),
    }),
    [disciplina, categoriaFiltro, estadoFiltro],
  )

  const lista = useListado(pilotosApi, { ordenInicial: 'last_name', filtros })

  const [categorias,    setCategorias]    = useState([])
  const [isFormOpen,    setIsFormOpen]    = useState(false)
  const [currentEditId, setCurrentEditId] = useState(null)
  const [pilotForm,     setPilotForm]     = useState(EMPTY_PILOT)
  const [guardando,     setGuardando]     = useState(false)
  const [porBorrar,     setPorBorrar]     = useState(null)

  // Las categorías se traen enteras una sola vez: son seis y alimentan
  // tanto el filtro de arriba como el selector del formulario.
  useEffect(() => {
    categoriasApi.listar({ sort_by: 'category_name', discipline: disciplina })
      .then(p => setCategorias(p.items))
      .catch(err => toast.error('No se pudieron cargar las categorías', err.message))
  }, [disciplina])   // eslint-disable-line react-hooks/exhaustive-deps

  const nombreCategoria = (id) =>
    categorias.find(c => c.category_id === id)?.category_name || `#${id}`

  // La foto se maneja aparte del resto del formulario: no viaja en el JSON
  // del piloto sino como archivo, y en un alta todavía no hay id al que
  // asociarla, así que se guarda aquí y se sube en cuanto el piloto existe.
  const [foto, setFoto] = useState(null)          // File elegido, sin subir
  const [fotoActual, setFotoActual] = useState(null)   // ruta ya guardada
  const inputFoto = useRef(null)

  // Vista previa de lo elegido antes de subirlo. Se revoca al cambiar para
  // no ir dejando URLs de objeto vivas en memoria.
  const [previa, setPrevia] = useState(null)
  useEffect(() => {
    if (!foto) { setPrevia(null); return }
    const url = URL.createObjectURL(foto)
    setPrevia(url)
    return () => URL.revokeObjectURL(url)
  }, [foto])

  const limpiarFoto = () => {
    setFoto(null)
    setFotoActual(null)
    if (inputFoto.current) inputFoto.current.value = ''
  }

  const openAddForm  = () => { setPilotForm(EMPTY_PILOT); setCurrentEditId(null); limpiarFoto(); setIsFormOpen(true) }
  const closeForm    = () => { setIsFormOpen(false); setCurrentEditId(null); setPilotForm(EMPTY_PILOT); limpiarFoto() }
  const handleFormToggle = () => isFormOpen ? closeForm() : openAddForm()

  const openEditForm = (piloto) => {
    setPilotForm({
      pilot_id: piloto.pilot_id,
      name: piloto.name,
      last_name: piloto.last_name,
      nationality: piloto.nationality || '',
      team_brand: piloto.team_brand || '',
      category_ids: piloto.categories || [],
    })
    setCurrentEditId(piloto.pilot_id)
    setFoto(null)
    setFotoActual(piloto.photo || null)
    if (inputFoto.current) inputFoto.current.value = ''
    setIsFormOpen(true)
  }

  const [recortando, setRecortando] = useState(false)

  /* Recorta al piloto de su fondo. Trabaja sobre la foto ya guardada, así
     que solo tiene sentido con el piloto creado: en un alta todavía no hay
     nada en el servidor sobre lo que trabajar.

     La primera del día tarda unos segundos —es cargar el modelo— y las
     siguientes son casi inmediatas. Se avisa mientras tanto para que nadie
     piense que se colgó. */
  const recortarFoto = async () => {
    if (!currentEditId) return
    setRecortando(true)
    try {
      const actualizado = await quitarFondoPiloto(currentEditId)
      // El recorte se guarda como PNG, así que la ruta cambia de extensión
      // y el navegador no puede servir la anterior de su caché.
      setFotoActual(actualizado.photo || null)
      lista.recargar()
      toast.exito('Fondo quitado', 'La foto queda recortada sobre transparente')
    } catch (err) {
      toast.error('No se pudo quitar el fondo', err.message)
    } finally {
      setRecortando(false)
    }
  }

  const quitarFoto = async () => {
    if (!currentEditId) { limpiarFoto(); return }
    try {
      await borrarFotoPiloto(currentEditId)
      limpiarFoto()
      lista.recargar()
      toast.exito('Foto quitada', 'El gráfico usará la silueta de reserva')
    } catch (err) {
      toast.error('No se pudo quitar la foto', err.message)
    }
  }

  const alternarCategoria = (id) => {
    setPilotForm(f => ({
      ...f,
      category_ids: f.category_ids.includes(id)
        ? f.category_ids.filter(c => c !== id)
        : [...f.category_ids, id],
    }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setGuardando(true)

    // El modelo la guarda como lista porque un piloto puede correr en las
    // dos disciplinas. Aquí se manda la activa; para que corra en ambas
    // habría que cargarlo desde cada una.
    const cuerpo = {
      name: pilotForm.name,
      last_name: pilotForm.last_name,
      nationality: pilotForm.nationality || null,
      team_brand: pilotForm.team_brand || null,
      category_ids: pilotForm.category_ids,
      discipline: [disciplina],
    }

    try {
      let id = currentEditId

      if (currentEditId) {
        await pilotosApi.actualizar(currentEditId, cuerpo)
        toast.exito('Piloto actualizado', `${pilotForm.name} ${pilotForm.last_name}`)
      } else {
        // Sin pilot_id: lo asigna el backend, que es el único que sabe
        // cuál está libre aunque haya dos altas a la vez.
        const creado = await pilotosApi.crear(cuerpo)
        id = creado.pilot_id
        toast.exito('Piloto creado', `${pilotForm.name} ${pilotForm.last_name}`)
      }

      // Va después de guardar porque en un alta el id no existe hasta
      // ahora. Si falla la foto no se deshace el piloto: se avisa y ya,
      // que volver a intentarlo es abrir y elegir el archivo otra vez.
      if (foto && id) {
        try {
          await subirFotoPiloto(id, foto)
        } catch (err) {
          toast.error('El piloto se guardó, pero la foto no', err.message)
        }
      }
      /* Se sigue en la ficha después de guardar, no se vuelve al listado.
         Al dar de alta hay cosas que solo se pueden hacer con el piloto ya
         creado —subirle la foto, recortarle el fondo— y devolver a la lista
         obligaba a buscarlo otra vez para entrar a editarlo.

         El id se fija aquí: sin esto la ficha seguiría en modo alta y volver
         a guardar crearía un piloto repetido. */
      setCurrentEditId(id)

      // La foto ya subió; se suelta para que no vuelva a mandarse.
      setFoto(null)
      if (inputFoto.current) inputFoto.current.value = ''

      lista.recargar()
    } catch (err) {
      toast.error(currentEditId ? 'No se pudo actualizar' : 'No se pudo crear', err.message)
    } finally {
      setGuardando(false)
    }
  }

  // Alta y baja sin borrar: un piloto que dejó de correr sigue apareciendo
  // en los resultados de las tandas que ya se disputaron, así que borrarlo
  // no es lo que se quiere casi nunca.
  const alternarActivo = async (piloto) => {
    const nombre = `${piloto.name} ${piloto.last_name}`.trim()
    try {
      await pilotosApi.actualizar(piloto.pilot_id, { is_active: !piloto.is_active })
      lista.recargar()
      toast.exito(piloto.is_active ? 'Piloto inactivo' : 'Piloto activo', nombre)
    } catch (err) {
      toast.error('No se pudo cambiar el estado', err.message)
    }
  }

  const confirmarBorrado = async () => {
    const piloto = porBorrar
    setPorBorrar(null)

    try {
      await pilotosApi.eliminar(piloto.pilot_id)
      toast.exito('Piloto eliminado', `${piloto.name} ${piloto.last_name}`)
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
        entityName="pilotos"
        searchText={lista.texto}
        onSearchChange={lista.setTexto}
        isFormOpen={isFormOpen}
        onFormToggle={handleFormToggle}
        addButtonLabel="NUEVO PILOTO"
        puedeCrear={puedeEscribir}
        exportData={() => pilotosApi.listar({ ...filtros, search: lista.texto || undefined, sort_by: lista.sortBy, sort_dir: lista.sortDir }).then(p => p.items)}
        onExportError={m => toast.error('No se pudo exportar', m)}
        exportFileName="pilotos"
        exportColumnMap={{ pilot_id: 'ID', name: 'Nombre', last_name: 'Apellido', nationality: 'Nacionalidad', team_brand: 'Equipo' }}
      />
      )}

      {!isFormOpen && (
      <div className="flex items-center gap-3 mb-4">
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

        {/* El estado se filtra en el backend como los demás: hacerlo sobre
            la página visible dejaría el total y la paginación mintiendo. */}
        <label className="text-xs uppercase tracking-wider text-neutral-500">{t('Estado')}</label>
        <select
          value={estadoFiltro}
          onChange={e => setEstadoFiltro(e.target.value)}
          className="bg-[#141414] border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-300 focus:outline-none focus:border-red-600"
        >
          <option value="">{t('Todos')}</option>
          <option value="true">{t('Activos')}</option>
          <option value="false">{t('Inactivos')}</option>
        </select>
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
            {currentEditId ? t('Editar piloto') : t('Nuevo piloto')}
          </h3>
        </div>

        <form onSubmit={handleSave} className="bg-[#141414] p-6 rounded-xl border border-red-600/30 mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Nombre')}</label>
            <input required type="text" value={pilotForm.name}
              onChange={e => setPilotForm({ ...pilotForm, name: e.target.value })}
              className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
          </div>
          <div>
            <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Apellido')}</label>
            <input required type="text" value={pilotForm.last_name}
              onChange={e => setPilotForm({ ...pilotForm, last_name: e.target.value })}
              className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
          </div>
          <div>
            <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Nacionalidad')}</label>
            <input type="text" value={pilotForm.nationality} placeholder="Panama"
              onChange={e => setPilotForm({ ...pilotForm, nationality: e.target.value })}
              className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
          </div>
          <div>
            <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Equipo')}</label>
            <input type="text" value={pilotForm.team_brand}
              onChange={e => setPilotForm({ ...pilotForm, team_brand: e.target.value })}
              className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
          </div>
          <div className="col-span-full flex items-center gap-4 border-t border-neutral-800 pt-4">

            <div className="w-20 h-20 rounded-lg bg-[#0a0a0a] border border-neutral-800 overflow-hidden flex items-center justify-center flex-shrink-0">
              {previa || fotoActual
                ? <img src={previa || urlFotoPiloto(fotoActual)} alt="" className="w-full h-full object-cover"/>
                : <User size={26} className="text-neutral-700"/>}
            </div>

            <div className="min-w-0">
              <label className="block text-neutral-400 text-xs mb-2 uppercase">{t('Foto del piloto')}</label>

              <input
                type="file" accept="image/*" ref={inputFoto} className="hidden"
                onChange={e => setFoto(e.target.files?.[0] || null)}
              />

              <div className="flex flex-wrap gap-2">
                <button
                  type="button" onClick={() => inputFoto.current?.click()}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-700 text-neutral-300 hover:border-blue-500 hover:text-blue-400 transition-colors font-bold text-xs"
                >
                  <Upload size={14}/>
                  {previa || fotoActual ? 'CAMBIAR' : 'ELEGIR FOTO'}
                </button>

                {/* Con foto puesta se ofrecen los tres; sin ella, solo el de
                    agregar. El recorte trabaja sobre el archivo guardado en
                    el servidor, asi que necesita el piloto ya creado. */}
                {fotoActual && currentEditId && (
                  <button
                    type="button" onClick={recortarFoto} disabled={recortando}
                    title="Recorta al piloto y deja el fondo transparente"
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-700 text-neutral-300 hover:border-green-500 hover:text-green-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-bold text-xs"
                  >
                    {recortando
                      ? <Loader2 size={14} className="animate-spin"/>
                      : <Scissors size={14}/>}
                    {recortando ? 'QUITANDO…' : 'QUITAR FONDO'}
                  </button>
                )}

                {(previa || fotoActual) && (
                  <button
                    type="button" onClick={quitarFoto}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-800 text-neutral-500 hover:border-red-600 hover:text-red-500 transition-colors font-bold text-xs"
                  >
                    <X size={14}/> {t('QUITAR')}
                  </button>
                )}
              </div>

              {/* Se avisa porque la foto no se sube al elegirla: en un alta
                  todavía no hay piloto al que asociarla. */}
              <p className="text-[11px] text-neutral-600 mt-2">
                {foto
                  ? 'Se sube al guardar el piloto.'
                  : 'La usan la ficha del piloto y la grilla con fotos.'}
              </p>
            </div>
          </div>

          <div className="col-span-full">
            <label className="block text-neutral-400 text-xs mb-2 uppercase">{t('Categorías')}</label>
            <div className="flex flex-wrap gap-2">
              {categorias.map(c => {
                const activa = pilotForm.category_ids.includes(c.category_id)
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
            </div>
          </div>

          <div className="col-span-full flex justify-end gap-3 mt-2">
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
        <table className="w-full min-w-[900px] text-left border-collapse">
          <thead>
            <tr className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 text-xs uppercase tracking-wider">
              <th className="p-4 font-bold"><span className="flex items-center">{t('Piloto')} <SortIcon columnKey="last_name" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold"><span className="flex items-center">{t('Nacionalidad')} <SortIcon columnKey="nationality" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold"><span className="flex items-center">{t('Equipo')} <SortIcon columnKey="team_brand" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold">{t('Categorías')}</th>
              <th className="p-4 font-bold text-right">{t('Estado')}</th>
              {puedeEscribir && <th className="p-4 font-bold text-right">{t('Acciones')}</th>}
            </tr>
          </thead>
          <tbody>
            {lista.cargando && (
              <tr><td colSpan={puedeEscribir ? 6 : 5} className="p-10 text-center">
                <Loader2 className="w-6 h-6 animate-spin mx-auto text-red-600"/>
              </td></tr>
            )}

            {!lista.cargando && lista.error && (
              <tr><td colSpan={puedeEscribir ? 6 : 5} className="p-10 text-center text-red-500">{lista.error.message}</td></tr>
            )}

            {!lista.cargando && !lista.error && lista.items.length === 0 && (
              <tr><td colSpan={puedeEscribir ? 6 : 5} className="p-10 text-center text-neutral-500">
                {lista.texto ? `Sin resultados para "${lista.texto}".` : 'No hay pilotos registrados.'}
              </td></tr>
            )}

            {!lista.cargando && !lista.error && lista.items.map(piloto => (
              <tr key={piloto.pilot_id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-neutral-800 flex items-center justify-center text-red-500 font-bold flex-shrink-0">
                      {piloto.name.charAt(0)}{piloto.last_name.charAt(0)}
                    </div>
                    <div>
                      <p className="font-bold text-white">{piloto.name} <span className="uppercase">{piloto.last_name}</span></p>
                    </div>
                  </div>
                </td>
                <td className="p-4 text-neutral-300 text-sm">{piloto.nationality || <span className="text-neutral-600">—</span>}</td>
                <td className="p-4 text-neutral-300 text-sm">{piloto.team_brand || <span className="text-neutral-600">—</span>}</td>
                <td className="p-4">
                  <div className="flex flex-wrap gap-1">
                    {piloto.categories?.length
                      ? piloto.categories.map(id => (
                          <span key={id} className="px-2 py-0.5 bg-neutral-800 text-neutral-300 text-[11px] rounded font-bold">
                            {nombreCategoria(id)}
                          </span>
                        ))
                      : <span className="text-neutral-600">—</span>}
                  </div>
                </td>
                <td className="p-4 text-right">
                  {/* La insignia es el interruptor: se pulsa y cambia. Antes
                      solo informaba y no había forma de dar de baja a nadie
                      salvo borrarlo. Sin permiso de escritura se queda como
                      etiqueta, sin prometer algo que el backend rechazaría. */}
                  {puedeEscribir ? (
                    <button
                      type="button"
                      onClick={() => alternarActivo(piloto)}
                      title={piloto.is_active ? 'Dar de baja' : 'Reactivar'}
                      className={`px-3 py-1 text-xs font-bold rounded-full border transition-colors ${
                        piloto.is_active
                          ? 'bg-green-500/10 text-green-500 border-green-600/40 hover:bg-green-500/20'
                          : 'bg-neutral-700/30 text-neutral-500 border-neutral-700 hover:text-neutral-300 hover:border-neutral-500'
                      }`}
                    >
                      {piloto.is_active ? 'ACTIVO' : 'INACTIVO'}
                    </button>
                  ) : (
                    <span className={`px-3 py-1 text-xs font-bold rounded-full ${
                      piloto.is_active ? 'bg-green-500/10 text-green-500' : 'bg-neutral-700/30 text-neutral-500'
                    }`}>
                      {piloto.is_active ? 'ACTIVO' : 'INACTIVO'}
                    </span>
                  )}
                </td>
                {puedeEscribir && (
                  <td className="p-4 text-right whitespace-nowrap">
                    <button onClick={() => openEditForm(piloto)} className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-700 transition-colors"><Pencil size={15}/></button>
                    <button onClick={() => setPorBorrar(piloto)} className="p-2 rounded-lg text-neutral-400 hover:text-red-500 hover:bg-red-500/10 transition-colors"><Trash2 size={15}/></button>
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
        titulo={t('Eliminar piloto')}
        mensaje={porBorrar ? `Se va a eliminar ${porBorrar.name} ${porBorrar.last_name}.` : ''}
        onCancelar={() => setPorBorrar(null)}
        onConfirmar={confirmarBorrado}
      />
    </div>
  )
}
