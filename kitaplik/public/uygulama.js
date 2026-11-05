// Melih'ten Dinle: müzik uygulaması düzeninde sesli kitap çalar.
// Sayfalar adres çubuğundaki #'e göre çizilir: #/ (ana sayfa), #/ara, #/kitapligim, #/eser/<id>.
// Her eser sitede ~20 dakikalık parçalardır (<yol>/<n>.mp3); çalar onları tek kayıt gibi gösterir:
// zaman çubuğu, kaldığı yer ve atlamalar eserin bütününe göredir.
// Kaldığı yer, hız, bitenler ve yer imleri yalnız bu tarayıcıda (localStorage) tutulur.
// İndirilen eserler telefonun kendi depolama alanında (Cache Storage, "indirilenler-v1") durur, Netlify'da değil;
// sw.js internet yokken parçaları oradan verir. Sitede yalnız TTS kayıtları vardır (kullanıcı, 29 Ekim 2026).
"use strict";

const $ = (s, k = document) => k.querySelector(s);
const $$ = (s, k = document) => [...k.querySelectorAll(s)];
const ses = $("#ses");
const KAYIT = "kitaplik-v1";
const HIZLAR = [0.8, 1, 1.15, 1.25, 1.5, 1.75, 2];
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

const durum = oku();
function oku() {
  try {
    const d = JSON.parse(localStorage.getItem(KAYIT)) || {};
    return { konum: d.konum || {}, bitti: d.bitti || {}, son: d.son || null, hiz: d.hiz || 1, zaman: d.zaman || {},
      imler: d.imler || {}, indirilen: d.indirilen || {}, sonra: d.sonra || [], gunluk: d.gunluk || {}, hedef: d.hedef || 20,
      begen: d.begen || {}, aramalar: d.aramalar || [], sirala: d.sirala || "ad",
      saatler: d.saatler || Array(24).fill(0), rozet: d.rozet || {}, kurGizle: !!d.kurGizle, sozGoruldu: d.sozGoruldu || "" };
  } catch {
    return { konum: {}, bitti: {}, son: null, hiz: 1, zaman: {}, imler: {}, indirilen: {}, sonra: [], gunluk: {}, hedef: 20,
      begen: {}, aramalar: [], sirala: "ad", saatler: Array(24).fill(0), rozet: {}, kurGizle: false, sozGoruldu: "" };
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
  for (const g of Object.keys(durum.gunluk).filter((g) => durum.gunluk[g] >= h).sort()) {
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
const SIRALAR = [["ad", "Ada göre"], ["yazar", "Yazara göre"], ["kisa", "Kısadan uzuna"], ["uzun", "Uzundan kısaya"], ["yeni", "Yeni eklenen"]];
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

// ---------- sayfalar ----------
function anaSayfa() {
  const sa = new Date().getHours();
  const selam = sa < 5 ? "İyi geceler" : sa < 12 ? "Günaydın" : sa < 18 ? "İyi günler" : "İyi akşamlar";
  const son = sonDinlenenler();
  const hizli = [...son, ...katalog.filter((k) => !son.includes(k) && !durum.bitti[k.id] && k.sure < 3600)].slice(0, 6);
  const sec = (f) => katalog.filter(f);
  return `<div class="sayfa">
    <div class="ust-renk" style="--ust:${son[0] ? renk(son[0])[0] : "#1f5a3a"}">
      <div class="selam-satir"><h1 class="selam">${selam}</h1>${sozBalonu()}</div>
      ${hedefKutusu()}${hikayeDugmesi()}
      <div class="hizli-izgara">${hizli.map((k) => `<div class="hizli"><a href="#/eser/${k.id}">${kapak(k)}<strong>${kac(k.eser)}</strong></a>${calDugmesi(k)}</div>`).join("")}</div>
    </div>
    ${gununEseri()}
    ${gununSozu()}
    ${cevrimdisi() ? raf("Telefonundakiler (internetsiz dinlenebilir)", katalog.filter(indirildi)) : ""}
    ${raf("Kaldığın yerden devam et", son)}
    ${vakitKutusu()}
    ${sansKutusu()}
    ${kurKutusu()}
    ${raf("Sonra dinle listen", durum.sonra.map(eserBul).filter(Boolean), "#/kitapligim/sonra")}
    ${raf("Yeni eklenenler", yeniler())}
    ${yakindaRaf()}
    ${raf("Kısa dinlemeler", sec((k) => k.sure < 3600), `#/ara/${encodeURIComponent("1 saatten kısa")}`)}
    ${KOKENLER.map(([koken, ad]) => raf(ad, sec((k) => k.koken === koken), `#/ara/${encodeURIComponent(ad)}`)).join("")}
    ${raf("Uzun soluklu", sec((k) => k.sure >= 3 * 3600), `#/ara/${encodeURIComponent("3 saatten uzun")}`)}
    ${istekKutusu()}
    <p class="dipnot">${katalog.length} eser · ${Math.round(katalog.reduce((a, k) => a + k.sure, 0) / 3600)} saat dinleme.
      Bütün kayıtlar eserin tam metnidir ve yapay zekâ sesiyle seslendirilmiştir.
      Kişisel arşivdir, yalnız davetli arkadaşlar içindir; lütfen bağlantıyı ve şifreyi başkalarıyla paylaşma.</p>
  </div>`;
}

function araSayfa() {
  return `<div class="sayfa">
    <div class="arama-kutu"><label><span data-simge="ara"></span>
      <input id="ara" type="search" placeholder="Ne dinlemek istersin?" value="${kac(aramaMetni)}" autocomplete="off" aria-label="Eser ya da yazar ara"></label></div>
    <div id="ara-sonuc">${araSonuc()}</div>
    ${istekKutusu()}
  </div>`;
}

function araSonuc() {
  const q = sade(aramaMetni.trim());
  if (q) {
    // önce ad/yazar/ülke eşleşenler, sonra konusu (tanıtımı) eşleşenler: "aşk", "savaş", "Petersburg" gibi
    const uyan = katalog.filter((k) => sade(`${k.eser} ${k.yazar} ${k.ulke}`).includes(q));
    const konu = katalog.filter((k) => !uyan.includes(k) && sade(`${k.tanitim || ""} ${k.yazarBilgi || ""}`).includes(q));
    if (!uyan.length && !konu.length) return `<p class="bos">“${kac(aramaMetni)}” için sonuç yok.</p>`;
    return (uyan.length ? `<div class="raf-bas"><h2>Sonuçlar</h2></div>${uyan.map(satir).join("")}` : "")
      + (konu.length ? `<div class="raf-bas konu-bas"><h2>Konusunda geçenler</h2></div>${konu.map(satir).join("")}` : "");
  }
  const tur = TURLER.find((t) => t.ad === aramaTur);
  if (tur) {
    return `<div class="raf-bas"><h2>${tur.ad}</h2><a href="#/ara">Tüm türler</a></div>${siraCipleri()}<div class="izgara">${sirala(katalog.filter(tur.suz)).map(kart).join("")}</div>`;
  }
  const sonAramalar = durum.aramalar.length ? `<div class="raf-bas"><h2>Son aramaların</h2><a href="#/ara" data-arama-temizle>Temizle</a></div>
    <div class="cipler">${durum.aramalar.map((a) => `<button class="cip" data-arama="${kac(a)}">${kac(a)}</button>`).join("")}</div>` : "";
  return `${sonAramalar}<div class="raf-bas"><h2>Göz at</h2></div><div class="tur-izgara">${TURLER.map((t) => {
    const ornek = katalog.find(t.suz);
    return `<a class="tur" href="#/ara/${encodeURIComponent(t.ad)}" style="--t:${t.renk}"><span>${t.ad}</span>${ornek ? kapak(ornek) : ""}</a>`;
  }).join("")}</div>`;
}

function kitaplikSayfa() {
  const indirilen = katalog.filter(indirildi);
  const sekmeler = [["devam", "Devam eden", sonDinlenenler()], ["sonra", "Sonra dinle", durum.sonra.map(eserBul).filter(Boolean)], ["indir", "İndirilenler", indirilen],
    ["begen", "Beğendiklerim", sirala(katalog.filter((k) => begenildi(k.id)))],
    ["bitti", "Bitenler", sirala(katalog.filter((k) => durum.bitti[k.id]))], ["hepsi", "Tümü", sirala(katalog)]];
  const [, , liste] = sekmeler.find(([s]) => s === kitaplikSekme);
  const bos = { devam: "Henüz yarıda bıraktığın bir eser yok. Ana sayfadan bir eser seç.",
    sonra: "Listen boş. Eser sayfasındaki “Sonra dinle” ile ekle; bir eser bitince sıradaki kendiliğinden başlar.",
    indir: "Telefona indirdiğin eser yok. Eser sayfasındaki “İndir” ile internetsiz dinleyebilirsin.",
    begen: "Henüz beğendiğin eser yok. Eser sayfasındaki kalbe dokunarak ekleyebilirsin.",
    bitti: "Henüz bitirdiğin bir eser yok.", hepsi: "" }[kitaplikSekme];
  const ust = kitaplikSekme === "indir" && indirilen.length
    ? `<p class="indir-ozet">Telefonda kayıtlı: <b>${mb(indirilen.reduce((a, k) => a + k.boyut, 0))}</b> · internetsiz dinlenebilir</p>` : "";
  return `<div class="sayfa"><div class="ust-renk" style="--ust:#3a2d6b"><h1 class="selam">Kitaplığım</h1>
    ${hedefKutusu()}
    <div class="cipler" role="group" aria-label="Süzgeç">${sekmeler.map(([s, ad, l]) =>
      `<button class="cip" data-sekme-sec="${s}" aria-pressed="${s === kitaplikSekme}">${ad} · ${l.length}</button>`).join("")}</div></div>
    ${ust}${["begen", "bitti", "hepsi"].includes(kitaplikSekme) && liste.length > 1 ? siraCipleri() : ""}
    ${liste.length ? liste.map(satir).join("") : `<p class="bos">${bos}</p>`}
    ${kitaplikSekme === "hepsi" ? `<p class="dipnot"><a href="#/karne">Dinleme karnen ve verilerini başka cihaza taşıma</a></p>` : ""}</div>`;
}

function eserSayfa(id, an) {
  const k = eserBul(id);
  if (!k) return `<div class="sayfa"><p class="bos">Eser bulunamadı. <a href="#/">Ana sayfaya dön</a></p></div>`;
  const o = oran(k), bitti = !!durum.bitti[k.id], basladi = o > 0 && !bitti;
  const etiket = simdiki && simdiki.id === k.id && !ses.paused ? "Duraklat" : basladi ? "Devam et" : bitti ? "Yeniden dinle" : "Dinle";
  const ayni = katalog.filter((x) => x.yazar === k.yazar && x.id !== k.id);
  const benzer = katalog.filter((x) => x.koken === k.koken && x.yazar !== k.yazar);
  const t = Number(an);
  const davet = an && t >= 0 && t < k.sure ? `<div class="davet">${simge("paylas")}<span>Sana bu eserin <b>${saat(t)}</b> anı paylaşıldı.</span>
    <button class="dev-cal istek-dugme" data-im-git="${k.id}|${Math.floor(t)}">${simge("cal")}<span>O andan dinle</span></button></div>` : "";
  return `<div class="sayfa">${davet}
    <div class="eser-ust" style="${renkStil(k)}"><div class="eser-kapak egik">${kapak(k)}</div>
      <div class="eser-bilgi"><small>Sesli kitap</small><h1>${kac(k.eser)}</h1>
        <div class="eser-meta"><b>${kac(k.yazar)}</b> · ${kac(k.ulke)} · ${sure(k.sure)}${k.ses ? ` · Ses: ${kac(k.ses)}` : ""}</div></div></div>
    <div class="eser-eylem">
      <button class="dev-cal${simdiki && simdiki.id === k.id && !ses.paused ? " caliyor" : ""}" data-cal="${k.id}">${calDur}<span class="js-etiket">${etiket}</span></button>
      ${basladi ? `<button class="ikincil" data-bastan="${k.id}">${simge("bastan")}Baştan başla</button>` : ""}
      <button class="ikincil${bitti ? " secili" : ""}" data-bitti="${k.id}">${simge("onay")}${bitti ? "Bitti" : "Bitti olarak işaretle"}</button>
      <button class="ikincil${listede(k.id) ? " secili" : ""}" data-sonra="${k.id}">${simge(listede(k.id) ? "onay" : "liste")}${listede(k.id) ? "Sonra dinle listende" : "Sonra dinle"}</button>
      <button class="ikincil${begenildi(k.id) ? " secili" : ""}" data-begen="${k.id}" aria-pressed="${begenildi(k.id)}">${simge(begenildi(k.id) ? "kalpDolu" : "kalp")}${begenildi(k.id) ? "Beğendin" : "Beğen"}</button>
      ${indirDugmesi(k)}
      <button class="ikincil" data-paylas="${k.id}">${simge("paylas")}Paylaş</button>
      <button class="ikincil" data-kart="${k.id}">${simge("resim")}Hikâye kartı</button>
    </div>
    ${basladi ? `<div class="eser-ilerleme">%${Math.round(o * 100)} dinlendi · ${sure(k.sure * (1 - o))} kaldı<div class="cizgi"><i style="width:${(o * 100).toFixed(1)}%"></i></div></div>` : ""}
    ${k.tanitim ? `<section class="hakkinda"><div class="raf-bas"><h2>Hakkında</h2></div><p>${kac(k.tanitim)}</p>
      ${k.yazarBilgi ? `<p class="yazar-bilgi"><b>${kac(k.yazar)}</b> · ${kac(k.yazarBilgi)}</p>` : ""}</section>` : ""}
    ${imListesi(k)}
    ${raf(`${kac(k.yazar)} yazarından`, ayni)}
    ${raf("Bunları da sevebilirsin", benzer)}
  </div>`;
}

function indirDugmesi(k) {
  if (!("caches" in window)) return "";
  if (k.id in indiriliyor) return `<button class="ikincil" disabled>${simge("indir")}İndiriliyor %${indiriliyor[k.id]}</button>`;
  if (indirildi(k)) return `<button class="ikincil secili" data-indir-sil="${k.id}">${simge("onay")}Telefonda · ${mb(k.boyut)} · Sil</button>`;
  return `<button class="ikincil" data-indir="${k.id}">${simge("indir")}İndir · ${mb(k.boyut)}</button>`;
}

function imListesi(k) {
  const imler = durum.imler[k.id] || [];
  if (!imler.length) return "";
  return `<section class="imler"><div class="raf-bas"><h2>Yer imleri</h2></div>${imler.map((m, i) =>
    `<div class="im"><button class="im-git" data-im-git="${k.id}|${m.t}">${simge("cal")}<b>${saat(m.t)}</b></button>
      <span class="im-not">${m.not ? kac(m.not) : "Not yok"}</span>
      <button class="im-sil" data-im-sil="${k.id}|${i}" aria-label="Yer imini sil">${simge("cop")}</button></div>`).join("")}</section>`;
}

// ---------- indirme (telefonun kendi depolamasına; Netlify'da hiçbir şey tutulmaz) ----------
async function indir(k) {
  indiriliyor[k.id] = 0;
  yenile();
  try {
    if (navigator.storage && navigator.storage.persist) await navigator.storage.persist();  // tarayıcı kendiliğinden silmesin
    const c = await caches.open(DEPO);
    for (let i = 0; i < k.parcalar.length; i++) {
      const u = `${k.yol}/${i + 1}.mp3`;
      if (!(await c.match(u))) {
        const r = await fetch(u, { cache: "no-store" });
        if (r.status !== 200) throw new Error(String(r.status));
        await c.put(u, r);
      }
      indiriliyor[k.id] = Math.round(((i + 1) / k.parcalar.length) * 100);
      if (location.hash === `#/eser/${k.id}`) yenile();
    }
    durum.indirilen[k.id] = k.yol;
    yaz();
    bildir(`${k.eser} telefona indirildi (${mb(k.boyut)})`);
  } catch (h) {
    bildir(h && h.name === "QuotaExceededError" ? "Telefonda yer kalmadı" : "İndirme yarıda kaldı, tekrar dene");
  } finally {
    delete indiriliyor[k.id];
    yenile();
  }
}

async function indirSil(id, yol) {
  const c = await caches.open(DEPO);
  for (const r of await c.keys()) if (new URL(r.url).pathname.startsWith(yol + "/")) await c.delete(r);
  delete durum.indirilen[id];
  yaz();
}

// eser yeniden kodlanınca (yolu değişince) ya da siteden çıkınca eski indirme telefonda yer kaplamasın
async function eskiIndirmeleriTemizle() {
  if (!("caches" in window)) return;
  for (const [id, yol] of Object.entries(durum.indirilen)) {
    const k = eserBul(id);
    if (!k || k.yol !== yol) await indirSil(id, yol);
  }
}

function karneSayfa() {
  const g = durum.gunluk, h = durum.hedef * 60;
  const top = Object.values(g).reduce((a, b) => a + b, 0);
  const hafta = [...Array(7)].map((_, i) => { const d = new Date(); d.setDate(d.getDate() - 6 + i); return { ad: d.toLocaleDateString("tr", { weekday: "short" }), sn: g[gun(d)] || 0 }; });
  const haftaTop = hafta.reduce((a, x) => a + x.sn, 0), enCok = Math.max(h, ...hafta.map((x) => x.sn));
  const kutu = (ad, deger) => `<div class="karne-kutu"><small>${ad}</small><b>${deger}</b></div>`;
  return `<div class="sayfa"><div class="ust-renk" style="--ust:#1f4f6b"><h1 class="selam">Dinleme karnen</h1>${hedefKutusu()}${hikayeDugmesi(true)}</div>
    <div class="karne-izgara">${kutu("Toplam dinleme", sureYaz(top))}${kutu("Bu hafta", sureYaz(haftaTop))}
      ${kutu("Bitirilen eser", katalog.filter((k) => durum.bitti[k.id]).length)}${kutu("Şu anki seri", `${seri()} gün`)}
      ${kutu("En uzun seri", `${enUzunSeri()} gün`)}${kutu("Günlük ortalama", sureYaz(haftaTop / 7))}</div>
    <section class="raf"><div class="raf-bas"><h2>Son 7 gün</h2></div>
      <div class="grafik"><i class="hedef-cizgi" style="bottom:calc(26px + 154px * ${(h / enCok).toFixed(3)})"></i>${hafta.map((x) =>
        `<div class="sutun${x.sn >= h ? " tamam" : ""}"><small>${Math.round(x.sn / 60)}</small><i style="height:${((x.sn / enCok) * 100).toFixed(1)}%"></i><span>${x.ad}</span></div>`).join("")}</div>
      <p class="vakit-not">Kesik çizgi günlük hedefin (${durum.hedef} dk). Sütunlardaki sayılar dakika.</p></section>
    ${isiHaritasi()}
    ${rozetBolumu()}
    <section class="raf"><div class="raf-bas"><h2>Günlük hedefin</h2></div>
      <div class="cipler">${[10, 20, 30, 45, 60].map((d) => `<button class="cip" data-hedef="${d}" aria-pressed="${durum.hedef === d}">${d} dk</button>`).join("")}</div></section>
    <section class="raf tasima"><div class="raf-bas"><h2>Verilerini taşı</h2></div>
      <p class="vakit-not">Kaldığın yerler, bitirdiklerin, yer imlerin, beğenilerin ve karnen yalnız bu cihazda durur.
        Telefondan bilgisayara (ya da yeni telefona) geçerken dosyaya kaydet, öbür cihazda “Dosyadan yükle” ile al. İkisindeki bilgiler birleşir, hiçbiri silinmez.</p>
      <div class="eser-eylem"><button class="ikincil" data-disa>${simge("indir")}Dosyaya kaydet</button>
        <label class="ikincil dosya-sec">${simge("tasi")}Dosyadan yükle<input type="file" accept="application/json,.json" data-ice hidden></label></div></section>
    <p class="dipnot">Karnen yalnız bu telefonda tutulur.</p></div>`;
}

// ---------- yönlendirme ----------
function yonlendir() {
  const yol = decodeURIComponent(location.hash.slice(1) || "/");
  const [, bolum, deger, ek] = yol.split("/");
  let html, sekme = "ana";
  if (bolum === "eser") html = eserSayfa(deger, ek);
  else if (bolum === "ara") { sekme = "ara"; aramaTur = deger || null; if (deger) aramaMetni = ""; html = araSayfa(); }
  else if (bolum === "kitapligim") { sekme = "kitapligim"; if (deger) kitaplikSekme = deger; html = kitaplikSayfa(); }
  else if (bolum === "karne") { sekme = "kitapligim"; html = karneSayfa(); }
  else html = anaSayfa();
  document.body.classList.toggle("cevrimdisi", cevrimdisi());
  $("#icerik").innerHTML = html;
  simgeleriDoldur($("#icerik"));
  for (const a of $$("[data-sekme]")) a.classList.toggle("aktif", a.dataset.sekme === sekme && bolum !== "eser");
  $("#ana").scrollTop = 0;
  window.scrollTo(0, 0);
  kenarCiz();
}

// yalnız şu an ekranda olan sayfayı yeniden çizer, kaydırma yerini korur
function yenile() {
  const ana = $("#ana"), y = ana.scrollTop, wy = window.scrollY;
  const raflar = $$(".raf-kaydir").map((r) => r.scrollLeft);
  const odak = document.activeElement && document.activeElement.id;
  yonlendir();
  ana.scrollTop = y;
  window.scrollTo(0, wy);
  $$(".raf-kaydir").forEach((r, i) => { r.scrollLeft = raflar[i] || 0; });
  if (odak === "ara") { const g = $("#ara"); g.focus(); g.setSelectionRange(g.value.length, g.value.length); }
}

function kenarCiz() {
  const son = sonDinlenenler().slice(0, 12);
  $("#kenar-son").innerHTML = son.length ? son.map(satir).join("") : `<p class="kenar-bos">Dinlemeye başladığın eserler burada görünür.</p>`;
}

// ---------- çalar ----------
const genel = () => (simdiki && parca >= 0 ? baslar[parca] + (ses.currentTime || 0) : 0);

// eserin bütünündeki t. saniyeye git; gerekirse o parçayı yükler
function git(t, oynat = !ses.paused) {
  t = Math.max(0, Math.min(simdiki.sure - 0.5, t));
  let p = baslar.length - 1;
  while (p > 0 && baslar[p] > t) p--;
  const ic = t - baslar[p];
  if (p !== parca) {
    parca = p;
    ses.src = `${simdiki.yol}/${p + 1}.mp3`;
    // yeni dosya yüklenince tarayıcı hızı defaultPlaybackRate'e döndürür
    ses.defaultPlaybackRate = ses.playbackRate = durum.hiz;
    if (ic > 0) ses.addEventListener("loadedmetadata", () => { ses.currentTime = ic; }, { once: true });
  } else {
    ses.currentTime = ic;
  }
  if (oynat) { duraklamaAni = 0; cal(); }
  zamanCiz(t);
  kaydet(true, t);
}

function ac(id, bastan = false) {
  const k = eserBul(id);
  if (!k) return;
  if (simdiki && simdiki.id === id && !bastan) return ses.paused ? cal() : ses.pause();
  kaydet(true);
  simdiki = k;
  durum.son = id;
  const sonZaman = durum.zaman[id];  // akıllı geri sarma için: kaydı güncellemeden önceki son dinleme anı
  durum.zaman[id] = Date.now();
  durum.sonra = durum.sonra.filter((x) => x !== id);  // dinlemeye başlanan eser "Sonra dinle"den "Devam eden"e geçer
  baslar = k.parcalar.reduce((a, d) => (a.push(a[a.length - 1] + d), a), [0]).slice(0, -1);
  parca = -1;
  ses.removeAttribute("src");
  const geri = bastan || durum.bitti[id] || !durum.konum[id] ? 0 : geriSar(sonZaman);
  const bas = bastan || durum.bitti[id] ? 0 : Math.max(0, (durum.konum[id] || 0) - geri);
  if (geri) setTimeout(() => bildir(`Uzun aradan sonra ${geri} sn geriden başladı`), 400);
  if (durum.bitti[id] || bastan) { delete durum.bitti[id]; durum.konum[id] = 0; }
  yaz();
  calarCiz();
  git(bas, true);
}

// kilit ekranı ve bildirim için kapağın resmi (sitedeki kapağın aynısı, tuvale çizilir)
function kapakResmi(k) {
  const c = document.createElement("canvas"), N = 512;
  c.width = c.height = N;
  kapakCiz(c.getContext("2d"), k, 0, 0, N);
  return c.toDataURL("image/png");
}

// sitedeki kapağı tuvalin (x0, y0) noktasına N boyunda çizer; desenResmi verilirse esere özel deseni de koyar
function kapakCiz(x, k, x0, y0, N, desenResmi) {
  const [a, b] = renk(k), o = N / 512;
  x.save();
  x.translate(x0, y0);
  x.beginPath(); x.roundRect ? x.roundRect(0, 0, N, N, 12 * o) : x.rect(0, 0, N, N); x.clip();
  let g = x.createLinearGradient(0, 0, N * 0.6, N);
  g.addColorStop(0, a); g.addColorStop(1, "#000");
  x.fillStyle = g; x.fillRect(0, 0, N, N);
  g = x.createRadialGradient(N * 0.85, 0, 0, N * 0.85, 0, N * 0.9);
  g.addColorStop(0, b); g.addColorStop(1, "transparent");
  x.globalAlpha = 0.85; x.fillStyle = g; x.fillRect(0, 0, N, N); x.globalAlpha = 1;
  if (desenResmi) x.drawImage(desenResmi, 0, 0, N, N);
  g = x.createLinearGradient(0, N * 0.45, 0, N);
  g.addColorStop(0, "transparent"); g.addColorStop(1, "rgba(0,0,0,.35)");
  x.fillStyle = g; x.fillRect(0, 0, N, N);
  x.fillStyle = "#fff"; x.textBaseline = "alphabetic"; x.textAlign = "left";
  x.font = `700 ${30 * o}px Figtree, sans-serif`;
  x.fillText(k.ulke.toLocaleUpperCase("tr"), 52 * o, 80 * o);
  x.font = `600 ${58 * o}px Fraunces, Georgia, serif`;
  const satirlar = [], kelime = k.eser.split(" ");
  let s = "";
  for (const w of kelime) { const d = s ? s + " " + w : w; if (x.measureText(d).width > N - 104 * o && s) { satirlar.push(s); s = w; } else s = d; }
  satirlar.push(s);
  const ust = N - 120 * o - (satirlar.length - 1) * 64 * o;
  satirlar.forEach((l, i) => x.fillText(l, 52 * o, ust + i * 64 * o));
  x.fillRect(52 * o, N - 96 * o, 70 * o, 4 * o);
  x.font = `700 ${28 * o}px Figtree, sans-serif`;
  x.fillText(k.yazar.toLocaleUpperCase("tr"), 52 * o, N - 52 * o);
  x.restore();
}

function calarCiz() {
  const k = simdiki;
  document.body.classList.add("calar-acik");
  $("#calar").hidden = false;
  $("#calar").style.cssText = renkStil(k);
  $("#tam").style.cssText = renkStil(k);
  for (const e of $$(".js-ad")) e.textContent = k.eser;
  for (const e of $$(".js-yazar")) e.textContent = k.yazar;
  $("#calar-kapak").innerHTML = kapak(k);
  $("#tam-kapak").innerHTML = kapak(k);
  $("#tam-esere").href = `#/eser/${k.id}`;
  if ("mediaSession" in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({ title: k.eser, artist: k.yazar, album: "Melih'ten Dinle",
      artwork: [{ src: kapakResmi(k), sizes: "512x512", type: "image/png" }] });
  }
  hizCiz();
}

function cal() {
  if (simdiki && duraklamaAni && ses.paused) {
    const geri = geriSar(duraklamaAni);
    duraklamaAni = 0;
    if (geri && genel() > geri) { git(genel() - geri, false); bildir(`Uzun aradan sonra ${geri} sn geri sarıldı`); }
  }
  ses.play().catch(() => { /* tarayıcı izin vermezse düğme "Çal" kalır */ });
}

function kaydet(zorla, t = genel()) {
  if (!simdiki || parca < 0) return;
  if (!zorla && Math.abs(t - sonKayit) < 5) return;
  if (t > 0) durum.konum[simdiki.id] = Math.floor(t);
  durum.zaman[simdiki.id] = Date.now();
  sonKayit = t;
  yaz();
}

function zamanCiz(t = genel()) {
  if (!simdiki) return;
  const top = simdiki.sure, o = Math.min(1, t / top);
  for (const e of $$(".js-gecen")) e.textContent = saat(t);
  for (const e of $$(".js-kalan")) e.textContent = "-" + saat((top - t) / durum.hiz);
  for (const e of $$(".js-cizgi")) e.style.width = `${(o * 100).toFixed(2)}%`;
  if (!surukleniyor) for (const e of $$(".js-konum")) { e.value = Math.round(o * 1000); e.style.setProperty("--dolu", `${(o * 100).toFixed(2)}%`); }
}

// çalıyor/duraklatıldı durumunu bütün düğmelere yansıt
function calDurumu() {
  const caliyor = !ses.paused;
  document.body.classList.toggle("caliyor", caliyor);
  document.title = simdiki && caliyor ? `▶ ${simdiki.eser} · Melih'ten Dinle` : "Melih'ten Dinle";
  for (const b of $$('[data-islem="calduraklat"]')) { b.classList.toggle("caliyor", caliyor); b.setAttribute("aria-label", caliyor ? "Duraklat" : "Çal"); }
  for (const b of $$("[data-cal]")) {
    const bu = simdiki && b.dataset.cal === simdiki.id && caliyor;
    b.classList.toggle("caliyor", bu);
    const et = $(".js-etiket", b);
    if (et) et.textContent = bu ? "Duraklat" : devamEdiyor(eserBul(b.dataset.cal)) ? "Devam et" : "Dinle";
  }
  for (const s of $$(".satir")) {
    const id = $("[data-cal]", s)?.dataset.cal;
    s.classList.toggle("calan", !!simdiki && id === simdiki.id);
  }
}

const atla = (sn) => git(genel() + sn);

let bildirimSaat = null;
function bildir(metin) {
  let b = $("#bildirim");
  if (!b) { b = document.createElement("div"); b.id = "bildirim"; b.setAttribute("role", "status"); document.body.append(b); }
  b.textContent = metin;
  b.classList.add("gorunur");
  clearTimeout(bildirimSaat);
  bildirimSaat = setTimeout(() => b.classList.remove("gorunur"), 2600);
}

// ---------- E: hız ve uyku menüsü ----------
function menuAc(dugme, baslik, secenekler, sec) {
  menuKapat();
  const m = document.createElement("div");
  m.className = "secim-menu";
  m.setAttribute("role", "menu");
  m.innerHTML = `<div class="secim-bas">${baslik}</div>` + secenekler.map((s, i) =>
    `<button role="menuitemradio" aria-checked="${s.secili}" data-i="${i}">${s.etiket}${s.secili ? simge("onay") : ""}</button>`).join("");
  document.body.append(m);
  const kutu = dugme.getBoundingClientRect();
  if (innerWidth >= 900) {  // masaüstü: düğmenin üstünde açılır pencere
    m.style.left = `${Math.min(innerWidth - m.offsetWidth - 8, Math.max(8, kutu.left + kutu.width / 2 - m.offsetWidth / 2))}px`;
    m.style.top = `${kutu.top - m.offsetHeight - 8}px`;
  } else m.classList.add("alt-sayfa");  // telefon: alttan çıkan sayfa
  m.addEventListener("click", (e) => {
    const b = e.target.closest("[data-i]");
    if (b) { sec(secenekler[b.dataset.i].deger); menuKapat(); }
  });
  setTimeout(() => document.addEventListener("click", menuDisi), 0);
  m.querySelector('[aria-checked="true"]')?.focus();
}
function menuDisi(e) { if (!e.target.closest(".secim-menu")) menuKapat(); }
function menuKapat() { $(".secim-menu")?.remove(); document.removeEventListener("click", menuDisi); }

function uykuKur(dk) {
  clearInterval(uykuSaat);
  ses.volume = 1;
  uykuBitis = dk ? Date.now() + dk * 60000 : 0;
  if (uykuBitis) {
    uykuSaat = setInterval(() => {
      const kalan = uykuBitis - Date.now();
      if (kalan <= 0) {
        ses.pause();
        ses.volume = 1;
        clearInterval(uykuSaat);
        uykuBitis = 0;
        bildir("Uyku zamanlayıcısı: dinleme durduruldu");
      } else if (kalan < 30000 && !ses.paused) ses.volume = Math.max(0.05, kalan / 30000);  // uyandırmadan, yavaşça kısılır
      uykuCiz();
    }, 1000);
  }
  uykuCiz();
  bildir(dk ? `Uyku zamanlayıcısı: ${dk} dk sonra durur` : "Uyku zamanlayıcısı kapatıldı");
}

function hizCiz() {
  for (const b of $$(".js-hiz")) b.textContent = `${String(durum.hiz).replace(".", ",")}×`;
}

function uykuCiz() {
  const kalan = uykuBitis ? Math.max(0, Math.ceil((uykuBitis - Date.now()) / 60000)) : 0;
  for (const b of $$(".js-uyku")) {
    b.classList.toggle("acik", !!uykuBitis);
    $("b", b).textContent = uykuBitis ? `${kalan} dk` : "";
    b.setAttribute("aria-label", uykuBitis ? `Uyku zamanlayıcısı: ${kalan} dakika kaldı` : "Uyku zamanlayıcısı kapalı");
  }
}

// F: telefonda tam ekran çaları aşağı kaydırarak kapatma
(() => {
  const tam = $("#tam");
  let y0 = null, dy = 0;
  tam.addEventListener("touchstart", (e) => { y0 = tam.scrollTop <= 0 && !e.target.closest("input") ? e.touches[0].clientY : null; dy = 0; }, { passive: true });
  tam.addEventListener("touchmove", (e) => {
    if (y0 === null) return;
    dy = Math.max(0, e.touches[0].clientY - y0);
    tam.style.transition = "none";
    tam.style.transform = `translateY(${dy}px)`;
  }, { passive: true });
  tam.addEventListener("touchend", () => {
    if (y0 === null) return;
    tam.style.transition = ""; tam.style.transform = "";
    if (dy > 120) tamAc(false);
    y0 = null;
  });
})();

// tam ekranda kapağa çift dokunuş: sol yarı 15 sn geri, sağ yarı 30 sn ileri
(() => {
  const kap = $("#tam-kapak");
  let son = 0;
  kap.addEventListener("click", (e) => {
    if (!simdiki) return;
    const an = Date.now();
    if (an - son > 320) { son = an; return; }
    son = 0;
    const r = kap.getBoundingClientRect(), sol = e.clientX < r.left + r.width / 2;
    atla(sol ? -15 : 30);
    const iz = document.createElement("span");
    iz.className = `dokunus ${sol ? "sol" : "sag"}`;
    iz.textContent = sol ? "−15 sn" : "+30 sn";
    kap.append(iz);
    setTimeout(() => iz.remove(), 700);
  });
})();

for (const ad of ["online", "offline"]) window.addEventListener(ad, () => {
  bildir(ad === "offline" ? "İnternet yok: yalnız telefona indirdiğin eserler çalınabilir" : "İnternet geri geldi");
  if (katalog.length) yenile();
});

function tamAc(acik) {
  $("#tam").classList.toggle("acik", acik);
  $("#tam").setAttribute("aria-hidden", String(!acik));
  document.body.style.overflow = acik ? "hidden" : "";
}

// ---------- olaylar ----------
document.addEventListener("click", (e) => {
  const c = e.target.closest("[data-cal]");
  if (c) { e.preventDefault(); kutlamaKapat(); return ac(c.dataset.cal); }
  const bs = e.target.closest("[data-bastan]");
  if (bs) return ac(bs.dataset.bastan, true);
  const bt = e.target.closest("[data-bitti]");
  if (bt) {
    setTimeout(rozetDenetle, 600);
    const id = bt.dataset.bitti;
    if (durum.bitti[id]) delete durum.bitti[id];
    else { durum.bitti[id] = true; durum.konum[id] = 0; if (simdiki && simdiki.id === id) ses.pause(); }
    bildir(durum.bitti[id] ? "Bitti olarak işaretlendi" : "Bitmedi olarak işaretlendi");
    yaz();
    return yenile();
  }
  const ind = e.target.closest("[data-indir]");
  if (ind) return indir(eserBul(ind.dataset.indir));
  const isl = e.target.closest("[data-indir-sil]");
  if (isl) {
    const k = eserBul(isl.dataset.indirSil);
    return indirSil(k.id, k.yol).then(() => { bildir(`${k.eser} telefondan silindi`); yenile(); });
  }
  const ig = e.target.closest("[data-im-git]");
  if (ig) {
    const [id, t] = ig.dataset.imGit.split("|");
    if (simdiki && simdiki.id === id) return git(Number(t), true);
    delete durum.bitti[id];
    durum.konum[id] = Number(t);
    return ac(id);
  }
  const ims = e.target.closest("[data-im-sil]");
  if (ims) {
    const [id, i] = ims.dataset.imSil.split("|");
    durum.imler[id].splice(Number(i), 1);
    if (!durum.imler[id].length) delete durum.imler[id];
    yaz();
    bildir("Yer imi silindi");
    return yenile();
  }
  if (e.target.closest("[data-istek]")) {
    const ad = prompt("Hangi eseri dinlemek istersin? (eser ve yazar)");
    if (ad && ad.trim()) window.open(`https://wa.me/${whatsapp}?text=${encodeURIComponent(`Merhaba Melih, Melih'ten Dinle'ye şu eseri ekler misin: ${ad.trim()}`)}`, "_blank");
    return;
  }
  const so = e.target.closest("[data-sonra]");
  if (so) {
    const id = so.dataset.sonra;
    if (listede(id)) { durum.sonra = durum.sonra.filter((x) => x !== id); bildir("Sonra dinle listesinden çıkarıldı"); }
    else { durum.sonra.push(id); bildir("Sonra dinle listesine eklendi"); }
    yaz();
    return yenile();
  }
  const pa = e.target.closest("[data-paylas]");
  if (pa) {
    const k = eserBul(pa.dataset.paylas), url = `${location.origin}/#/eser/${k.id}`;
    const metin = `${k.eser} (${k.yazar}) Melih'ten Dinle'de, bence dinle:`;
    if (navigator.share) navigator.share({ title: k.eser, text: metin, url }).catch(() => {});
    else window.open(`https://wa.me/?text=${encodeURIComponent(`${metin} ${url}`)}`, "_blank");
    return;
  }
  const be = e.target.closest("[data-begen]");
  if (be) {
    const id = be.dataset.begen;
    if (durum.begen[id]) delete durum.begen[id]; else durum.begen[id] = Date.now();
    yaz();
    bildir(durum.begen[id] ? "Beğendiklerine eklendi" : "Beğendiklerinden çıkarıldı");
    setTimeout(rozetDenetle, 600);
    return yenile();
  }
  if (e.target.closest("[data-sans]")) {
    const aday = katalog.filter((k) => !durum.bitti[k.id] && !devamEdiyor(k) && (!simdiki || k.id !== simdiki.id));
    const k = aday[Math.floor(Math.random() * aday.length)];
    if (k) { location.hash = `#/eser/${k.id}`; bildir(`Senin için seçtik: ${k.eser}`); }
    return;
  }
  const sr = e.target.closest("[data-sirala]");
  if (sr) { durum.sirala = sr.dataset.sirala; yaz(); return yenile(); }
  const ar = e.target.closest("[data-arama]");
  if (ar) { aramaMetni = ar.dataset.arama; return yenile(); }
  if (e.target.closest("[data-arama-temizle]")) { e.preventDefault(); durum.aramalar = []; yaz(); return yenile(); }
  if (e.target.closest("[data-disa]")) return disaAktar();
  if (e.target.closest("[data-hikaye]")) return hikayeAc();
  const ka = e.target.closest("[data-kart]");
  if (ka) return kartPaylas(eserBul(ka.dataset.kart));
  if (e.target.closest("[data-an-paylas]")) return anPaylas();
  if (e.target.closest("[data-kur]")) return kur();
  if (e.target.closest("[data-kur-gizle]")) { durum.kurGizle = true; yaz(); return yenile(); }
  if (e.target.closest("[data-rozet-git]")) { $(".rozet-pop")?.remove(); location.hash = "#/karne"; return; }
  if (e.target.closest("[data-kutlama-kapat]")) return kutlamaKapat();
  const ku = e.target.closest("[data-kutlama-cal]");
  if (ku) { kutlamaKapat(); return ac(ku.dataset.kutlamaCal); }
  const va = e.target.closest("[data-vakit]");
  if (va) { vakit = vakit === Number(va.dataset.vakit) ? 0 : Number(va.dataset.vakit); return yenile(); }
  const he = e.target.closest("[data-hedef]");
  if (he) { durum.hedef = Number(he.dataset.hedef); yaz(); bildir(`Günlük hedef: ${durum.hedef} dk`); return yenile(); }
  const sk = e.target.closest("[data-sekme-sec]");
  if (sk) { kitaplikSekme = sk.dataset.sekmeSec; return yenile(); }
  const is = e.target.closest("[data-islem]");
  if (!is) return;
  const islem = is.dataset.islem;
  if (islem === "calduraklat") ses.paused ? cal() : ses.pause();
  else if (islem === "geri") atla(-15);
  else if (islem === "ileri") atla(30);
  else if (islem === "imle" && simdiki) {
    const t = Math.floor(genel());
    const not = prompt(`${saat(t)} için yer imi. İstersen kısa bir not yaz:`, "");
    if (not === null) return;
    (durum.imler[simdiki.id] = durum.imler[simdiki.id] || []).push({ t, not: not.trim().slice(0, 140), zaman: Date.now() });
    durum.imler[simdiki.id].sort((a, b) => a.t - b.t);
    yaz();
    bildir(`Yer imi eklendi: ${saat(t)}`);
    setTimeout(rozetDenetle, 600);
    if (location.hash === `#/eser/${simdiki.id}`) yenile();
  }
  else if (islem === "kart" && simdiki) kartPaylas(simdiki);
  else if (islem === "tam-ac") tamAc(true);
  else if (islem === "tam-kapat") tamAc(false);
  else if (islem === "hiz") {
    e.stopPropagation();
    menuAc(is, "Okuma hızı", HIZLAR.map((h) => ({ etiket: `${String(h).replace(".", ",")}×${h === 1 ? " (normal)" : ""}`, deger: h, secili: h === durum.hiz })), (h) => {
      durum.hiz = h;
      ses.defaultPlaybackRate = ses.playbackRate = h;
      hizCiz(); zamanCiz(); yaz();
      bildir(`Okuma hızı: ${String(h).replace(".", ",")}×`);
    });
  } else if (islem === "uyku") {
    e.stopPropagation();
    const kalan = uykuBitis ? Math.ceil((uykuBitis - Date.now()) / 60000) : 0;
    menuAc(is, "Uyku zamanlayıcısı", UYKU.map((dk) => ({ etiket: dk ? `${dk} dakika` : "Kapalı", deger: dk,
      secili: dk ? false : !uykuBitis })).concat(uykuBitis ? [] : []), uykuKur);
    if (kalan) $(".secim-bas").textContent = `Uyku zamanlayıcısı · ${kalan} dk kaldı`;
  }
});

document.addEventListener("input", (e) => {
  if (e.target.id === "ara") {
    aramaMetni = e.target.value;
    clearTimeout(aramaSaat);
    aramaSaat = setTimeout(aramaKaydet, 1500);
    $("#ara-sonuc").innerHTML = araSonuc();
    simgeleriDoldur($("#ara-sonuc"));
  } else if (e.target.classList.contains("js-konum") && simdiki) {
    surukleniyor = true;
    const v = e.target.value / 1000;
    e.target.style.setProperty("--dolu", `${v * 100}%`);
    for (const g of $$(".js-gecen")) g.textContent = saat(v * simdiki.sure);
  }
});
// sonuç veren aramalar "Son aramaların"a girer (en çok 6)
let aramaSaat = null;
function aramaKaydet() {
  const a = aramaMetni.trim();
  if (a.length < 2 || !$("#ara-sonuc .satir")) return;
  durum.aramalar = [a, ...durum.aramalar.filter((x) => sade(x) !== sade(a))].slice(0, 6);
  yaz();
}

// ---------- verileri taşı (dosyaya kaydet / dosyadan yükle) ----------
function disaAktar() {
  const { indirilen, ...veri } = durum;  // indirilenler cihaza özeldir, taşınmaz
  const b = new Blob([JSON.stringify({ uygulama: "melihten-dinle", surum: 1, tarih: new Date().toISOString(), veri })], { type: "application/json" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(b), download: `melihten-dinle-verilerim-${gun()}.json` });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  bildir("Verilerin dosyaya kaydedildi");
}
function iceAktar(dosya) {
  dosya.text().then((metin) => {
    const j = JSON.parse(metin), v = j && j.uygulama === "melihten-dinle" && j.veri;
    if (!v) throw new Error("dosya");
    // birleştir: hiçbir bilgi kaybolmaz; aynı eserde en ileri konum, aynı günde en uzun dinleme alınır
    for (const [id, t] of Object.entries(v.konum || {})) durum.konum[id] = Math.max(durum.konum[id] || 0, t);
    for (const [id, t] of Object.entries(v.zaman || {})) durum.zaman[id] = Math.max(durum.zaman[id] || 0, t);
    for (const [g, sn] of Object.entries(v.gunluk || {})) durum.gunluk[g] = Math.max(durum.gunluk[g] || 0, sn);
    Object.assign(durum.bitti, v.bitti || {});
    Object.assign(durum.begen, v.begen || {});
    Object.assign(durum.rozet, v.rozet || {});
    (v.saatler || []).forEach((sn, i) => { durum.saatler[i] = Math.max(durum.saatler[i] || 0, sn || 0); });
    for (const [id, l] of Object.entries(v.imler || {})) {
      const var_ = durum.imler[id] || [];
      durum.imler[id] = [...var_, ...l.filter((m) => !var_.some((x) => x.t === m.t))].sort((a, b) => a.t - b.t);
    }
    durum.sonra = [...durum.sonra, ...(v.sonra || []).filter((id) => !durum.sonra.includes(id))];
    if (!durum.son && v.son) durum.son = v.son;
    yaz();
    yenile();
    bildir("Veriler yüklendi ve bu cihazdakilerle birleştirildi");
  }).catch(() => bildir("Bu dosya okunamadı. Melih'ten Dinle'den kaydedilmiş dosyayı seç."));
}

// ---------- eser bitince kutlama ----------
function kutlama(k, sonraki) {
  const bitenSay = Object.keys(durum.bitti).filter(eserBul).length;
  const oneri = sonraki || [...katalog.filter((x) => x.yazar === k.yazar), ...katalog.filter((x) => x.koken === k.koken)]
    .find((x) => x.id !== k.id && !durum.bitti[x.id] && !devamEdiyor(x));
  kutlamaKapat();
  const d = document.createElement("div");
  d.className = "kutlama";
  d.setAttribute("role", "dialog");
  d.setAttribute("aria-label", "Eser bitti");
  d.innerHTML = `<div class="kutlama-kart" style="${renkStil(k)}">
    <div class="konfeti" aria-hidden="true">${[...Array(18)].map((_, i) => `<i style="--i:${i}"></i>`).join("")}</div>
    <div class="kutlama-kapak">${kapak(k)}</div>
    <h2>Tebrikler, bitirdin!</h2>
    <p><b>${kac(k.eser)}</b> · ${kac(k.yazar)}<br>${sure(k.sure)} dinledin. Bu, bitirdiğin ${bitenSay}. eser.</p>
    ${oneri ? `<div class="kutlama-oneri"><small>${sonraki ? "Sonra dinle listende sıradaki" : "Sıradaki önerimiz"}</small>${satir(oneri)}</div>` : ""}
    <div class="kutlama-dugme">${oneri ? `<button class="dev-cal istek-dugme" data-kutlama-cal="${oneri.id}">${simge("cal")}<span>${sonraki ? "Şimdi başlat" : "Dinle"}</span></button>` : ""}
      <button class="ikincil" data-kutlama-kapat>Kapat</button></div></div>`;
  document.body.append(d);
  simgeleriDoldur(d);
  d.addEventListener("click", (e) => { if (e.target === d) kutlamaKapat(); });
}
function kutlamaKapat() { $(".kutlama")?.remove(); }

document.addEventListener("change", (e) => {
  if (e.target.matches("[data-ice]")) { if (e.target.files[0]) iceAktar(e.target.files[0]); e.target.value = ""; return; }
  if (!e.target.classList.contains("js-konum") || !simdiki) return;
  surukleniyor = false;
  git((e.target.value / 1000) * simdiki.sure);
});

let sonRozet = 0;
let sonGecerli = 0, baglantiDeneme = 0, ilerlemeYok = null, onYukleme = null;

// bağlantı kopunca (ya da sunucu dosyayı yarıda keserse) kaldığı saniyeden yeniden yükleyip sürdürür
function yenidenBaglan() {
  if (!simdiki) return;
  baglantiDeneme++;
  if (baglantiDeneme > 8) { document.body.classList.remove("yukleniyor"); return bildir("Bağlantı kurulamadı. İnternetini kontrol edip tekrar çal."); }
  const bekle = Math.min(30, 2 ** baglantiDeneme);
  bildir("Bağlantı koptu, kaldığın yerden devam ediliyor…");
  document.body.classList.add("yukleniyor");
  setTimeout(() => { parca = -1; git(sonGecerli, true); }, bekle * 1000);
}

ses.addEventListener("timeupdate", () => {
  const an = Date.now();
  if (!ses.paused && sonTik && an - sonTik < 4000) {
    const g = gun(), once = durum.gunluk[g] || 0;
    durum.gunluk[g] = once + (an - sonTik) / 1000;
    const sa = new Date(an).getHours();
    durum.saatler[sa] = (durum.saatler[sa] || 0) + (an - sonTik) / 1000;
    if (an - sonRozet > 30000) { sonRozet = an; rozetDenetle(); }
    if (once < durum.hedef * 60 && durum.gunluk[g] >= durum.hedef * 60) bildir(`Bugünkü hedefin tamam! ${seri()} gündür seri`);
  }
  sonTik = an;
  zamanCiz(); kaydet(false);
  if (ses.currentTime > 0 && parca >= 0) sonGecerli = baslar[parca] + ses.currentTime;
  // D: parça bitimine 90 sn kala bir sonrakini önceden yükle (geçişte boşluk olmasın)
  if (simdiki && parca >= 0 && parca < baslar.length - 1 && simdiki.parcalar[parca] - ses.currentTime < 90) {
    const sonraki = `${simdiki.yol}/${parca + 2}.mp3`;
    if (!onYukleme || onYukleme.dataset.yol !== sonraki) {
      onYukleme = new Audio();
      onYukleme.preload = "auto";
      onYukleme.dataset.yol = sonraki;
      onYukleme.src = sonraki;
    }
  }
});
// B: ses beklerken çal düğmesinde yükleniyor halkası
for (const ad of ["waiting", "loadstart", "seeking"]) ses.addEventListener(ad, () => { if (!ses.paused || ad !== "seeking") document.body.classList.add("yukleniyor"); });
for (const ad of ["playing", "canplay", "pause", "seeked"]) ses.addEventListener(ad, () => document.body.classList.remove("yukleniyor"));
ses.addEventListener("playing", () => { baglantiDeneme = 0; });
ses.addEventListener("error", () => { if (simdiki && ses.getAttribute("src")) yenidenBaglan(); });
// C: çalarken 15 sn ilerleme olmazsa bağlantı takılmış say
setInterval(() => {
  if (!simdiki || ses.paused) { ilerlemeYok = null; return; }
  const t = genel();
  if (ilerlemeYok && ilerlemeYok.t === t && Date.now() - ilerlemeYok.zaman > 15000) { ilerlemeYok = null; yenidenBaglan(); }
  else if (!ilerlemeYok || ilerlemeYok.t !== t) ilerlemeYok = { t, zaman: Date.now() };
}, 5000);
ses.addEventListener("play", calDurumu);
ses.addEventListener("pause", () => { sonTik = 0; duraklamaAni = Date.now(); calDurumu(); kaydet(true); kenarCiz(); });
ses.addEventListener("ended", () => {
  // sunucu dosyayı yarıda keserse tarayıcı "bitti" sanar: parçanın gerçek süresine ulaşılmadıysa kaldığı yerden sür
  if (ses.currentTime < simdiki.parcalar[parca] - 3) return yenidenBaglan();
  if (parca < baslar.length - 1) return git(baslar[parca + 1], true); // sonraki parça, ara vermeden
  durum.bitti[simdiki.id] = true;
  durum.konum[simdiki.id] = 0;
  const sonraki = durum.sonra.map(eserBul).find((k) => k && !durum.bitti[k.id]);
  yaz();
  yenile();
  const biten = simdiki;
  kutlama(biten, sonraki);
  setTimeout(rozetDenetle, 2500);
  if (sonraki) {  // "Sonra dinle" listesindeki sıradaki eser kendiliğinden başlar
    setTimeout(() => { if (simdiki === biten && ses.paused) { kutlamaKapat(); ac(sonraki.id); } }, 8000);
  }
});
window.addEventListener("hashchange", () => { tamAc(false); kutlamaKapat(); hikayeKapat(); yonlendir(); });
window.addEventListener("pagehide", () => kaydet(true));
document.addEventListener("visibilitychange", () => document.hidden && kaydet(true));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { menuKapat(); hikayeKapat(); return tamAc(false); }
  if ($(".hikaye") && (e.key === "ArrowRight" || e.key === "ArrowLeft")) return hikayeGit(e.key === "ArrowRight" ? 1 : -1);
  if (!simdiki || e.target.closest("input, button, a, textarea")) return;
  if (e.key === " ") { e.preventDefault(); ses.paused ? cal() : ses.pause(); }
  if (e.key === "ArrowLeft") atla(-15);
  if (e.key === "ArrowRight") atla(30);
});

if ("mediaSession" in navigator) {
  navigator.mediaSession.setActionHandler("play", cal);
  navigator.mediaSession.setActionHandler("pause", () => ses.pause());
  navigator.mediaSession.setActionHandler("seekbackward", () => atla(-15));
  navigator.mediaSession.setActionHandler("seekforward", () => atla(30));
  try {
    navigator.mediaSession.setActionHandler("seekto", (d) => git(d.seekTime));
  } catch { /* eski tarayıcı */ }
}

// ---------- 1 Kasım 2026 ikinci tur: göz alıcı yenilikler ----------
// esere özel kapak deseni, günün eseri, canlı tam ekran, eğilen kapak, dinleme hikâyesi, rozetler,
// resimli hikâye kartı, anı paylaşma, dinleme takvimi, ana ekrana ekleme

// aynı tohumdan hep aynı sayılar (desen ve günün eseri her açılışta aynı çıksın)
function rastgele(t) {
  let h = 2166136261;
  for (const c of String(t)) h = Math.imul(h ^ c.codePointAt(0), 16777619);
  return () => {
    h = (h + 0x6d2b79f5) | 0;
    let x = Math.imul(h ^ (h >>> 15), h | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

// her esere kendine özgü bir motif: halkalar, dalgalar, kemerler, takımyıldız ya da çizgiler
const desenler = new Map();
function desen(k) {
  const anahtar = `${k.eser}|${k.yazar}`;
  if (desenler.has(anahtar)) return desenler.get(anahtar);
  const r = rastgele(anahtar), tur = Math.floor(r() * 5), s = [];
  const y = (a, b) => (a + r() * (b - a)).toFixed(1);
  const cizgi = (o) => `fill="none" stroke="#fff" stroke-width=".7" opacity="${o.toFixed(2)}"`;
  if (tur === 0) {          // güneş: iç içe halkalar
    const cx = y(55, 95), cy = y(5, 40);
    for (let i = 1; i <= 8; i++) s.push(`<circle cx="${cx}" cy="${cy}" r="${i * 6.5}" ${cizgi(0.6 - i * 0.06)}/>`);
    s.push(`<circle cx="${cx}" cy="${cy}" r="4.5" fill="#fff" opacity=".6"/>`);
  } else if (tur === 1) {   // dalgalar
    const gen = Number(y(2.5, 6)), sik = Number(y(14, 28)), kay = Number(y(0, 20));
    for (let i = 0; i < 9; i++) {
      const yy = 6 + i * 5.5;
      let d = `M-5 ${yy}`;
      for (let x = 0; x <= 110; x += 5) d += ` L${x} ${(yy + Math.sin(((x + kay + i * 3) / sik) * Math.PI) * gen).toFixed(1)}`;
      s.push(`<path d="${d}" ${cizgi(0.55 - i * 0.045)}/>`);
    }
  } else if (tur === 2) {   // kemerler
    const cx = Number(y(45, 85)), taban = Number(y(42, 56));
    for (let i = 1; i <= 7; i++) s.push(`<path d="M${cx - i * 6} ${taban} A${i * 6} ${i * 6} 0 0 1 ${cx + i * 6} ${taban}" ${cizgi(0.62 - i * 0.06)}/>`);
  } else if (tur === 3) {   // takımyıldız
    const n = 11, p = [...Array(n)].map(() => [Number(y(8, 94)), Number(y(6, 52))]);
    for (let i = 1; i < n; i++) if (r() < 0.75) s.push(`<line x1="${p[i - 1][0]}" y1="${p[i - 1][1]}" x2="${p[i][0]}" y2="${p[i][1]}" ${cizgi(0.32)}/>`);
    for (const [x, yy] of p) s.push(`<circle cx="${x}" cy="${yy}" r="${y(0.7, 1.9)}" fill="#fff" opacity="${y(0.5, 0.9)}"/>`);
  } else {                  // çapraz çizgiler
    const aci = y(-50, -25);
    s.push(`<g transform="rotate(${aci} 50 50)">`);
    for (let x = -60; x <= 160; x += 5.5) s.push(`<line x1="${x}" y1="-60" x2="${x}" y2="160" ${cizgi(r() < 0.25 ? 0.4 : 0.13)}/>`);
    s.push("</g>");
  }
  const svg = `<svg class="k-desen" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${s.join("")}</svg>`;
  desenler.set(anahtar, svg);
  return svg;
}
// desenin tuvale çizilebilir resmi (paylaşım kartları için)
function desenResmi(k) {
  return new Promise((ok) => {
    const i = new Image();
    i.onload = () => ok(i);
    i.onerror = () => ok(null);
    i.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(desen(k).replace("<svg ", '<svg width="512" height="512" '));
  });
}

const esCubuk = '<span class="es" aria-hidden="true"><i></i><i></i><i></i><i></i></span>';

// "Günün eseri": her gün bitirilmemiş eserlerden biri büyük vitrinde (o gün herkes için aynı)
function gununEseri() {
  const aday = katalog.filter((k) => !durum.bitti[k.id]);
  if (!aday.length) return "";
  const k = aday[Math.floor(rastgele(gun())() * aday.length)];
  const ozet = (k.tanitim || "").split(/(?<=[.!?…])\s+/).slice(0, 2).join(" ");
  return `<section class="vitrin" style="${renkStil(k)}"><div class="vitrin-zemin" aria-hidden="true">${desen(k)}</div>
    <a class="vitrin-kapak egik" href="#/eser/${k.id}" tabindex="-1">${kapak(k)}</a>
    <div class="vitrin-yazi"><small>Günün eseri · ${new Date().toLocaleDateString("tr", { day: "numeric", month: "long" })}</small>
      <h2>${kac(k.eser)}</h2><b>${kac(k.yazar)} · ${sure(k.sure)}</b>${ozet ? `<p>${kac(ozet)}</p>` : ""}
      <div class="vitrin-dugme"><button class="dev-cal istek-dugme" data-cal="${k.id}">${calDur}<span class="js-etiket">${devamEdiyor(k) ? "Devam et" : "Dinle"}</span></button>
        <a class="ikincil" href="#/eser/${k.id}">Ayrıntılar</a></div></div></section>`;
}

// ---------- günün sözü (3 Kasım 2026, kullanıcı: "yüklediğimiz kitaplardan özlü söz paylaşalım, 15 tane, günlük;
// hikâye olacak şekilde tasarla"): her gün sıradaki söz, herkes için aynı; "Hikâye olarak paylaş" 1080×1920 resim verir ----------
const SOZLER = [
  ["gazali-dilin-afetleri", "Bil ki dilin tehlikesi büyüktür ve onun tehlikesinden ancak susmakla kurtulunur."],
  ["seneca-hayatin-kisaligi", "Kısa bir hayat almadık, onu biz kısa yaptık; hayattan yoksun değiliz, onu savuruyoruz."],
  ["cibran-ermis", "Çalışmak, görünür kılınmış sevgidir."],
  ["insan-ne-ile-yasar", "Öğrendim ki her insan kendi kaygısıyla değil, sevgiyle yaşar."],
  ["suntzu-savas-sanati", "Yüz savaşta yüz kez kazanmak iyinin en iyisi değildir; savaşmadan düşman ordusunu boyun eğdirmek iyinin en iyisidir."],
  ["melville-katip-bartleby", "Yapmamayı tercih ederim."],
  ["ivan-ilyicin-olumu", "İvan İlyiç'in geçmiş hayatının hikâyesi son derece basit, son derece sıradan ve son derece korkunçtu."],
  ["stevenson-jekyll-hyde", "İnsan gerçekte bir değil, gerçekte ikidir."],
  ["efendi-ile-usagi", "Nikita yaşıyor, demek ki ben de yaşıyorum."],
  ["carroll-alis", "Burada hepimiz deliyiz. Ben deliyim. Sen delisin."],
  ["lovecraft-cthulhunun-cagrisi", "Dünyadaki en merhametli şey, bence, insan zihninin bütün içeriğini birbiriyle ilişkilendirme yetisinden yoksun olmasıdır."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Yalnızca Sen, yalnızca Sen beni hiç tanımadın!"],
  ["kafka-donusum", "Gregor Samsa bir sabah huzursuz rüyalardan uyandığında kendini yatağında korkunç bir böceğe dönüşmüş buldu."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Irgat kazmayı aldı, Pahom'a bir mezar kazdı; tam ayağından başına kadar kapladığı kadar, üç arşın; onu oraya gömdü."],
  ["hugo-idam-mahkumunun-son-gunu", "Artık tek bir düşüncem, tek bir inancım, tek bir kesinliğim var: İdama mahkûm!"],
  // 4 Kasım: 350 söz daha (16. günden başlar; hepsi eser metninden birebir, .tmp/sozler350)
  ["zweig-bilinmeyen-kadinin-mektubu", "Ömür boyu Seni sevmekten yorulmamış olan benden bu çeyrek saati dinlemekten yorulma, ne olur."],
  ["wilde-mutlu-prens", "Sıkı çalışmanın yapacak hiçbir şeyi olmayan insanların sığınağı olduğu kanısında olmuşumdur."],
  ["seneca-hayatin-kisaligi", "En büyük nimetler kaygılıdır; hiçbir talihe en iyi talihten daha az güvenilmez."],
  ["gazali-dilin-afetleri", "Dil, şeytanın insanı azdırmak için kullandığı en büyük alettir."],
  ["kafka-donusum", "Kendini yeniden insanlar çemberine dahil edilmiş hissetti."],
  ["cibran-ermis", "Kendinizi emekle tutarken aslında hayatı seversiniz; Hayatı emek yoluyla sevmek de hayatın en derin sırrına yakın olmaktır."],
  ["carroll-alis", "Lütfen söyler misin, buradan hangi yöne gitmeliyim?"],
  ["suntzu-savas-sanati", "Savaş devletin en büyük işidir; ölüm ile kalımın alanı, var olmak ile yok olmanın yoludur."],
  ["melville-katip-bartleby", "Yıkılmış bir tapınağın son sütunu gibi, başka türlü ıssız olan odanın ortasında dilsiz ve yalnız ayakta kaldı."],
  ["gazali-dilin-afetleri", "Kalem iki dilden biridir."],
  ["poe-anlatan-yurek-kara-kedi", "Gökte ve yerde olan her şeyi duyuyordum. Cehennemde olan pek çok şeyi de duyuyordum."],
  ["hugo-idam-mahkumunun-son-gunu", "Her şeyin bir sonu var; bunun da bir başkası kadar."],
  ["ivan-ilyicin-olumu", "Kayus bir insandır, insanlar ölümlüdür, öyleyse Kayus ölümlüdür; bütün hayatı boyunca ona yalnızca Kayus için doğru görünmüş, kendisi için hiç görünmemişti."],
  ["seneca-hayatin-kisaligi", "Hayatın artıklarını kendine ayırmaktan ve iyi bir akla yalnızca hiçbir işe yaramayacak zamanı adamaktan utanmıyor musun?"],
  ["cibran-ermis", "İçinizde en zayıf ve en şaşkın görünen şey, en güçlü ve en kararlı olandır."],
  ["wilde-mutlu-prens", "Kötü ile büyük kulağa çok benzer, aslında çoğu zaman aynı şeydir."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Yine yalnızım, hiç olmadığım kadar yalnız."],
  ["gazali-dilin-afetleri", "İnsanların en kötülerinden biri, şerrinden korkulduğu için insanların kendisinden sakındığı kimsedir."],
  ["suntzu-savas-sanati", "İyi savaşan düşmanı kendine getirir, kendisi düşmanın istediği yere gitmez."],
  ["efendi-ile-usagi", "Doğayla yaşayan ve yokluğu bilen bütün insanlar gibi sabırlıydı."],
  ["akutagawa-rasomon-bambu-korulukta", "Karımı hiçbir zaman o anki kadar güzel görmedim."],
  ["stevenson-jekyll-hyde", "Her şeyin bir sonu gelir; en geniş ölçek de sonunda dolar."],
  ["seneca-hayatin-kisaligi", "Yaşamayı bütün hayat boyunca öğrenmek gerekir; ve belki daha çok şaşacağın şey, ölmeyi de bütün hayat boyunca öğrenmek gerekir."],
  ["cibran-ermis", "Hayat geriye gitmez, dünle de oyalanmaz."],
  ["lovecraft-cthulhunun-cagrisi", "Muazzam, korkunç ve hesaplanamaz yaşı yanılmaz biçimde belliydi."],
  ["poe-usher-evinin-cokusu", "Heyecanlı ve son derece hastalıklı bir idealizm her şeyin üstüne kükürtlü bir parıltı salıyordu."],
  ["carroll-alis", "Herkes kendi işine baksa, dünya şimdikinden çok daha hızlı dönerdi."],
  ["kafka-donusum", "İçinde her yöne rahatsız edilmeden sürünebileceği, ama aynı zamanda insani geçmişini hızla ve tamamen unutacağı bir mağaraya çevrilmesini gerçekten istiyor muydu?"],
  ["insan-ne-ile-yasar", "Anladım ki Tanrı insanların ayrı ayrı yaşamasını istemedi."],
  ["gazali-dilin-afetleri", "Maksadı tek bir sözle yerine geldiği hâlde iki söz söylerse, ikincisi fazladır."],
  ["hugo-idam-mahkumunun-son-gunu", "Hiç değilse akıl acı çekmez; uyur, ölü gibidir."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Kârın büyük kardeşi zarardır."],
  ["ivan-ilyicin-olumu", "Yalnızken korkunç bir hüzün var, birini çağırmak istiyor, ama başkalarının yanında daha da kötü olacağını önceden biliyor."],
  ["wilde-mutlu-prens", "Bir iyiliğin hep bir başkasını doğurması ne kadar dikkate değer."],
  ["cibran-ermis", "Sevginin gidişini yönetebileceğini de sanma; çünkü sevgi seni layık bulursa senin gidişini o yönetir."],
  ["suntzu-savas-sanati", "Düşmana göre değişip yengi kazanabilene tanrısal denir."],
  ["seneca-hayatin-kisaligi", "Sen ise kendine bakmaya, kendini dinlemeye hiç tenezzül etmedin."],
  ["gazali-dilin-afetleri", "Dilini hayırdan başka her şeyden sakla; böylece şeytana galip gelirsin."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Seni asla, asla suçlamayacağım; hayır, yalnızca hep Sana teşekkür edeceğim."],
  ["cibran-ermis", "Yürek küçük şeylerin çiyinde sabahını bulur ve tazelenir."],
  ["carroll-alis", "Son zamanlarda öyle çok olağandışı şey olmuştu ki Alis gerçekten olanaksız olan pek az şey bulunduğunu düşünmeye başlamıştı."],
  ["gazali-dilin-afetleri", "Başkasının kötülüklerini diliyle başkasına anlatmak sana haram olduğu gibi, kendi kendine konuşarak kardeşin hakkında kötü zanda bulunman da sana caiz değildir."],
  ["melville-katip-bartleby", "Nedense son zamanlarda bu \"tercih etmek\" sözcüğünü pek de uygun olmayan her türlü durumda istemeden kullanmaya başlamıştım."],
  ["seneca-hayatin-kisaligi", "Gerisini talih dilediği gibi düzenlesin: Hayat artık güvendedir."],
  ["hugo-idam-mahkumunun-son-gunu", "Şimdi dünyayla benim aramda bir çit gibi bir şeyi açıkça seçiyordum."],
  ["suntzu-savas-sanati", "İyi savaşanın yengisi ne bilgelik ünü, ne de yiğitlik şanı getirir."],
  ["kafka-donusum", "Gregor kız kardeşiyle konuşabilseydi ve onun kendisi için yapmak zorunda olduğu her şey için ona teşekkür edebilseydi, hizmetlerine daha kolay katlanırdı."],
  ["wilde-mutlu-prens", "Yine de Aşk Hayattan üstündür; bir kuşun yüreği bir insanın yüreğinin yanında nedir ki?"],
  ["stevenson-jekyll-hyde", "Her şey yolundaysa, omuzlarım suçu taşıyacak kadar geniştir."],
  ["cibran-ermis", "Sevgi kendinden başka bir şey vermez, kendinden başka bir şeyden de almaz."],
  ["poe-anlatan-yurek-kara-kedi", "Bir hayvanın bencillikten uzak, kendini feda eden sevgisinde, sırf İnsanın değersiz dostluğunu ve örümcek ağı gibi incecik sadakatini sık sık sınama fırsatı bulmuş birinin doğrudan yüreğine işleyen bir şey vardır."],
  ["gazali-dilin-afetleri", "Söz taşımak yalan, haset ve nifak üzerine kurulmuştur."],
  ["ivan-ilyicin-olumu", "Ya gerçekten de bütün hayatım, bilinçli hayatım «yanlış» idiyse?"],
  ["insan-ne-ile-yasar", "Sözle ya da dille değil, eylemle ve gerçekle sevelim."],
  ["efendi-ile-usagi", "Bütün hayatı sürekli bir bayram olmamış, tersine, yorulmaya başladığı, hiç bitmeyen bir hizmet olmuştu."],
  ["seneca-hayatin-kisaligi", "Her şeyin en değerlisiyle oynanıyor; ama onları aldatan şey onun maddesiz bir şey olması, gözle görülmemesi ve bu yüzden en ucuz şey sayılmasıdır."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Ah, beni sezmiyordun ki, hayatımdan hiçbir zaman hiçbir şey sezmedin!"],
  ["akutagawa-rasomon-bambu-korulukta", "Bana ne kadar işkence etseniz de bilmediğim bir şeyi söyleyemem."],
  ["suntzu-savas-sanati", "İlerlerken ün peşinde koşmayan, geri çekilirken suçtan kaçmayan, yalnızca halkı korumayı düşünen ve hükümdarın yararına hizmet eden komutan devletin hazinesidir."],
  ["gazali-dilin-afetleri", "Sözü çok olanın hatası çok olur. Hatası çok olanın günahı çok olur."],
  ["cibran-ermis", "Bir insanın görüşü kanatlarını başka bir insana ödünç vermez."],
  ["carroll-alis", "Ah, aşktır, aşktır dünyayı döndüren!"],
  ["hugo-idam-mahkumunun-son-gunu", "Bu sakatlanmış yazıtlara, bu parçalanmış cümlelere, bu kesik sözcüklere, onları yazanlar gibi başsız bedenlere, anlamı ve hayatı geri vermeyi isterdim."],
  ["lovecraft-cthulhunun-cagrisi", "O bakış, gerçeğe atılan bütün korkunç bakışlar gibi, ayrı şeylerin rastlantısal olarak bir araya getirilmesinden çaktı."],
  ["wilde-mutlu-prens", "Aşk kendi çapında çok güzel bir şey, ama dostluk çok daha yücedir."],
  ["seneca-hayatin-kisaligi", "Sanki hep yaşayacakmışsınız gibi yaşıyorsunuz; çelimsizliğiniz aklınıza hiç gelmiyor."],
  ["gazali-dilin-afetleri", "Kişi, kendisini faziletini göstermeye sevk eden kibri ve başkasını küçük düşürmeye sevk eden yırtıcılığı kırmalıdır."],
  ["kafka-donusum", "Sabahleyin kapılar kilitliyken herkes yanına girmek istemişti; şimdi o bir kapıyı açmışken ve öbürleri de belli ki gün içinde açılmışken artık kimse gelmiyordu."],
  ["cibran-ermis", "Hayat ve yaşayan her şey kristalde değil, siste döllenir."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Toprak bol olsa ben kimseden, şeytanın kendisinden bile korkmam!"],
  ["suntzu-savas-sanati", "Ne zaman savaşılıp ne zaman savaşılmayacağını bilen kazanır."],
  ["ivan-ilyicin-olumu", "Yalnız kalan İvan İlyiç, ne kadar korkunç olsa da ağrıdan çok hüzünden inledi."],
  ["poe-usher-evinin-cokusu", "Ruhun bu dayanılmaz heyecanı üzerinde etkili olabilecek her olayın, en önemsizinin bile düşüncesiyle ürperiyorum."],
  ["gazali-dilin-afetleri", "Şeytan, en küçük bir belirtiyle bile insanların kötülüğünü kalbe yerleştirir."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Sözlerimden korkma; bir ölü artık hiçbir şey istemez; ne sevgi ister ne acıma ne de avuntu."],
  ["stevenson-jekyll-hyde", "Bu ölüm ve doğum ıstıraplarından bir iblis yerine bir melek olarak çıkardım."],
  ["cibran-ermis", "İstendiğinde vermek iyidir, ama istenmeden, anlayarak vermek daha iyidir."],
  ["seneca-hayatin-kisaligi", "Meşgul bir insan hiçbir şeyi iyi yapamaz."],
  ["carroll-alis", "Deli olmalısın, yoksa buraya gelmezdin."],
  ["hugo-idam-mahkumunun-son-gunu", "Herkesin beni tanıdığı ve benim kimseyi tanımadığım bu kalabalık."],
  ["melville-katip-bartleby", "Bu eski sandalyelerin herhangi biri kadar zararsız ve sessizsin."],
  ["wilde-mutlu-prens", "Gerçek aşk acı çeker ve susar."],
  ["gazali-dilin-afetleri", "Ölüm hepimizi kuşatacak, kabir hepimizi içine alacak, kıyamet hepimizi bir araya toplayacak."],
  ["suntzu-savas-sanati", "En üstün savaş düşmanın planını bozmaktır."],
  ["insan-ne-ile-yasar", "İnsan bir yıllık hazırlık yapıyor, ama akşama kadar yaşamayacağını bilmiyor."],
  ["cibran-ermis", "İçinizdeki hekimin hasta benliğinizi iyileştirdiği acı ilaçtır."],
  ["seneca-hayatin-kisaligi", "İyi insanlar için kendi seçtikleri yerde doğmak mümkündür."],
  ["kafka-donusum", "Ailesini duygulanarak ve sevgiyle düşündü."],
  ["poe-anlatan-yurek-kara-kedi", "Gecenin ölü saatinde, o eski evin korkunç sessizliğinin ortasında böylesine tuhaf bir ses beni zapt edilmez bir dehşete sürükledi."],
  ["efendi-ile-usagi", "Çoktandır kendi iradesi olmamaya ve başkalarına hizmet etmeye alışmıştı."],
  ["gazali-dilin-afetleri", "Hayır söyle, kazanırsın; kötülükten sus, pişman olmadan selamete erersin."],
  ["ivan-ilyicin-olumu", "Kendini aldatamazdı: İçinde korkunç, yeni ve İvan İlyiç'in hayatında hiç başına gelmemiş kadar önemli bir şey oluyordu."],
  ["akutagawa-rasomon-bambu-korulukta", "Akıl yoluyla bunu iyiye mi kötüye mi yazacağını bilmiyordu."],
  ["cibran-ermis", "Kötü, kendi açlığı ve susuzluğuyla işkence gören iyiden başka nedir ki?"],
  ["hugo-idam-mahkumunun-son-gunu", "İnsan kötülük olsun diye kötü olmaz."],
  ["carroll-alis", "Düne dönmenin yararı yok, çünkü o zaman başka biriydim."],
  ["suntzu-savas-sanati", "Yol, halkı yönetenle aynı amaçta birleştiren şeydir."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Kendimi bağlamak istemiyordum; her saatte Senin için özgür olmak istiyordum."],
  ["wilde-mutlu-prens", "Gerçek dost her zaman tatsız şeyler söyler ve can acıtmaktan çekinmez."],
  ["seneca-hayatin-kisaligi", "Rastlantıyla gelen her şey kararsızdır: Ne kadar yükseğe çıkarsa düşmeye o kadar elverişlidir."],
  ["gazali-dilin-afetleri", "Şaka aklı alıp götürür, dostları birbirinden koparır."],
  ["lovecraft-cthulhunun-cagrisi", "Umarım başka hiç kimse bu birleştirmeyi tamamlamaz."],
  ["cibran-ermis", "Sendeleyen bir konuşma bile zayıf bir dili güçlendirebilir."],
  ["stevenson-jekyll-hyde", "Sokak sokak ardına, herkes uykuda; sokak sokak ardına, hepsi bir tören alayı için yakılmış gibi aydınlık ve hepsi bir kilise kadar boş."],
  ["gazali-dilin-afetleri", "Söz taşıyanın sana naklettiği doğru olsa bile, sana sövmeye cüret eden odur."],
  ["suntzu-savas-sanati", "Biçimsiz olursan en derinlere sızan casus bile seni gözetleyemez, en bilge kişi bile sana karşı plan kuramaz."],
  ["kafka-donusum", "Umutsuz kararlardan çok sakin, en sakin düşünmenin daha iyi olduğunu kendine hatırlatmayı da unutmadı."],
  ["seneca-hayatin-kisaligi", "Her zamanı kendi kullanımına sunan, her günü son günüymüş gibi düzenleyen kişi ne yarını ister ne de ondan korkar."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Gerçi kasvetli yaşıyoruz ama korku nedir bilmiyoruz."],
  ["ivan-ilyicin-olumu", "Sanki ölüm yalnızca İvan İlyiç'e özgü olup kendisine hiç uymayan bir serüvenmiş gibi."],
  ["cibran-ermis", "Onlara sevginizi verebilirsiniz, ama düşüncelerinizi değil; Çünkü onların kendi düşünceleri vardır."],
  ["hugo-idam-mahkumunun-son-gunu", "Çevremdeki her şey hapishane; hapishaneyi her biçimde, parmaklık ya da sürgü biçiminde olduğu gibi insan biçiminde de yeniden buluyorum."],
  ["wilde-mutlu-prens", "Sevmediğimiz her şeyi kınayan kararlar aldık."],
  ["carroll-alis", "Hem bunlar alt tarafı bir deste iskambil kâğıdı."],
  ["insan-ne-ile-yasar", "Sevgi içinde olan Tanrı'dadır, Tanrı da ondadır; çünkü Tanrı sevgidir."],
  ["melville-katip-bartleby", "Belli bir noktaya kadar sefaletin düşüncesinin ya da görüntüsünün en iyi duygularımızı harekete geçirdiği, ama bazı özel durumlarda bu noktanın ötesinde geçirmediği öyle doğru, öyle de korkunç ki."],
  ["gazali-dilin-afetleri", "Şiirin bir kısmı hikmettir."],
  ["zweig-bilinmeyen-kadinin-mektubu", "İnsanların arasında yalnız olmaktan daha korkunç bir şey yoktur."],
  ["seneca-hayatin-kisaligi", "Meşgul bir insanın yaşamaktan daha az yaptığı bir şey yoktur."],
  ["cibran-ermis", "Sevgi ayrılık saatine kadar kendi derinliğini bilmez."],
  ["suntzu-savas-sanati", "İyi savaşan kendini yenilmez kılabilir, ama düşmanı mutlaka yenilebilir kılamaz."],
  ["gazali-dilin-afetleri", "Kişi kendine yalan kapısını açarsa, bu kapının, ihtiyaç duyulmayan şeylere ve zorunluluk sınırında kalmayan şeylere doğru genişlemesinden korkulur."],
  ["poe-usher-evinin-cokusu", "Ruhsal bozuklukların tarihi buna benzer tuhaflıklarla doludur."],
  ["efendi-ile-usagi", "Özgür olduğunu, artık hiçbir şeyin onu tutmadığını hissediyor."],
  ["akutagawa-rasomon-bambu-korulukta", "Her türlü kötülüğe karşı duyduğu tiksinti dakikadan dakikaya güçleniyordu."],
  ["wilde-mutlu-prens", "Bilgelerin yazdığı her şeyi okudum, felsefenin bütün sırları benim; yine de bir kırmızı gülün yokluğu yüzünden hayatım perişan oldu."],
  ["poe-anlatan-yurek-kara-kedi", "Bir zamanlar beni o kadar sevmiş bir yaratığın bu açık hoşnutsuzluğu önce beni üzecek kadar eski yüreğimden bir şey kalmıştı."],
  ["hugo-idam-mahkumunun-son-gunu", "Tavırlarında az önce bir ölüm hükmü vermiş insanları belli eden hiçbir şey yoktu."],
  ["cibran-ermis", "Tek başına hüküm süren akıl kısıtlayıcı bir güçtür; gözetimsiz tutku da kendi yıkımına kadar yanan bir alevdir."],
  ["kafka-donusum", "Eskiden pencereden dışarı bakmanın kendisine verdiği özgürleştirici duyguya dair bir anıyla."],
  ["ivan-ilyicin-olumu", "Orada daha gerçekten iyi bir şeyler vardı: Orada neşe vardı, orada dostluk vardı, orada umutlar vardı."],
  ["seneca-hayatin-kisaligi", "Kendine hiç vakit ayırmayan biri başkasının kibrinden yakınmaya cesaret edebilir mi?"],
  ["stevenson-jekyll-hyde", "Kardeşimi kendi bildiği yoldan şeytana gitmeye bırakırım."],
  ["carroll-alis", "Zaman'ı benim kadar tanısaydın, onu harcamaktan söz etmezdin."],
  ["gazali-dilin-afetleri", "Mal ve makam sevgisi, suyun sebzeyi bitirdiği gibi kalpte nifakı bitirir."],
  ["suntzu-savas-sanati", "Ne düşmanını ne kendini bilirsen her savaşta mutlaka tehlikeye düşersin."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Biricik çocuğunun ölüm saatinde insan yalan söylemez."],
  ["cibran-ermis", "Gerçekte hayata veren hayattır; kendinizi verici sanan sizler ise yalnızca bir tanıksınız."],
  ["gazali-dilin-afetleri", "Allah Teâlâ'yı anmaya sarılın; çünkü o şifadır."],
  ["seneca-hayatin-kisaligi", "Ne kadar az olursa olsun bol bol yeter; ve bu yüzden son gün ne zaman gelirse gelsin bilge kişi ölüme kararlı bir adımla gitmekte duraksamayacaktır."],
  ["lovecraft-cthulhunun-cagrisi", "Şimdi ben de dinlenene kadar beni asla bırakmayacak o kara dehşetin iç organlarımı kemirdiğini hissettim."],
  ["insan-ne-ile-yasar", "Bütün insanlar da kendi başlarının çaresine baktıkları için değil, insanlarda sevgi olduğu için yaşarlar."],
  ["wilde-mutlu-prens", "Çevremdeki her şey o kadar güzeldi ki."],
  ["hugo-idam-mahkumunun-son-gunu", "Çevremde gün nasıl ışıldıyorsa umut da içimde öyle ışıldamaya başladı."],
  ["suntzu-savas-sanati", "Askerin çok olması üstünlük değildir; yalnızca körü körüne saldırmamak, güçlerini birleştirmek, düşmanı doğru kestirmek ve adamlarının gönlünü kazanmak yeter."],
  ["gazali-dilin-afetleri", "Övünme korkusu beni sözün çoğundan alıkoyar."],
  ["cibran-ermis", "Sevginin kendini gerçekleştirmekten başka arzusu yoktur."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Alışınca bu toprak da ona dar gelmeye başladı."],
  ["carroll-alis", "Alis olağandışı şeylerden başka bir şey olmasını beklemeye öyle alışmıştı ki hayatın olağan biçimde sürüp gitmesi ona çok sıkıcı ve aptalca geliyordu."],
  ["ivan-ilyicin-olumu", "İvan İlyiç'in başlıca işkencesi yalandı."],
  ["melville-katip-bartleby", "Gençliğimden beri hayatın en kolay yolunun en iyisi olduğuna derinden inanmış bir adamım."],
  ["kafka-donusum", "Gregor olsaydı insanların böyle bir hayvanla birlikte yaşamasının mümkün olmadığını çoktan anlar ve kendi isteğiyle giderdi."],
  ["seneca-hayatin-kisaligi", "Hayatın en büyük kaybı ertelemedir: Her günü elden alan, daha ötesini vaat ederken şimdiyi kapıp götüren odur."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Bütün gün aslında Seni beklemekten ve Seni kollamaktan başka hiçbir şey yapmıyordum."],
  ["gazali-dilin-afetleri", "Kişi Allah'ın rızasına uygun bir söz söyler; onun ulaştığı yere ulaşacağını hiç sanmaz."],
  ["cibran-ermis", "Gerçekten de okyanus her zaman masumla birlikte güler."],
  ["stevenson-jekyll-hyde", "Hayatımızın yazgısının ve yükünün sonsuza dek insanın omuzlarına bağlı olduğunu ve onu atmaya kalkışıldığında yalnızca daha yabancı ve daha korkunç bir baskıyla üstümüze döndüğünü öğrenmek zorunda bırakıldım."],
  ["suntzu-savas-sanati", "Savaşta beceriksizce bir çabukluk duyulmuştur, ama ustaca bir uzatma hiç görülmemiştir."],
  ["wilde-mutlu-prens", "Başkalarının da insanın kendisi kadar olağanüstü olmasını beklemek haksızlık olur."],
  ["efendi-ile-usagi", "Bu zayıflık ona tatsız gelmek şöyle dursun, daha önce hiç yaşamadığı özel bir sevinç veriyordu."],
  ["seneca-hayatin-kisaligi", "Dinlenen, dinlenmesinin bilincinde olandır."],
  ["hugo-idam-mahkumunun-son-gunu", "Başvuru, sizi uçurumun üstünde asılı tutan ve kopana kadar her an çatırdadığını duyduğunuz bir iptir."],
  ["gazali-dilin-afetleri", "Doğrulukta yalana ihtiyaç bırakmayan bir genişlik vardır."],
  ["akutagawa-rasomon-bambu-korulukta", "Orada parlayan ne öfkeydi ne de keder; yalnızca beni küçümseyen soğuk bir ışık değil miydi?"],
  ["cibran-ermis", "Ölümün ruhunu gerçekten görmek istiyorsanız yüreğinizi hayatın bedenine ardına kadar açın."],
  ["carroll-alis", "Resimsiz, konuşmasız bir kitap ne işe yarar ki?"],
  ["poe-anlatan-yurek-kara-kedi", "Beni deli sanıyorsunuz. Deliler hiçbir şey bilmez."],
  ["ivan-ilyicin-olumu", "Bir tek Gerasim yalan söylemiyordu."],
  ["gazali-dilin-afetleri", "Konuşmanın dinlemekten daha sevimli gelmesi, âlimin fitnesindendir."],
  ["kafka-donusum", "Yolculuklarının sonunda kızları ilk ayağa kalkıp genç bedenini gerdiğinde, bu onlara yeni rüyalarının ve iyi niyetlerinin bir doğrulaması gibi geldi."],
  ["suntzu-savas-sanati", "Güç gerilmiş bir yay gibidir, zamanlama tetiği çekmek gibidir."],
  ["insan-ne-ile-yasar", "Tanrı sevgidir; sevgide yaşayan Tanrı'da yaşar, Tanrı da onda."],
  ["seneca-hayatin-kisaligi", "Bütün hayatının kısımları arasında dolaşmak kaygısız ve dingin bir aklın işidir."],
  ["cibran-ermis", "Tek bir yaprak bütün ağacın sessiz bilgisi olmadan nasıl sararmazsa, Kötülük yapan da hepinizin gizli iradesi olmadan kötülük yapamaz."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Şimdi biliyorsun, hayır, yalnızca seziyorsun, Seni ne kadar sevdiğimi; ve yine de bu aşktan hiçbir yük taşımıyorsun."],
  ["poe-usher-evinin-cokusu", "Kuşkusuz hiçbir insan bu kadar kısa sürede Roderick Usher kadar korkunç biçimde değişmemişti!"],
  ["wilde-mutlu-prens", "Her şeyden daha harikası erkeklerin ve kadınların çektiği acılardır."],
  ["gazali-dilin-afetleri", "Allah'a en sevimli olanınız, ahlakı en güzel olanlarınız, alçakgönüllü ve yumuşak huylu olanlar, insanlarla kaynaşan ve kendileriyle kaynaşılanlardır."],
  ["hugo-idam-mahkumunun-son-gunu", "İnsanların hepsi süresi belirsiz ertelemelerle ölüme mahkûmdur."],
  ["lovecraft-cthulhunun-cagrisi", "Ölü değildir sonsuza dek yatabilen; ve tuhaf çağlarla ölüm bile ölebilir."],
  ["cibran-ermis", "Birlikte şarkı söyleyin, dans edin ve sevinin; ama her biriniz yalnız olsun, Tıpkı bir udun tellerinin aynı müzikle titreseler de yalnız olmaları gibi."],
  ["carroll-alis", "En azından bu sabah kalktığımda kim olduğumu biliyorum, ama o zamandan beri birkaç kez değiştirilmiş olmalıyım sanırım."],
  ["seneca-hayatin-kisaligi", "Umut umudu, hırs hırsı uyandırır."],
  ["suntzu-savas-sanati", "Üstünlük yarışının güçlüğü, dolambaçlı yolu dosdoğru yol, sıkıntıyı yarar hâline getirmektir."],
  ["stevenson-jekyll-hyde", "Hayatımın yitip gittiğini gördüm."],
  ["melville-katip-bartleby", "Öteki hukuk kopyacılarının bütün hayatını yazabilirim, ama Bartleby için böyle bir şey yapılamaz."],
  ["gazali-dilin-afetleri", "Biriniz konuştuğunda yalan söylemesin; vaat ettiğinde sözünden dönmesin; kendisine bir şey emanet edildiğinde hıyanet etmesin."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Siz iyi insanlar veriyorsunuz; günü gelir, çocuklarınız geri alır."],
  ["ivan-ilyicin-olumu", "Etrafındaki ve kendi içindeki bu yalan, İvan İlyiç'in hayatının son günlerini her şeyden çok zehirledi."],
  ["cibran-ermis", "Hayatın soluğu güneş ışığında, hayatın eli de rüzgârdadır."],
  ["kafka-donusum", "Yatakta düşünmekle akla yatkın bir sonuca varamayacağını iyi fark ediyordu."],
  ["wilde-mutlu-prens", "Başkaları için yapılan iş kadar zevkli bir iş yoktur."],
  ["zweig-bilinmeyen-kadinin-mektubu", "O gecelere asla pişman olmadım; Sana olan aşkımı asla azarlamadım; Seni hep sevdim."],
  ["seneca-hayatin-kisaligi", "Herkesten yalnızca bilgeliğe vakit ayıranlar dinlenenlerdir, yalnızca onlar yaşar."],
  ["gazali-dilin-afetleri", "Söz taşıyan cennete giremez."],
  ["hugo-idam-mahkumunun-son-gunu", "Başkalarını ürperten şeye çoktan alıştı."],
  ["suntzu-savas-sanati", "Herkes benim hangi biçimle kazandığımı görür, ama yengiyi hangi biçimle kurduğumu kimse bilmez."],
  ["efendi-ile-usagi", "Bu gerçek ölümden sonra uyandığı yerde daha mı iyi, daha mı kötü?"],
  ["akutagawa-rasomon-bambu-korulukta", "Doğru, kan akmaz, adam yaşar gider; ama yine de öldürmüşsünüzdür."],
  ["cibran-ermis", "Gerçekten de haz bir özgürlük şarkısıdır."],
  ["carroll-alis", "Herkes istediği zaman koşmaya başlıyor, istediği zaman bırakıyordu; bu yüzden koşunun ne zaman bittiğini anlamak kolay değildi."],
  ["insan-ne-ile-yasar", "Gördüğü kardeşini sevmeyen, görmediği Tanrı'yı nasıl sevebilir?"],
  ["gazali-dilin-afetleri", "Çirkin söz ve çirkin söze özenmek İslam'dan hiçbir şey değildir."],
  ["seneca-hayatin-kisaligi", "Sözler dışarı fışkırınca duygular yine alışkanlığa geri kayar."],
  ["poe-anlatan-yurek-kara-kedi", "Sinirliydim, çok, korkunç derecede sinirliydim, hâlâ da öyleyim; ama neden deli olduğumu söyleyeceksiniz?"],
  ["ivan-ilyicin-olumu", "Ama her şeyi olması gerektiği gibi yaptığım hâlde nasıl yanlış olur?"],
  ["wilde-mutlu-prens", "Yaşayanlar hep altının kendilerini mutlu edebileceğini düşünür."],
  ["cibran-ermis", "Düşüncelerinizle barış içinde olmayı bıraktığınızda konuşursunuz."],
  ["suntzu-savas-sanati", "Bilgenin düşüncesinde yarar ile zarar mutlaka birbirine karışır."],
  ["gazali-dilin-afetleri", "Gıybetten sakın; çünkü o, insan köpeklerinin katığıdır."],
  ["stevenson-jekyll-hyde", "Bu kadar sevmediğim bir adam hiç görmedim, ama yine de nedenini pek bilmiyorum."],
  ["kafka-donusum", "Hep değişen, hiç sürmeyen, hiçbir zaman içtenleşmeyen insan ilişkileri."],
  ["hugo-idam-mahkumunun-son-gunu", "Dünyada yalnızca tek bir varlığı ateşle sevmek, onu bütün sevginle sevmek, ve onu karşında bulmak; seni gören ve sana bakan, seninle konuşan ve sana cevap veren ve seni tanımayan!"],
  ["zweig-bilinmeyen-kadinin-mektubu", "Beni asla tanımayacaksın, hiçbir zaman."],
  ["seneca-hayatin-kisaligi", "İstediklerine zahmetle ulaşırlar, ulaştıklarını kaygıyla tutarlar."],
  ["cibran-ermis", "Arının hazzının çiçekten bal toplamak olduğunu öğreneceksiniz, Ama balını arıya vermek de çiçeğin hazzıdır."],
  ["carroll-alis", "Bir zamanlar, gerçek bir Kaplumbağaydım."],
  ["gazali-dilin-afetleri", "Her şeyin bir tohumu vardır; düşmanlığın tohumu da şakadır."],
  ["lovecraft-cthulhunun-cagrisi", "Bir gün birbirinden kopuk bilgilerin bir araya getirilmesi gerçekliğin ve onun içindeki korkunç konumumuzun öyle dehşet verici manzaralarını açacak ki ya bu açığa çıkış karşısında aklımızı yitireceğiz ya da ölümcül ışıktan yeni bir karanlık çağın huzuruna ve güvenliğine kaçacağız."],
  ["melville-katip-bartleby", "Hiçbir şey ciddi bir insanı edilgen bir direniş kadar sinirlendirmez."],
  ["suntzu-savas-sanati", "Eskilerin iyi savaşan dediği kişi, kolay yenilen düşmanı yenendir."],
  ["wilde-mutlu-prens", "Mutlu Prens hiçbir şey için ağlamayı aklından bile geçirmez."],
  ["poe-usher-evinin-cokusu", "Neydi, diye durup düşündüm, Usher Evi'ni seyrederken beni bu kadar sarsan neydi?"],
  ["cibran-ermis", "Gerçekten bilgeyse sizi bilgeliğinin evine girmeye çağırmaz, daha çok sizi kendi zihninizin eşiğine götürür."],
  ["seneca-hayatin-kisaligi", "Kimse kendini kendine ayırmaz; biri öbürü için tükenir."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Kendi toprağım olsaydı, diye düşündü, kimseye boyun eğmezdim, günaha da girmezdim."],
  ["gazali-dilin-afetleri", "Doğruluk ile yalan kalpte birbiriyle boğuşur; sonunda biri öbürünü dışarı atar."],
  ["ivan-ilyicin-olumu", "Çaresizliğine, korkunç yalnızlığına, insanların acımasızlığına, Tanrı'nın acımasızlığına, Tanrı'nın yokluğuna ağlıyordu."],
  ["hugo-idam-mahkumunun-son-gunu", "Kesip attıkları insanda bir zekânın, hayata güvenmiş bir zekânın, ölüme hiç hazırlanmamış bir ruhun bulunduğu o yürek dağlayıcı düşünce üzerinde hiç olsun durmuşlar mıdır?"],
  ["insan-ne-ile-yasar", "İnsan anasız babasız yaşar, ama Tanrısız yaşamaz."],
  ["efendi-ile-usagi", "Neden titrediğini, soğuktan mı korkudan mı, kendisi de bilmiyordu."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Sana yük olmaktansa her şeyi üstlenmeyi, bütün kadınların arasında her zaman sevgiyle, minnetle düşündüğün tek kadın olmayı yeğliyordum."],
  ["kafka-donusum", "Kız kardeşinin iyiliğiyle gerçekte ne yaptığını asla tahmin edemezdi."],
  ["akutagawa-rasomon-bambu-korulukta", "Açgözlülük denen şey korkunç değil mi?"],
  ["suntzu-savas-sanati", "Halkını aşırı seven komutan tedirgin edilebilir."],
  ["gazali-dilin-afetleri", "Kim öfkesine hâkim olursa Allah onu azabından korur."],
  ["cibran-ermis", "Size sevinç verenin, yalnızca size keder vermiş olan şey olduğunu göreceksiniz."],
  ["carroll-alis", "Gittikçe tuhaflaşıyor, gittikçe tuhaflaşıyor!"],
  ["seneca-hayatin-kisaligi", "Mutluluğuna herkesin koştuğu kişilere bak: Kendi nimetleriyle boğuluyorlar."],
  ["stevenson-jekyll-hyde", "Merakı köreltmek bir şeydir, onu yenmek başka bir şey."],
  ["wilde-mutlu-prens", "Aynı şeyi defalarca, defalarca söylerseniz sonunda doğru olacağını düşünen insanlardandı."],
  ["gazali-dilin-afetleri", "Kişi bir mecliste bulunur da konuşmak hoşuna giderse sussun. Susuyorken susmak hoşuna giderse konuşsun."],
  ["cibran-ermis", "İhtiyaç korkusu, ihtiyacın kendisinden başka nedir ki?"],
  ["poe-anlatan-yurek-kara-kedi", "Bu düşüncenin beynime ilk nasıl girdiğini söylemek imkânsız; ama bir kez tasarlandıktan sonra gece gündüz peşimi bırakmadı."],
  ["hugo-idam-mahkumunun-son-gunu", "Ben artık aynı insan değildim."],
  ["suntzu-savas-sanati", "İyi saldıranın karşısındaki düşman neresini savunacağını bilmez; iyi savunanın karşısındaki düşman da nereye saldıracağını bilmez."],
  ["ivan-ilyicin-olumu", "Düzenlenecek bir şey kalmayınca biraz can sıkıntısı başladı, bir şeyler eksik gibi geldi."],
  ["seneca-hayatin-kisaligi", "Hastalığını bilmek birçoklarının ölüm nedeni olmuştur."],
  ["gazali-dilin-afetleri", "Sevgi üzerine kurulan evler çok azdır."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Daha Sen kendin hayatıma girmeden çevrende bir hâle vardı; zenginliğin, tuhaflığın ve gizemin bir havası."],
  ["cibran-ermis", "Keder varlığınıza ne kadar derin oyarsa, o kadar çok sevinç alabilirsiniz."],
  ["kafka-donusum", "Ona bakmak ve katlanmak için insanca mümkün olan her şeyi denedik."],
  ["carroll-alis", "Bu büyük ölçüde nereye varmak istediğine bağlı."],
  ["melville-katip-bartleby", "Davranışım her zamanki gibi akıllıca görünüyordu, ama yalnızca kuramda."],
  ["wilde-mutlu-prens", "Bugünlerde her iyi hikâyeci sondan başlar, sonra başlangıca geçer ve ortayla bitirir."],
  ["seneca-hayatin-kisaligi", "Hiçbir zamanının kendisinden kırpılmasına izin vermemek büyük ve insan yanılgılarının üstünde yükselen bir adamın işidir."],
  ["gazali-dilin-afetleri", "Her şeyde maksatla yetinmek gerekir."],
  ["lovecraft-cthulhunun-cagrisi", "Özgür ve yabani ve iyinin ve kötünün ötesinde."],
  ["suntzu-savas-sanati", "Savaş uzadığı hâlde devletin yararına olduğu hiç görülmemiştir."],
  ["insan-ne-ile-yasar", "Kendi çocuğum da vardı ama Tanrı onu aldı; onu bile bunları sevdiğim kadar sevmedim."],
  ["cibran-ermis", "Acınız size sevinciniz kadar harika görünürdü."],
  ["hugo-idam-mahkumunun-son-gunu", "Giyotinin önü kalabalıktır ve herkes ancak sırası gelince geçmelidir."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Bizim gibiler küçükten beri toprak anayı alt üst eder; kafamıza saçma sapan şeyler girmez."],
  ["stevenson-jekyll-hyde", "Ne daha zengin ne daha bilge; meğer ki ölümcül bir sıkıntı içindeki bir adama yapılan hizmetin duygusu bir tür ruh zenginliği sayılsın."],
  ["efendi-ile-usagi", "Başka bir yer bulunmadıkça yaşamak ve verileni almak gerektiğini hissediyordu."],
  ["gazali-dilin-afetleri", "Kişi ölümün önünde durduğunu, her sözden sorguya çekileceğini ve nefeslerinin sermayesi olduğunu bilmelidir."],
  ["ivan-ilyicin-olumu", "Hoş hayatının bütün bu en güzel anları şimdi hiç de o zaman göründükleri gibi görünmüyordu."],
  ["akutagawa-rasomon-bambu-korulukta", "İnsanın hayatı gerçekten de bir çiy damlası, bir şimşek çakması gibidir."],
  ["seneca-hayatin-kisaligi", "Parasını paylaşmak isteyen kimse bulunmaz; ama herkes hayatını kaç kişiye dağıtıyor!"],
  ["cibran-ermis", "Adili adaletsizden, iyiyi kötüden ayıramazsınız."],
  ["carroll-alis", "Baştan başla, sona gelene kadar devam et; sonra dur."],
  ["suntzu-savas-sanati", "Eskiden iyi savaşanlar önce kendilerini yenilmez kılar, sonra düşmanın yenilebileceği anı beklerlerdi."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Her şey yalnızca Seninle bir ilgisi olduğu ölçüde vardı; varlığımdaki her şey ancak Sana bağlı olduğunda anlam taşıyordu."],
  ["wilde-mutlu-prens", "Şeyleri hiçbir zaman gerçekte oldukları gibi düşünmem, her zaman büsbütün başka türlü düşünürüm."],
  ["kafka-donusum", "Son zamanlarda başkalarını o kadar az gözetmesine pek şaşmıyordu; eskiden bu gözetme onun gururuydu."],
  ["gazali-dilin-afetleri", "Husumette, münakaşada ve tartışmada kişinin kaçırdığı en az şey, güzel söz ve onun hakkında bildirilen sevaptır."],
  ["poe-usher-evinin-cokusu", "Ah, yas tutalım, çünkü o ıssız hükümdarın üstüne hiçbir yarın doğmayacak!"],
  ["cibran-ermis", "Özgür olabilmek için atmak istediğiniz şey, kendi benliğinizin parçalarından başka nedir ki?"],
  ["seneca-hayatin-kisaligi", "Zamanın hızıyla onu kullanmanın çabukluğuyla yarışmak ve hızlı akan ve her zaman akmayacak bir selden içer gibi çabuk içmek gerek."],
  ["hugo-idam-mahkumunun-son-gunu", "Belki bir gün yayımlanırlar da akıllarını birkaç an aklın acıları üzerinde durdururlar; çünkü onların hiç sezmedikleri acılar bunlardır."],
  ["gazali-dilin-afetleri", "Kişiye, sözden ihtiyacını karşılayacak kadarı yeter."],
  ["suntzu-savas-sanati", "Her savaşta olağan olanla karşılaşılır, olağanüstü olanla kazanılır."],
  ["poe-anlatan-yurek-kara-kedi", "Ama her şey bu ıstıraptan iyiydi!"],
  ["ivan-ilyicin-olumu", "Eskiden ona tamamen imkânsız görünen şey, yani hayatını yaşaması gerektiği gibi yaşamadığı, doğru olabilirdi."],
  ["cibran-ermis", "Gerçekte özgürlük dediğiniz şey bu zincirlerin en güçlüsüdür; halkaları güneşte parlayıp gözlerinizi kamaştırsa da."],
  ["wilde-mutlu-prens", "Aşk, bilge olsa da Felsefe'den daha bilge, kudretli olsa da Güç'ten daha kudretlidir."],
  ["carroll-alis", "Hiçbir akıllı balık yunussuz bir yere gitmez."],
  ["insan-ne-ile-yasar", "İnsanların içinde sevgi olduğunu öğrendim."],
  ["seneca-hayatin-kisaligi", "Her şeyden ölümlüler gibi korkuyorsunuz, her şeyi ölümsüzler gibi istiyorsunuz."],
  ["melville-katip-bartleby", "Ertesi gün Bartleby'nin ölü duvar hayaline dalmış hâlde penceresinin önünde durmaktan başka hiçbir şey yapmadığını fark ettim."],
  ["gazali-dilin-afetleri", "İbadet on kısımdır; dokuzu susmakta, biri de insanlardan kaçmaktadır."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Yalnızca yalnız çocuklar tutkularını bütünüyle bir arada tutabilir."],
  ["stevenson-jekyll-hyde", "Olağanüstü görünüşlü bir adam, ama yine de gerçekten olağandışı hiçbir şey sayamıyorum."],
  ["kafka-donusum", "Birileri yardımına gelse her şeyin ne kadar basit olacağı aklına geldi."],
  ["cibran-ermis", "Dünün bugünün anısı, yarının da bugünün rüyası olduğunu bilir."],
  ["hugo-idam-mahkumunun-son-gunu", "Bedenen ve ruhen sağlamım, uzun bir hayat için yaratılmışım; evet, bütün bunlar doğru; ama yine de bir hastalığım var; ölümcül bir hastalık, insan eliyle yapılmış bir hastalık."],
  ["suntzu-savas-sanati", "Savaşın karmaşası ve kargaşası içinde düzensizlik görünür, ama asla düzen bozulmaz."],
  ["lovecraft-cthulhunun-cagrisi", "Sonsuzluğun kara denizlerinin ortasında sakin bir cehalet adasında yaşıyoruz ve uzaklara yolculuk etmemiz amaçlanmamıştı."],
  ["gazali-dilin-afetleri", "Kulun imanı, kalbi dosdoğru olmadıkça dosdoğru olmaz; kalbi de dili dosdoğru olmadıkça dosdoğru olmaz."],
  ["seneca-hayatin-kisaligi", "Hayat yeterince uzundur ve tamamı iyi kullanılsaydı en büyük işlerin başarılması için cömertçe verilmiştir."],
  ["efendi-ile-usagi", "Vasili Brehunov denen bu insanın neden bütün o uğraştığı şeylerle uğraştığını anlamakta güçlük çekiyor."],
  ["akutagawa-rasomon-bambu-korulukta", "Sizler kılıç kullanmazsınız; yalnızca güçle öldürürsünüz, parayla öldürürsünüz, bazen de iyilik kılığına girmiş sözlerle bile öldürürsünüz."],
  ["wilde-mutlu-prens", "Bir kırmızı gül için ölüm büyük bir bedel, diye bağırdı Bülbül, Hayat da herkese çok değerlidir."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Dinlenmek istiyor ama olmaz; güneş batmadan yetişemez."],
  ["cibran-ermis", "Dostunuzdan ayrıldığınızda yas tutmayın; Çünkü onda en çok sevdiğiniz şey, dağın tırmanıcıya ovadan daha açık görünmesi gibi, onun yokluğunda daha açık görünebilir."],
  ["ivan-ilyicin-olumu", "Hayat, artan acıların bir dizisi; sona, en korkunç acıya doğru gittikçe hızlanarak uçuyor."],
  ["carroll-alis", "Genellikle kendine çok iyi öğütler verirdi (ama onlara pek ender uyardı)."],
  ["gazali-dilin-afetleri", "Sana söz taşıyan, senden de söz taşır."],
  ["suntzu-savas-sanati", "Hiç düşünmeden düşmanı hafife alan mutlaka onun tutsağı olur."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Benim için her şey olmuş ve her şey olan Sana değilse kime konuşayım ki!"],
  ["seneca-hayatin-kisaligi", "Yaşamaya, bitirmek gerektiği zaman başlamak ne kadar geç!"],
  ["hugo-idam-mahkumunun-son-gunu", "Elimden alınan kırk yıllık hayatım için isteyeceğim her şey yalnızca buydu."],
  ["cibran-ermis", "Her bilgi boştur, çalışma olmadıkça; Her çalışma boştur, sevgi olmadıkça."],
  ["gazali-dilin-afetleri", "Allah'ı zikretmekle meşgul olmak daha iyidir; bu olmazsa susmakta selamet vardır."],
  ["kafka-donusum", "Dışarıda, pencerenin önünde genel aydınlanmanın başlangıcını hâlâ yaşadı."],
  ["insan-ne-ile-yasar", "İnsanlara yalnızca kendi kaygılarıyla yaşıyorlarmış gibi gelir; oysa onlar yalnızca sevgiyle yaşarlar."],
  ["stevenson-jekyll-hyde", "Keşfime daha soylu bir ruhla yaklaşsaydım, deneyi cömert ya da dindarca isteklerin egemenliği altındayken göze alsaydım, her şey başka türlü olmalıydı."],
  ["wilde-mutlu-prens", "Pek çok insan iyi davranır, diye cevap vermiş Değirmenci; ama çok az insan iyi konuşur."],
  ["suntzu-savas-sanati", "Önceden bilmek ruhlardan ve tanrılardan elde edilemez, benzer olaylardan çıkarılamaz, yıldızların ölçümüyle doğrulanamaz; mutlaka insanlardan, düşmanın durumunu bilen kişilerden elde edilir."],
  ["seneca-hayatin-kisaligi", "Kendi hayatının hesabını bilmek devletin tahılının hesabını bilmekten daha iyidir."],
  ["gazali-dilin-afetleri", "Bil ki sözün fazlası sınırsızdır."],
  ["cibran-ermis", "Sözcük bilgisi, sözsüz bilginin bir gölgesinden başka nedir ki?"],
  ["poe-anlatan-yurek-kara-kedi", "En iyi yargımıza rağmen, Yasa olanı, yalnızca onun yasa olduğunu anladığımız için çiğnemeye sürekli bir eğilimimiz yok mu?"],
  ["carroll-alis", "Bugün her şey ne kadar tuhaf! Dün her şey her zamanki gibi gidiyordu."],
  ["ivan-ilyicin-olumu", "Bütün bunların hem hayatı hem ölümü örten korkunç, devasa bir aldatmaca olduğunu açıkça görüyordu."],
  ["melville-katip-bartleby", "İnsanlar kıskançlık, öfke, nefret, bencillik ve manevi kibir uğruna cinayet işlemişlerdir; ama duyduğum hiçbir insan tatlı merhamet uğruna şeytanca bir cinayet işlememiştir."],
  ["poe-usher-evinin-cokusu", "Hiçbir melek kanat germemişti bunun yarısı kadar güzel bir yapının üstüne."],
  ["hugo-idam-mahkumunun-son-gunu", "İçinde bulunduğum umutsuz durumda insan zaman zaman bir saç teliyle bir zinciri kırabileceğine inanıyor."],
  ["zweig-bilinmeyen-kadinin-mektubu", "Bir kez, yalnızca bu tek kez Sana konuşmak için bütün gücümü toplayacağım, Sen sevgilim, beni hiç tanımamış olan."],
  ["gazali-dilin-afetleri", "Sözü çok olanın yalanı çok olur."],
  ["cibran-ermis", "Gerçekten de rahatlık şehveti ruhun tutkusunu öldürür, sonra cenazede sırıtarak yürür."],
  ["seneca-hayatin-kisaligi", "Ne zaman tükeneceğini bilmediğin şey daha dikkatle korunmalıdır."],
  ["suntzu-savas-sanati", "Düşmanını bilir, kendini de bilirsen yüz savaşta da tehlikeye düşmezsin."],
  ["wilde-mutlu-prens", "Bir gülün yüreğini yalnızca bir Bülbül'ün yürek kanı kızıla boyayabilir."],
  ["kafka-donusum", "Odası, gerçek, yalnızca biraz fazla küçük bir insan odası, iyi bildiği dört duvarın arasında sessizce duruyordu."],
  ["efendi-ile-usagi", "Böyle bir hayattan insan ölmek istemez."],
  ["lovecraft-cthulhunun-cagrisi", "Rılyeh'teki evinde ölü Kutulu düş görerek bekler."],
  ["gazali-dilin-afetleri", "İnsanları cehenneme yüzüstü atan, dillerinin biçtiklerinden başka bir şey değildir."],
  ["akutagawa-rasomon-bambu-korulukta", "Ama bu \"olursa\", ne kadar zaman geçerse geçsin, sonunda yine \"olursa\" olarak kalıyordu."],
  ["cibran-ermis", "Karın altında rüya gören tohumlar gibi yüreğiniz de ilkbaharın rüyasını görür."],
  ["carroll-alis", "Ah, öyle tuhaf bir düş gördüm ki!"],
  ["seneca-hayatin-kisaligi", "Geçmişi unutan, şimdiyi ihmal eden, gelecekten korkanların ömrü en kısa ve en kaygılı ömürdür."],
  ["bir-insana-ne-kadar-toprak-gerekir", "Oysa şeytan sobanın arkasında oturmuş, her şeyi duymuştu."],
  ["ivan-ilyicin-olumu", "Hiçbir korku yoktu, çünkü ölüm de yoktu. Ölümün yerinde ışık vardı."],
  ["gazali-dilin-afetleri", "İblis'e lanet etmekten susmakta bile hiçbir tehlike yoktur; başkasına lanet etmeyi bırakmakta haydi haydi yoktur."],
  ["hugo-idam-mahkumunun-son-gunu", "Bana öyle geliyordu ki iyi Tanrı bana acımalı ve hiç değilse orada, karşıda, çatının kenarında şakıması için bana küçük bir kuş göndermeliydi."],
  ["suntzu-savas-sanati", "Öfke yeniden sevince, kızgınlık yeniden hoşnutluğa dönebilir; ama yok olmuş bir devlet yeniden var olamaz, ölenler yeniden dirilemez."],
  ["stevenson-jekyll-hyde", "O cehennem çocuğunun insanca hiçbir yanı yoktu; içinde korku ve nefretten başka hiçbir şey yaşamıyordu."],
  ["insan-ne-ile-yasar", "Ölümden yaşama geçtiğimizi biliyoruz, çünkü kardeşlerimizi seviyoruz; kardeşini sevmeyen ölümde kalır."],
  ["cibran-ermis", "Birbirinizi sevin, ama sevgiden bir bağ yapmayın: O daha çok ruhlarınızın kıyıları arasında dalgalanan bir deniz olsun."]
];
const SOZ_BASI = new Date(2026, 10, 3);  // 1. gün
function bugununSozu() {
  const l = SOZLER.map(([id, soz]) => ({ k: eserBul(id), soz })).filter((s) => s.k);
  if (!l.length) return null;
  const n = Math.floor((new Date(gun()) - new Date(gun(SOZ_BASI))) / 864e5);
  return l[((n % l.length) + l.length) % l.length];
}
function gununSozu() {
  const s = bugununSozu();
  if (!s) return "";
  const { k, soz } = s;
  return `<section class="soz-karti" style="${renkStil(k)}"><div class="vitrin-zemin" aria-hidden="true">${desen(k)}</div>
    <small>Günün sözü</small>
    <blockquote>${kac(soz)}</blockquote>
    <a class="soz-eser" href="#/eser/${k.id}"><i class="soz-renk" aria-hidden="true">${desen(k)}</i><span><b>${kac(k.eser)}</b>${kac(k.yazar)}</span></a>
    <div class="vitrin-dugme"><button class="dev-cal istek-dugme" data-cal="${k.id}">${calDur}<span class="js-etiket">${devamEdiyor(k) ? "Devam et" : "Dinle"}</span></button>
      <button class="ikincil" data-soz-paylas>${simge("resim")}Hikâye olarak paylaş</button></div></section>`;
}
async function sozPaylas() {
  const s = bugununSozu();
  if (!s) return;
  bildir("Hikâye hazırlanıyor…");
  await document.fonts.ready;
  const { k, soz } = s, [a, b] = renk(k), [c, x] = tuval();
  kartZemini(x, a, b);
  const d = await desenResmi(k);  // eserin motifi üstte, solgun
  if (d) { x.globalAlpha = 0.35; x.drawImage(d, 0, 0, 1080, 1080); x.globalAlpha = 1; }
  let g = x.createLinearGradient(0, 500, 0, 1100);
  g.addColorStop(0, "transparent"); g.addColorStop(1, "rgba(0,0,0,.55)");
  x.fillStyle = g; x.fillRect(0, 500, 1080, 1420);
  x.textAlign = "center"; x.fillStyle = "rgba(255,255,255,.8)"; x.font = "800 38px Figtree, sans-serif";
  x.letterSpacing = "6px"; x.fillText("GÜNÜN SÖZÜ", 540, 230); x.letterSpacing = "0px";
  x.fillStyle = b; x.font = "600 300px Fraunces, Georgia, serif"; x.fillText("“", 540, 560);
  // söz uzunluğuna göre yazı boyu: 560–1260 arasına sığsın
  let boy = 96, satir = [];
  for (; boy >= 54; boy -= 6) {
    x.font = `600 ${boy}px Fraunces, Georgia, serif`;
    satir = []; let s_ = "";
    for (const w of soz.split(" ")) { const t = s_ ? `${s_} ${w}` : w; if (x.measureText(t).width > 880 && s_) { satir.push(s_); s_ = w; } else s_ = t; }
    satir.push(s_);
    if (satir.length * boy * 1.28 <= 700) break;
  }
  const ara = boy * 1.28, ust = 910 - ((satir.length - 1) * ara) / 2;
  x.fillStyle = "#fff"; x.shadowColor = "rgba(0,0,0,.5)"; x.shadowBlur = 30;
  satir.forEach((l, i) => x.fillText(l, 540, ust + i * ara));
  x.shadowColor = "transparent";
  x.fillStyle = b; x.fillRect(500, 1330, 80, 6);
  kapakCiz(x, k, 440, 1390, 200, d);
  // eser adı tek satıra sığana kadar küçülür (uzun adda yazar satırı alttaki ada binmesin)
  x.textAlign = "center"; x.fillStyle = "#fff";
  let ab = 54;
  do x.font = `600 ${ab}px Fraunces, Georgia, serif`; while (x.measureText(k.eser).width > 940 && (ab -= 2) > 34);
  x.fillText(k.eser, 540, 1665);
  x.fillStyle = "rgba(255,255,255,.75)"; x.font = "700 38px Figtree, sans-serif";
  x.fillText(`${k.yazar} · sesli dinle`, 540, 1725);
  kartAlti(x);
  resimPaylas(c, `gunun-sozu-${k.id}.png`, `“${soz}” — ${k.yazar}, ${k.eser}. Melih'ten Dinle'de sesli dinle.`);
}
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-soz-paylas]")) return sozPaylas();
  if (e.target.closest("[data-soz-ac]")) return sozAc();
  if (e.target.closest("[data-soz-kapat]") || e.target.classList.contains("soz-hikaye")) return sozKapat();
  if ($(".soz-hikaye") && e.target.closest("[data-cal]")) sozKapat();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") sozKapat(); });

// selamın yanında hikâye yuvarlağı: o gün açılmadıysa halka renkli döner ve bir kez zıplar, açılınca solar
function sozBalonu() {
  const s = bugununSozu();
  if (!s) return "";
  const yeni = durum.sozGoruldu !== gun();
  return `<button class="soz-balon${yeni ? " yeni" : ""}" data-soz-ac aria-label="Günün sözünü aç" style="${renkStil(s.k)}">
    <span class="soz-halka"><i>${desen(s.k)}<b>“</b></i></span><small>Günün sözü</small></button>`;
}
function sozAc() {
  const s = bugununSozu();
  if (!s || $(".soz-hikaye")) return;
  const { k, soz } = s;
  durum.sozGoruldu = gun(); yaz();
  $$(".soz-balon").forEach((b) => b.classList.remove("yeni"));
  const tarih = new Date().toLocaleDateString("tr-TR", { day: "numeric", month: "long" });
  const d = document.createElement("div");
  d.className = "soz-hikaye";
  d.setAttribute("role", "dialog");
  d.setAttribute("aria-label", "Günün sözü");
  d.style.cssText = renkStil(k);
  let n = 0;
  d.innerHTML = `<div class="vitrin-zemin" aria-hidden="true">${desen(k)}</div>
    <div class="sh-ust"><i class="sh-cubuk"><b></b></i>
      <div class="sh-bas"><span class="soz-renk" aria-hidden="true">${desen(k)}</span><span><b>Günün sözü</b>${tarih}</span>
      <button class="sh-kapat" data-soz-kapat aria-label="Kapat">✕</button></div></div>
    <blockquote>${kac(soz).split(" ").map((w) => `<span style="--n:${n++}">${w}</span>`).join(" ")}</blockquote>
    <div class="sh-alt" style="--n:${n}">
      <a class="soz-eser" href="#/eser/${k.id}" data-soz-kapat><i class="soz-renk" aria-hidden="true">${desen(k)}</i><span><b>${kac(k.eser)}</b>${kac(k.yazar)} · ${sure(k.sure)}</span></a>
      <div class="vitrin-dugme"><button class="dev-cal istek-dugme" data-cal="${k.id}">${calDur}<span class="js-etiket">${devamEdiyor(k) ? "Devam et" : "Sesli dinle"}</span></button>
        <button class="ikincil" data-soz-paylas>${simge("resim")}Paylaş</button></div></div>`;
  document.body.append(d);
  simgeleriDoldur(d);
}
function sozKapat() { $(".soz-hikaye")?.remove(); }

// eğilen kapak: fare ya da parmakla kapağın üstünde gezinince üç boyutlu eğilir, üstünde ışık kayar
let egik = null;
function egikBirak() {
  if (!egik) return;
  egik.classList.remove("egiliyor");
  egik.style.removeProperty("--rx"); egik.style.removeProperty("--ry");
  egik = null;
}
function egikAyarla(el, x, y) {  // x, y: -0.5 … 0.5
  el.style.setProperty("--rx", `${(-y * 16).toFixed(1)}deg`);
  el.style.setProperty("--ry", `${(x * 16).toFixed(1)}deg`);
  el.style.setProperty("--px", `${((x + 0.5) * 100).toFixed(0)}%`);
  el.style.setProperty("--py", `${((y + 0.5) * 100).toFixed(0)}%`);
  el.classList.add("egiliyor");
}
document.addEventListener("pointermove", (e) => {
  const el = e.target.closest(".egik");
  if (egik && egik !== el) egikBirak();
  if (!el || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const r = el.getBoundingClientRect();
  egikAyarla(el, (e.clientX - r.left) / r.width - 0.5, (e.clientY - r.top) / r.height - 0.5);
  egik = el;
});
for (const ad of ["pointerup", "pointercancel"]) document.addEventListener(ad, () => setTimeout(egikBirak, 250));
document.documentElement.addEventListener("pointerleave", egikBirak);
// Android'de tam ekran kapak telefonun eğimine göre de oynar
window.addEventListener("deviceorientation", (e) => {
  if (!$("#tam").classList.contains("acik") || e.gamma === null || egik) return;
  const el = $("#tam-kapak");
  egikAyarla(el, Math.max(-0.5, Math.min(0.5, e.gamma / 60)), Math.max(-0.5, Math.min(0.5, (e.beta - 45) / 60)));
});

// ---------- rozetler ----------
const ROZETLER = [
  ["ilk-adim", "🎧", "İlk adım", "İlk dinlemeni yaptın", (v) => v.top >= 60],
  ["ilk-eser", "📖", "İlk eser", "Bir eseri baştan sona bitirdin", (v) => v.biten >= 1],
  ["bes-eser", "📚", "Kitap kurdu", "5 eser bitirdin", (v) => v.biten >= 5],
  ["on-eser", "🏛️", "Kütüphane", "10 eser bitirdin", (v) => v.biten >= 10],
  ["on-saat", "⏳", "On saat", "Toplam 10 saat dinledin", (v) => v.top >= 36000],
  ["elli-saat", "🏔️", "Elli saat", "Toplam 50 saat dinledin", (v) => v.top >= 180000],
  ["seri-3", "🔥", "Isınma turu", "3 gün üst üste hedefini tutturdun", (v) => v.seri >= 3],
  ["seri-7", "⚡", "Bir hafta", "7 gün üst üste hedefini tutturdun", (v) => v.seri >= 7],
  ["seri-30", "👑", "Bir ay", "30 gün üst üste hedefini tutturdun", (v) => v.seri >= 30],
  ["maraton", "🏃", "Maraton", "Bir günde 2 saat dinledin", (v) => v.enGun >= 7200],
  ["gece", "🦉", "Gece kuşu", "Gece yarısından sonra dinledin", (v) => v.gece],
  ["sabah", "🌅", "Erkenci", "Sabah 5 ile 8 arası dinledin", (v) => v.sabah],
  ["rus", "❄️", "Rus ruhu", "3 Rus klasiği bitirdin", (v) => v.rus >= 3],
  ["gezgin", "🌍", "Dünya gezgini", "4 farklı ülkeden eser dinledin", (v) => v.ulke >= 4],
  ["kalp", "❤️", "Koleksiyoncu", "5 eseri beğendin", (v) => v.begen >= 5],
  ["im", "🔖", "Not defteri", "5 yer imi ekledin", (v) => v.im >= 5],
];
function rozetVerisi() {
  const biten = katalog.filter((k) => durum.bitti[k.id]), sa = durum.saatler;
  const gunler = Object.values(durum.gunluk);
  return {
    top: gunler.reduce((a, b) => a + b, 0), enGun: Math.max(0, ...gunler), biten: biten.length,
    seri: Math.max(seri(), enUzunSeri()), rus: biten.filter((k) => k.koken === "Rus").length,
    gece: sa.slice(0, 5).some((x) => x >= 60), sabah: sa.slice(5, 8).some((x) => x >= 60),
    ulke: new Set(katalog.filter((k) => durum.bitti[k.id] || durum.konum[k.id]).map((k) => k.ulke)).size,
    begen: Object.keys(durum.begen).length, im: Object.values(durum.imler).reduce((a, l) => a + l.length, 0),
  };
}
function rozetDenetle() {
  if (!katalog.length) return;
  const v = rozetVerisi(), yeni = ROZETLER.filter(([id, , , , kosul]) => !durum.rozet[id] && kosul(v));
  if (!yeni.length) return;
  for (const [id] of yeni) durum.rozet[id] = Date.now();
  yaz();
  rozetGoster(yeni);
  if (location.hash === "#/karne") yenile();
}
function rozetGoster(yeni) {
  $(".rozet-pop")?.remove();
  const d = document.createElement("button");
  d.className = "rozet-pop";
  d.dataset.rozetGit = "";
  d.setAttribute("role", "status");
  const [, isaret, ad, aciklama] = yeni[0];
  d.innerHTML = yeni.length === 1
    ? `<span class="rozet-isaret">${isaret}</span><span><small>Yeni rozet kazandın!</small><b>${ad}</b><em>${aciklama}</em></span>`
    : `<span class="rozet-isaret">${isaret}</span><span><small>${yeni.length} yeni rozet kazandın!</small><b>${yeni.map((r) => r[1]).join(" ")}</b><em>Hepsini karnende gör</em></span>`;
  document.body.append(d);
  setTimeout(() => d.classList.add("gidiyor"), 4800);
  setTimeout(() => d.remove(), 5400);
}
function rozetBolumu() {
  const sayi = ROZETLER.filter(([id]) => durum.rozet[id]).length;
  return `<section class="raf"><div class="raf-bas"><h2>Rozetlerin · ${sayi}/${ROZETLER.length}</h2></div>
    <div class="rozetler">${ROZETLER.map(([id, isaret, ad, aciklama]) => {
      const t = durum.rozet[id];
      return `<div class="rozet${t ? " kazanildi" : ""}" title="${kac(aciklama)}"><span>${isaret}</span><b>${ad}</b><small>${t
        ? new Date(t).toLocaleDateString("tr", { day: "numeric", month: "short" }) : kac(aciklama)}</small></div>`;
    }).join("")}</div></section>`;
}

// ---------- dinleme takvimi (son 18 hafta, renk koyulaştıkça çok dinlenmiş) ----------
function isiHaritasi() {
  const H = 18, h = durum.hedef * 60, bugun = new Date();
  bugun.setHours(12, 0, 0, 0);
  const bas = new Date(bugun);
  bas.setDate(bas.getDate() - ((bas.getDay() + 6) % 7) - (H - 1) * 7);  // 18 hafta önceki pazartesi
  const hucre = [];
  for (let i = 0; i < H * 7; i++) {
    const d = new Date(bas);
    d.setDate(bas.getDate() + i);
    if (d > bugun) { hucre.push('<i class="gelecek"></i>'); continue; }
    const sn = durum.gunluk[gun(d)] || 0;
    const sev = sn < 60 ? 0 : sn >= h ? 4 : sn >= h * 0.66 ? 3 : sn >= h * 0.33 ? 2 : 1;
    hucre.push(`<i class="s${sev}${gun(d) === gun() ? " bugun" : ""}" title="${d.toLocaleDateString("tr", { day: "numeric", month: "long" })}: ${Math.round(sn / 60)} dk"></i>`);
  }
  const aylar = [...Array(H)].map((_, w) => {
    const d = new Date(bas); d.setDate(bas.getDate() + w * 7);
    return d.getDate() <= 7 ? `<span style="grid-column:${w + 1}">${d.toLocaleDateString("tr", { month: "short" })}</span>` : "";
  }).join("");
  const gunSay = Object.values(durum.gunluk).filter((sn) => sn >= 60).length;
  return `<section class="raf"><div class="raf-bas"><h2>Dinleme takvimin</h2></div>
    <div class="takvim-aylar">${aylar}</div><div class="takvim">${hucre.join("")}</div>
    <p class="vakit-not takvim-alt"><span>${gunSay} gün dinledin</span><span class="takvim-renk">Az <i class="s0"></i><i class="s1"></i><i class="s2"></i><i class="s3"></i><i class="s4"></i> Çok</span></p></section>`;
}

// ---------- dinleme hikâyesi (tam ekran, kaydırmalı kartlar) ----------
const hikayeDugmesi = (karne) => (Object.values(durum.gunluk).reduce((a, b) => a + b, 0) >= 60 || karne
  ? `<button class="hikaye-dugme" data-hikaye><span>✨</span>Dinleme hikâyeni izle</button>` : "");
let hikayeSira = 0, hikayeSaat = null, hikayeKartlar = [];
function hikayeVerisi() {
  const top = Object.values(durum.gunluk).reduce((a, b) => a + b, 0);
  const eserler = katalog.map((k) => [k, durum.bitti[k.id] ? k.sure : durum.konum[k.id] || 0]).filter(([, s]) => s > 0).sort((a, b) => b[1] - a[1]);
  const yazar = {};
  for (const [k, s] of eserler) { yazar[k.yazar] = yazar[k.yazar] || { s: 0, n: 0 }; yazar[k.yazar].s += s; yazar[k.yazar].n++; }
  const enYazar = Object.entries(yazar).sort((a, b) => b[1].s - a[1].s)[0];
  const sa = durum.saatler, saatTop = sa.reduce((a, b) => a + b, 0);
  const enSaat = saatTop >= 60 ? sa.indexOf(Math.max(...sa)) : -1;
  return { top, eserler, enYazar, enSaat, biten: katalog.filter((k) => durum.bitti[k.id]),
    rozet: ROZETLER.filter(([id]) => durum.rozet[id]) };
}
function hikayeHazirla() {
  const v = hikayeVerisi(), K = [];
  K.push({ zemin: "#1f5a3a", html: `<small>Melih'ten Dinle</small><h2>Senin dinleme hikâyen</h2><p>Bugüne kadar kulağına neler değdi, birlikte bakalım.</p>` });
  if (v.top < 60) {
    K.push({ zemin: "#3a2d6b", html: `<small>Hikâyen yeni başlıyor</small><h2>İlk sayfayı sen çevir</h2><p>Bir eser dinlemeye başla; burası seninle birlikte dolacak.</p>` });
    return K;
  }
  const dk = v.top / 60;
  K.push({ zemin: "#3a2d6b", html: `<small>Toplam dinleme</small><div class="h-dev">${sureYaz(v.top)}</div>
    <p>${dk < 90 ? `Bu, ${Math.max(1, Math.round(dk / 15))} demlik çay süresi kadar.` : `Bu, yaklaşık ${Math.round(v.top / 6300)} uzun metraj film demek.`}</p>` });
  if (v.eserler[0]) {
    const [k, s] = v.eserler[0];
    K.push({ stil: renkStil(k), html: `<small>En çok dinlediğin eser</small><div class="h-kapak egik">${kapak(k)}</div>
      <h2>${kac(k.eser)}</h2><p>${kac(k.yazar)} · ${sureYaz(s)} dinledin</p>` });
  }
  if (v.enYazar) {
    const [ad, { s, n }] = v.enYazar;
    K.push({ zemin: "#7c2d12", html: `<small>En çok dinlediğin yazar</small><div class="h-dev h-ad">${kac(ad)}</div>
      <p>Onunla ${sureYaz(s)} geçirdin${n > 1 ? `, ${n} eserini açtın` : ""}.</p>` });
  }
  K.push({ zemin: "#134e63", html: `<small>Bitirdiğin eserler</small><div class="h-dev">${v.biten.length}</div>
    ${v.biten.length ? `<div class="h-mozaik">${v.biten.slice(0, 9).map(kapak).join("")}</div><p>Her biri baştan sona, tam metin.</p>` : "<p>İlk bitiş seni bekliyor. Kısa bir eserle başlamaya ne dersin?</p>"}` });
  if (v.enSaat >= 0) {
    const s = v.enSaat;
    const tip = s < 5 ? "Gece kuşusun: herkes uyurken sen dinliyorsun." : s < 9 ? "Erkencisin: güne bir klasikle başlıyorsun."
      : s < 18 ? "Gün ortasında kulağın kitapta." : "Akşam dinleyicisisin: günün yorgunluğunu klasiklerle atıyorsun.";
    K.push({ zemin: "#4c1d95", html: `<small>En sevdiğin dinleme saati</small><div class="h-dev">${String(s).padStart(2, "0")}:00</div><p>${tip}</p>` });
  }
  K.push({ zemin: "#6b4a0e", html: `<small>En uzun serin</small><div class="h-dev">${enUzunSeri()} gün</div>
    <p>${seri() ? `Şu an ${seri()} gündür seri yapıyorsun. Bozma!` : "Bugün dinleyerek yeni bir seri başlatabilirsin."}</p>` });
  K.push({ zemin: "#5c1a1a", html: `<small>Rozetlerin</small><div class="h-dev">${v.rozet.length}/${ROZETLER.length}</div>
    <div class="h-rozet">${v.rozet.map((r) => `<span title="${r[2]}">${r[1]}</span>`).join("")}</div>` });
  K.push({ zemin: "#1f5a3a", html: `<small>Şimdilik bu kadar</small><h2>Dinlemeye devam!</h2><p>Hikâyeni bir resim olarak arkadaşlarınla paylaşabilirsin.</p>
    <button class="dev-cal istek-dugme" data-hikaye-paylas>${simge("paylas")}<span>Hikâyemi paylaş</span></button>` });
  return K;
}
function hikayeAc() {
  hikayeKapat();
  hikayeKartlar = hikayeHazirla();
  const d = document.createElement("div");
  d.className = "hikaye";
  d.setAttribute("role", "dialog");
  d.setAttribute("aria-label", "Dinleme hikâyen");
  d.innerHTML = `<div class="h-cubuklar">${hikayeKartlar.map(() => "<i><b></b></i>").join("")}</div>
    <button class="h-kapat" data-hikaye-kapat aria-label="Kapat">✕</button><div class="h-kart"></div>`;
  document.body.append(d);
  d.addEventListener("click", (e) => {
    if (e.target.closest("[data-hikaye-kapat]")) return hikayeKapat();
    if (e.target.closest("[data-hikaye-paylas]")) return hikayePaylas();
    if (e.target.closest("button, a")) return;
    hikayeGit(e.clientX < innerWidth * 0.3 ? -1 : 1);
  });
  document.body.style.overflow = "hidden";
  hikayeSira = 0;
  hikayeCiz();
}
function hikayeCiz() {
  const d = $(".hikaye");
  if (!d) return;
  const k = hikayeKartlar[hikayeSira];
  d.style.cssText = k.stil || `--a:${k.zemin};--b:${k.zemin}`;
  const kart = $(".h-kart", d);
  kart.innerHTML = `<div class="h-ic">${k.html}</div>`;
  simgeleriDoldur(kart);
  $$(".h-cubuklar i", d).forEach((c, i) => { c.className = i < hikayeSira ? "dolu" : i === hikayeSira ? "simdi" : ""; });
  clearTimeout(hikayeSaat);
  if (hikayeSira < hikayeKartlar.length - 1) hikayeSaat = setTimeout(() => hikayeGit(1), 6000);
}
function hikayeGit(adim) {
  const yeni = hikayeSira + adim;
  if (yeni >= hikayeKartlar.length) return hikayeKapat();
  hikayeSira = Math.max(0, yeni);
  hikayeCiz();
}
function hikayeKapat() {
  clearTimeout(hikayeSaat);
  if ($(".hikaye")) { $(".hikaye").remove(); document.body.style.overflow = ""; }
}

// ---------- resimli paylaşım kartları (Instagram/WhatsApp hikâyesine uygun 1080×1920) ----------
function tuval() {
  const c = document.createElement("canvas");
  c.width = 1080; c.height = 1920;
  return [c, c.getContext("2d")];
}
function kartZemini(x, a, b) {
  let g = x.createLinearGradient(0, 0, 0, 1920);
  g.addColorStop(0, a); g.addColorStop(0.75, "#0b0b0b"); g.addColorStop(1, "#000");
  x.fillStyle = g; x.fillRect(0, 0, 1080, 1920);
  g = x.createRadialGradient(900, 120, 0, 900, 120, 900);
  g.addColorStop(0, b); g.addColorStop(1, "transparent");
  x.globalAlpha = 0.55; x.fillStyle = g; x.fillRect(0, 0, 1080, 1920); x.globalAlpha = 1;
}
function kartAlti(x) {
  x.fillStyle = "#2fd36b"; x.beginPath(); x.arc(390, 1800, 14, 0, 7); x.fill();
  x.fillStyle = "#fff"; x.font = "800 40px Figtree, sans-serif"; x.textAlign = "left";
  x.fillText("Melih'ten Dinle", 420, 1814);
}
function sarYaz(x, metin, cx, y, en, satirBoy) {  // ortalanmış, satıra bölünmüş yazı; son satırın altını döndürür
  const satirlar = [];
  let s = "";
  for (const w of metin.split(" ")) { const d = s ? `${s} ${w}` : w; if (x.measureText(d).width > en && s) { satirlar.push(s); s = w; } else s = d; }
  satirlar.push(s);
  satirlar.forEach((l, i) => x.fillText(l, cx, y + i * satirBoy));
  return y + (satirlar.length - 1) * satirBoy;
}
async function resimPaylas(c, ad, metin) {
  const blob = await new Promise((ok) => c.toBlob(ok, "image/png"));
  const dosya = new File([blob], ad, { type: "image/png" });
  if (navigator.canShare && navigator.canShare({ files: [dosya] })) {
    try { await navigator.share({ files: [dosya], text: metin }); } catch { /* vazgeçildi */ }
    return;
  }
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: ad });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  bildir("Kart resim olarak kaydedildi");
}
async function kartPaylas(k) {
  if (!k) return;
  bildir("Kart hazırlanıyor…");
  const [c, x] = tuval(), [a, b] = renk(k), o = oran(k);
  kartZemini(x, a, b);
  x.shadowColor = "rgba(0,0,0,.6)"; x.shadowBlur = 80; x.shadowOffsetY = 30;
  x.fillStyle = "#000"; x.beginPath(); x.roundRect ? x.roundRect(170, 330, 740, 740, 17) : x.rect(170, 330, 740, 740); x.fill();
  x.shadowColor = "transparent";
  kapakCiz(x, k, 170, 330, 740, await desenResmi(k));
  x.textAlign = "center"; x.fillStyle = "rgba(255,255,255,.75)"; x.font = "700 40px Figtree, sans-serif";
  x.fillText(durum.bitti[k.id] ? "BİTİRDİM" : o > 0 ? "ŞU AN DİNLİYORUM" : "BUNU DİNLE", 540, 230);
  x.fillStyle = "#fff"; x.font = "600 84px Fraunces, Georgia, serif";
  const alt = sarYaz(x, k.eser, 540, 1220, 900, 96);
  x.fillStyle = "rgba(255,255,255,.8)"; x.font = "700 44px Figtree, sans-serif";
  x.fillText(`${k.yazar} · ${sure(k.sure)}`, 540, alt + 90);
  if (o > 0 && o < 1) {
    const y = alt + 170;
    x.fillStyle = "rgba(255,255,255,.18)"; x.fillRect(190, y, 700, 12);
    x.fillStyle = "#2fd36b"; x.fillRect(190, y, 700 * o, 12);
    x.fillStyle = "rgba(255,255,255,.75)"; x.font = "600 38px Figtree, sans-serif";
    x.fillText(`%${Math.round(o * 100)} dinlendi · ${sure(k.sure * (1 - o))} kaldı`, 540, y + 75);
  }
  kartAlti(x);
  resimPaylas(c, `${k.id}-kart.png`, `${k.eser} (${k.yazar}) Melih'ten Dinle'de`);
}
async function hikayePaylas() {
  const v = hikayeVerisi(), [c, x] = tuval();
  kartZemini(x, "#1f5a3a", "#2fd36b");
  x.textAlign = "center"; x.fillStyle = "rgba(255,255,255,.75)"; x.font = "700 40px Figtree, sans-serif";
  x.fillText("DİNLEME HİKÂYEM", 540, 200);
  const kutular = [["Toplam dinleme", sureYaz(v.top)], ["Bitirdiğim eser", String(v.biten.length)],
    ["En uzun seri", `${enUzunSeri()} gün`], ["Rozet", `${v.rozet.length}/${ROZETLER.length}`]];
  kutular.forEach(([ad, deger], i) => {
    const cx = i % 2 ? 790 : 290, y = 330 + Math.floor(i / 2) * 300;
    x.fillStyle = "rgba(255,255,255,.08)"; x.beginPath(); x.roundRect ? x.roundRect(cx - 230, y, 460, 250, 28) : x.rect(cx - 230, y, 460, 250); x.fill();
    x.fillStyle = "rgba(255,255,255,.7)"; x.font = "600 36px Figtree, sans-serif"; x.fillText(ad, cx, y + 80);
    x.fillStyle = "#fff"; x.font = "800 76px Figtree, sans-serif"; x.fillText(deger, cx, y + 180);
  });
  if (v.eserler[0]) {
    const [k] = v.eserler[0];
    x.fillStyle = "rgba(255,255,255,.7)"; x.font = "600 38px Figtree, sans-serif"; x.fillText("En çok dinlediğim", 540, 1000);
    kapakCiz(x, k, 340, 1040, 400, await desenResmi(k));
    x.textAlign = "center"; x.fillStyle = "#fff"; x.font = "600 60px Fraunces, Georgia, serif";
    sarYaz(x, k.eser, 540, 1530, 900, 70);
  }
  if (v.enYazar) {
    x.fillStyle = "rgba(255,255,255,.75)"; x.font = "700 40px Figtree, sans-serif";
    x.fillText(`En sevdiğim yazar: ${v.enYazar[0]}`, 540, 1680);
  }
  kartAlti(x);
  resimPaylas(c, "dinleme-hikayem.png", "Melih'ten Dinle'deki dinleme hikâyem");
}

// ---------- anı paylaşma: arkadaşın bağlantıyı açınca eser tam o saniyeden başlar ----------
function anPaylas() {
  if (!simdiki) return;
  const t = Math.floor(genel()), k = simdiki, url = `${location.origin}/#/eser/${k.id}/${t}`;
  const metin = `${k.eser} (${k.yazar}), ${saat(t)}. dakikadaki şu kısmı mutlaka dinle:`;
  if (navigator.share) return navigator.share({ title: k.eser, text: metin, url }).catch(() => {});
  (navigator.clipboard ? navigator.clipboard.writeText(`${metin} ${url}`) : Promise.reject())
    .then(() => bildir(`Bağlantı kopyalandı: ${saat(t)} anı`))
    .catch(() => window.open(`https://wa.me/?text=${encodeURIComponent(`${metin} ${url}`)}`, "_blank"));
}

// ---------- ana ekrana ekle: site telefonda gerçek uygulama gibi açılsın ----------
let kurIstegi = null;
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); kurIstegi = e; if (katalog.length) yenile(); });
window.addEventListener("appinstalled", () => { kurIstegi = null; bildir("Melih'ten Dinle ana ekranına eklendi"); if (katalog.length) yenile(); });
const uygulamaModu = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
const iosMu = () => /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
function kurKutusu() {
  if (uygulamaModu() || durum.kurGizle || (!kurIstegi && !iosMu())) return "";
  return `<section class="istek kur"><img src="/simge-192.png" alt="" width="56" height="56"><div><h2>Uygulama gibi kullan</h2>
    <p>${kurIstegi ? "Melih'ten Dinle'yi ana ekranına ekle: tek dokunuşla, tam ekran açılsın."
      : "Safari'de alttaki <b>Paylaş</b> düğmesine dokun, sonra <b>“Ana Ekrana Ekle”</b>yi seç. Tek dokunuşla, tam ekran açılır."}</p></div>
    <div class="kur-dugme">${kurIstegi ? `<button class="dev-cal istek-dugme" data-kur>${simge("indir")}<span>Ana ekrana ekle</span></button>` : ""}
      <button class="ikincil" data-kur-gizle>Gizle</button></div></section>`;
}
function kur() {
  if (!kurIstegi) return;
  kurIstegi.prompt();
  kurIstegi.userChoice.finally(() => { kurIstegi = null; yenile(); });
}

// ---------- başlangıç ----------
simgeleriDoldur();
// internetsiz açılış ve indirilen parçaları çalmak için (sw.js); desteklemeyen tarayıcıda site yine çalışır
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
fetch("/yakinda.json", { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).then((y) => {
  if (!y) return;
  yakinda = y.yakinda || [];
  whatsapp = y.whatsapp || "";
  if (katalog.length) yenile();
}).catch(() => {});
function acilisKaldir() {
  const a = $("#acilis");
  if (!a) return;
  a.classList.add("gitti");
  setTimeout(() => a.remove(), 400);
}
let katalogHazir = false;
function katalogKur(k) {
  const ilk = !katalogHazir;
  katalogHazir = true;
  katalog = k;
  if (!ilk) return yenile();
  yonlendir();
  acilisKaldir();
  // son dinlenen eser çalara yüklenir (çalmadan): tek dokunuşla devam edilebilsin
  const son = eserBul(durum.son);
  if (son && devamEdiyor(son)) {
    simdiki = son;
    baslar = son.parcalar.reduce((a, d) => (a.push(a[a.length - 1] + d), a), [0]).slice(0, -1);
    parca = -1;
    calarCiz();
    git(durum.konum[son.id] || 0, false);
    duraklamaAni = durum.zaman[son.id] || 0;
  }
  setTimeout(rozetDenetle, 1500);
}
// telefondaki son katalog kopyası beklemeden açar; ağdaki güncel katalog gelince sessizce yerine geçer
if ("caches" in window) caches.match("/katalog.json").then((r) => r && r.json()).then((k) => { if (k && !katalogHazir) katalogKur(k); }).catch(() => {});
fetch("/katalog.json", { cache: "no-cache" })
  .then((r) => {
    if (r.status === 401) { location.href = "/giris"; throw new Error("giriş"); }
    return r.json();
  })
  .then((k) => {
    if (katalogHazir && JSON.stringify(k) === JSON.stringify(katalog)) return eskiIndirmeleriTemizle();
    katalogKur(k);
    eskiIndirmeleriTemizle();
  })
  .catch(() => {
    if (katalogHazir) return;
    acilisKaldir();
    $("#icerik").innerHTML = `<div class="sayfa"><p class="bos">Katalog yüklenemedi. İnternetini kontrol edip sayfayı yenile.</p></div>`;
  });

// sw.js telefondaki kopyayı beklemeden açar; site güncellendiyse haber verir
if ("serviceWorker" in navigator) navigator.serviceWorker.addEventListener("message", (e) => {
  if (!e.data || e.data.tip !== "yeni-surum" || $(".yeni-surum")) return;
  const d = document.createElement("button");
  d.className = "yeni-surum";
  d.innerHTML = `${simge("bastan")}<span>Yeni sürüm hazır · <b>Yenile</b></span>`;
  d.addEventListener("click", () => { kaydet(true); location.reload(); });
  document.body.append(d);
});
