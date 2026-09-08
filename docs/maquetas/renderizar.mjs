import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
const b = await chromium.launch();
const p = await b.newPage({ viewport:{width:1280,height:880}, deviceScaleFactor:2 });
await p.goto('file://' + process.argv[2], { waitUntil:'networkidle' });
for (let i = 1; i <= 8; i++) {
  const el = await p.$('#p' + i);
  await el.screenshot({ path: `${process.argv[3]}/pantalla-${String(i).padStart(2,'0')}.png` });
}
console.log('8 pantallas renderizadas');
await b.close();
