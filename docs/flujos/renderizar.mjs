import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
const b = await chromium.launch();
const p = await b.newPage({ viewport:{width:1240,height:2000}, deviceScaleFactor:2 });
await p.goto('file://' + process.argv[2], { waitUntil:'networkidle' });
await p.screenshot({ path: process.argv[3], fullPage:true });
const h = await p.evaluate(()=>document.body.scrollHeight);
console.log('alto de página:', h, 'px');
await b.close();
