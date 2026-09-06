// ─── CRUD de pilotos, vehículos y categorías ──────────────────
// Los listados vienen paginados desde el backend: {items, total, skip,
// limit}. La paginación, la búsqueda y el ordenamiento ocurren en Mongo,
// así que la página que se ve siempre corresponde al total que se muestra.

import { avisarSesionExpirada, cabeceraAuth } from './auth'

const BASE =
  // Ruta relativa: el frontend pide a quien se lo sirvió. Así vale
  // igual en localhost, en la red local o a través del túnel, sin
  // tener que recompilar con la dirección de turno.
  import.meta.env.VITE_API_URL || '/api/v1'

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// FastAPI devuelve `detail` como string en los HTTPException que lanzamos,
// pero como lista de objetos cuando falla la validación del cuerpo. Los dos
// casos tienen que llegar al toast como una frase legible.
function leerDetalle(payload, status) {
  const detail = payload?.detail

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    return detail
      .map(e => {
        const campo = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : null
        return campo ? `${campo}: ${e.msg}` : e.msg
      })
      .join(' · ')
  }

  return `Error ${status}`
}

async function pedir(ruta, { method = 'GET', body } = {}) {
  let response
  try {
    response = await fetch(`${BASE}${ruta}`, {
      method,
      headers: {
        ...cabeceraAuth(),
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('No se pudo contactar al backend', 0)
  }

  if (response.status === 401) {
    avisarSesionExpirada()
    throw new ApiError('La sesión expiró, vuelve a iniciar sesión', 401)
  }

  const payload = await response.json().catch(() => null)

  if (!response.ok) throw new ApiError(leerDetalle(payload, response.status), response.status)

  return payload
}

// Arma el query string saltando lo vacío: sin esto se manda `search=` y el
// backend recibe una cadena vacía en vez de ausencia de filtro.
function query(params = {}) {
  const qs = new URLSearchParams()

  Object.entries(params).forEach(([clave, valor]) => {
    if (valor === undefined || valor === null || valor === '') return
    qs.append(clave, valor)
  })

  const texto = qs.toString()
  return texto ? `?${texto}` : ''
}

function recurso(ruta) {
  return {
    listar:    (params) => pedir(`${ruta}/${query(params)}`),
    obtener:   (id)     => pedir(`${ruta}/${id}`),
    crear:     (datos)  => pedir(`${ruta}/`, { method: 'POST', body: datos }),
    actualizar:(id, d)  => pedir(`${ruta}/${id}`, { method: 'PUT', body: d }),
    eliminar:  (id)     => pedir(`${ruta}/${id}`, { method: 'DELETE' }),
  }
}

export const pilotosApi    = recurso('/pilots')

// ─── Foto del piloto ──────────────────────────────────────────────
// El archivo va al disco del backend y en la base queda solo su ruta.
// Guardarlo dentro del documento obligaría a arrastrar la imagen en cada
// listado, y las plantillas de CasparCG piden la foto por URL.

export const urlFotoPiloto = (photo) =>
  photo ? `${ORIGEN}/public/${photo}` : null

export const subirFotoPiloto = (pilotId, archivo) =>
  subirArchivo(`/pilots/${pilotId}/foto`, archivo)

// Recorta al piloto de su fondo. Trabaja sobre la foto que ya está
// guardada, así que no hay que volver a subirla.
export const quitarFondoPiloto = (pilotId) =>
  pedir(`/pilots/${pilotId}/foto/sin-fondo`, { method: 'POST' })

export const borrarFotoPiloto = (pilotId) =>
  pedir(`/pilots/${pilotId}/foto`, { method: 'DELETE' })
export const vehiculosApi  = recurso('/vehicles')

// ─── Fotos del vehículo ───────────────────────────────────────
// Hasta cuatro por carro, en orden. Cuál se saca al aire se decide al
// graficar, así que aquí solo se suben, se listan y se borran.

export const subirFotoVehiculo = (vehicleId, archivo) =>
  subirArchivo(`/vehicles/${vehicleId}/fotos`, archivo)

// Recorta el carro de su fondo. Hay que decir cuál de las dos fotos.
export const quitarFondoVehiculo = (vehicleId, archivo) =>
  pedir(`/vehicles/${vehicleId}/fotos/${encodeURIComponent(archivo)}/sin-fondo`,
        { method: 'POST' })

export const borrarFotoVehiculo = (vehicleId, archivo) =>
  pedir(`/vehicles/${vehicleId}/fotos/${encodeURIComponent(archivo)}`, { method: 'DELETE' })

// El backend ya devuelve photo_urls relativas al origen; esto las
// completa para usarlas en un <img>.
export const urlFotoVehiculo = (ruta) => (ruta ? `${ORIGEN}${ruta}` : null)
export const categoriasApi = recurso('/categories')

// ─── Logo de la categoría ─────────────────────────────────────────
// El del campeonato: TCR, GT Challenge, Fórmula 1.

export const subirLogoCategoria = (categoryId, archivo) =>
  subirArchivo(`/categories/${categoryId}/logo`, archivo)

// Deja transparente el fondo del logo. Va por color y no por el modelo
// que usan las fotos: un logotipo con letras no es una figura que un
// modelo de segmentación sepa reconocer.
export const quitarFondoLogoCategoria = (categoryId) =>
  pedir(`/categories/${categoryId}/logo/sin-fondo`, { method: 'POST' })

export const borrarLogoCategoria = (categoryId) =>
  pedir(`/categories/${categoryId}/logo`, { method: 'DELETE' })

export const urlLogoCategoria = (ruta) => (ruta ? `${ORIGEN}${ruta}` : null)

// Solo responde al usuario dueño; a cualquier otro rol el backend le
// devuelve 403 aunque llame la ruta directamente.
export const eventosApi    = recurso('/events')

// ─── Imagen del evento ────────────────────────────────────────────
// Logo del campeonato o imagen alusiva. Sale en el gráfico de Evento, a
// la derecha del nombre, con el logo del autódromo al otro lado.

export const subirImagenEvento = (eventId, archivo) =>
  subirArchivo(`/events/${eventId}/imagen`, archivo)

export const borrarImagenEvento = (eventId) =>
  pedir(`/events/${eventId}/imagen`, { method: 'DELETE' })

export const urlImagenEvento = (ruta) => (ruta ? `${ORIGEN}${ruta}` : null)

// Las sesiones no son un recurso aparte: viven dentro del evento y las
// dos operaciones devuelven el evento entero ya recalculado, con el
// nombre y el número que le tocó a la sesión nueva.
export const agregarSesion = (eventId, datos) =>
  pedir(`/events/${eventId}/sesiones`, { method: 'POST', body: datos })

export const quitarSesion = (eventId, numeroOrden) =>
  pedir(`/events/${eventId}/sesiones/${numeroOrden}`, { method: 'DELETE' })

// ─── Ajustes en caliente ──────────────────────────────────────
// La ruta del current.xml se cambia sin reiniciar el backend: queda
// guardada en la base y se aplica en la siguiente lectura.

export const leerAjustes = () => pedir('/settings/')

/* Carpetas y XML del servidor, para llegar al current.xml navegando. Sin
   ruta devuelve las unidades de disco. Es el disco del servidor, no el de
   quien mira el panel: un <input type=file> del navegador entrega el
   archivo pero nunca su ruta, y la ruta es justo lo que se guarda. */
export const explorarRutaXml = (ruta) =>
  pedir(`/settings/timing/explorar${ruta ? `?ruta=${encodeURIComponent(ruta)}` : ''}`)

export const probarRutaXml = (ruta) =>
  pedir('/settings/timing/probar', { method: 'POST', body: { timing_xml_path: ruta } })

export const guardarRutaXml = (ruta) =>
  pedir('/settings/timing', { method: 'PUT', body: { timing_xml_path: ruta } })


// ─── Logo del cliente ─────────────────────────────────────────────
// El del autódromo que usa el software. Las plantillas apuntan todas al
// mismo archivo, así que cambiarlo aquí lo cambia en los 22 gráficos.

export const subirLogoCliente = (archivo) =>
  subirArchivo('/settings/logo', archivo)

export const quitarLogoCliente = () =>
  pedir('/settings/logo', { method: 'DELETE' })

export const urlLogoCliente = (ruta) => (ruta ? `${ORIGEN}${ruta}` : null)


// ─── Trazados ─────────────────────────────────────────────────
// Un mismo recinto se corre de varias formas —pista corta, pista larga,
// cuarto de milla— y cada una tiene su imagen. El gráfico de Circuito usa
// el que esté marcado como activo.

// Las imágenes se sirven fuera del prefijo del API, así que se recorta.
const ORIGEN = BASE.replace(/\/api\/v1\/?$/, '')

export const urlImagenTrazado = (imagen) =>
  imagen ? `${ORIGEN}/media/circuits/${imagen}` : null

// Las tipografías empaquetadas con el software. La URL que devuelve cada
// una apunta a /media/fonts, que sirve los mismos archivos que usan las
// plantillas: así el panel enseña exactamente la letra que va a salir.
// El idioma vale para la interfaz y para los gráficos: al cambiarlo, el
// backend reescribe además el archivo de textos que leen las plantillas.
export const listarIdiomas = () => pedir('/settings/idiomas')

export const elegirIdioma = (id) =>
  pedir(`/settings/idiomas/${id}`, { method: 'PUT' })

export const listarFuentes = () => pedir('/settings/fuentes')

export const elegirFuente = (id) =>
  pedir(`/settings/fuentes/${id}`, { method: 'PUT' })

export const urlFuente = (ruta) => `${ORIGEN}${ruta}`

export const listarTrazados = () => pedir('/settings/trazados')

export const crearTrazado = (datos) =>
  pedir('/settings/trazados', { method: 'POST', body: datos })

export const editarTrazado = (id, datos) =>
  pedir(`/settings/trazados/${id}`, { method: 'PUT', body: datos })

export const activarTrazado = (id) =>
  pedir(`/settings/trazados/${id}/activar`, { method: 'PUT' })

export const borrarTrazado = (id) =>
  pedir(`/settings/trazados/${id}`, { method: 'DELETE' })

export const imagenTrazadoPorRuta = (id, ruta) =>
  pedir(`/settings/trazados/${id}/imagen`, { method: 'PUT', body: { ruta } })

// La subida no pasa por `pedir`: con FormData el navegador tiene que poner
// él mismo el Content-Type, porque lleva el boundary que separa las partes.
// Fijarlo a application/json dejaría el cuerpo ilegible para el servidor.
async function subirArchivo(ruta, archivo) {
  const cuerpo = new FormData()
  cuerpo.append('archivo', archivo)

  let response
  try {
    response = await fetch(`${BASE}${ruta}`, {
      method: 'POST',
      headers: { ...cabeceraAuth() },
      body: cuerpo,
    })
  } catch {
    throw new ApiError('No se pudo contactar al backend', 0)
  }

  if (response.status === 401) {
    avisarSesionExpirada()
    throw new ApiError('La sesión expiró, vuelve a iniciar sesión', 401)
  }

  const payload = await response.json().catch(() => null)

  if (!response.ok) throw new ApiError(leerDetalle(payload, response.status), response.status)

  return payload
}

export const subirImagenTrazado = (id, archivo) =>
  subirArchivo(`/settings/trazados/${id}/imagen`, archivo)

export const usuariosApi   = recurso('/users')

// Apaga CasparCG, el frontend y el backend. MongoDB no se toca. Solo
// responde a owner y admin; a un estándar el backend le da 403.
//
// El backend se cierra a sí mismo justo después de contestar, así que
// esta llamada devuelve el resumen y acto seguido el API deja de existir:
// quien la use no debe encadenar nada detrás.
export const apagarSistema = () => pedir('/system/shutdown', { method: 'POST' })
