
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

SYMBOLS = {
    "ELFW.DE": ["ELFW.DE"],
    "0P0000P8Q6.F": ["0P0000P8Q6.F", "0P000P8Q6.F"],
}

def read_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback

def fetch_quote(symbol):
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol, safe="")
        + "?range=5d&interval=1d"
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    result = data.get("chart", {}).get("result")
    if not result:
        raise RuntimeError("No quote available")

    item = result[0]
    meta = item.get("meta", {})
    closes = item.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    closes = [x for x in closes if isinstance(x, (int, float))]
    if not closes:
        raise RuntimeError("No closing prices")

    price = float(meta.get("regularMarketPrice") or closes[-1])
    previous = float(
        meta.get("chartPreviousClose")
        or meta.get("previousClose")
        or (closes[-2] if len(closes) > 1 else price)
    )
    return {
        "symbol": symbol,
        "price": round(price, 6),
        "prevClose": round(previous, 6),
        "changePercent": round((price / previous - 1) * 100, 4)
        if previous else 0,
        "currency": meta.get("currency", "EUR"),
        "source": "Yahoo Finance",
    }

now = datetime.now(ZoneInfo("Europe/Berlin"))
quotes = {}
errors = {}

for canonical, aliases in SYMBOLS.items():
    for symbol in aliases:
        try:
            quotes[canonical] = fetch_quote(symbol)
            break
        except Exception as error:
            errors[canonical] = str(error)

baseline_path = DATA / "baseline.json"
baseline = read_json(baseline_path, {})
for symbol, quote in quotes.items():
    baseline.setdefault(symbol, quote["price"])

baseline_path.write_text(
    json.dumps(baseline, indent=2) + "\n", encoding="utf-8"
)

payload = {
    "updatedAt": now.isoformat(),
    "source": "Yahoo Finance",
    "quotes": quotes,
    "baseline": baseline,
    "errors": errors,
}
(DATA / "quotes.json").write_text(
    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
)

history_path = DATA / "history.json"
history = read_json(history_path, [])
delta = 0.0

if "ELFW.DE" in quotes and "ELFW.DE" in baseline:
    delta += 750 * (
        quotes["ELFW.DE"]["price"] / baseline["ELFW.DE"] - 1
    )
if "0P0000P8Q6.F" in quotes and "0P0000P8Q6.F" in baseline:
    delta += 750 * (
        quotes["0P0000P8Q6.F"]["price"]
        / baseline["0P0000P8Q6.F"] - 1
    )

if quotes:
    entry = {
        "date": now.date().isoformat(),
        "updatedAt": now.isoformat(),
        "estimatedValue": round(1561 + delta, 2),
        "deltaSinceStart": round(delta, 2),
    }
    if history and history[-1].get("date") == entry["date"]:
        history[-1] = entry
    else:
        history.append(entry)
    history = history[-730:]

history_path.write_text(
    json.dumps(history, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(payload, indent=2))
