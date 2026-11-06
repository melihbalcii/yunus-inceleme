// Melih'ten Dinle — dinleme hikâyesi, paylaşım kartları, anı paylaşma, ana ekrana ekle (js/1-temel.js'teki açıklamaya bakın).
"use strict";

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
  return resimPaylas(c, `${k.id}-kart.png`, `${k.eser} (${k.yazar}) Melih'ten Dinle'de`);
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
  resimPaylas(c, "dinleme-hikayem.png", "Melih'ten Dinle'deki dinleme hikâyem").catch(() => bildir("Paylaşılamadı"));
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

