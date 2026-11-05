// Ön yüz: tarayıcı deposundan ve içe aktarılan dosyadan gelen veri (kalite/HATA-DEFTERI.md H-004).
// Gerçek Chromium'da çalışır: zararlı veri sayfaya kod olarak girmemeli, kullanıcının gerçek verisi kaybolmamalı.
// Çalıştırma: npm run test:tarayici  (Chromium: npx playwright install chromium)
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { writeFileSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const KOK = fileURLToPath(new URL("../public/", import.meta.url));
const TUR = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg", ".webmanifest": "application/json" };
const KATALOG = [{ id: "kisa-oyku", yol: "/ses/kisa-oyku-abc", no: 1, eser: "Kısa Öykü", yazar: "Yazar Bir", koken: "Rus",
  ulke: "Rusya", sure: 1800, boyut: 1000, parcalar: [1800], ses: "Fola", tanitim: "", yazarBilgi: "", eklenme: "2026-11-01T10:00" }];

// Kullanıcının gerçek, geçerli verisine benzer örnek: temizlikte hiçbir alanı değişmemeli.
const GECERLI = {
  konum: { "kisa-oyku": 125 }, bitti: { "kisa-oyku": true }, son: "kisa-oyku", hiz: 1.25, zaman: { "kisa-oyku": 1762300000000 },
  imler: { "kisa-oyku": [{ t: 60, not: "güzel bölüm", zaman: 1762300000000 }] }, indirilen: { "kisa-oyku": "/ses/kisa-oyku-abc" },
  sonra: ["kisa-oyku"], gunluk: { "2026-11-05": 900 }, hedef: 30, begen: { "kisa-oyku": 1762300000000 },
  aramalar: ["tolstoy"], sirala: "yazar", saatler: Array.from({ length: 24 }, (_, i) => i * 10),
  rozet: { "ilk-adim": 1762300000000 }, kurGizle: true, sozGoruldu: "2026-11-05",
};
const KOTU = '"><img src=x onerror="window.__xss=1">';

let sunucu, adres, tarayici;
// Ön yüz test kapsamı (puanlama "Ön yüz test kapsamı"): KAPSAM_DOSYASI verilirse Chromium'un kod kapsamıyla
// uygulama.js'in testlerde çalışan satır oranı yazılır.
const kapsamlar = [];
before(async () => {
  sunucu = createServer(async (istek, yanit) => {
    const yol = decodeURIComponent(new URL(istek.url, "http://x").pathname);
    if (yol === "/katalog.json") return yanit.writeHead(200, { "content-type": TUR[".json"] }).end(JSON.stringify(KATALOG));
    if (yol === "/yakinda.json") return yanit.writeHead(200, { "content-type": TUR[".json"] }).end('{"yakinda":[],"whatsapp":""}');
    const dosya = normalize(join(KOK, yol === "/" ? "index.html" : yol));
    if (!dosya.startsWith(KOK)) return yanit.writeHead(403).end();
    try {
      yanit.writeHead(200, { "content-type": TUR[extname(dosya)] || "application/octet-stream" }).end(await readFile(dosya));
    } catch {
      yanit.writeHead(404).end();
    }
  });
  await new Promise((tamam) => sunucu.listen(0, "127.0.0.1", tamam));
  adres = `http://127.0.0.1:${sunucu.address().port}`;
  tarayici = await chromium.launch();
});
after(async () => {
  await tarayici?.close();
  sunucu?.close();
  if (process.env.KAPSAM_DOSYASI) writeFileSync(process.env.KAPSAM_DOSYASI, JSON.stringify(satirKapsami(kapsamlar)));
});

// V8 blok kapsamı → satır kapsamı: bir satır, boş olmayan bir karakteri çalıştıysa kapsanmış sayılır.
function satirKapsami(girdiler) {
  if (!girdiler.length) return null;
  const kaynak = girdiler[0].source;
  const calisti = new Uint8Array(kaynak.length);
  for (const g of girdiler) {
    const sayim = new Int32Array(kaynak.length).fill(-1);
    const araliklar = g.functions.flatMap((f) => f.ranges).sort((a, b) => (b.endOffset - b.startOffset) - (a.endOffset - a.startOffset));
    for (const a of araliklar) sayim.fill(a.count, a.startOffset, a.endOffset);
    for (let i = 0; i < sayim.length; i++) if (sayim[i] > 0) calisti[i] = 1;
  }
  let toplam = 0, kapsanan = 0, i = 0;
  for (const satir of kaynak.split("\n")) {
    if (satir.trim()) {
      toplam++;
      for (let j = 0; j < satir.length; j++) if (satir[j].trim() && calisti[i + j]) { kapsanan++; break; }
    }
    i += satir.length + 1;
  }
  return { satir: Math.round((1000 * kapsanan) / toplam) / 10, kapsanan, toplam };
}

async function sayfa(depo) {
  const baglam = await tarayici.newContext({ serviceWorkers: "block" });
  const p = await baglam.newPage();
  await p.coverage.startJSCoverage({ resetOnNavigation: false });
  const hatalar = [];
  p.on("pageerror", (h) => hatalar.push(String(h)));
  if (depo !== undefined) await p.addInitScript((d) => localStorage.setItem("kitaplik-v1", JSON.stringify(d)), depo);
  await p.goto(`${adres}/index.html`);
  await p.waitForFunction(() => document.querySelector("#icerik")?.innerHTML.length > 0);
  const kapat = async () => {
    kapsamlar.push(...(await p.coverage.stopJSCoverage()).filter((x) => x.url.endsWith("/uygulama.js")));
    await baglam.close();
  };
  return { p, hatalar, kapat };
}

async function butunSayfalariGez(p) {
  for (const h of ["#/", "#/kitapligim", "#/karne", "#/ara", "#/eser/kisa-oyku"]) {
    await p.evaluate((x) => { location.hash = x; }, h);
    await p.waitForTimeout(150);
  }
}

test("geçerli kullanıcı verisi temizlikte aynen korunur", async () => {
  const { p, hatalar, kapat } = await sayfa(GECERLI);
  assert.deepEqual(await p.evaluate(() => durum), GECERLI);
  assert.deepEqual(hatalar, []);
  await kapat();
});

test("bozuk ya da boş depo siteyi düşürmez, varsayılanlara döner", async () => {
  for (const depo of [null, "metin", [1, 2], { hedef: "yirmi", saatler: "x", imler: { "kisa-oyku": "x" } }]) {
    const { p, hatalar, kapat } = await sayfa(depo);
    const d = await p.evaluate(() => durum);
    assert.equal(d.hedef, 20);
    assert.equal(d.saatler.length, 24);
    assert.deepEqual(d.imler, {});
    assert.deepEqual(hatalar, []);
    await kapat();
  }
});

test("depodaki zararlı değer sayfada kod olarak çalışmaz", async () => {
  const zararli = { ...GECERLI, hedef: KOTU, sirala: KOTU, son: KOTU, sozGoruldu: KOTU, hiz: KOTU,
    sonra: [KOTU], aramalar: [KOTU], imler: { "kisa-oyku": [{ t: 5, not: KOTU }], [KOTU]: [{ t: 1, not: "x" }] },
    indirilen: { "kisa-oyku": "javascript:alert(1)" }, rozet: { [KOTU]: 1 } };
  const { p, hatalar, kapat } = await sayfa(zararli);
  await butunSayfalariGez(p);
  assert.equal(await p.evaluate(() => window.__xss), undefined);
  const d = await p.evaluate(() => durum);
  assert.equal(d.hedef, 20);
  assert.equal(d.sirala, "ad");
  assert.equal(d.son, null);
  assert.deepEqual(d.sonra, []);
  assert.deepEqual(d.indirilen, {});
  assert.deepEqual(Object.keys(d.imler), ["kisa-oyku"]);
  assert.deepEqual(hatalar, []);
  await kapat();
});

test("zararlı yedek dosyası içe aktarılınca kod çalışmaz, geçerli kısmı birleşir", async () => {
  const { p, hatalar, kapat } = await sayfa({ konum: { "kisa-oyku": 50 } });
  const dosya = JSON.stringify({ uygulama: "melihten-dinle", surum: 1, veri: {
    konum: { "kisa-oyku": 300, [KOTU]: 5 }, zaman: { "kisa-oyku": "dün" }, son: KOTU, sonra: ["kisa-oyku", KOTU],
    imler: { "kisa-oyku": [{ t: 10, not: KOTU }, { t: "x" }] }, gunluk: { [KOTU]: 50, "2026-11-04": 600 },
    saatler: [KOTU, 30], rozet: { "ilk-adim": KOTU } } });
  await p.evaluate((icerik) => iceAktar(new File([icerik], "yedek.json")), dosya);
  await p.waitForFunction(() => durum.konum["kisa-oyku"] === 300);
  await butunSayfalariGez(p);
  assert.equal(await p.evaluate(() => window.__xss), undefined);
  const d = await p.evaluate(() => durum);
  assert.deepEqual(d.konum, { "kisa-oyku": 300 });           // en ileri konum alındı, zararlı anahtar atıldı
  assert.deepEqual(d.zaman, {});                              // sayı olmayan zaman alınmadı
  assert.deepEqual(d.sonra, ["kisa-oyku"]);
  assert.deepEqual(d.imler["kisa-oyku"].map((m) => m.t), [10]);
  assert.deepEqual(d.gunluk, { "2026-11-04": 600 });
  assert.equal(d.saatler[1], 30);
  assert.deepEqual(d.rozet, {});
  assert.deepEqual(hatalar, []);
  await kapat();
});
