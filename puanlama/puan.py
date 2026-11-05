"""Puan hesabı: puanlama/sonuclar/ içindeki araç çıktılarını okur, PUANLAMA.md'deki formülü uygular.

Bu betik ölçüm yapmaz, yalnız hesaplar. Ölçülemeyen alt ölçüm 0 sayılır ve "ÖLÇÜLMEDİ" yazılır.
Kullanım: python puanlama/puan.py  → ekrana rapor, puanlama/sonuclar/puan.json'a sonuç
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from pathlib import Path
from typing import Any

S = Path(__file__).parent / "sonuclar"
NOT = {"A": 100, "B": 80, "C": 60, "D": 40, "E": 20, "1.0": 100, "2.0": 80, "3.0": 60, "4.0": 40, "5.0": 20}


def oku(ad: str) -> Any:
    try:
        return json.loads((S / ad).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def sinirla(x: float) -> float:
    return max(0.0, min(100.0, x))


# --- alt ölçümler: (değer 0-100 ya da None, açıklama) ---

def mutmut() -> tuple[float | None, str]:
    d = oku("mutmut.json")
    if not d:
        return None, "ÖLÇÜLMEDİ"
    oldu = d["killed"] + d.get("timeout", 0)
    payda = d["total"] - d.get("skipped", 0)
    return 100 * oldu / payda, f"{oldu}/{payda} hata yakalandı, {d['survived']} kaçtı, {d.get('no_tests', 0)} testsiz"


def stryker() -> tuple[float | None, str]:
    d = oku("stryker.json")
    if not d:
        return None, "ÖLÇÜLMEDİ"
    say: dict[str, int] = {}
    for f in d["files"].values():
        for m in f["mutants"]:
            say[m["status"]] = say.get(m["status"], 0) + 1
    oldu = say.get("Killed", 0) + say.get("Timeout", 0)
    payda = oldu + say.get("Survived", 0) + say.get("NoCoverage", 0)
    return 100 * oldu / payda, f"{oldu}/{payda} hata yakalandı"


def dal_kapsami() -> tuple[float | None, str]:
    d = oku("kapsam-python.json")
    if not d:
        return None, "ÖLÇÜLMEDİ"
    t = d["totals"]
    return 100 * t["covered_branches"] / t["num_branches"], f"{t['covered_branches']}/{t['num_branches']} dal"


def ts_kapsami() -> tuple[float | None, str]:
    d = oku("kapsam-ts.json")
    return (None, "ÖLÇÜLMEDİ") if d is None else (d["satir"], f"satır %{d['satir']:.1f}, dal %{d['dal']:.1f}")


def katmanlar() -> tuple[float | None, str]:
    d = oku("importlinter.json")
    if not d:
        return None, "ÖLÇÜLMEDİ"
    toplam = d["kept"] + d["broken"]
    return 100 * d["kept"] / toplam, f"{d['kept']}/{toplam} sözleşme tuttu"


def karmasiklik() -> tuple[float | None, str]:
    r, b = oku("ruff.json"), oku("boyut.json")
    if r is None or not b:
        return None, "ÖLÇÜLMEDİ"
    asan = sum(x["code"] == "C901" for x in r)
    return 100 * (1 - asan / b["python_islev"]), f"{asan}/{b['python_islev']} işlev sınırı aşıyor"


def modul_boyutu() -> tuple[float | None, str]:
    b = oku("boyut.json")
    if not b:
        return None, "ÖLÇÜLMEDİ"
    buyuk = [f"{Path(m).name} ({n})" for m, n in b["moduller"] if n > 400]
    return 100 * (1 - len(buyuk) / len(b["moduller"])), f"{len(buyuk)}/{len(b['moduller'])} modül 400 satırı aşıyor " \
                                                         f"{', '.join(buyuk)}".rstrip()


def sonar_notlari() -> tuple[float | None, str]:
    d = oku("sonar.json")
    if not d:
        return None, "ÖLÇÜLMEDİ (SonarQube Cloud bağlı değil)"
    g, b = NOT[str(d["reliability_rating"])], NOT[str(d["sqale_rating"])]
    return (g + b) / 2, f"güvenilirlik {d['reliability_rating']}, bakım {d['sqale_rating']}"


def sonar_tekrar() -> tuple[float | None, str]:
    d = oku("sonar.json")
    if not d:
        return None, "ÖLÇÜLMEDİ (SonarQube Cloud bağlı değil)"
    return sinirla(100 - 10 * float(d["duplicated_lines_density"])), f"tekrar %{d['duplicated_lines_density']}"


def ruff_yogunluk() -> tuple[float | None, str]:
    r, b = oku("ruff.json"), oku("boyut.json")
    if r is None or not b:
        return None, "ÖLÇÜLMEDİ"
    y = len(r) / (b["python_satir"] / 1000)
    return sinirla(100 - 10 * y), f"{len(r)} ihlal / {b['python_satir']} satır = {y:.1f} ihlal/1000 satır"


def bandit() -> tuple[float | None, str]:
    d = oku("bandit.json")
    if d is None:
        return None, "ÖLÇÜLMEDİ"
    say = {k: sum(r["issue_severity"] == k for r in d["results"]) for k in ("HIGH", "MEDIUM", "LOW")}
    return sinirla(100 - 25 * say["HIGH"] - 10 * say["MEDIUM"] - 2 * say["LOW"]), \
        f"yüksek {say['HIGH']}, orta {say['MEDIUM']}, düşük {say['LOW']}"


def bagimlilik_acik_sayisi() -> tuple[int | None, str]:
    p, n = oku("pip-audit.json"), oku("npm-audit.json")
    if p is None or n is None:
        return None, "ÖLÇÜLMEDİ"
    pa = sum(len(x.get("vulns", [])) for x in p["dependencies"])
    na = n["metadata"]["vulnerabilities"]["total"]
    paketler = [f"{x['name']} {x['version']}" for x in p["dependencies"] if x.get("vulns")] + list(n["vulnerabilities"])
    return pa + na, f"Python {pa}, npm {na} açık ({', '.join(paketler)})"


def bagimlilik() -> tuple[float | None, str]:
    n, a = bagimlilik_acik_sayisi()
    return (None, a) if n is None else (sinirla(100 - 20 * n), a)


def scorecard() -> tuple[float | None, str]:
    d = oku("scorecard.json")
    return (None, "ÖLÇÜLMEDİ (GitHub'da çalışır)") if not d else (10 * float(d["score"]), f"{d['score']}/10")


def lighthouse(kategori: str) -> tuple[float | None, str]:
    sayfalar = []
    for sayfa in ("giris", "index"):
        dosyalar = sorted(glob.glob(str(S / f"lighthouse/*{sayfa}_html*.report.json")))
        r = [json.loads(Path(f).read_text()) for f in dosyalar]
        if r:
            sayfalar.append(100 * statistics.median(x["categories"][kategori]["score"] for x in r))
    if len(sayfalar) < 2:
        return None, "ÖLÇÜLMEDİ"
    return sum(sayfalar) / 2, f"giriş {sayfalar[0]:.0f}, ana sayfa {sayfalar[1]:.0f}"


def axe() -> tuple[float | None, str]:
    d = oku("axe.json")
    if d is None:
        return None, "ÖLÇÜLMEDİ"
    ciddi = sum(v["adet"] for s in d.values() for v in s if v["etki"] in ("serious", "critical"))
    diger = sum(v["adet"] for s in d.values() for v in s if v["etki"] not in ("serious", "critical"))
    kurallar = sorted({v["id"] for s in d.values() for v in s})
    return sinirla(100 - 15 * ciddi - 5 * diger), f"ciddi/kritik {ciddi} öğe, diğer {diger} öğe ({', '.join(kurallar)})"


def on_yuz_kapsami() -> tuple[float | None, str]:
    d = oku("kapsam-on-yuz.json")
    return (0.0, "ön yüz testi yok") if d is None else (d["satir"], f"satır %{d['satir']:.1f}")


ALANLAR: list[tuple[str, int, list[tuple[str, float, Any]]]] = [
    ("Doğruluk ve hata dayanıklılığı", 35, [
        ("Mutasyon (Python, mutmut)", .45, mutmut), ("Mutasyon (TypeScript, Stryker)", .15, stryker),
        ("Dal kapsamı (Python)", .25, dal_kapsami), ("Satır kapsamı (TypeScript)", .15, ts_kapsami)]),
    ("Mimari", 20, [
        ("Katman kuralları", .40, katmanlar), ("İşlev karmaşıklığı", .40, karmasiklik),
        ("Modül boyutu", .20, modul_boyutu)]),
    ("Kod kalitesi", 15, [
        ("SonarQube notları", .50, sonar_notlari), ("SonarQube kod tekrarı", .20, sonar_tekrar),
        ("Kural ihlali yoğunluğu (ruff)", .30, ruff_yogunluk)]),
    ("Güvenlik", 15, [
        ("bandit", .40, bandit), ("Bağımlılık açıkları", .30, bagimlilik), ("OpenSSF Scorecard", .30, scorecard)]),
    ("Ön yüz", 15, [
        ("Lighthouse performans", .20, lambda: lighthouse("performance")),
        ("Lighthouse erişilebilirlik", .20, lambda: lighthouse("accessibility")),
        ("Lighthouse iyi uygulamalar", .20, lambda: lighthouse("best-practices")),
        ("axe erişilebilirlik", .20, axe), ("Ön yüz test kapsamı", .20, on_yuz_kapsami)]),
]


def _guvenlik_sarti(bandit_yuksek: int | None, codeql_yuksek: int | None) -> bool | None:
    """Biri bile bulgu verdiyse tutmadı; ikisi de 0 ise tuttu; aksi hâlde ölçülmedi."""
    if (bandit_yuksek or 0) > 0 or (codeql_yuksek or 0) > 0:
        return False
    if bandit_yuksek is None or codeql_yuksek is None:
        return None
    return True


def kesin_sartlar() -> list[tuple[str, bool | None, str]]:
    d = oku("kesin.json") or {}
    b = oku("bandit.json")
    yuksek = None if b is None else sum(r["issue_severity"] == "HIGH" for r in b["results"])
    k = oku("importlinter.json")
    acik, _ = bagimlilik_acik_sayisi()
    codeql = (oku("codeql.json") or {}).get("yuksek")
    return [
        ("0 tip hatası (mypy, deno check)", d.get("tip_hatasi_yok"), ""),
        ("0 katman ihlali", None if not k else k["broken"] == 0, ""),
        ("0 yüksek/kritik güvenlik bulgusu (bandit, CodeQL)", _guvenlik_sarti(yuksek, codeql),
         f"bandit yüksek {yuksek}, CodeQL " + ("ölçülmedi" if codeql is None else f"yüksek {codeql}")),
        ("Açığı bilinen 0 bağımlılık", None if acik is None else acik == 0, f"{acik} açık"),
        ("Bütün testler geçer", d.get("testler_gecti"), ""),
    ]


def main() -> int:
    toplam, rapor = 0.0, {"alanlar": [], "kesin": []}
    for ad, agirlik, olcumler in ALANLAR:
        alan = 0.0
        print(f"\n{ad} ({agirlik} puan)")
        satirlar = []
        for oad, pay, f in olcumler:
            deger, aciklama = f()
            alan += pay * (deger or 0)
            print(f"  {oad:<34} {'—' if deger is None else f'{deger:5.1f}':>6}  {aciklama}")
            satirlar.append({"ad": oad, "pay": pay, "deger": deger, "aciklama": aciklama})
        puan = agirlik * alan / 100
        toplam += puan
        print(f"  {'alan puanı':<34} {puan:5.1f} / {agirlik}")
        rapor["alanlar"].append({"ad": ad, "agirlik": agirlik, "puan": round(puan, 2), "olcumler": satirlar})
    print("\nKesin şartlar")
    gecti = True
    for ad, durum, ek in kesin_sartlar():
        gecti &= durum is True
        print(f"  {'TUTTU' if durum else ('ÖLÇÜLMEDİ' if durum is None else 'TUTMADI'):<10} {ad} {ek}".rstrip())
        rapor["kesin"].append({"ad": ad, "durum": durum, "ek": ek})
    rapor["toplam"], rapor["sonuc"] = round(toplam, 1), "GEÇTİ" if gecti else "GEÇMEDİ"
    print(f"\nTOPLAM: {toplam:.1f} / 100 — {rapor['sonuc']}")
    (S / "puan.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if gecti else 1


if __name__ == "__main__":
    sys.exit(main())
