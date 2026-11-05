// Her isteği karşılayan şifre kapısı. Giriş yapmamış kişi yalnız giriş sayfasını ve onun dosyalarını görür
// (ses parçaları dahil her şey kapalı). POST /giris ortak şifreyi denetleyip bir yıllık oturum çerezi verir.
// Kurallar ve çerez biçimi ../lib/oturum.ts'de (testleri: kitaplik/netlify/testler).
//
// Ortam değişkenleri: SIFRE (ortak şifre), ANAHTAR (çerez imzası sırrı). Biri eksikse kapı hiç açılmaz (503):
// eskiden ANAHTAR boşsa imza boş anahtarla atılıyordu, yani sahte çerezi herkes üretebilirdi.
import type { Config, Context } from "https://edge.netlify.com";
import { acikMi, cerezDegeri, oturumGecerliMi, setCookie, sifreDogruMu } from "../lib/oturum.ts";

const YANLIS_SIFRE_BEKLEMESI_MS = 1500; // art arda tahmini yavaşlat
const EN_BUYUK_FORM = 4096; // bayt

type Ortam = { get(ad: string): string | undefined };
declare const Netlify: { env: Ortam };

export async function kapi(request: Request, ortam: Ortam, simdiMs = Date.now()): Promise<Response | undefined> {
  const sifre = ortam.get("SIFRE") ?? "", sir = ortam.get("ANAHTAR") ?? "";
  if (!sifre || !sir) return new Response("site ayarı eksik", { status: 503 });

  const yol = new URL(request.url).pathname;
  if (yol === "/giris" && request.method === "POST") return giris(request, sifre, sir, simdiMs);
  if (acikMi(yol) || (await oturumGecerliMi(request.headers.get("Cookie"), sir, simdiMs))) return undefined; // Netlify sunar
  const sayfaIstegi = (request.method === "GET" || request.method === "HEAD") &&
    (request.headers.get("Accept") ?? "").includes("text/html");
  if (sayfaIstegi) return Response.redirect(new URL("/giris", request.url), 302);
  return new Response("giriş gerekli", { status: 401 });
}

async function giris(request: Request, sifre: string, sir: string, simdiMs: number): Promise<Response> {
  const hatali = () => Response.redirect(new URL("/giris?hata=1", request.url), 303);
  const boy = Number(request.headers.get("Content-Length") ?? "0");
  if (boy > EN_BUYUK_FORM) return new Response("istek çok büyük", { status: 413 });
  let girilen = "";
  try {
    girilen = String((await request.formData()).get("sifre") ?? "");
  } catch {
    return hatali(); // form değil ya da bozuk gövde
  }
  if (!(await sifreDogruMu(girilen, sifre))) {
    await new Promise((r) => setTimeout(r, YANLIS_SIFRE_BEKLEMESI_MS));
    return hatali();
  }
  return new Response(null, {
    status: 303,
    headers: { Location: "/", "Set-Cookie": setCookie(await cerezDegeri(sir, simdiMs)) },
  });
}

export default (request: Request, _context: Context) => kapi(request, Netlify.env);

export const config: Config = { path: "/*" };
