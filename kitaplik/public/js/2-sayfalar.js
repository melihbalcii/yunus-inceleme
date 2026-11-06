// Melih'ten Dinle — sayfalar ve indirme (js/1-temel.js'teki açıklamaya bakın).
"use strict";

// ---------- sayfalar ----------
function anaSayfa() {
  const sa = new Date().getHours();
  const selam = sa < 5 ? "İyi geceler" : sa < 12 ? "Günaydın" : sa < 18 ? "İyi günler" : "İyi akşamlar";
  const son = sonDinlenenler();
  const hizli = [...son, ...katalog.filter((k) => !son.includes(k) && !durum.bitti[k.id] && k.sure < 3600)].slice(0, 6);
  const sec = (f) => katalog.filter((k) => f(k));
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
      <div class="cipler">${HEDEFLER.map((d) => `<button class="cip" data-hedef="${d}" aria-pressed="${durum.hedef === d}">${d} dk</button>`).join("")}</div></section>
    <section class="raf tasima"><div class="raf-bas"><h2>Verilerini taşı</h2></div>
      <p class="vakit-not">Kaldığın yerler, bitirdiklerin, yer imlerin, beğenilerin ve karnen yalnız bu cihazda durur.
        Telefondan bilgisayara (ya da yeni telefona) geçerken dosyaya kaydet, öbür cihazda “Dosyadan yükle” ile al. İkisindeki bilgiler birleşir, hiçbiri silinmez.</p>
      <div class="eser-eylem"><button class="ikincil" data-disa>${simge("indir")}Dosyaya kaydet</button>
        <label class="ikincil dosya-sec">${simge("tasi")}Dosyadan yükle<input type="file" accept="application/json,.json" data-ice hidden></label></div></section>
    <p class="dipnot">Karnen yalnız bu telefonda tutulur.</p></div>`;
}

