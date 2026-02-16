# Bershka Stock Monitor

A lightweight Python-based stock monitoring tool for **Bershka online products**.

This project periodically checks product availability using Bershka’s internal API endpoints and sends **real-time Telegram notifications** whenever stock status changes.

Designed for personal use, simplicity, and reliability.

---

## Features

- Monitors multiple Bershka products  
- Tracks specific sizes (XS / S / M / etc.)  
- Detects stock state changes  
- Handles low-stock situations  
- Debounced notifications (reduces false alerts)  
- Built-in error handling & backoff  
- Free Telegram push notifications  
- Runs locally or 24/7 on a VPS  

---

## What It Does

The monitor:

1. Queries Bershka’s internal stock API (`itxrest`)
2. Checks availability for configured size IDs
3. Compares results against stored state
4. Sends a Telegram alert **only when something changes**

Example notifications:

```
IN STOCK — Double sleeve print jumper — size M
OUT OF STOCK — Double sleeve print jumper — size M
```

---

## How It Works

Bershka exposes stock data via internal JSON endpoints.

Instead of scraping HTML, this project:

- Uses direct API calls (fast & efficient)  
- Reads stock availability from JSON responses  
- Matches variant IDs (size IDs)  
- Tracks changes across polling cycles  

This approach is:

- More reliable than scraping
- Computationally lightweight
- Less prone to breaking UI changes

---

## Requirements

- Python 3.8+
- `httpx`

Install dependency:

```bash
pip install httpx
```

---

## Setup Guide

### 1. Create a Telegram Bot

Telegram is used for free push notifications.

**Steps:**

1. Open Telegram  
2. Search for **@BotFather**  
3. Run:

```
/newbot
```

4. Follow the instructions  
5. Copy your **Bot Token**

Example:

```
123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ
```

---

### 2. Get Your Chat ID

1. Start a chat with your new bot  
2. Send any message (e.g. `hi`)  
3. Open in your browser:

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

4. Locate:

```
"chat": { "id": XXXXXXX }
```

That number is your **chat_id**.

---

### 3. Find Bershka Product IDs

Each product requires:

- `product_id`  
- `size_id` (variant ID)  

**How to get them:**

1. Open the product page  
2. Open DevTools → Network  
3. Filter requests by:

```
itxrest
```

4. Inspect stock/detail JSON calls  

You will quickly find:

- Product ID  
- Size/variant IDs  
- Store & catalog IDs  

(Exact structure may vary by market.)

---

### 4. Configure `config.json`

Example configuration:

```json
{
  "bershka": {
    "store_id": 45109558,
    "catalog_id": 40259530
  },
  "polling": {
    "interval_seconds": 180,
    "confirm_count": 2
  },
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_TOKEN_HERE",
    "chat_id": "YOUR_CHAT_ID_HERE"
  },
  "products": [
    {
      "title": "Double sleeve print jumper",
      "url": "https://www.bershka.com/...",
      "product_id": 212744460,
      "checks": [
        { "size_label": "M", "size_id": 212735809 }
      ]
    }
  ]
}
```

---

## Running the Monitor

### Normal Mode (continuous monitoring)

```bash
python monitor_bershka.py
```

---

### Test Telegram Notifications

Send a one-time snapshot:

```bash
python monitor_bershka.py --test-telegram
```

Useful for verifying Telegram configuration.

---

## Running 24/7 (VPS Recommended)

For continuous monitoring, deployment on a VPS is recommended.

Typical stack:

- Ubuntu 24.04 / Debian 12  
- Python virtual environment  
- systemd service  

Benefits:

- Runs independently from SSH sessions  
- Auto-restarts on crashes  
- Starts automatically on reboot  

---

## Smart Behaviours

### Debounced Change Detection

Stock state must be observed multiple times before notifying.

This prevents flickering or transient API inconsistencies from triggering false alerts.

---

### Error Backoff

On network/API errors:

- No false stock changes  
- Exponential retry delays  
- Automatic recovery  

---

### Low Stock Awareness

Detects Bershka’s low-stock threshold:

```
BSK_UMBRAL_BAJO
```

Low-stock situations are reflected in notifications.

---

## Why Use API Instead of Scraping?

- Faster  
- More stable  
- Lower CPU usage  
- Less brittle  
- Cleaner logic  

---

## Disclaimer

This tool is intended for **personal use only**.

It:

- Does not bypass protections  
- Uses publicly accessible endpoints  
- Polls at conservative intervals  

Please respect Bershka’s infrastructure and avoid excessive request rates.

---

## License

Use freely for personal projects.

