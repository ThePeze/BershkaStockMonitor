from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from notifiers import TelegramNotifier


CONFIG_PATH = Path("config.json")
STATE_PATH = Path("state.json")


@dataclass(frozen=True)
class Check:
    size_label: str
    size_id: int


@dataclass(frozen=True)
class Product:
    title: str
    url: str
    product_id: int
    checks: List[Check]


def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def load_config() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_state() -> Dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"products": {}}


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_stock_url(store_id: int, catalog_id: int, product_id: int, language_id: int, app_id: int) -> str:
    return (
        f"https://www.bershka.com/itxrest/2/catalog/store/{store_id}/{catalog_id}"
        f"/product/{product_id}/stock?languageId={language_id}&appId={app_id}"
    )


def parse_stock_entry(stock_json: Dict[str, Any], product_id: int, size_id: int) -> Optional[Dict[str, Any]]:
    blocks = stock_json.get("stocks", [])
    if not isinstance(blocks, list):
        return None

    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("productId") != product_id:
            continue
        inner = block.get("stocks")
        if not isinstance(inner, list):
            continue
        for entry in inner:
            if isinstance(entry, dict) and entry.get("id") == size_id:
                return entry
    return None


def normalize_status(entry: Dict[str, Any]) -> Dict[str, Any]:
    availability = str(entry.get("availability", "")).lower().strip()
    low_stock = entry.get("typeThreshold") == "BSK_UMBRAL_BAJO"

    if availability == "in_stock":
        return {"status": "AVAILABLE", "low_stock": low_stock}
    if availability == "out_of_stock":
        return {"status": "OUT", "low_stock": low_stock}
    return {"status": "UNKNOWN", "low_stock": low_stock}


def status_banner(curr: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (emoji_prefix, human_label)
    """
    if curr["status"] == "AVAILABLE":
        if curr["low_stock"]:
            return "✅", "IN STOCK (LOW)"
        return "✅", "IN STOCK"
    if curr["status"] == "OUT":
        return "❌", "OUT OF STOCK"
    return "⚠️", "STATUS UNKNOWN"


def format_change_message(product: Product, check: Check, curr: Dict[str, Any]) -> str:
    emoji, label = status_banner(curr)
    # First line = instantly readable notification preview
    first_line = f"{emoji} {label} — {product.title} — size {check.size_label}"

    # Keep the rest of the info
    return (
        f"{first_line}\n"
        f"Time: {now_ts()}\n"
        f"Product ID: {product.product_id}\n"
        f"Size ID: {check.size_id}\n"
        f"{product.url}"
    )


def main() -> None:
    cfg = load_config()

    bershka = cfg["bershka"]
    store_id = int(bershka["store_id"])
    catalog_id = int(bershka["catalog_id"])
    language_id = int(bershka.get("language_id", -1))
    app_id = int(bershka.get("app_id", 1))

    polling = cfg.get("polling", {})
    interval_seconds = int(polling.get("interval_seconds", 180))
    jitter_seconds = int(polling.get("jitter_seconds", 30))
    per_product_delay = float(polling.get("per_product_delay_seconds", 2))
    timeout_seconds = float(polling.get("timeout_seconds", 20))

    confirm_count = int(polling.get("confirm_count", 2))
    suppress_initial = bool(polling.get("suppress_initial_notifications", True))

    backoff_base = float(polling.get("backoff_base_seconds", 10))
    backoff_max = float(polling.get("backoff_max_seconds", 600))

    telegram_cfg = cfg.get("telegram", {})
    tg_enabled = bool(telegram_cfg.get("enabled", False))
    notifier: Optional[TelegramNotifier] = None
    if tg_enabled:
        notifier = TelegramNotifier(
            bot_token=str(telegram_cfg["bot_token"]),
            chat_id=str(telegram_cfg["chat_id"]),
            timeout_seconds=timeout_seconds,
        )

    products_raw = cfg["products"]
    products: List[Product] = []
    for p in products_raw:
        checks = [Check(c["size_label"], int(c["size_id"])) for c in p["checks"]]
        products.append(Product(p["title"], p.get("url", ""), int(p["product_id"]), checks))

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; bershka-personal-monitor/1.2)",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }

    state = load_state()
    state.setdefault("products", {})

    print(
        f"[{now_ts()}] monitoring {len(products)} product(s). "
        f"interval={interval_seconds}s jitter=±{jitter_seconds}s confirm_count={confirm_count} "
        f"telegram={'on' if tg_enabled else 'off'}"
    )

    with httpx.Client(headers=headers, timeout=timeout_seconds, follow_redirects=True) as client:
        while True:
            cycle_stamp = now_ts()

            for idx, product in enumerate(products, start=1):
                pid_key = str(product.product_id)
                prod_state = state["products"].setdefault(pid_key, {})
                error_count = int(prod_state.get("_error_count", 0))

                url = build_stock_url(store_id, catalog_id, product.product_id, language_id, app_id)

                # Fetch with backoff on errors
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    stock_json = r.json()
                    if error_count != 0:
                        prod_state["_error_count"] = 0
                        save_state(state)
                except Exception as e:
                    error_count += 1
                    prod_state["_error_count"] = error_count
                    save_state(state)

                    sleep_for = min(backoff_base * (2 ** (error_count - 1)), backoff_max)
                    print(f"[{cycle_stamp}] [{idx}/{len(products)}] ERROR {product.title}: {e} (backoff {int(sleep_for)}s)")
                    time.sleep(sleep_for)
                    continue

                # Update size states & notify on confirmed changes
                for check in product.checks:
                    entry = parse_stock_entry(stock_json, product.product_id, check.size_id)
                    if not entry:
                        continue

                    curr = normalize_status(entry)

                    sid_key = str(check.size_id)
                    rec = prod_state.setdefault(sid_key, {})

                    last_seen = rec.get("last_seen")
                    seen_streak = int(rec.get("seen_streak", 0))
                    last_emitted = rec.get("last_emitted")

                    if last_seen == curr:
                        seen_streak += 1
                    else:
                        last_seen = curr
                        seen_streak = 1

                    rec["last_seen"] = last_seen
                    rec["seen_streak"] = seen_streak

                    if seen_streak >= confirm_count:
                        if suppress_initial and last_emitted is None:
                            rec["last_emitted"] = curr
                        elif last_emitted != curr:
                            rec["last_emitted"] = curr

                            msg = format_change_message(product, check, curr)
                            print(f"[{cycle_stamp}] {msg.replace(chr(10), ' | ')}")

                            if notifier is not None:
                                try:
                                    notifier.send(msg)
                                except Exception as te:
                                    print(f"[{cycle_stamp}] Telegram send failed: {te}")

                save_state(state)

                if per_product_delay > 0:
                    time.sleep(per_product_delay)

            sleep_for = interval_seconds + random.randint(-jitter_seconds, jitter_seconds)
            sleep_for = max(30, sleep_for)
            print(f"[{now_ts()}] cycle done. next check in ~{int(sleep_for)}s")
            time.sleep(sleep_for)


if __name__ == "__main__":
    main()
