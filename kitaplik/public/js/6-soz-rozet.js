// Melih'ten Dinle — günün sözü, eğilen kapak, rozetler, dinleme takvimi (js/1-temel.js'teki açıklamaya bakın).
"use strict";

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

