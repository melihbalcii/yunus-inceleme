// Şifre kapısı testleri. Çalıştırma (kitaplik/ içinden): node --test testler/
import assert from "node:assert/strict";
import { test } from "node:test";
import { kapi } from "../netlify/edge-functions/kapi.ts";
import {
  acikMi, cerezDegeri, cereziBul, esitMi, imzala, oturumGecerliMi, sade, sifreDogruMu,
} from "../netlify/lib/oturum.ts";

const SIR = "deneme-anahtari";
const ORTAM = { get: (ad: string) => ({ SIFRE: "Kitaplık", ANAHTAR: SIR } as Record<string, string>)[ad] };
const SIMDI = Date.UTC(2026, 10, 5);
const istek = (yol: string, init: RequestInit = {}) => new Request(`https://site.test${yol}`, init);

test("şifre Türkçe harf ve büyük/küçük harf farkı gözetmez", async () => {
  assert.equal(sade(" İSTANBUL "), "istanbul");
  assert.equal(sade("Işık"), "isik");
  assert.ok(await sifreDogruMu("KİTAPLIK", "Kitaplık"));
  assert.ok(await sifreDogruMu("kitaplik", "Kitaplık"));
  assert.ok(!(await sifreDogruMu("kitap", "Kitaplık")));
  assert.ok(!(await sifreDogruMu("", "")), "boş şifre hiçbir zaman tutmaz");
});

test("sabit süreli karşılaştırma doğru sonuç verir", async () => {
  assert.ok(await esitMi("abc", "abc"));
  assert.ok(!(await esitMi("abc", "abd")));
  assert.ok(!(await esitMi("abc", "abcd")));
});

test("açık yollar", () => {
  for (const y of ["/giris", "/stil.css", "/manifest.webmanifest", "/acilis/1170x2532.png"]) assert.ok(acikMi(y), y);
  for (const y of ["/", "/katalog.json", "/ses/x-1/1.mp3", "/acilis/../katalog.json", "/acilis/x.png"]) {
    assert.ok(!acikMi(y), y);
  }
});

test("çerez: geçerli, süresi dolmuş, sahte imza, başka anahtar", async () => {
  const deger = await cerezDegeri(SIR, SIMDI);
  assert.ok(await oturumGecerliMi(`a=1; kitaplik=${deger}; b=2`, SIR, SIMDI));
  assert.ok(!(await oturumGecerliMi(`kitaplik=${deger}`, SIR, SIMDI + 366 * 24 * 3600 * 1000)));
  assert.ok(!(await oturumGecerliMi(`kitaplik=${deger}`, "baska", SIMDI)));
  const [bitis] = deger.split(".");
  assert.ok(!(await oturumGecerliMi(`kitaplik=${bitis}.sahte`, SIR, SIMDI)));
  assert.ok(!(await oturumGecerliMi(`kitaplik=${Number(bitis) + 1}.${deger.split(".")[1]}`, SIR, SIMDI)));
  assert.ok(!(await oturumGecerliMi("kitaplik=bozuk", SIR, SIMDI)));
  assert.ok(!(await oturumGecerliMi(null, SIR, SIMDI)));
  assert.ok(!(await oturumGecerliMi(`kitaplik=${deger}`, "", SIMDI)));
});

test("eski biçimdeki çerez geçerli kalır (yayından sonra kimse çıkış yapmasın)", async () => {
  // eski kapi.ts: bitis.base64url(HMAC-SHA256(ANAHTAR, bitis))
  const bitis = String(SIMDI + 1000);
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(SIR), { name: "HMAC", hash: "SHA-256" },
    false, ["sign"]);
  const s = await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(bitis));
  const imza = btoa(String.fromCharCode(...new Uint8Array(s))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  assert.equal(await imzala(SIR, bitis), imza);
  assert.ok(await oturumGecerliMi(`kitaplik=${bitis}.${imza}`, SIR, SIMDI));
});

test("çerez başlığı ayrıştırma", () => {
  assert.equal(cereziBul("x=1;kitaplik=a.b"), "a.b");
  assert.equal(cereziBul("kitaplikx=1"), null);
  assert.equal(cereziBul(null), null);
});

test("boş anahtarla imza atılmaz", async () => {
  await assert.rejects(imzala("", "1"));
});

test("kapı: girişsiz sayfa isteği giriş sayfasına, dosya isteği 401", async () => {
  const sayfa = await kapi(istek("/", { headers: { Accept: "text/html" } }), ORTAM, SIMDI);
  assert.equal(sayfa?.status, 302);
  assert.equal(sayfa?.headers.get("Location"), "https://site.test/giris");
  assert.equal((await kapi(istek("/katalog.json"), ORTAM, SIMDI))?.status, 401);
  assert.equal(await kapi(istek("/stil.css"), ORTAM, SIMDI), undefined);
});

test("kapı: doğru şifre çerez verir, çerezle her şey açılır", async () => {
  const form = new URLSearchParams({ sifre: "kitaplık" });
  const y = await kapi(istek("/giris", { method: "POST", body: form }), ORTAM, SIMDI);
  assert.equal(y?.status, 303);
  assert.equal(y?.headers.get("Location"), "/");
  const cerez = y?.headers.get("Set-Cookie") ?? "";
  assert.match(cerez, /^kitaplik=\d+\.[\w-]+; Max-Age=31536000; Path=\/; HttpOnly; Secure; SameSite=Lax$/);
  const ac = await kapi(istek("/ses/x/1.mp3", { headers: { Cookie: cerez.split(";")[0] } }), ORTAM, SIMDI);
  assert.equal(ac, undefined);
});

test("kapı: yanlış şifre ve bozuk gövde giriş sayfasına hata ile döner", async () => {
  const yanlis = await kapi(istek("/giris", { method: "POST", body: new URLSearchParams({ sifre: "x" }) }), ORTAM, SIMDI);
  assert.equal(yanlis?.headers.get("Location"), "https://site.test/giris?hata=1");
  const bozuk = await kapi(istek("/giris", { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } }),
    ORTAM, SIMDI);
  assert.equal(bozuk?.status, 303);
  const buyuk = await kapi(istek("/giris", { method: "POST", body: "x", headers: { "Content-Length": "99999" } }),
    ORTAM, SIMDI);
  assert.equal(buyuk?.status, 413);
});

test("kapı: ayar eksikse hiçbir şey açılmaz", async () => {
  const eksik = { get: (ad: string) => (ad === "SIFRE" ? "x" : undefined) };
  assert.equal((await kapi(istek("/stil.css"), eksik, SIMDI))?.status, 503);
});
