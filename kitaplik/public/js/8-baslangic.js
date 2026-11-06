// Melih'ten Dinle — başlangıç: katalog ve Yakında yüklenir (js/1-temel.js'teki açıklamaya bakın).
"use strict";

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
