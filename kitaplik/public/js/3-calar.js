// Melih'ten Dinle — yönlendirme, çalar, hız ve uyku menüsü (js/1-temel.js'teki açıklamaya bakın).
"use strict";

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

