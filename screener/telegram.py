"""Envoi d'un signal sur le canal Telegram (photo + légende)."""

import os
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/sendPhoto"


def send_photo(caption: str, image: bytes, name: str) -> None:
    """Envoie la photo ; sans TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID, l'enregistre dans out/ (mode essai)."""
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        out = Path("out")
        out.mkdir(exist_ok=True)
        (out / f"{name}.png").write_bytes(image)
        (out / f"{name}.txt").write_text(caption, encoding="utf-8")
        print(f"[essai] {name} enregistré dans out/")
        return
    r = requests.post(API.format(token=token),
                      data={"chat_id": chat, "caption": caption, "parse_mode": "HTML"},
                      files={"photo": (f"{name}.png", image, "image/png")}, timeout=30)
    if not r.ok:
        # On n'affiche pas l'URL (elle contient le token).
        raise RuntimeError(f"Telegram a refusé l'envoi ({r.status_code}) : {r.text[:200]}")
