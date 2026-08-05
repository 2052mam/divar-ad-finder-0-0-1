from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import requests
import re
import time
import sqlite3
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from config import (
    DATABASE_PATH,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    NOTIFY_EMAIL,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASS,
    SMTP_USE_SSL,
)

app = Flask(__name__)
app.secret_key = "divar-monitor-secret-key-change-this"

LOGIN_USER = "admin"
LOGIN_PASS = "12345678"


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"success": False, "error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ====================== مدل‌ها ======================
MOBILE_MODELS = {
    "samsung": [
        "samsung galaxy a57", "samsung galaxy s25 ultra", "samsung galaxy s26", "samsung galaxy s26 ultra",
        "samsung galaxy s25 plus", "samsung galaxy s25 edge", "samsung galaxy s25 fe", "samsung galaxy s25",
        "samsung galaxy z fold6", "samsung galaxy s24 ultra", "samsung galaxy s24", "samsung galaxy s24 fe",
        "samsung galaxy z fold5", "samsung galaxy z flip5", "samsung galaxy z fold4", "samsung galaxy z flip4",
        "samsung galaxy s23 ultra", "samsung galaxy s23 plus", "samsung galaxy s23 5g", "samsung galaxy s23 fe",
        "samsung galaxy z fold3 5g", "samsung galaxy z flip3 5g", "samsung galaxy z flip 5g", "samsung galaxy z flip",
        "samsung galaxy z fold2 5g", "samsung galaxy s22 ultra 5g", "samsung galaxy s22+ 5g", "samsung galaxy s22 5g",
        "samsung galaxy s21 ultra 5g", "samsung galaxy s21+ 5g", "samsung galaxy s21 5g", "samsung galaxy s21 fe 5g",
        "samsung galaxy s21", "samsung galaxy s20 ultra 5g", "samsung galaxy s20 ultra", "samsung galaxy s20+ 5g",
        "samsung galaxy s20 5g", "samsung galaxy s20 fe 5g", "samsung galaxy s20 fe", "samsung galaxy s20",
        "samsung galaxy note20 ultra 5g", "samsung galaxy note20 ultra", "samsung galaxy note20 5g", "samsung galaxy note20",
        "samsung galaxy note10+ 5g", "samsung galaxy note10 5g", "samsung galaxy note10", "samsung galaxy note9",
        "samsung galaxy note8", "samsung galaxy s10 5g", "samsung galaxy s10+", "samsung galaxy s10e", "samsung galaxy s10",
        "samsung galaxy s10 lite", "samsung galaxy s9+", "samsung galaxy s9", "samsung galaxy s8+", "samsung galaxy s8",
        "samsung galaxy s7 edge", "samsung galaxy s7", "samsung galaxy s6 edge+", "samsung galaxy s6 edge", "samsung galaxy s6",
        "samsung galaxy a73 5g", "samsung galaxy a72", "samsung galaxy a71", "samsung galaxy a70", "samsung galaxy a55",
        "samsung galaxy a54", "samsung galaxy a53 5g", "samsung galaxy a52s 5g", "samsung galaxy a52 5g", "samsung galaxy a52",
        "samsung galaxy a51", "samsung galaxy a50", "samsung galaxy a35", "samsung galaxy a34", "samsung galaxy a33 5g",
        "samsung galaxy a32", "samsung galaxy a25", "samsung galaxy a24", "samsung galaxy a23", "samsung galaxy a22",
        "samsung galaxy a21s", "samsung galaxy a16", "samsung galaxy a15", "samsung galaxy a14 5g", "samsung galaxy a13",
        "samsung galaxy a12", "samsung galaxy a06", "samsung galaxy a05s", "samsung galaxy a05", "samsung galaxy a04s",
        "samsung galaxy a04", "samsung galaxy a03", "samsung galaxy a02s", "samsung galaxy a02", "samsung galaxy a01",
        "samsung galaxy m55", "samsung galaxy m54", "samsung galaxy m53", "samsung galaxy m34 5g", "samsung galaxy m33",
        "samsung galaxy m32", "samsung galaxy m31", "samsung galaxy m14", "samsung galaxy m13", "samsung galaxy m12",
        "samsung galaxy f54", "samsung galaxy f34", "samsung galaxy f23", "samsung galaxy f14", "samsung galaxy f13"
    ],
    "apple": [
        "apple iphone 17 pro max", "apple iphone 17 pro", "apple iphone 17", "apple iphone air",
        "apple iphone 16 pro max", "apple iphone 16 pro", "apple iphone 16 plus", "apple iphone 16",
        "apple iphone 15 pro max", "apple iphone 15 pro", "apple iphone 15 plus", "apple iphone 15",
        "apple iphone 14 pro max", "apple iphone 14 pro", "apple iphone 14 plus", "apple iphone 14",
        "apple iphone 13 pro max", "apple iphone 13 pro", "apple iphone 13", "apple iphone 13 mini",
        "apple iphone 12 pro max", "apple iphone 12 pro", "apple iphone 12", "apple iphone 12 mini",
        "apple iphone se (2022)", "apple iphone 11 pro max", "apple iphone 11 pro", "apple iphone 11",
        "apple iphone se (2020)", "apple iphone xs max", "apple iphone xs", "apple iphone xr",
        "apple iphone x", "apple iphone 8 plus", "apple iphone 8", "apple iphone 7 plus", "apple iphone 7",
        "apple iphone 6s plus", "apple iphone 6s", "apple iphone se", "apple iphone 6 plus", "apple iphone 6"
    ],
    "xiaomi": [
        "xiaomi 15t pro", "xiaomi 15 ultra", "xiaomi 15t", "xiaomi 14t pro", "xiaomi 14t", "xiaomi 14",
        "xiaomi 13t pro", "xiaomi 13t", "xiaomi 13 pro", "xiaomi 13", "xiaomi 12t pro", "xiaomi 12t",
        "xiaomi 12 pro", "xiaomi 12", "xiaomi 11t pro", "xiaomi 11t", "xiaomi mi 11 ultra", "xiaomi mi 11",
        "xiaomi poco f7 pro", "xiaomi poco f7", "xiaomi poco f6 pro", "xiaomi poco f6", "xiaomi poco f5 pro",
        "xiaomi poco f5", "xiaomi poco x7 pro", "xiaomi poco x7", "xiaomi poco x6 pro", "xiaomi poco x6",
        "xiaomi poco x5 pro", "xiaomi poco x5", "xiaomi poco m6 pro", "xiaomi poco m6", "xiaomi poco m5",
        "xiaomi redmi note 14 pro+", "xiaomi redmi note 14 pro", "xiaomi redmi note 14",
        "xiaomi redmi note 13 pro+", "xiaomi redmi note 13 pro", "xiaomi redmi note 13",
        "xiaomi redmi note 12 pro+", "xiaomi redmi note 12 pro", "xiaomi redmi note 12",
        "xiaomi redmi note 11 pro+", "xiaomi redmi note 11 pro", "xiaomi redmi note 11",
        "xiaomi redmi note 10 pro", "xiaomi redmi note 10", "xiaomi redmi 14c", "xiaomi redmi 13c",
        "xiaomi redmi 13", "xiaomi redmi 12", "xiaomi redmi 12c", "xiaomi redmi a3", "xiaomi redmi a2"
    ],
    "huawei": [
        "huawei pura 70", "huawei p60 pro", "huawei p60", "huawei mate 50 pro", "huawei mate 50",
        "huawei mate 40 pro", "huawei mate 40", "huawei p50 pro", "huawei p50", "huawei p40 pro",
        "huawei p40", "huawei p30 pro", "huawei p30", "huawei nova 12", "huawei nova 11",
        "huawei nova 10", "huawei nova 9", "huawei nova 8", "huawei nova 7", "huawei y9a",
        "huawei y7a", "huawei y6p", "huawei y5p", "huawei p smart", "huawei enjoy 20"
    ]
}

CAR_MODELS = {
    "saipa": [
        "Saipa 421P", "Saipa 441P", "Saipa Arya", "Saipa Atlas E-normal", "Saipa Atlas E Plus",
        "Saipa Atlas G", "Saipa Atlas GL", "Saipa Atlas L", "Saipa Atlas S",
        "Saipa Sahand E", "Saipa Sahand G", "Saipa Sahand G CNG", "Saipa Sahand S", "Saipa Karvan Saipa"
    ],
    "pride": [
        "Pride 111", "Pride 131", "Pride 132", "Pride 141", "Pride Automatic", "Pride Station",
        "Pride Sedan", "Pride Pickup Plus", "Pride Pickup 151 Bi-fuel", "Pride Pickup 151 GX",
        "Pride Pickup 151 SE", "Pride Hatchback", "Pride Saba GLXI"
    ],
    "peugeot": [
        "Peugeot 2008", "Peugeot 206", "Peugeot 207i", "Peugeot 301", "Peugeot 405", "Peugeot 406",
        "Peugeot 407", "Peugeot 508", "Peugeot Pars", "Peugeot Roa Petrol", "Peugeot Roa Bi-fuel",
        "Peugeot Partner", "Peugeot RD", "Peugeot RDI"
    ],
    "iran_khodro": [
        "Paykan Bi-fuel(CNG)", "Paykan Bi-fuel(LPG)", "Paykan Petrol", "Paykan Pickup Petrol",
        "Tara Automatic", "Tara Manual", "Tara V3", "Tara V1 plus", "Tara v4",
        "Tiba Hatchback", "Tiba Sedan Plus", "Tiba Sedan EX-normal", "Tiba Sedan EX Bi-fuel",
        "Tiba Sedan LX-normal", "Tiba Sedan LX Bi-fuel", "Tiba Sedan SX-normal", "Tiba Sedan SX Bi-fuel",
        "Dena plus turbo", "Dena plus EF7 MT", "Dena plus Manual 6 Turbo", "Dena plus 1700cc Automatic",
        "Dena plus Turbo CVT", "Dena basic", "Runna Plus P", "Runna Plus-normal", "Runna Plus TU5P", "Runna EL",
        "Saina automatic", "Saina manual Plus", "Saina manual EX", "Saina manual G", "Saina GX",
        "Saina GXL-normal", "Saina GXL CNG", "Samand Sarir", "Samand Soren", "Samand EL", "Samand LX",
        "Samand SE", "Samand X7 Bi-fuel", "Shahin Plus", "Shahin G CVT", "Shahin GL"
    ],
    "other" : [
        "Saipa 421P","Saipa 441P","Saipa Arya","Saipa Atlas E-normal","Saipa Atlas E Plus","Saipa Atlas G","Saipa Atlas GL","Saipa Atlas L","Saipa Atlas S","Saipa Sahand E","Saipa Sahand G","Saipa Sahand G CNG","Saipa Sahand S","Saipa Karvan Saipa","PARS KHODRO P90","Pride 111","Pride 131","Pride 132","Pride 141","Pride Automatic","Pride Station","Pride Sedan","Pride Pickup Plus","Pride Pickup 151 Bi-fuel","Pride Pickup 151 GX","Pride Pickup 151 SE","Pride Hatchback","Pride Saba GLXI","Peugeot 2008","Peugeot 204","Peugeot 205","Peugeot 206","Peugeot 207i","Peugeot 301","Peugeot 304","Peugeot 306","Peugeot 307","Peugeot 308","Peugeot 403","Peugeot 404","Peugeot 405","Peugeot 406","Peugeot 407","Peugeot 504","Peugeot 505","Peugeot 508","Peugeot 605","Peugeot 607","Peugeot 806","Peugeot RD","Peugeot RDI","Peugeot Partner","Peugeot Pars","Peugeot Limousine","Peugeot Roa Petrol","Peugeot Roa Bi-fuel","Peugeot Roa Sal Bi-fuel","Peugeot RCZ","Paykan Bi-fuel(CNG)","Paykan Bi-fuel(LPG)","Paykan Petrol","Paykan Pickup Petrol","Paykan Pickup CNG","Tara Automatic","Tara Manual","Tara V3","Tara V1 plus","Tara v4","Tiba Hatchback","Tiba Sedan Plus","Tiba Sedan EX-normal","Tiba Sedan EX Bi-fuel","Tiba Sedan LX-normal","Tiba Sedan LX Bi-fuel","Tiba Sedan SX-normal","Tiba Sedan SX Bi-fuel","Dena plus turbo","Dena plus EF7 MT","Dena plus Manual 6 Turbo","Dena plus EF7P 6 Speed Manual","Dena plus 6 Speed Manual","Dena plus 1700cc Automatic","Dena plus Turbo 1","Dena plus Manual 1","Dena plus 1700cc Manual","Dena plus EF7 Automatic Turbo Optional","Dena plus Turbo CVT","Dena basic","Runna Plus P","Runna Plus-normal","Runna Plus TU5P","Runna EL","Saina automatic","Saina manual Plus","Saina manual EX","Saina manual G","Saina manual S","Saina GX","Saina GXL-normal","Saina GXL CNG","Saina S","Samand Sarir","Samand Soren","Samand EL","Samand LX","Samand SE","Samand X7 Bi-fuel","Shahin Plus","Shahin G CVT","Shahin GL"
    ],
    "pars_khodro": ["PARS KHODRO P90"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
}


# ====================== دیتابیس ======================
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
    CREATE TABLE IF NOT EXISTS monitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        settings_json TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        track_price INTEGER DEFAULT 0,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS seen_ads (
        token TEXT PRIMARY KEY,
        monitor_id INTEGER,
        title TEXT,
        price TEXT,
        price_num INTEGER,
        link TEXT,
        found_at TEXT,
        last_checked TEXT
    );
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        monitor_id INTEGER,
        monitor_name TEXT,
        token TEXT,
        title TEXT,
        price TEXT,
        link TEXT,
        matched_keywords TEXT,
        found_at TEXT
    );
    CREATE TABLE IF NOT EXISTS price_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT,
        monitor_id INTEGER,
        title TEXT,
        old_price TEXT,
        new_price TEXT,
        link TEXT,
        changed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """
    )
    # سازگاری با دیتابیس قدیمی
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(monitors)").fetchall()]
        if "track_price" not in cols:
            conn.execute("ALTER TABLE monitors ADD COLUMN track_price INTEGER DEFAULT 0")
        cols2 = [r[1] for r in conn.execute("PRAGMA table_info(seen_ads)").fetchall()]
        if "price_num" not in cols2:
            conn.execute("ALTER TABLE seen_ads ADD COLUMN price_num INTEGER")
        if "last_checked" not in cols2:
            conn.execute("ALTER TABLE seen_ads ADD COLUMN last_checked TEXT")
    except Exception as e:
        print("db migrate:", e)
    conn.commit()
    conn.close()


init_db()


# ====================== توابع کمکی ======================
def parse_price(price_str: str) -> Optional[int]:
    if not price_str:
        return None
    numbers = re.findall(r"\d+", str(price_str).replace(",", "").replace("٬", ""))
    if numbers:
        try:
            return int("".join(numbers))
        except Exception:
            return None
    return None


def is_model_match(title: str, model: str) -> bool:
    if not title or not model:
        return False
    title = title.lower().replace("‌", " ").replace("-", " ").replace("_", " ")
    model = model.lower().replace("‌", " ").replace("-", " ").replace("_", " ")
    stop = {
        "samsung", "apple", "xiaomi", "huawei", "galaxy", "iphone", "redmi", "poco", "mi",
        "saipa", "pride", "peugeot", "samand", "dena", "tiba", "saina", "shahin", "tara",
        "runna", "paykan", "pars", "khodro", "گوشی", "موبایل", "خودرو", "ماشین",
    }
    parts = [w for w in model.split() if w not in stop and len(w) > 1]
    if not parts:
        return model in title
    matched = sum(1 for p in parts if p in title)
    required = 1 if len(parts) <= 2 else max(1, len(parts) - 1)
    return matched >= required


def get_post_description(token: str) -> str:
    for url in [
        f"https://api.divar.ir/v8/posts/{token}",
        f"https://api.divar.ir/v8/posts-v2/web/{token}",
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            data = r.json()
            if isinstance(data.get("description"), str) and len(data["description"]) > 5:
                return data["description"]
            if isinstance(data.get("data"), dict) and isinstance(data["data"].get("description"), str):
                return data["data"]["description"]

            def dig(obj, depth=0):
                if depth > 6:
                    return ""
                if isinstance(obj, dict):
                    for k in ["description", "text", "value", "content"]:
                        v = obj.get(k)
                        if isinstance(v, str) and len(v) > 20 and not v.startswith("http"):
                            return v
                    for v in obj.values():
                        f = dig(v, depth + 1)
                        if f:
                            return f
                elif isinstance(obj, list):
                    for i in obj:
                        f = dig(i, depth + 1)
                        if f:
                            return f
                return ""

            found = dig(data)
            if found:
                return found
        except Exception:
            pass
    return ""


def find_matched_keywords(text: str, keywords: List[str]) -> List[str]:
    if not text or not keywords:
        return []
    t = text.lower()
    return [k for k in keywords if k.lower() in t]


def has_negative_keyword(text: str, negative_keywords: List[str]) -> bool:
    if not text or not negative_keywords:
        return False
    t = text.lower()
    return any(k.lower() in t for k in negative_keywords if k.strip())


def filter_negative_keywords(ads: List[Dict], negative_keywords: List[str], max_fetch: int = 25) -> List[Dict]:
    """کلمه منفی اولویت مطلق دارد"""
    if not negative_keywords:
        return ads
    negative_keywords = [k.strip() for k in negative_keywords if k.strip()]
    if not negative_keywords:
        return ads

    kept = []
    fetch = 0
    for ad in ads:
        title = ad.get("title") or ""
        if has_negative_keyword(title, negative_keywords):
            continue
        blocked = False
        if fetch < max_fetch:
            desc = get_post_description(ad["token"])
            time.sleep(0.45)
            fetch += 1
            if has_negative_keyword(desc, negative_keywords):
                blocked = True
        if not blocked:
            kept.append(ad)
    return kept


def enrich_ads_with_keywords(ads: List[Dict], keywords: List[str], max_fetch: int = 20) -> List[Dict]:
    if not keywords:
        for ad in ads:
            ad["matched_keywords"] = []
            ad["has_keyword"] = False
        return ads
    keywords = [k.strip() for k in keywords if k.strip()]
    fetch = 0
    for ad in ads:
        matched = find_matched_keywords(ad.get("title") or "", keywords)
        if not matched and fetch < max_fetch:
            desc = get_post_description(ad["token"])
            time.sleep(0.5)
            fetch += 1
            matched = find_matched_keywords(desc, keywords)
        ad["matched_keywords"] = matched
        ad["has_keyword"] = bool(matched)
    ads.sort(key=lambda x: (not x.get("has_keyword", False), -(x.get("value_score") or 0)))
    return ads


# ====================== امتیازدهی سخت‌گیرانه ======================
def mobile_status_score(status_text: str) -> float:
    if not status_text:
        return 1.5
    s = status_text.lower()
    if "نو" in s and "در حد" not in s:
        return 4.5
    if "در حد نو" in s:
        return 3.5
    if "کارکرده" in s:
        return 1.8
    if "تعمیر" in s or "نیاز" in s:
        return 0.4
    return 1.8


def mobile_storage_score(title: str) -> float:
    t = (title or "").lower()
    if any(x in t for x in ["1tb", "1024"]):
        return 3.5
    if "512" in t:
        return 3.0
    if "256" in t:
        return 2.5
    if "128" in t:
        return 2.0
    if "64" in t:
        return 1.2
    return 0.7


def mobile_ram_score(title: str) -> float:
    t = (title or "").lower()
    if any(x in t for x in ["16gb", "18gb", "12gb"]):
        return 3.0
    if "8gb" in t or "۸ گیگ" in t or "8 گیگ" in t:
        return 2.5
    if "6gb" in t or "۶ گیگ" in t or "6 گیگ" in t:
        return 2.0
    if "4gb" in t or "۴ گیگ" in t or "4 گیگ" in t:
        return 1.4
    return 0.8


def mobile_value_score(ad: Dict, avg: float) -> float:
    """
    سخت‌گیرانه:
    - فقط قیمت بین 35% تا 90% میانگین
    - وضعیت تعمیر حذف
    - کیفیت پایه ضعیف حذف
    """
    price = ad.get("price_num")
    if not price or not avg or avg <= 0:
        return 0
    if price < avg * 0.35 or price > avg * 0.90:
        return 0

    status_s = mobile_status_score(ad.get("status", ""))
    if status_s < 1.8:
        return 0

    storage_s = mobile_storage_score(ad.get("title", ""))
    ram_s = mobile_ram_score(ad.get("title", ""))
    quality = status_s + storage_s + ram_s
    if quality < 5.5:
        return 0

    discount = (avg - price) / avg
    score = quality + discount * 12
    return round(score, 2)


def car_body_score(title: str, status: str = "") -> float:
    text = ((title or "") + " " + (status or "")).lower()
    if any(x in text for x in ["بدون رنگ", "سالم", "intact", "صفر"]):
        return 4.5
    if any(x in text for x in ["لکه", "خش", "scratch"]):
        return 3.0
    if any(x in text for x in ["رنگ", "paint"]):
        return 1.8
    if any(x in text for x in ["تصادف", "accident"]):
        return 0.8
    return 2.5


def car_motor_score(title: str) -> float:
    t = (title or "").lower()
    if any(x in t for x in ["موتور سالم", "healthy"]):
        return 3.0
    if any(x in t for x in ["تعویض موتور", "replaced"]):
        return 1.5
    if any(x in t for x in ["نیاز به تعمیر", "needs-repair"]):
        return 0.5
    return 2.0


def car_value_score(ad: Dict, avg: float) -> float:
    price = ad.get("price_num")
    if not price or not avg or avg <= 0:
        return 0
    if price < avg * 0.35 or price > avg * 0.90:
        return 0
    body = car_body_score(ad.get("title", ""), ad.get("status", ""))
    motor = car_motor_score(ad.get("title", ""))
    if body < 2.0:
        return 0
    quality = body + motor
    if quality < 4.0:
        return 0
    discount = (avg - price) / avg
    return round(quality * 1.4 + discount * 12, 2)


# ====================== API دیوار ======================
def search_divar(payload: Dict) -> Dict:
    try:
        r = requests.post(
            "https://api.divar.ir/v8/postlist/w/search",
            headers=HEADERS,
            json=payload,
            timeout=25,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("search error:", e)
        return {}


def extract_ads(data: Dict) -> List[Dict]:
    ads = []
    for w in data.get("list_widgets", []):
        if w.get("widget_type") != "POST_ROW":
            continue
        p = w.get("data", {})
        token = p.get("token")
        if not token:
            continue
        price_str = p.get("middle_description_text")
        ads.append(
            {
                "token": token,
                "title": p.get("title"),
                "price": price_str,
                "price_num": parse_price(price_str),
                "status": p.get("top_description_text"),
                "red_text": p.get("red_text") or "",
                "image_url": p.get("image_url"),
                "is_nardeban": "نردبان" in (p.get("red_text") or ""),
                "is_shop": "فروشگاه" in (p.get("red_text") or ""),
                "link": f"https://divar.ir/v/{token}",
            }
        )
    return ads


def build_mobile_payload(
    city_ids,
    brand_models,
    min_price="1000000",
    max_price="900000000",
    recent_ads="1d",
    sort="sort_date",
    has_photo=True,
    has_installment=False,
    business_type="ALL",
    status=None,
    internal_storage=None,
    ram_memory=None,
    sim_card_slot=None,
    base_color=None,
):
    status = status or ["ALL_POSSIBLE_OPTIONS"]
    internal_storage = internal_storage or ["ALL_POSSIBLE_OPTIONS"]
    ram_memory = ram_memory or ["ALL_POSSIBLE_OPTIONS"]
    sim_card_slot = sim_card_slot or ["ALL_POSSIBLE_OPTIONS"]
    base_color = base_color or ["ALL_POSSIBLE_OPTIONS"]
    if not brand_models:
        brand_models = [m for lst in MOBILE_MODELS.values() for m in lst]

    form = {
        "brand_model": {"repeated_string": {"value": brand_models}},
        "has_installment_sale": {"boolean": {"value": has_installment}},
        "has-photo": {"boolean": {"value": has_photo}},
        "originality": {"str": {"value": "original"}},
        "price": {"number_range": {"minimum": str(min_price), "maximum": str(max_price)}},
        "recent_ads": {"str": {"value": recent_ads}},
        "category": {"str": {"value": "mobile-phones"}},
        "status": {"repeated_string": {"value": status}},
        "internal_storage": {"repeated_string": {"value": internal_storage}},
        "ram_memory": {"repeated_string": {"value": ram_memory}},
        "sim_card_slot": {"repeated_string": {"value": sim_card_slot}},
        "base_color": {"repeated_string": {"value": base_color}},
    }
    if business_type == "personal":
        form["goods-business-type"] = {"repeated_string": {"value": ["personal"]}}
    elif business_type == "marketplace":
        form["goods-business-type"] = {"repeated_string": {"value": ["marketplace"]}}
    else:
        form["goods-business-type"] = {"repeated_string": {"value": ["ALL_POSSIBLE_OPTIONS"]}}

    return {
        "city_ids": city_ids,
        "source_view": "FILTER",
        "disable_recommendation": False,
        "map_state": {"camera_info": {"bbox": {}}},
        "search_data": {
            "form_data": {"data": form},
            "server_payload": {
                "@type": "type.googleapis.com/widgets.SearchData.ServerPayload",
                "additional_form_data": {"data": {"sort": {"str": {"value": sort}}}},
            },
        },
        "previous_place_ids": [],
    }


def build_car_payload(
    city_ids,
    brand_models,
    min_price="100000000",
    max_price="5000000000",
    recent_ads="1d",
    sort="sort_date",
    has_photo=True,
    has_installment=False,
    has_video=False,
    year_min="1390",
    year_max="1404",
    usage_min="0",
    usage_max="300000",
    body_status=None,
    chassis_status=None,
    motor_status=None,
    gearbox=None,
    fuel_type=None,
    color=None,
    origin=None,
):
    if not brand_models:
        brand_models = [m for lst in CAR_MODELS.values() for m in lst]
    body_status = body_status or ["ALL_POSSIBLE_OPTIONS"]
    chassis_list = chassis_status or []
    chassis_val = chassis_list[0] if chassis_list else "both-healthy"
    motor_status = motor_status or ["ALL_POSSIBLE_OPTIONS"]
    gearbox = gearbox or ["ALL_POSSIBLE_OPTIONS"]
    fuel_type = fuel_type or ["ALL_POSSIBLE_OPTIONS"]
    color = color or ["ALL_POSSIBLE_OPTIONS"]
    origin = origin or ["ALL_POSSIBLE_OPTIONS"]
    motor_val = motor_status[0] if motor_status and motor_status[0] != "ALL_POSSIBLE_OPTIONS" else "healthy"
    gear_val = gearbox[0] if gearbox and gearbox[0] != "ALL_POSSIBLE_OPTIONS" else "manual"

    form = {
        "brand_model": {"repeated_string": {"value": brand_models}},
        "body_status": {"repeated_string": {"value": body_status}},
        "brand_model_manufacturer_origin": {"repeated_string": {"value": origin}},
        "chassis_status": {"str": {"value": chassis_val}},
        "color": {"repeated_string": {"value": color}},
        "exchange": {"str": {"value": "exclude-exchanges"}},
        "fuel_type": {"repeated_string": {"value": fuel_type}},
        "gearbox": {"str": {"value": gear_val}},
        "has_installment_sale": {"boolean": {"value": has_installment}},
        "has-photo": {"boolean": {"value": has_photo}},
        "has-video": {"boolean": {"value": has_video}},
        "motor_status": {"str": {"value": motor_val}},
        "price": {"number_range": {"minimum": str(min_price), "maximum": str(max_price)}},
        "production-year": {"number_range": {"minimum": str(year_min), "maximum": str(year_max)}},
        "recent_ads": {"str": {"value": recent_ads}},
        "third_party_insurance_deadline": {"number_range": {"minimum": "1", "maximum": "12"}},
        "usage": {"number_range": {"minimum": str(usage_min), "maximum": str(usage_max)}},
        "category": {"str": {"value": "light"}},
    }
    return {
        "city_ids": city_ids,
        "source_view": "FILTER",
        "disable_recommendation": False,
        "map_state": {"camera_info": {"bbox": {}}},
        "search_data": {
            "form_data": {"data": form},
            "server_payload": {
                "@type": "type.googleapis.com/widgets.SearchData.ServerPayload",
                "additional_form_data": {"data": {"sort": {"str": {"value": sort}}}},
            },
        },
        "previous_place_ids": [],
    }


def clean_avg(prices: List[int]) -> float:
    if not prices:
        return 0
    temp = sum(prices) / len(prices)
    clean = [p for p in prices if p >= temp * 0.30] or prices
    return sum(clean) / len(clean)


def finalize_ads(ads: List[Dict], keywords: List[str], negative_keywords: List[str]) -> List[Dict]:
    ads = filter_negative_keywords(ads, negative_keywords)
    ads = enrich_ads_with_keywords(ads, keywords)
    return ads


# ====================== منطق جستجو ======================
def run_search_logic(data: dict) -> dict:
    category = data.get("category", "mobile")
    city_ids = [data.get("city", "5")]
    recent_ads = data.get("recent_ads", "1d")
    selected_models = data.get("models") or []
    smart_search = data.get("smart_search", False)
    smart_avg = data.get("smart_avg", False)
    smart_days = int(data.get("smart_days", 3) or 3)
    keywords = [k.strip() for k in (data.get("keywords") or "").replace("،", ",").split(",") if k.strip()]
    negative_keywords = [k.strip() for k in (data.get("negative_keywords") or "").replace("،", ",").split(",") if k.strip()]
    try:
        min_smart_score = float(data.get("min_smart_score") or 10)
    except Exception:
        min_smart_score = 10.0

    if smart_search or smart_avg:
        if smart_days <= 1:
            recent_ads = "1d"
        elif smart_days <= 2:
            recent_ads = "2d"
        else:
            recent_ads = f"{smart_days}d"

    models_dict = MOBILE_MODELS if category == "mobile" else CAR_MODELS
    models_to_search = selected_models if selected_models else [m for lst in models_dict.values() for m in lst]

    seen = set()
    all_ads = []

    # ---------- جستجوی هوشمند ----------
    if smart_search:
        model_info = {}
        for model in models_to_search:
            if category == "mobile":
                payload = build_mobile_payload(
                    city_ids,
                    [model],
                    recent_ads=recent_ads,
                    has_photo=True,
                    has_installment=False,
                    business_type=data.get("business_type", "ALL"),
                )
                score_fn = mobile_value_score
            else:
                payload = build_car_payload(
                    city_ids,
                    [model],
                    recent_ads=recent_ads,
                    has_photo=True,
                    has_installment=False,
                )
                score_fn = car_value_score

            ads = [a for a in extract_ads(search_divar(payload)) if is_model_match(a.get("title", ""), model)]
            prices = [a["price_num"] for a in ads if a.get("price_num")]
            if not prices:
                time.sleep(0.8)
                continue

            avg = clean_avg(prices)
            scored = []
            for ad in ads:
                if not ad.get("price_num") or ad["token"] in seen:
                    continue
                sc = score_fn(ad, avg)
                if sc >= min_smart_score:
                    ad["value_score"] = sc
                    ad["model_avg"] = int(avg)
                    scored.append(ad)
                    seen.add(ad["token"])

            scored.sort(key=lambda x: x["value_score"], reverse=True)
            best = scored[:8]
            if best:
                model_info[model] = {"avg": int(avg), "count": len(best)}
                all_ads.extend(best)
            time.sleep(0.9)

        all_ads = finalize_ads(all_ads, keywords, negative_keywords)
        all_ads.sort(key=lambda x: (not x.get("has_keyword", False), -(x.get("value_score") or 0)))
        return {
            "success": True,
            "count": len(all_ads),
            "ads": all_ads,
            "smart_search_enabled": True,
            "smart_avg_enabled": False,
            "model_info": model_info,
            "min_smart_score": min_smart_score,
        }

    # ---------- میانگین قیمت هوشمند ----------
    elif smart_avg:
        model_averages = {}
        for model in models_to_search:
            if category == "mobile":
                payload = build_mobile_payload(
                    city_ids,
                    [model],
                    recent_ads=recent_ads,
                    has_photo=data.get("has_photo", True),
                    has_installment=data.get("has_installment", False),
                    business_type=data.get("business_type", "ALL"),
                    min_price=str(data.get("min_price", "1000000")),
                    max_price=str(data.get("max_price", "900000000")),
                    sort=data.get("sort", "sort_date"),
                    status=data.get("status") or ["ALL_POSSIBLE_OPTIONS"],
                    internal_storage=data.get("internal_storage") or ["ALL_POSSIBLE_OPTIONS"],
                    ram_memory=data.get("ram_memory") or ["ALL_POSSIBLE_OPTIONS"],
                    sim_card_slot=data.get("sim_card_slot") or ["ALL_POSSIBLE_OPTIONS"],
                    base_color=data.get("base_color") or ["ALL_POSSIBLE_OPTIONS"],
                )
            else:
                payload = build_car_payload(
                    city_ids,
                    [model],
                    recent_ads=recent_ads,
                    has_photo=data.get("has_photo", True),
                    has_installment=data.get("has_installment", False),
                    has_video=data.get("has_video", False),
                    min_price=str(data.get("min_price", "100000000")),
                    max_price=str(data.get("max_price", "5000000000")),
                    year_min=str(data.get("year_min", "1390")),
                    year_max=str(data.get("year_max", "1404")),
                    usage_min=str(data.get("usage_min", "0")),
                    usage_max=str(data.get("usage_max", "300000")),
                    body_status=data.get("body_status") or ["ALL_POSSIBLE_OPTIONS"],
                    chassis_status=data.get("chassis_status"),
                    motor_status=data.get("motor_status") or ["ALL_POSSIBLE_OPTIONS"],
                    gearbox=data.get("gearbox") or ["ALL_POSSIBLE_OPTIONS"],
                    fuel_type=data.get("fuel_type") or ["ALL_POSSIBLE_OPTIONS"],
                    color=data.get("color") or ["ALL_POSSIBLE_OPTIONS"],
                    origin=data.get("origin") or ["ALL_POSSIBLE_OPTIONS"],
                    sort=data.get("sort", "sort_date"),
                )

            ads = [a for a in extract_ads(search_divar(payload)) if is_model_match(a.get("title", ""), model)]
            prices = [a["price_num"] for a in ads if a.get("price_num")]
            if not prices:
                time.sleep(0.8)
                continue
            avg = clean_avg(prices)
            model_averages[model] = int(avg)
            for ad in ads:
                if ad.get("price_num") and ad["token"] not in seen and (avg * 0.3) <= ad["price_num"] < avg:
                    all_ads.append(ad)
                    seen.add(ad["token"])
            time.sleep(0.9)

        all_ads = finalize_ads(all_ads, keywords, negative_keywords)
        return {
            "success": True,
            "count": len(all_ads),
            "ads": all_ads,
            "smart_search_enabled": False,
            "smart_avg_enabled": True,
            "model_averages": model_averages,
        }

    # ---------- حالت عادی ----------
    else:
        for model in models_to_search:
            if category == "mobile":
                payload = build_mobile_payload(
                    city_ids,
                    [model],
                    recent_ads=recent_ads,
                    has_photo=data.get("has_photo", True),
                    has_installment=data.get("has_installment", False),
                    business_type=data.get("business_type", "ALL"),
                    min_price=str(data.get("min_price", "1000000")),
                    max_price=str(data.get("max_price", "900000000")),
                    sort=data.get("sort", "sort_date"),
                    status=data.get("status") or ["ALL_POSSIBLE_OPTIONS"],
                    internal_storage=data.get("internal_storage") or ["ALL_POSSIBLE_OPTIONS"],
                    ram_memory=data.get("ram_memory") or ["ALL_POSSIBLE_OPTIONS"],
                    sim_card_slot=data.get("sim_card_slot") or ["ALL_POSSIBLE_OPTIONS"],
                    base_color=data.get("base_color") or ["ALL_POSSIBLE_OPTIONS"],
                )
            else:
                payload = build_car_payload(
                    city_ids,
                    [model],
                    recent_ads=recent_ads,
                    has_photo=data.get("has_photo", True),
                    has_installment=data.get("has_installment", False),
                    has_video=data.get("has_video", False),
                    min_price=str(data.get("min_price", "100000000")),
                    max_price=str(data.get("max_price", "5000000000")),
                    year_min=str(data.get("year_min", "1390")),
                    year_max=str(data.get("year_max", "1404")),
                    usage_min=str(data.get("usage_min", "0")),
                    usage_max=str(data.get("usage_max", "300000")),
                    body_status=data.get("body_status") or ["ALL_POSSIBLE_OPTIONS"],
                    chassis_status=data.get("chassis_status"),
                    motor_status=data.get("motor_status") or ["ALL_POSSIBLE_OPTIONS"],
                    gearbox=data.get("gearbox") or ["ALL_POSSIBLE_OPTIONS"],
                    fuel_type=data.get("fuel_type") or ["ALL_POSSIBLE_OPTIONS"],
                    color=data.get("color") or ["ALL_POSSIBLE_OPTIONS"],
                    origin=data.get("origin") or ["ALL_POSSIBLE_OPTIONS"],
                    sort=data.get("sort", "sort_date"),
                )

            ads = [a for a in extract_ads(search_divar(payload)) if is_model_match(a.get("title", ""), model)]
            for ad in ads:
                if ad["token"] not in seen:
                    all_ads.append(ad)
                    seen.add(ad["token"])
            time.sleep(0.8)

        all_ads = finalize_ads(all_ads, keywords, negative_keywords)
        return {
            "success": True,
            "count": len(all_ads),
            "ads": all_ads,
            "smart_search_enabled": False,
            "smart_avg_enabled": False,
        }


# ====================== نوتیف ======================
def send_email(subject: str, body: str):
    if not NOTIFY_EMAIL or not SMTP_USER:
        print("Email not configured")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = NOTIFY_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, int(SMTP_PORT), timeout=20)
        else:
            server = smtplib.SMTP(SMTP_HOST, int(SMTP_PORT), timeout=20)
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())
        server.quit()
        print("Email sent")
    except Exception as e:
        print("Email error:", e)


def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print("Telegram error:", e)


def notify(text: str, subject: str = "آگهی جدید دیوار"):
    clean = text.replace("<b>", "").replace("</b>", "").replace("<br>", "\n")
    send_email(subject, clean)
    send_telegram(text)


# ====================== Routes ======================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == LOGIN_USER and password == LOGIN_PASS:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "نام کاربری یا رمز اشتباه است"
    if session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html", mobile_models=MOBILE_MODELS, car_models=CAR_MODELS)


@app.route("/search", methods=["POST"])
@api_login_required
def search():
    data = request.json or {}
    return jsonify(run_search_logic(data))


@app.route("/api/monitors", methods=["GET"])
@api_login_required
def list_monitors():
    conn = get_db()
    rows = conn.execute("SELECT * FROM monitors ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/monitors", methods=["POST"])
@api_login_required
def create_monitor():
    data = request.json or {}
    name = data.get("name") or "مانیتور بدون نام"
    category = data.get("category", "mobile")
    settings = data.get("settings") or {}
    track_price = 1 if data.get("track_price") else 0
    conn = get_db()
    conn.execute(
        "INSERT INTO monitors (name, category, settings_json, is_active, track_price, created_at) VALUES (?,?,?,?,?,?)",
        (name, category, json.dumps(settings, ensure_ascii=False), 1, track_price, datetime.now().isoformat()),
    )
    conn.commit()
    mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({"success": True, "id": mid})


@app.route("/api/monitors/<int:mid>/toggle", methods=["POST"])
@api_login_required
def toggle_monitor(mid):
    conn = get_db()
    row = conn.execute("SELECT is_active FROM monitors WHERE id=?", (mid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False}), 404
    new_val = 0 if row["is_active"] else 1
    conn.execute("UPDATE monitors SET is_active=? WHERE id=?", (new_val, mid))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "is_active": new_val})


@app.route("/api/monitors/<int:mid>", methods=["DELETE"])
@api_login_required
def delete_monitor(mid):
    conn = get_db()
    conn.execute("DELETE FROM monitors WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/history")
@api_login_required
def history():
    limit = int(request.args.get("limit", 100))
    conn = get_db()
    rows = conn.execute("SELECT * FROM history ORDER BY found_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/test-telegram", methods=["POST"])
@api_login_required
def test_telegram():
    send_telegram("✅ تست نوتیفیکیشن دیوار مانیتور")
    return jsonify({"success": True})


@app.route("/api/test-email", methods=["POST"])
@api_login_required
def test_email():
    notify("این یک پیام تست از مانیتور دیوار است.", subject="تست نوتیف دیوار")
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)