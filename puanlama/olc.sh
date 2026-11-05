#!/usr/bin/env bash
# Bütün ölçümleri çalıştırır, ham çıktıları puanlama/sonuclar/'a yazar, sonra puanı hesaplar.
# Kullanım (depo kökünden):  PY=python3.11 puanlama/olc.sh
#   PY       ölçüm araçları ve proje kütüphaneleri kurulu Python (varsayılan: python3)
#   ATLA     boşlukla ayrılmış atlanacak adımlar, ör. "mutmut stryker" (önceki çıktı kullanılır)
# Bir adım hata verirse betik durmaz; o ölçüm "ÖLÇÜLMEDİ" kalır ve puan.py bunu gösterir.
set -uo pipefail

KOK="$(cd "$(dirname "$0")/.." && pwd)"
S="$KOK/puanlama/sonuclar"
PY="${PY:-python3}"
ATLA=" ${ATLA:-} "
mkdir -p "$S"

adim() { [[ "$ATLA" != *" $1 "* ]]; }
baslik() { printf '\n== %s\n' "$1"; }

cd "$KOK/araclar"
tip=""       # boş: bu çalıştırmada ölçülmedi (önceki ölçümün sonucu kullanılır)
testler=""

if adim tip; then
  baslik "mypy (strict)"
  tip=true
  "$PY" -m mypy || tip=false
fi

if adim kapsam; then
  baslik "testler + dal kapsamı (coverage)"
  rm -f .coverage
  testler=true
  PYTHONPATH=. "$PY" -m coverage run -m unittest discover -s testler -t . -p "test_*.py" || testler=false
  "$PY" -m coverage json -q -o "$S/kapsam-python.json"
fi

if adim dayaniklilik; then
  baslik "dayanıklılık testleri (ağ arızası, çökme, rastgele hata sırası)"
  "$PY" - "$S/dayaniklilik.json" <<'PYEOF'
import json, subprocess, sys
sonuc = {}
for m in ("test_ag_kopmasi", "test_cokme", "test_dayaniklilik"):
    r = subprocess.run([sys.executable, "-m", "unittest", "-v", f"testler.{m}"], capture_output=True, text=True)
    satir = [x for x in r.stderr.splitlines() if " ... " in x]
    sonuc[m] = {"gecen": sum(x.endswith(" ok") for x in satir), "atlanan": sum(" skipped" in x for x in satir),
                "kalan": sum(x.endswith(("FAIL", "ERROR")) for x in satir)}
    print(m, sonuc[m])
json.dump(sonuc, open(sys.argv[1], "w"))
PYEOF
fi

if adim ruff; then
  baslik "ruff"
  "$PY" -m ruff check --no-cache --output-format json . > "$S/ruff.json" || true
fi

if adim bandit; then
  baslik "bandit"
  "$PY" -m bandit -q -r sesli -f json -o "$S/bandit.json" || true
fi

if adim katman; then
  baslik "import-linter"
  cikti="$(PYTHONPATH=. "$PY" -c "import sys; from importlinter.cli import lint_imports_command; sys.exit(lint_imports_command())" --no-cache 2>&1 || true)"
  echo "$cikti" | tail -4
  echo "$cikti" | "$PY" -c '
import json, re, sys
m = re.search(r"Contracts: (\d+) kept, (\d+) broken", sys.stdin.read())
json.dump({"kept": int(m[1]), "broken": int(m[2])} if m else None, open(sys.argv[1], "w"))' "$S/importlinter.json"
fi

if adim pip-audit; then
  baslik "pip-audit"
  "$PY" -m pip_audit -r gereksinimler.txt -f json -o "$S/pip-audit.json" --progress-spinner off || true
fi

if adim boyut; then
  baslik "modül boyutu ve işlev sayısı"
  (cd "$KOK" && "$PY" - "$S/boyut.json" <<'EOF'
import ast, json, sys
from pathlib import Path
dosyalar = (sorted(Path("araclar/sesli").glob("*.py")) + [Path("araclar/sesli_kitap.py")]
            + sorted(Path("kitaplik/netlify").rglob("*.ts")) + [Path("kitaplik/public/uygulama.js"), Path("kitaplik/public/sw.js")])
mod, fonk, satir = [], 0, 0
for p in dosyalar:
    yazi = p.read_text(encoding="utf-8")
    mod.append((str(p), len(yazi.splitlines())))
    if p.suffix == ".py":
        satir += len(yazi.splitlines())
        fonk += sum(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) for x in ast.walk(ast.parse(yazi)))
json.dump({"moduller": mod, "python_islev": fonk, "python_satir": satir}, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
EOF
  )
fi

if adim mutmut; then
  baslik "mutmut (uzun sürer)"
  rm -rf mutants
  "$PY" -m mutmut run > "$S/mutmut-gunluk.txt" 2>&1 || true
  "$PY" -m mutmut export-cicd-stats >/dev/null 2>&1 && cp mutants/mutmut-cicd-stats.json "$S/mutmut.json"
fi

if adim sonar; then
  baslik "SonarQube Cloud (GitHub'daki son analiz; herkese açık arayüz, anahtar gerekmez)"
  curl -sf "https://sonarcloud.io/api/measures/component?component=melihbalcii_yunus-inceleme&metricKeys=reliability_rating,sqale_rating,security_rating,duplicated_lines_density,bugs,code_smells,vulnerabilities,ncloc" \
    | "$PY" -c '
import json, sys
d = {m["metric"]: m.get("value") for m in json.load(sys.stdin)["component"]["measures"]}
print(d); json.dump(d, open(sys.argv[1], "w"))' "$S/sonar.json" || echo "SonarQube okunamadı"
fi

cd "$KOK/kitaplik"

if adim deno; then
  baslik "deno check"
  [ -z "$tip" ] && tip=true
  npm run --silent tip >/dev/null 2>&1 || tip=false
fi

if adim node-test; then
  baslik "node testleri + kapsam"
  [ -z "$testler" ] && testler=true
  cikti="$(node --test --experimental-test-coverage "testler/*.test.ts" 2>&1)" || testler=false
  echo "$cikti" | grep -E "^ℹ (tests|pass|fail)"
  echo "$cikti" | "$PY" -c '
import json, re, sys
m = re.search(r"all files\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)", sys.stdin.read())
json.dump({"satir": float(m[1]), "dal": float(m[2])} if m else None, open(sys.argv[1], "w"))' "$S/kapsam-ts.json"
fi

if adim tarayici; then
  baslik "ön yüz tarayıcı testleri (Chromium)"
  [ -z "$testler" ] && testler=true
  npm run --silent test:tarayici 2>&1 | grep -E "^ℹ (tests|pass|fail)" || true
  KAPSAM_DOSYASI="$S/kapsam-on-yuz.json" npm run --silent test:tarayici >/dev/null 2>&1 || testler=false
fi

if adim npm-audit; then
  baslik "npm audit (çalışma zamanı paketleri)"
  npm audit --omit=dev --json > "$S/npm-audit.json" 2>/dev/null || true
fi

if adim stryker; then
  baslik "Stryker"
  npx stryker run > /dev/null 2>&1 || true
fi

if adim on-yuz; then
  baslik "Lighthouse + axe"
  # gerçek sayfa ölçülsün: site örnek bir eser listesiyle yayınlanır (eser listesi yoksa boş sayfa ölçülürdü)
  olcum_kok="$(mktemp -d)"
  cp -R public/. "$olcum_kok/"
  cp olcum/ornek-katalog.json "$olcum_kok/katalog.json"
  cp olcum/ornek-yakinda.json "$olcum_kok/yakinda.json"
  (cd "$olcum_kok" && "$PY" -m http.server 8765 >/dev/null 2>&1) &
  sunucu=$!
  sleep 2
  rm -rf "$S/lighthouse" .lighthouseci
  CHROME_PATH="$(node -e 'console.log(require("playwright").chromium.executablePath())')" \
    npx lhci collect --config=lighthouserc.json >/dev/null 2>&1 && npx lhci upload --config=lighthouserc.json >/dev/null 2>&1
  node olcum/axe.mjs http://localhost:8765 "$S/axe.json" >/dev/null 2>&1 || true
  kill "$sunucu" 2>/dev/null
fi

"$PY" - "$tip" "$testler" "$S/kesin.json" <<'EOF'
import json, sys
from pathlib import Path
yol = Path(sys.argv[3])
eski = json.loads(yol.read_text()) if yol.exists() else {}
def deger(x, ad):
    return eski.get(ad) if x == "" else x == "true"
json.dump({"tip_hatasi_yok": deger(sys.argv[1], "tip_hatasi_yok"),
           "testler_gecti": deger(sys.argv[2], "testler_gecti")}, open(yol, "w"))
EOF

baslik "PUAN"
"$PY" "$KOK/puanlama/puan.py"
