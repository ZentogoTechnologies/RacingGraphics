import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';

const orden = [1, 2, 3, 4, 5, 6, 10, 7, 9, 8];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 880 }, deviceScaleFactor: 2 });
await p.goto('file://' + process.argv[2], { waitUntil: 'networkidle' });

for (let i = 0; i < orden.length; i++) {
  const el = await p.$('#p' + orden[i]);
  if (!el) { console.log('falta #p' + orden[i]); continue; }
  const n = String(i + 1).padStart(2, '0');
  await el.screenshot({ path: process.argv[3] + '/pantalla-' + n + '.png' });
}

console.log(orden.length + ' pantallas renderizadas');
await b.close();
