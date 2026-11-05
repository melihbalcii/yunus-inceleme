// Melih'ten Dinle: anında açılış, internetsiz açılış ve telefona indirilmiş eserleri çalma.
// İndirilen parçalar telefonun Cache Storage'ında ("indirilenler-v1") durur; uygulama.js indirir, burası verir.
// Çalar parçaları parça parça (Range) ister: önbellekteki dosyadan istenen bayt aralığı 206 ile döner.
// 2 Kasım 2026 (kullanıcı: "telefondan açınca yavaş, beyaz ekran"): sayfa, program ve görünüm dosyası telefondaki
// kopyadan BEKLEMEDEN açılır, güncel hâli arkadan iner; değişmişse sayfaya "yeni sürüm" haberi gider.
// Önceden ağ 3 sn beklendiği için mobil internette her açılış gecikiyordu. Katalog uygulama.js'te zaten
// önce kopyadan açıldığından ağdan alınır (yeni eser hemen görünsün).
// 3 Kasım 2026 (kullanıcı: "metin işini siteden ve sistemimizden çıkaralım"): Oku sekmesi kaldırıldı; telefonlarda
// kalmış metin önbelleği ("metinler-v1") ilk açılışta silinir
const KABUK = "kabuk-v5", DEPO = "indirilenler-v1";
const DOSYALAR = ["/", "/uygulama.js", "/stil.css", "/simge-192.png", "/simge.svg"];
const AGDAN = ["/katalog.json", "/yakinda.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(KABUK).then((c) => Promise.all([...DOSYALAR, ...AGDAN].map((d) => c.add(d).catch(() => {}))))
    .then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ad) => Promise.all(ad.filter((a) => (a.startsWith("kabuk-") && a !== KABUK) || a.startsWith("metinler-")).map((a) => caches.delete(a))))
    .then(() => self.clients.claim())));

self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  if (u.pathname.startsWith("/ses/")) return e.respondWith(ses(e.request));
  if (e.request.mode === "navigate" || DOSYALAR.includes(u.pathname)) return e.respondWith(kopyaOnce(e, u));
  if (AGDAN.includes(u.pathname)) return e.respondWith(agOnce(e, u));
});

async function ses(istek) {
  const r = await (await caches.open(DEPO)).match(istek.url, { ignoreVary: true });
  if (!r) return fetch(istek);
  const aralik = /bytes=(\d*)-(\d*)/.exec(istek.headers.get("range") || "");
  if (!aralik) return r;
  const veri = await r.arrayBuffer(), n = veri.byteLength;
  const bas = aralik[1] ? Number(aralik[1]) : Math.max(0, n - Number(aralik[2]));
  const son = aralik[1] && aralik[2] ? Math.min(n - 1, Number(aralik[2])) : n - 1;
  return new Response(veri.slice(bas, son + 1), { status: 206, headers: {
    "Content-Type": "audio/mpeg", "Accept-Ranges": "bytes", "Content-Length": String(son - bas + 1),
    "Content-Range": `bytes ${bas}-${son}/${n}` } });
}

const anahtar = (e, u) => (e.request.mode === "navigate" ? "/" : u.pathname);

function agdanAl(e, u) {
  return fetch(e.request, { cache: "no-cache" }).then((r) => {
    // giriş sayfasına yönlenen yanıt saklanmaz (oturum düşmüşse site girişe gitsin)
    if (r.ok && !r.redirected) { const kopya = r.clone(); e.waitUntil(caches.open(KABUK).then((c) => c.put(anahtar(e, u), kopya)).catch(() => {})); }
    return r;
  });
}

async function kopyaOnce(e, u) {
  const kopya = await caches.match(anahtar(e, u));
  const ag = agdanAl(e, u);
  if (!kopya) return ag.catch(() => Response.error());
  e.waitUntil(ag.then(async (r) => {
    if (u.pathname !== "/uygulama.js" || !r.ok || r.redirected) return;
    if ((await r.clone().text()) === (await kopya.clone().text())) return;
    for (const c of await self.clients.matchAll()) c.postMessage({ tip: "yeni-surum" });
  }).catch(() => {}));
  return kopya;
}

const BEKLE = 3000;
async function agOnce(e, u) {
  const ag = agdanAl(e, u);
  e.waitUntil(ag.catch(() => {}));
  const kopya = await caches.match(u.pathname);
  if (!kopya) return ag.catch(() => Response.error());
  const sure = new Promise((ok) => setTimeout(() => ok(null), BEKLE));
  return (await Promise.race([ag.catch(() => null), sure])) || kopya;
}
