// Erişilebilirlik taraması (puanlama/PUANLAMA.md, alan 5): giriş ve ana sayfa, axe-core kuralları.
// Kullanım: public/ bir yerel sunucudan yayınlanırken  node olcum/axe.mjs http://localhost:8765 çıktı.json
import { writeFileSync } from "node:fs";
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const [kok, cikti] = process.argv.slice(2);
const tarayici = await chromium.launch();
const baglam = await tarayici.newContext();
const sonuc = {};
for (const sayfa of ["giris.html", "index.html"]) {
  const p = await baglam.newPage();
  await p.goto(`${kok}/${sayfa}`, { waitUntil: "networkidle" });
  const r = await new AxeBuilder({ page: p }).analyze();
  sonuc[sayfa] = r.violations.map((v) => ({ id: v.id, etki: v.impact, adet: v.nodes.length, aciklama: v.help }));
  await p.close();
}
await tarayici.close();
writeFileSync(cikti, JSON.stringify(sonuc, null, 1));
console.log(JSON.stringify(sonuc, null, 1));
