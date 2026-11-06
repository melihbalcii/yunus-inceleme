// Ön yüz, gerçek Chromium'da: (1) tarayıcı deposundan ve içe aktarılan dosyadan gelen veri (kalite/HATA-DEFTERI.md
// H-004): zararlı veri sayfaya kod olarak girmemeli, kullanıcının gerçek verisi kaybolmamalı; (2) kullanıcı akışları:
// arama, eser sayfası eylemleri, verileri başka cihaza taşıma.
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
  ulke: "Rusya", sure: 1800, boyut: 1000, parcalar: [1800], ses: "Fola", tanitim: "", yazarBilgi: "", eklenme: "2026-11-01T10:00" },
  { id: "uzun-roman", yol: "/ses/uzun-roman-def", no: 2, eser: "Uzun Roman", yazar: "Yazar İki", koken: "Fransız", ulke: "Fransa",
    sure: 36000, boyut: 2000, parcalar: [18000, 18000], ses: "Fola", tanitim: "Petersburg sokaklarında bir hayat.", yazarBilgi: "",
    eklenme: "2026-11-03T10:00" }];

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
// programın (public/js/) testlerde çalışan satır oranı yazılır.
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
  const sonuc = [...Map.groupBy(girdiler, (g) => g.url).values()].map(dosyaKapsami);
  const kapsanan = sonuc.reduce((a, x) => a + x.kapsanan, 0), toplam = sonuc.reduce((a, x) => a + x.toplam, 0);
  return { satir: Math.round((1000 * kapsanan) / toplam) / 10, kapsanan, toplam, dosya: sonuc.length };
}

function dosyaKapsami(girdiler) {
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
  return { kapsanan, toplam };
}

async function sayfa(depo) {
  const baglam = await tarayici.newContext({ serviceWorkers: "block" });
  const p = await baglam.newPage();
  await p.coverage.startJSCoverage({ resetOnNavigation: false });
  const hatalar = [];
  p.on("pageerror", (h) => hatalar.push(String(h)));
  if (depo !== undefined) {  // yalnız ilk açılışta: sayfa yenilenince kullanıcının kaydettiği veri kalmalı
    await p.addInitScript((d) => {
      if (sessionStorage.getItem("ilk-acilis")) return;
      sessionStorage.setItem("ilk-acilis", "1");
      localStorage.setItem("kitaplik-v1", JSON.stringify(d));
    }, depo);
  }
  await p.goto(`${adres}/index.html`);
  await p.waitForFunction(() => document.querySelector("#icerik")?.innerHTML.length > 0);
  const kapat = async () => {
    kapsamlar.push(...(await p.coverage.stopJSCoverage()).filter((x) => new URL(x.url).pathname.startsWith("/js/")));
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

test("arama ada, yazara ve konuya göre süzer; sonuç yoksa söyler", async () => {
  const { p, hatalar, kapat } = await sayfa({});
  await p.evaluate(() => { location.hash = "#/ara"; });
  await p.fill("#ara", "Roman");
  await p.waitForFunction(() => document.querySelector("#ara-sonuc").textContent.includes("Uzun Roman"));
  assert.ok(!(await p.textContent("#ara-sonuc")).includes("Kısa Öykü"));
  await p.fill("#ara", "Yazar Bir");
  await p.waitForFunction(() => document.querySelector("#ara-sonuc").textContent.includes("Kısa Öykü"));
  await p.fill("#ara", "petersburg");  // yalnız tanıtımda geçiyor
  await p.waitForFunction(() => document.querySelector("#ara-sonuc").textContent.includes("Konusunda geçenler"));
  assert.ok((await p.textContent("#ara-sonuc")).includes("Uzun Roman"));
  await p.fill("#ara", "böyle bir eser yok");
  await p.waitForFunction(() => document.querySelector("#ara-sonuc").textContent.includes("sonuç yok"));
  assert.deepEqual(hatalar, []);
  await kapat();
});

test("eser sayfasında sonra dinle ve beğen kalıcıdır, ikinci tık geri alır", async () => {
  const { p, hatalar, kapat } = await sayfa({});
  await p.evaluate(() => { location.hash = "#/eser/uzun-roman"; });
  await p.waitForSelector('[data-sonra="uzun-roman"]');
  assert.equal(await p.textContent(".eser-bilgi h1"), "Uzun Roman");
  await p.click('[data-sonra="uzun-roman"]');
  await p.click('[data-begen="uzun-roman"]');
  await p.waitForFunction(() => durum.sonra.includes("uzun-roman") && durum.begen["uzun-roman"]);
  await p.reload();
  await p.waitForSelector('[data-sonra="uzun-roman"].secili');
  assert.deepEqual(await p.evaluate(() => [durum.sonra, Object.keys(durum.begen)]), [["uzun-roman"], ["uzun-roman"]]);
  await p.click('[data-sonra="uzun-roman"]');
  await p.waitForFunction(() => !durum.sonra.includes("uzun-roman"));
  assert.deepEqual(hatalar, []);
  await kapat();
});

test("verileri dışa aktarıp başka cihazda içe aktarmak dinleme geçmişini taşır", async () => {
  const eski = await sayfa(GECERLI);
  const [indirme] = await Promise.all([eski.p.waitForEvent("download"), eski.p.evaluate(() => disaAktar())]);
  const icerik = await readFile(await indirme.path(), "utf-8");
  assert.equal(JSON.parse(icerik).veri.indirilen, undefined, "indirilenler cihaza özeldir, taşınmamalı");
  await eski.kapat();
  const yeni = await sayfa({});
  await yeni.p.evaluate((x) => iceAktar(new File([x], "yedek.json")), icerik);
  await yeni.p.waitForFunction(() => durum.konum["kisa-oyku"] === 125);
  const d = await yeni.p.evaluate(() => durum);
  for (const alan of ["konum", "bitti", "imler", "begen", "sonra", "gunluk", "rozet"]) assert.deepEqual(d[alan], GECERLI[alan], alan);
  assert.deepEqual(d.indirilen, {});
  assert.deepEqual(yeni.hatalar, []);
  await yeni.kapat();
});

test("olmayan eser sayfası siteyi düşürmez", async () => {
  const { p, hatalar, kapat } = await sayfa({});
  await p.evaluate(() => { location.hash = "#/eser/boyle-bir-eser-yok"; });
  await p.waitForFunction(() => document.querySelector("#icerik").textContent.includes("Eser bulunamadı"));
  assert.deepEqual(hatalar, []);
  await kapat();
});
