// Melih'ten Dinle: müzik uygulaması düzeninde sesli kitap çalar.
// Sayfalar adres çubuğundaki #'e göre çizilir: #/ (ana sayfa), #/ara, #/kitapligim, #/eser/<id>.
// Her eser sitede ~20 dakikalık parçalardır (<yol>/<n>.mp3); çalar onları tek kayıt gibi gösterir:
// zaman çubuğu, kaldığı yer ve atlamalar eserin bütününe göredir.
// Kaldığı yer, hız, bitenler ve yer imleri yalnız bu tarayıcıda (localStorage) tutulur.
// İndirilen eserler telefonun kendi depolama alanında (Cache Storage, "indirilenler-v1") durur, Netlify'da değil;
// sw.js internet yokken parçaları oradan verir. Sitede yalnız TTS kayıtları vardır (kullanıcı, 29 Ekim 2026).
// Program index.html'de sırayla yüklenen js/1…8 dosyalarına bölündü (yükleme sırası önemli: her
// dosya yalnız kendinden öncekilerin tanımlarını yüklenirken kullanır; olay işleyicileri hepsi yüklenince çalışır).
"use strict";


const $ = (s, k = document) => k.querySelector(s);
const $$ = (s, k = document) => [...k.querySelectorAll(s)];
const ses = $("#ses");
const KAYIT = "kitaplik-v1";
const HIZLAR = [0.8, 1, 1.15, 1.25, 1.5, 1.75, 2];
const HEDEFLER = [10, 20, 30, 45, 60];   // günlük dinleme hedefi seçenekleri (dk)
const SIRALAR = [["ad", "Ada göre"], ["yazar", "Yazara göre"], ["kisa", "Kısadan uzuna"], ["uzun", "Uzundan kısaya"], ["yeni", "Yeni eklenen"]];
const UYKU = [0, 15, 30, 45, 60];
const KOKENLER = [["Rus", "Rus klasikleri"], ["Dünya", "Dünya klasikleri"]];
const DEPO = "indirilenler-v1";
// kapak renk çiftleri (koyu, açık); eser numarasına göre seçilir
const RENKLER = [
  ["#7a1f2b", "#e0566b"], ["#1e3a8a", "#5b8def"], ["#065f46", "#2fd39a"], ["#7c2d12", "#f2894a"],
  ["#4c1d95", "#b07cf5"], ["#0f5f59", "#4fd6c4"], ["#831843", "#ef6aa8"], ["#6b4a0e", "#e8b931"],
  ["#283548", "#8aa0bd"], ["#134e63", "#3fc7e6"], ["#3f5f12", "#9ed64a"], ["#5c1a1a", "#ee7d6d"],
];
const TURLER = [
  { ad: "Rus klasikleri", renk: "#2d5fb4", suz: (k) => k.koken === "Rus" },
  { ad: "Dünya klasikleri", renk: "#1e8a5a", suz: (k) => k.koken === "Dünya" },
  { ad: "1 saatten kısa", renk: "#b3462a", suz: (k) => k.sure < 3600 },
  { ad: "1–3 saat", renk: "#8d4fb8", suz: (k) => k.sure >= 3600 && k.sure < 3 * 3600 },
  { ad: "3 saatten uzun", renk: "#a8741a", suz: (k) => k.sure >= 3 * 3600 },
];

const SIMGE = {
  cal: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.14v13.72a1 1 0 0 0 1.52.85l10.6-6.86a1 1 0 0 0 0-1.7L9.52 4.29A1 1 0 0 0 8 5.14z"/></svg>',
  dur: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4.5" width="4.2" height="15" rx="1.2"/><rect x="13.8" y="4.5" width="4.2" height="15" rx="1.2"/></svg>',
  ev: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3.2 3 10.4V21h6.5v-6.2h5V21H21V10.4z"/></svg>',
  ara: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m20 20-4.6-4.6"/></svg>',
  kitaplik: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 4h2.4v16H4zM9.2 4h2.4v16H9.2zM14.3 4.9l2.3-.7 4.6 15.2-2.3.7z"/></svg>',
  geri15: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 0 2.3-5.6"/><path d="M4 4v4h4"/><text x="12.2" y="15.4" font-size="7.2" text-anchor="middle" fill="currentColor" stroke="none" font-family="system-ui" font-weight="700">15</text></svg>',
  ileri30: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v4h-4"/><text x="11.8" y="15.4" font-size="7.2" text-anchor="middle" fill="currentColor" stroke="none" font-family="system-ui" font-weight="700">30</text></svg>',
  ay: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>',
  asagi: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
  buyut: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M10 20H4v-6M20 4l-6.5 6.5M4 20l6.5-6.5"/></svg>',
  bilgi: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.01"/></svg>',
  onay: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
  im: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 3.5h11v17l-5.5-4-5.5 4z"/></svg>',
  indir: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 10.5l5 5 5-5M5 20h14"/></svg>',
  cop: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13h9l1-13"/></svg>',
  sohbet: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 11.5a8.5 8.5 0 0 1-12.6 7.4L3.5 20l1.2-4.2A8.5 8.5 0 1 1 20.5 11.5z"/></svg>',
  liste: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h11M4 12h11M4 18h7M18 15v6M15 18h6"/></svg>',
  paylas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3.5M7.5 8 12 3.5 16.5 8M5 12.5V20h14v-7.5"/></svg>',
  kalp: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 20.3S3.5 15.2 3.5 9.1A4.6 4.6 0 0 1 12 6.6a4.6 4.6 0 0 1 8.5 2.5c0 6.1-8.5 11.2-8.5 11.2z"/></svg>',
  kalpDolu: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 20.3S3.5 15.2 3.5 9.1A4.6 4.6 0 0 1 12 6.6a4.6 4.6 0 0 1 8.5 2.5c0 6.1-8.5 11.2-8.5 11.2z"/></svg>',
  zar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3.5"/><circle cx="9" cy="9" r="1.3" fill="currentColor"/><circle cx="15" cy="15" r="1.3" fill="currentColor"/><circle cx="15" cy="9" r="1.3" fill="currentColor"/><circle cx="9" cy="15" r="1.3" fill="currentColor"/></svg>',
  tasi: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4v12M3.5 12.5 7 16l3.5-3.5M17 20V8M13.5 11.5 17 8l3.5 3.5"/></svg>',
  resim: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="3.5" width="17" height="17" rx="3"/><circle cx="9" cy="9" r="1.8"/><path d="m20.5 15-5-5-11 11"/></svg>',
  bastan: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1"/><path d="M3.5 4v4.5H8"/></svg>',
};
const simge = (ad) => SIMGE[ad] || "";
const calDur = '<span class="i-cal">' + simge("cal") + '</span><span class="i-dur">' + simge("dur") + "</span>";
function simgeleriDoldur(kok = document) {
  for (const s of $$("[data-simge]", kok)) if (!s.firstChild) s.innerHTML = simge(s.dataset.simge);
}

let katalog = [];
let yakinda = [], whatsapp = "";   // yakinda.json: Fola kuyruğundaki eserler ve "Eser iste" numarası
const indiriliyor = {};            // eser id → indirme yüzdesi
let simdiki = null;
let parca = -1;        // çalan parçanın sırası (0'dan)
let baslar = [0];      // her parçanın eser içindeki başlangıç saniyesi
let uykuSira = 0, uykuBitis = 0, uykuSaat = null;
let sonKayit = 0;
let surukleniyor = false;
let aramaMetni = "", aramaTur = null, kitaplikSekme = "devam";
let vakit = 0;     // "Ne kadar vaktin var?" seçimi (dk)
let sonTik = 0;    // dinleme süresi sayacı: son timeupdate anı

// Tarayıcı deposundan ya da içe aktarılan dosyadan gelen veri türüne göre temizlenir (kalite/HATA-DEFTERI.md H-004):
// beklenmeyen alan ve tür atılır. Sayfaya yazılabilecek her değer ya sayı, ya bilinen bir seçenek, ya da (kaçışla
// yazılan) kısa bir metin olur. Eskiden örneğin "hedef" alanı denetlenmeden HTML'e giriyordu.
const KIMLIK = /^[a-z0-9-]{1,80}$/, GUN_BICIMI = /^\d{4}-\d{2}-\d{2}$/;
const sayi = (x, enAz = 0, enCok = Number.MAX_SAFE_INTEGER) => (Number.isFinite(x) && x >= enAz && x <= enCok ? x : null);
const dizi = (x) => (Array.isArray(x) ? x : []);
function sozluk(x, anahtar, deger) {
  const s = {};
  if (x && typeof x === "object" && !Array.isArray(x)) {
    for (const [k, v] of Object.entries(x)) {
      const d = deger(v);
      if (anahtar.test(k) && d !== null) s[k] = d;
    }
  }
  return s;
}
const im = (m) => (m && sayi(m.t) !== null ? { t: m.t, not: typeof m.not === "string" ? m.not.slice(0, 140) : "", zaman: sayi(m.zaman) ?? 0 } : null);
function temizle(d) {
  d = d && typeof d === "object" && !Array.isArray(d) ? d : {};
  return {
    konum: sozluk(d.konum, KIMLIK, (v) => sayi(v)),
    bitti: sozluk(d.bitti, KIMLIK, (v) => (v === true ? true : null)),
    son: typeof d.son === "string" && KIMLIK.test(d.son) ? d.son : null,
    hiz: HIZLAR.includes(d.hiz) ? d.hiz : 1,
    zaman: sozluk(d.zaman, KIMLIK, (v) => sayi(v)),
    imler: sozluk(d.imler, KIMLIK, (l) => { const m = dizi(l).map(im).filter(Boolean); return m.length ? m : null; }),
    indirilen: sozluk(d.indirilen, KIMLIK, (v) => (typeof v === "string" && v.startsWith("/ses/") && v.length < 200 ? v : null)),
    sonra: dizi(d.sonra).filter((x) => typeof x === "string" && KIMLIK.test(x)),
    gunluk: sozluk(d.gunluk, GUN_BICIMI, (v) => sayi(v, 0, 86400)),
    hedef: HEDEFLER.includes(d.hedef) ? d.hedef : 20,
    begen: sozluk(d.begen, KIMLIK, (v) => sayi(v)),
    aramalar: dizi(d.aramalar).filter((x) => typeof x === "string").map((x) => x.slice(0, 100)).slice(0, 6),
    sirala: SIRALAR.some(([k]) => k === d.sirala) ? d.sirala : "ad",
    saatler: Array.from({ length: 24 }, (_, i) => sayi(dizi(d.saatler)[i], 0, 86400 * 3650) ?? 0),
    rozet: sozluk(d.rozet, KIMLIK, (v) => sayi(v)),
    kurGizle: d.kurGizle === true,
    sozGoruldu: typeof d.sozGoruldu === "string" && GUN_BICIMI.test(d.sozGoruldu) ? d.sozGoruldu : "",
  };
}
const durum = oku();
function oku() {
  try {
    return temizle(JSON.parse(localStorage.getItem(KAYIT)));
  } catch {
    return temizle({});
  }
}
function yaz() {
  try { localStorage.setItem(KAYIT, JSON.stringify(durum)); } catch { /* gizli sekme: kaydetmeden sürer */ }
}

// ---------- biçim ----------
function saat(sn) {
  sn = Math.max(0, Math.floor(sn || 0));
  const s = Math.floor(sn / 3600), d = Math.floor((sn % 3600) / 60), n = sn % 60;
  return (s ? `${s}:${String(d).padStart(2, "0")}` : `${d}`) + `:${String(n).padStart(2, "0")}`;
}
function sure(sn) {
  const s = Math.floor(sn / 3600), d = Math.round((sn % 3600) / 60);
  return s ? `${s} sa${d ? ` ${d} dk` : ""}` : `${Math.max(1, d)} dk`;
}
const sade = (t) => t.toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i");
const kac = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const eserBul = (id) => katalog.find((x) => x.id === id);
const mb = (b) => `${Math.max(1, Math.round(b / 1048576))} MB`;
// günlük dinleme süresi (saniye, duvar saati) durum.gunluk["YYYY-AA-GG"]'de; hedef dakika durum.hedef'te
const gun = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const bugunDk = () => Math.floor((durum.gunluk[gun()] || 0) / 60);
function seri() {  // hedefin tutturulduğu ardışık günler; bugün henüz tutmadıysa dünden geriye sayılır
  const h = durum.hedef * 60, d = new Date();
  let n = 0;
  if ((durum.gunluk[gun(d)] || 0) < h) d.setDate(d.getDate() - 1);
  while ((durum.gunluk[gun(d)] || 0) >= h) { n++; d.setDate(d.getDate() - 1); }
  return n;
}
function enUzunSeri() {
  const h = durum.hedef * 60;
  let en = 0, n = 0, onceki = null;
  for (const g of Object.keys(durum.gunluk).filter((g) => durum.gunluk[g] >= h).sort((a, b) => a.localeCompare(b))) {
    const t = Date.parse(g);
    n = onceki !== null && t - onceki < 1.5 * 864e5 ? n + 1 : 1;
    en = Math.max(en, n);
    onceki = t;
  }
  return en;
}
const sureYaz = (sn) => (sn < 60 ? "0 dk" : sure(sn));
const listede = (id) => durum.sonra.includes(id);
const indirildi = (k) => durum.indirilen[k.id] === k.yol;  // eser yeniden kodlanırsa yolu değişir, indirme eskir
const begenildi = (id) => !!durum.begen[id];
// 1 Kasım 2026 yenilikleri: sıralama, akıllı geri sarma, beğeniler, şans eseri, veri taşıma, internetsiz şerit,
// bitiş kutlaması, çift dokunuşla atlama, genişletilmiş arama, uykuda sesin yavaşça kısılması
function sirala(liste) {
  const l = [...liste], tr = (a, b) => a.localeCompare(b, "tr");
  const f = { ad: (a, b) => tr(a.eser, b.eser), yazar: (a, b) => tr(a.yazar, b.yazar) || tr(a.eser, b.eser),
    kisa: (a, b) => a.sure - b.sure, uzun: (a, b) => b.sure - a.sure,
    yeni: (a, b) => (b.eklenme || "").localeCompare(a.eklenme || "") || tr(a.eser, b.eser) }[durum.sirala];
  return f ? l.sort(f) : l;
}
const siraCipleri = () => `<div class="cipler sira-cip" role="group" aria-label="Sırala"><span>Sırala:</span>${SIRALAR.map(([d, ad]) =>
  `<button class="cip" data-sirala="${d}" aria-pressed="${durum.sirala === d}">${ad}</button>`).join("")}</div>`;
// akıllı geri sarma: uzun aradan sonra cümlenin başını kaçırmamak için birkaç saniye geriden başlar
function geriSar(sonZaman) {
  if (!sonZaman) return 0;
  const ara = Date.now() - sonZaman;
  return ara > 24 * 3600e3 ? 30 : ara > 3600e3 ? 20 : ara > 600e3 ? 10 : ara > 120e3 ? 5 : 0;
}
let duraklamaAni = 0;   // çalar en son ne zaman duraklatıldı (akıllı geri sarma için)
const cevrimdisi = () => navigator.onLine === false;

function oran(k) {
  if (durum.bitti[k.id]) return 1;
  return Math.min(1, (durum.konum[k.id] || 0) / k.sure);
}
const devamEdiyor = (k) => !durum.bitti[k.id] && (durum.konum[k.id] || 0) > 0;
const sonDinlenenler = () => katalog.filter(devamEdiyor).sort((a, b) => (durum.zaman[b.id] || 0) - (durum.zaman[a.id] || 0));
// son 7 günde eklenen ve henüz dinlenmeye başlanmamış eser "Yeni" etiketi alır
// etiket yalnız en son eklenen 6 esere (hepsi aynı gün eklenince her kart "Yeni" olmasın)
const yeniler = () => katalog.filter((k) => k.eklenme && Date.now() - Date.parse(k.eklenme) < 7 * 864e5)
  .sort((a, b) => b.eklenme.localeCompare(a.eklenme)).slice(0, 10);
const yeniMi = (k) => yeniler().slice(0, 6).includes(k) && !durum.konum[k.id] && !durum.bitti[k.id];
const renk = (k) => RENKLER[(k.no * 5) % RENKLER.length];
const renkStil = (k) => `--a:${renk(k)[0]};--b:${renk(k)[1]}`;

// ---------- parçalar ----------
function kapak(k) {
  const o = oran(k);
  return `<div class="kapak" style="${renkStil(k)}">${desen(k)}
    <span class="k-ust"><span>${kac(k.ulke)}</span></span>
    <span class="k-govde"><span class="k-ad">${kac(k.eser)}</span><span class="k-cizgi"></span><span class="k-yazar">${kac(k.yazar)}</span></span>
    ${durum.bitti[k.id] ? `<span class="k-bitti" title="Bitti">${simge("onay")}</span>` : yeniMi(k) ? `<span class="k-yeni">Yeni</span>` : ""}
    ${o > 0 && o < 1 ? `<span class="k-ilerleme"><i style="width:${(o * 100).toFixed(1)}%"></i></span>` : ""}
  </div>`;
}

const calDugmesi = (k) =>
  `<button class="kart-cal${simdiki && simdiki.id === k.id && !ses.paused ? " caliyor" : ""}" data-cal="${k.id}" aria-label="${kac(k.eser)} dinle">${calDur}</button>`;

function kart(k) {
  return `<div class="kart${indirildi(k) ? "" : " inmemis"}"><div class="kart-kapak"><a href="#/eser/${k.id}" tabindex="-1">${kapak(k)}</a>${calDugmesi(k)}</div>
    <a href="#/eser/${k.id}"><div class="kart-ad">${kac(k.eser)}</div><div class="kart-alt">${kac(k.yazar)}</div>
    <div class="kart-sure">${durum.bitti[k.id] ? "Bitti" : oran(k) > 0 ? `<b>${sure(k.sure * (1 - oran(k)))} kaldı</b>` : sure(k.sure)}</div></a></div>`;
}

function satir(k) {
  const o = oran(k);
  const alt = durum.bitti[k.id] ? "Bitti" : o > 0 ? `<span class="ilerleme-yazi">${sure(k.sure * (1 - o))} kaldı</span>` : `${kac(k.yazar)} · ${sure(k.sure)}`;
  return `<div class="satir${simdiki && simdiki.id === k.id ? " calan" : ""}${indirildi(k) ? "" : " inmemis"}"><a href="#/eser/${k.id}">${kapak(k)}
    <div class="satir-yazi"><strong>${esCubuk}${kac(k.eser)}</strong><span>${o > 0 ? kac(k.yazar) + " · " : ""}${alt}</span></div></a>${calDugmesi(k)}</div>`;
}

// "Yakında": henüz sitede olmayan, TTS ile okunmakta ya da sırada bekleyen eserler (çalınamaz)
function yakindaRaf() {
  if (!yakinda.length) return "";
  return `<section class="raf"><div class="raf-bas"><h2>Yakında</h2></div><div class="raf-kaydir">${yakinda.map((y) =>
    `<div class="kart yakinda-kart"><div class="kart-kapak">${kapak(y)}<span class="k-durum${y.okunuyor ? " okunuyor" : ""}">${y.okunuyor ? "Okunuyor" : "Sırada"}</span></div>
      <div class="kart-ad">${kac(y.eser)}</div><div class="kart-alt">${kac(y.yazar)}</div></div>`).join("")}</div></section>`;
}

function hedefKutusu() {
  const dk = bugunDk(), h = durum.hedef, o = Math.min(1, dk / h), s = seri();
  return `<a class="hedef" href="#/karne"><span class="halka${o >= 1 ? " tamam" : ""}" style="--o:${o.toFixed(3)}"><b>${o >= 1 ? simge("onay") : dk}</b></span>
    <span class="hedef-yazi"><strong>${o >= 1 ? "Bugünkü hedefin tamam" : `Bugün ${dk} / ${h} dk`}</strong>
    <small>${s ? `${s} gündür seri` : "Seriye bugün başla"} · Dinleme karnen</small></span></a>`;
}

// "Ne dinlesem?": seçilen sürede bitirilebilecek yarım ve yeni eserler
function vakitKutusu() {
  if (!katalog.length) return "";
  return `<section class="raf vakit"><div class="raf-bas"><h2>Ne kadar vaktin var?</h2></div>
    <div class="cipler">${[15, 30, 60, 120].map((d) => `<button class="cip" data-vakit="${d}" aria-pressed="${vakit === d}">${d < 60 ? `${d} dk` : `${d / 60} saat`}</button>`).join("")}</div>
    ${vakit ? vakitOner() : ""}</section>`;
}
function vakitOner() {
  const sn = vakit * 60 * 1.15;
  const yarim = sonDinlenenler().filter((k) => k.sure * (1 - oran(k)) <= sn);
  const yeni = katalog.filter((k) => !durum.bitti[k.id] && !devamEdiyor(k) && k.sure <= sn).sort((a, b) => b.sure - a.sure);
  const liste = [...yarim, ...yeni].slice(0, 6);
  if (liste.length) return `<p class="vakit-not">${vakit < 60 ? `${vakit} dakikada` : `${vakit / 60} saatte`} bitirebileceklerin:</p>${liste.map(satir).join("")}`;
  const devam = sonDinlenenler().slice(0, 3);
  const kisa = katalog.filter((k) => !durum.bitti[k.id]).sort((a, b) => a.sure - b.sure).slice(0, 3);
  return `<p class="vakit-not">Bu süreye sığan bir eser yok. ${devam.length ? "Kaldığın yerden biraz dinleyebilirsin:" : "En kısa eserler:"}</p>${(devam.length ? devam : kisa).map(satir).join("")}`;
}

// "Kararsız mısın?": henüz başlanmamış eserlerden rastgele biri
function sansKutusu() {
  if (!katalog.some((k) => !durum.bitti[k.id] && !devamEdiyor(k))) return "";
  return `<section class="istek sans"><div><h2>Ne dinleyeceğine karar veremedin mi?</h2>
    <p>Henüz başlamadığın eserlerden birini senin için seçelim.</p></div>
    <button class="dev-cal istek-dugme" data-sans>${simge("zar")}<span>Bana bir eser seç</span></button></section>`;
}

function istekKutusu() {
  if (!whatsapp) return "";
  return `<section class="istek"><div><h2>Dinlemek istediğin bir eser mi var?</h2>
    <p>Eserin adını yaz, Melih'e WhatsApp'tan iletilsin.</p></div>
    <button class="dev-cal istek-dugme" data-istek>${simge("sohbet")}<span>Eser iste</span></button></section>`;
}

function raf(baslik, liste, tumu) {
  if (!liste.length) return "";
  return `<section class="raf"><div class="raf-bas"><h2>${baslik}</h2>${tumu ? `<a href="${tumu}">Tümünü göster</a>` : ""}</div>
    <div class="raf-kaydir">${liste.map(kart).join("")}</div></section>`;
}

