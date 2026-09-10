// ─── El asistente de instalación ──────────────────────────────
//
// Estas rutas son las únicas del backend que funcionan sin sesión: cuando
// se usan todavía no existe ningún usuario, así que no hay con qué entrar.
// A cambio exigen el token de un solo uso que el instalador dejó en el
// disco y puso en la dirección al abrir el navegador.
//
// El token se guarda en localStorage, no en sessionStorage. La segunda
// opción parecía la prudente —vale para una instalación, no tiene por qué
// sobrevivir a cerrar el navegador— pero sessionStorage es de una sola
// pestaña: abrir el asistente en otra, o duplicar la que hay, dejaba
// fuera a quien estaba instalando, sin más salida que buscar el token en
// el disco. Cambiarlo no abre nada: el token sigue siendo obligatorio,
// sigue sin salir de este navegador, y el backend cierra el asistente al
// terminar, que es lo que de verdad lo caduca.

const BASE = import.meta.env.VITE_API_URL || '/api/v1'
const CLAVE_TOKEN = 'rcs.setup-token'

export class SetupError extends Error {
  constructor(message, status = 0) {
    super(message)
    this.name = 'SetupError'
    this.status = status
  }
}

// ── El token ─────────────────────────────────────────────────

export function leerToken() {
  try {
    return localStorage.getItem(CLAVE_TOKEN) || ''
  } catch {
    return ''
  }
}

export function guardarToken(token) {
  try {
    if (token) localStorage.setItem(CLAVE_TOKEN, token)
  } catch { /* almacenamiento bloqueado: dura lo que la petición */ }
}

/** Al cerrar el asistente. Lo que ya no sirve, no se guarda. */
export function olvidarToken() {
  try {
    localStorage.removeItem(CLAVE_TOKEN)
  } catch { /* nada que hacer */ }
}

/**
 * Recoge el token de la dirección y lo guarda.
 *
 * El instalador abre el navegador en /instalacion?token=… Se saca de ahí
 * y se limpia la barra de direcciones, para que el token no quede a la
 * vista ni se copie sin querer al compartir el enlace con alguien.
 */
export function recogerTokenDeLaUrl() {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')

  if (token) {
    guardarToken(token)
    const limpia = window.location.pathname + window.location.hash
    window.history.replaceState({}, '', limpia)
  }

  return leerToken()
}

// ── Peticiones ───────────────────────────────────────────────

function leerDetalle(payload, status) {
  const detail = payload?.detail

  if (typeof detail === 'string') return detail

  // FastAPI manda una lista de objetos cuando falla la validación del
  // cuerpo. Tiene que llegar a la pantalla como una frase legible.
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

async function pedir(ruta, { method = 'GET', body, conToken = true } = {}) {
  let response

  try {
    response = await fetch(`${BASE}/setup${ruta}`, {
      method,
      headers: {
        ...(conToken ? { 'X-Setup-Token': leerToken() } : {}),
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new SetupError('No se pudo contactar al backend', 0)
  }

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    throw new SetupError(leerDetalle(payload, response.status), response.status)
  }

  return payload
}

// ── Lo que usa el asistente ──────────────────────────────────

// Abierta: la consulta la app al arrancar para saber si toca instalar o
// entrar. No lleva token porque todavía puede no haberlo.
export const estado = () => pedir('/estado', { conToken: false })

export const licencia = () => pedir('/licencia')
export const red      = () => pedir('/red')

export const guardarOrganizacion = (datos) =>
  pedir('/organizacion', { method: 'POST', body: datos })

export const crearUsuarios = (datos) =>
  pedir('/usuarios', { method: 'POST', body: datos })

export const verificarRuta = (ruta) =>
  pedir('/verificar-ruta', { method: 'POST', body: { ruta } })

export const guardarCronometraje = (ruta) =>
  pedir('/cronometraje', { method: 'POST', body: { ruta } })

export const probarCasparcg  = () => pedir('/probar-casparcg', { method: 'POST' })
export const guardarCasparcg = () => pedir('/casparcg', { method: 'POST' })

export const buscarUbicacion = (q, idioma = 'es') =>
  pedir(`/buscar-ubicacion?q=${encodeURIComponent(q)}&idioma=${idioma}`)

export const interpretarUbicacion = (texto) =>
  pedir('/interpretar-ubicacion', { method: 'POST', body: { texto } })

export const guardarClima = (datos) =>
  pedir('/clima', { method: 'POST', body: datos })

export const completar = () => pedir('/completar', { method: 'POST' })

/**
 * El logo va aparte: es multipart, no JSON.
 *
 * No se pone Content-Type a mano — el navegador tiene que ponerlo él para
 * incluir el `boundary` que separa las partes. Escribirlo rompe la subida
 * de una forma que no se ve hasta que el backend responde 422.
 */
export async function subirLogo(archivo) {
  const cuerpo = new FormData()
  cuerpo.append('archivo', archivo)

  let response
  try {
    response = await fetch(`${BASE}/setup/logo`, {
      method: 'POST',
      headers: { 'X-Setup-Token': leerToken() },
      body: cuerpo,
    })
  } catch {
    throw new SetupError('No se pudo contactar al backend', 0)
  }

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    throw new SetupError(leerDetalle(payload, response.status), response.status)
  }

  return payload
}
