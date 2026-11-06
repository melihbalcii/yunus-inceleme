// Melih'ten Dinle — olaylar, verileri taşıma, kutlama, desenler (js/1-temel.js'teki açıklamaya bakın).
"use strict";

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
  if (ka) return kartPaylas(eserBul(ka.dataset.kart)).catch(() => bildir("Kart paylaşılamadı"));
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
  else if (islem === "kart" && simdiki) kartPaylas(simdiki).catch(() => bildir("Kart paylaşılamadı"));
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
      secili: dk ? false : !uykuBitis })), uykuKur);
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
    const j = JSON.parse(metin);
    if (!j || j.uygulama !== "melihten-dinle" || !j.veri) throw new Error("dosya");
    const v = temizle(j.veri);   // dosya dışarıdan gelir: hiçbir alanı denetlenmeden alınmaz
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

