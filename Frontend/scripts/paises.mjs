/* ==========================================================================
   REGENERAR LA TABLA DE PAÍSES Y SUS BANDERAS

   Uso:  npm pack flag-icons@7.5.0 && tar -xzf flag-icons-*.tgz
         node scripts/paises.mjs <carpeta-del-paquete-extraido>

   Hace dos cosas:
     · copia las banderas 4x3 a Casparcg/template/img/banderas, que es
       donde las lee la plantilla al aire y de donde las sirve el backend;
     · escribe src/data/paises.js con el código ISO y el nombre en español
       y en inglés.

   Los nombres salen de ICU (Intl.DisplayNames), que ya viene en Node: no
   hay que mantener a mano una lista de 255 traducciones.

   Se filtran los archivos que no son un país ISO 3166-1 alfa-2 —gb-eng,
   eu, xk—: son banderas de verdad pero no valen como nacionalidad y
   ninguna llamada de ICU les da nombre.
========================================================================== */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const AQUI     = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(AQUI, '..')
const RAIZ     = path.resolve(FRONTEND, '..')
const BANDERAS = path.join(RAIZ, 'Casparcg', 'template', 'img', 'banderas')
const SALIDA   = path.join(FRONTEND, 'src', 'data', 'paises.js')

const paquete = process.argv[2]
if (!paquete) {
  console.error('Falta la carpeta del paquete flag-icons extraído.')
  process.exit(1)
}

const origen = path.join(paquete, 'flags', '4x3')
const es = new Intl.DisplayNames(['es'], { type: 'region' })
const en = new Intl.DisplayNames(['en'], { type: 'region' })

const paises = []
for (const archivo of fs.readdirSync(origen)) {
  const codigo = path.basename(archivo, '.svg')
  if (!/^[a-z]{2}$/.test(codigo)) continue

  const iso = codigo.toUpperCase()
  let nombre
  try { nombre = es.of(iso) } catch { continue }
  if (!nombre || nombre === iso) continue

  paises.push({ codigo, nombre, en: en.of(iso) })
}
paises.sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))

fs.mkdirSync(BANDERAS, { recursive: true })
for (const p of paises) {
  fs.copyFileSync(path.join(origen, `${p.codigo}.svg`), path.join(BANDERAS, `${p.codigo}.svg`))
}
fs.copyFileSync(path.join(paquete, 'LICENSE'), path.join(BANDERAS, 'LICENSE-flag-icons.txt'))

const filas = paises
  .map(p => `  ${JSON.stringify([p.codigo, p.nombre, p.en])},`)
  .join('\n')

const contenido = `${fs.readFileSync(SALIDA, 'utf8').split('export const PAISES = ')[0]}export const PAISES = [
${filas}
].map(([codigo, nombre, en]) => ({ codigo, nombre, en }))
${fs.readFileSync(SALIDA, 'utf8').split(').map(([codigo, nombre, en]) => ({ codigo, nombre, en }))')[1] || ''}`

fs.writeFileSync(SALIDA, contenido)
console.log(`${paises.length} países, banderas en ${BANDERAS}`)
