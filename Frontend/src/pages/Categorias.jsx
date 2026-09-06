import { t } from '../i18n'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft, Pencil, Trash2, Plus, X, ChevronUp, ChevronDown, ChevronsUpDown, Loader2,
  Scissors, Upload, ImageIcon,
} from 'lucide-react'
import ModuleHeader from '../components/shared/ModuleHeader'
import Pagination from '../components/shared/Pagination'
import ConfirmDialog from '../components/shared/ConfirmDialog'
import {
  borrarLogoCategoria, categoriasApi, quitarFondoLogoCategoria,
  subirLogoCategoria, urlLogoCategoria,
} from '../api/registro'
import { useListado } from '../hooks/useListado'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { useDisciplina } from '../context/DisciplinaContext'

// Sin category_id: lo asigna el servidor tomando el siguiente libre.
// Sin discipline: la hereda del selector global, que es el que decide qué
// se está viendo. Crear aquí una categoría de la otra disciplina solo
// serviría para que desapareciera de la lista al guardarla.
const EMPTY_CATEGORY = {
  category_name: '', description: '', sub_categories: [],
}

// El id de una subcategoría es a lo que apunta el `sub_category_id` de cada
// vehículo, así que no se reutiliza ni se edita a mano: cambiarlo dejaría a
// los carros señalando a otra cosa. Se toma siempre el siguiente libre.
function siguienteSubId(subs) {
  return subs.reduce((mayor, s) => Math.max(mayor, s.sub_category_id), 0) + 1
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

export default function CategoriasModule() {
  const toast = useToast()
  const { puedeEscribir } = useAuth()
  const { disciplina, etiqueta: etiquetaDisciplina } = useDisciplina()

  const filtros = useMemo(() => ({ discipline: disciplina }), [disciplina])
  const lista = useListado(categoriasApi, { ordenInicial: 'category_name', filtros })

  const [isFormOpen,    setIsFormOpen]    = useState(false)
  const [currentEditId, setCurrentEditId] = useState(null)
  const [categoryForm,  setCategoryForm]  = useState(EMPTY_CATEGORY)
  const [guardando,     setGuardando]     = useState(false)
  const [porBorrar,     setPorBorrar]     = useState(null)

  // El logo no viaja en el JSON de la categoría sino como archivo, y en un
  // alta todavía no hay id al que asociarlo: se guarda aquí y se sube en
  // cuanto la categoría existe.
  const [logo,       setLogo]       = useState(null)   // File sin subir
  const [logoActual, setLogoActual] = useState(null)   // ruta ya guardada
  const inputLogo = useRef(null)

  const [previaLogo, setPreviaLogo] = useState(null)
  useEffect(() => {
    if (!logo) { setPreviaLogo(null); return }
    const url = URL.createObjectURL(logo)
    setPreviaLogo(url)
    return () => URL.revokeObjectURL(url)
  }, [logo])

  const vistaLogo = previaLogo || urlLogoCategoria(logoActual)

  const limpiarLogo = () => {
    setLogo(null); setLogoActual(null)
    if (inputLogo.current) inputLogo.current.value = ''
  }

  const [recortando, setRecortando] = useState(false)

  /* Deja transparente el fondo del logo. Trabaja sobre el archivo ya
     guardado, así que necesita la categoría creada: en un alta todavía no
     hay nada en el servidor sobre lo que trabajar. */
  const recortarLogo = async () => {
    if (!currentEditId) return
    setRecortando(true)
    try {
      const c = await quitarFondoLogoCategoria(currentEditId)
      // logo_url y no logo: aquí se guarda la ruta, que es lo que espera
      // urlLogoCategoria. El campo `logo` es solo el nombre del archivo y
      // daría una dirección rota.
      //
      // El recorte se guarda como PNG, así que la extensión cambia y el
      // navegador no puede servir la imagen anterior de su caché.
      setLogoActual(c.logo_url || null)
      lista.recargar()
      toast.exito('Fondo quitado', 'El logo queda recortado sobre transparente')
    } catch (err) {
      toast.error('No se pudo quitar el fondo', err.message)
    } finally {
      setRecortando(false)
    }
  }

  const quitarLogo = async () => {
    if (!currentEditId) { limpiarLogo(); return }
    try {
      await borrarLogoCategoria(currentEditId)
      limpiarLogo()
      lista.recargar()
      toast.exito('Logo quitado', '')
    } catch (err) {
      toast.error('No se pudo quitar el logo', err.message)
    }
  }

  const openAddForm  = () => { setCategoryForm(EMPTY_CATEGORY); setCurrentEditId(null); limpiarLogo(); setIsFormOpen(true) }
  const closeForm    = () => { setIsFormOpen(false); setCurrentEditId(null); setCategoryForm(EMPTY_CATEGORY); limpiarLogo() }
  const handleFormToggle = () => isFormOpen ? closeForm() : openAddForm()

  // Si falla el logo no se deshace la categoría: se avisa y ya, que
  // reintentarlo es abrir y elegir el archivo otra vez.
  const subirLogo = async (id) => {
    try {
      await subirLogoCategoria(id, logo)
    } catch (err) {
      toast.error('La categoría se guardó, pero el logo no', err.message)
    }
  }

  const openEditForm = (categoria) => {
    setCategoryForm({
      category_name: categoria.category_name,
      description: categoria.description || '',
      sub_categories: categoria.sub_categories || [],
    })
    setCurrentEditId(categoria.category_id)

    setLogo(null)
    setLogoActual(categoria.logo_url || null)
    if (inputLogo.current) inputLogo.current.value = ''

    setIsFormOpen(true)
  }

  const agregarSub = () => {
    setCategoryForm(f => ({
      ...f,
      sub_categories: [
        ...f.sub_categories,
        { sub_category_id: siguienteSubId(f.sub_categories), sub_category_name: '' },
      ],
    }))
  }

  const renombrarSub = (id, nombre) => {
    setCategoryForm(f => ({
      ...f,
      sub_categories: f.sub_categories.map(s =>
        s.sub_category_id === id ? { ...s, sub_category_name: nombre } : s,
      ),
    }))
  }

  const quitarSub = (id) => {
    setCategoryForm(f => ({
      ...f,
      sub_categories: f.sub_categories.filter(s => s.sub_category_id !== id),
    }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setGuardando(true)

    // Una fila en blanco es una que abrieron y no llenaron; se descarta en
    // vez de guardar una subcategoría sin nombre.
    const subs = categoryForm.sub_categories
      .filter(s => s.sub_category_name.trim())
      .map(s => ({ ...s, sub_category_name: s.sub_category_name.trim() }))

    try {
      let id = currentEditId

      if (currentEditId) {
        // El category_id no viaja en el update: es la llave por la que se
        // busca el documento, no un campo editable.
        // La disciplina no se manda al actualizar: no se cambia desde
        // aquí, y omitirla deja intacta la que ya tiene el documento.
        await categoriasApi.actualizar(currentEditId, {
          category_name: categoryForm.category_name,
          description: categoryForm.description || null,
          sub_categories: subs,
        })
        toast.exito('Categoría actualizada', categoryForm.category_name)
        if (logo) await subirLogo(currentEditId)
      } else {
        // Sin category_id: lo pone el servidor. Calcularlo en el navegador
        // haría chocar a dos personas que abran el formulario a la vez.
        const creada = await categoriasApi.crear({
          category_name: categoryForm.category_name,
          discipline: disciplina,
          description: categoryForm.description || null,
          sub_categories: subs,
        })
        id = creada.category_id
        toast.exito('Categoría creada', `${creada.category_name} · ${etiquetaDisciplina}`)
        // Después de crear porque hasta ahora no había id al que asociarlo.
        if (logo) await subirLogo(creada.category_id)
      }
      /* Se sigue en la ficha después de guardar, no se vuelve al listado.
         Al dar de alta hay cosas que solo se pueden hacer con el registro ya
         creado —subir su imagen, recortarle el fondo— y devolver a la lista
         obligaba a buscarlo otra vez para entrar a editarlo.

         El id se fija aquí: sin esto la ficha seguiría en modo alta y volver
         a guardar crearía un registro repetido. */
      setCurrentEditId(id)

      // El logo ya subio; se suelta para que no vuelva a mandarse.
      setLogo(null)
      lista.recargar()
    } catch (err) {
      // El formulario se queda abierto con lo escrito: si el guardado
      // falló, perder lo cargado sería el peor final posible.
      toast.error(currentEditId ? 'No se pudo actualizar' : 'No se pudo crear', err.message)
    } finally {
      setGuardando(false)
    }
  }

  const confirmarBorrado = async () => {
    const categoria = porBorrar
    setPorBorrar(null)

    try {
      await categoriasApi.eliminar(categoria.category_id)
      toast.exito('Categoría eliminada', categoria.category_name)
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
        entityName="categorías"
        searchText={lista.texto}
        onSearchChange={lista.setTexto}
        isFormOpen={isFormOpen}
        onFormToggle={handleFormToggle}
        addButtonLabel="NUEVA CATEGORÍA"
        puedeCrear={puedeEscribir}
        exportData={() => categoriasApi.listar({ ...filtros, search: lista.texto || undefined, sort_by: lista.sortBy, sort_dir: lista.sortDir }).then(p => p.items)}
        onExportError={m => toast.error('No se pudo exportar', m)}
        exportFileName="categorias"
        exportColumnMap={{ category_name: 'Categoría', discipline: 'Disciplina', description: 'Descripción' }}
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
            {currentEditId ? t('Editar categoría') : t('Nueva categoría')}
          </h3>
        </div>

        <form onSubmit={handleSave} className="bg-[#141414] p-6 rounded-xl border border-red-600/30 mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Nombre')}</label>
            <input required type="text" value={categoryForm.category_name}
              onChange={e => setCategoryForm({ ...categoryForm, category_name: e.target.value })}
              className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
          </div>
          <div>
            <label className="block text-neutral-400 text-xs mb-1 uppercase">{t('Descripción')}</label>
            <input type="text" value={categoryForm.description}
              onChange={e => setCategoryForm({ ...categoryForm, description: e.target.value })}
              className="w-full bg-[#0a0a0a] border border-neutral-800 rounded p-2 focus:border-red-600 focus:outline-none text-white"/>
          </div>
          {/* Logo del campeonato: TCR, GT Challenge, Fórmula 1. Sale junto
              al nombre en la tabla. */}
          <div className="col-span-full flex items-center gap-4 border-t border-neutral-800 pt-4 mt-2">
            <div className="w-20 h-20 rounded-lg bg-[#0a0a0a] border border-neutral-800 overflow-hidden flex items-center justify-center flex-shrink-0">
              {vistaLogo
                ? <img src={vistaLogo} alt="" className="w-full h-full object-contain"/>
                : <ImageIcon size={22} className="text-neutral-700"/>}
            </div>

            <div className="min-w-0">
              <label className="block text-neutral-400 text-xs mb-2 uppercase">
                {t('Logo de la categoría')}
              </label>

              <input
                type="file" accept="image/*" ref={inputLogo} className="hidden"
                onChange={e => setLogo(e.target.files?.[0] || null)}
              />

              <div className="flex flex-wrap gap-2">
                <button
                  type="button" onClick={() => inputLogo.current?.click()}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-700 text-neutral-300 hover:border-blue-500 hover:text-blue-400 transition-colors font-bold text-xs"
                >
                  <Upload size={14}/>
                  {vistaLogo ? 'CAMBIAR' : 'ELEGIR LOGO'}
                </button>

                {/* Con logo guardado se ofrecen los tres; sin él, solo el de
                    elegir. El recorte trabaja sobre el archivo del servidor,
                    así que necesita la categoría ya creada. */}
                {logoActual && currentEditId && (
                  <button
                    type="button" onClick={recortarLogo} disabled={recortando}
                    title="Deja transparente el fondo, si es de un solo color"
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-700 text-neutral-300 hover:border-green-500 hover:text-green-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-bold text-xs"
                  >
                    {recortando
                      ? <Loader2 size={14} className="animate-spin"/>
                      : <Scissors size={14}/>}
                    {recortando ? 'QUITANDO…' : 'QUITAR FONDO'}
                  </button>
                )}

                {vistaLogo && (
                  <button
                    type="button" onClick={quitarLogo}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg border border-neutral-800 text-neutral-500 hover:border-red-600 hover:text-red-500 transition-colors font-bold text-xs"
                  >
                    <X size={14}/> {t('QUITAR')}
                  </button>
                )}
              </div>

              <p className="text-[11px] text-neutral-600 mt-2">
                {logo ? 'Se sube al guardar la categoría.' : 'Sale junto al nombre en el listado.'}
              </p>
            </div>
          </div>

          <div className="col-span-full mt-2">
            <div className="flex items-center justify-between mb-2">
              <label className="text-neutral-400 text-xs uppercase">
                Subcategorías ({categoryForm.sub_categories.length})
              </label>
              <button
                type="button" onClick={agregarSub}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-neutral-700 text-neutral-300 hover:border-red-600 hover:text-red-400 transition-colors text-xs font-bold"
              >
                <Plus size={14}/> {t('AGREGAR')}
              </button>
            </div>

            {categoryForm.sub_categories.length === 0 ? (
              <p className="text-sm text-neutral-600 py-2">
                Sin subcategorías. Son las divisiones dentro de la categoría (GTS, GTS Jr, V8…) y
                es lo que se elige después en cada vehículo.
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {categoryForm.sub_categories.map(sub => (
                  <div key={sub.sub_category_id} className="flex items-center gap-2">
                    {/* El id se muestra pero no se edita: es a lo que apunta
                        el sub_category_id de cada vehículo. */}
                    <span className="w-10 text-center text-xs font-mono text-neutral-600 flex-shrink-0">
                      #{sub.sub_category_id}
                    </span>
                    <input
                      type="text" value={sub.sub_category_name}
                      placeholder={t('Nombre de la subcategoría')}
                      onChange={e => renombrarSub(sub.sub_category_id, e.target.value)}
                      className="flex-1 bg-[#0a0a0a] border border-neutral-800 rounded p-2 text-sm focus:border-red-600 focus:outline-none text-white"
                    />
                    <button
                      type="button" onClick={() => quitarSub(sub.sub_category_id)}
                      className="p-2 rounded-lg text-neutral-500 hover:text-red-500 hover:bg-red-500/10 transition-colors flex-shrink-0"
                      aria-label={t('Quitar subcategoría')}
                    >
                      <X size={15}/>
                    </button>
                  </div>
                ))}
              </div>
            )}
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
        <table className="w-full min-w-[620px] text-left border-collapse">
          <thead>
            <tr className="bg-neutral-900 border-b border-neutral-800 text-neutral-400 text-xs uppercase tracking-wider">
              {/* Ni el ID ni la disciplina se muestran: el ID es interno y
                  la disciplina ya la fija el selector global, así que la
                  columna repetiría el mismo valor en todas las filas. */}
              <th className="p-4 font-bold"><span className="flex items-center">{t('Categoría')} <SortIcon columnKey="category_name" sortField={lista.sortBy} sortDirection={lista.sortDir} onSort={lista.ordenarPor}/></span></th>
              <th className="p-4 font-bold">{t('Subcategorías')}</th>
              {puedeEscribir && <th className="p-4 font-bold text-right">{t('Acciones')}</th>}
            </tr>
          </thead>
          <tbody>
            {lista.cargando && (
              <tr><td colSpan={puedeEscribir ? 3 : 2} className="p-10 text-center">
                <Loader2 className="w-6 h-6 animate-spin mx-auto text-red-600"/>
              </td></tr>
            )}

            {!lista.cargando && lista.error && (
              <tr><td colSpan={puedeEscribir ? 3 : 2} className="p-10 text-center text-red-500">{lista.error.message}</td></tr>
            )}

            {!lista.cargando && !lista.error && lista.items.length === 0 && (
              <tr><td colSpan={puedeEscribir ? 3 : 2} className="p-10 text-center text-neutral-500">
                {lista.texto ? `Sin resultados para "${lista.texto}".` : 'No hay categorías registradas.'}
              </td></tr>
            )}

            {!lista.cargando && !lista.error && lista.items.map(categoria => (
              <tr key={categoria.category_id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    {/* Sin logo no se deja el hueco: la fila se corre y se
                        lee igual. Con hueco vacío parecería que falta algo
                        en todas las categorías que no lo tienen. */}
                    {categoria.logo_url && (
                      <img
                        src={urlLogoCategoria(categoria.logo_url)}
                        alt=""
                        className="w-10 h-10 object-contain flex-shrink-0"
                      />
                    )}
                    <div className="min-w-0">
                      <p className="font-bold text-white italic">{categoria.category_name}</p>
                      {categoria.description && <p className="text-xs text-neutral-500 mt-0.5">{categoria.description}</p>}
                    </div>
                  </div>
                </td>
                <td className="p-4 text-neutral-400 text-sm">
                  {categoria.sub_categories?.length
                    ? categoria.sub_categories.map(s => s.sub_category_name).join(', ')
                    : <span className="text-neutral-600">—</span>}
                </td>
                {puedeEscribir && (
                  <td className="p-4 text-right whitespace-nowrap">
                    <button onClick={() => openEditForm(categoria)} className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-700 transition-colors"><Pencil size={15}/></button>
                    <button onClick={() => setPorBorrar(categoria)} className="p-2 rounded-lg text-neutral-400 hover:text-red-500 hover:bg-red-500/10 transition-colors"><Trash2 size={15}/></button>
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
        titulo={t('Eliminar categoría')}
        mensaje={porBorrar ? `Se va a eliminar ${porBorrar.category_name}.` : ''}
        onCancelar={() => setPorBorrar(null)}
        onConfirmar={confirmarBorrado}
      />
    </div>
  )
}
