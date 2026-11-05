// Şifre kapısının saf (Netlify'dan bağımsız, test edilebilir) çekirdeği.
// Oturum çerezi "bitiş.imza" biçimindedir: bitiş milisaniye cinsinden zaman, imza ANAHTAR sırrıyla HMAC-SHA256
// (base64url). Biçim değişirse herkesin oturumu kapanır; değiştirmeden önce eski biçimi de kabul et.

export const CEREZ = "kitaplik";
export const YIL_SN = 365 * 24 * 3600;

// giriş ekranının ve "Ana Ekrana Ekle"nin şifresiz alması gerekenler (telefon simgeyi/manifest'i çerezsiz ister)
const ACIK = new Set([
  "/giris", "/giris.html", "/stil.css", "/simge.svg", "/giris-foto.jpg", "/giris-foto.webp",
  "/manifest.webmanifest", "/simge-180.png", "/simge-192.png", "/simge-512.png", "/favicon.ico",
]);
const ACILIS_RESMI = /^\/acilis\/\d+x\d+\.png$/; // iPhone'un ana ekran açılış resimleri

export function acikMi(yol: string): boolean {
  return ACIK.has(yol) || ACILIS_RESMI.test(yol);
}

// büyük/küçük harf ve Türkçe harf farkı sayılmaz: telefon ilk harfi "I" ya da "İ" yapsa da şifre tutar
export function sade(s: string): string {
  return s.trim().toLocaleLowerCase("tr").replace(/ı/g, "i").normalize("NFD").replace(/[̀-ͯ]/g, "");
}

const kodlayici = new TextEncoder();
const anahtarlar = new Map<string, Promise<CryptoKey>>(); // aynı süreçte her istekte yeniden kurulmasın

function hmacAnahtari(sir: string): Promise<CryptoKey> {
  let k = anahtarlar.get(sir);
  if (!k) {
    k = crypto.subtle.importKey("raw", kodlayici.encode(sir), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    anahtarlar.set(sir, k);
  }
  return k;
}

function base64url(baytlar: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(baytlar))).replace(/\+/g, "-").replace(/\//g, "_")
    .replace(/=+$/, "");
}

export async function imzala(sir: string, metin: string): Promise<string> {
  if (!sir) throw new Error("ANAHTAR tanımlı değil"); // boş anahtarla imzayı herkes üretebilirdi
  return base64url(await crypto.subtle.sign("HMAC", await hmacAnahtari(sir), kodlayici.encode(metin)));
}

// sabit süreli karşılaştırma: iki tarafın SHA-256 özeti karşılaştırılır, uzunluk ya da ilk farklı harf süre farkı
// olarak sızmaz (şifre ve imza tahmini için ipucu vermesin)
export async function esitMi(a: string, b: string): Promise<boolean> {
  const [x, y] = await Promise.all([a, b].map((s) => crypto.subtle.digest("SHA-256", kodlayici.encode(s))));
  const p = new Uint8Array(x), q = new Uint8Array(y);
  let fark = 0;
  for (let i = 0; i < p.length; i++) fark |= p[i] ^ q[i];
  return fark === 0;
}

export async function sifreDogruMu(girilen: string, sifre: string): Promise<boolean> {
  return sifre !== "" && (await esitMi(sade(girilen), sade(sifre)));
}

export async function cerezDegeri(sir: string, simdiMs: number): Promise<string> {
  const bitis = String(simdiMs + YIL_SN * 1000);
  return `${bitis}.${await imzala(sir, bitis)}`;
}

export function setCookie(deger: string): string {
  return `${CEREZ}=${deger}; Max-Age=${YIL_SN}; Path=/; HttpOnly; Secure; SameSite=Lax`;
}

export function cereziBul(cerezBasligi: string | null): string | null {
  for (const parca of (cerezBasligi ?? "").split(";")) {
    const i = parca.indexOf("=");
    if (i > 0 && parca.slice(0, i).trim() === CEREZ) return parca.slice(i + 1).trim();
  }
  return null;
}

export async function oturumGecerliMi(cerezBasligi: string | null, sir: string, simdiMs: number): Promise<boolean> {
  const deger = cereziBul(cerezBasligi);
  if (!deger || !sir) return false;
  const nokta = deger.indexOf(".");
  if (nokta <= 0) return false;
  const bitis = deger.slice(0, nokta), imza = deger.slice(nokta + 1);
  if (!/^\d{1,16}$/.test(bitis) || Number(bitis) < simdiMs) return false;
  return esitMi(imza, await imzala(sir, bitis));
}
