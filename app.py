from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, as_completed
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import re
import time
import sqlite3
import json
import smtplib
import threading
import statistics
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
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    TRIAL_DAYS,
    SEARCH_COOLDOWN_SECONDS,
    MAX_PARALLEL_DIVAR_REQUESTS,
    SEARCH_RESULT_PAGES,
)

app = Flask(__name__)
app.secret_key = "divar-monitor-secret-key-change-this"

MAX_WORKERS = max(6, MAX_PARALLEL_DIVAR_REQUESTS * 2)
SEARCH_SEMAPHORE = threading.Semaphore(MAX_PARALLEL_DIVAR_REQUESTS)

DESC_CACHE: Dict[str, tuple] = {}
DESC_CACHE_LOCK = threading.Lock()
DESC_CACHE_TTL = 600

LAST_SEARCH: Dict[int, float] = {}
LAST_SEARCH_LOCK = threading.Lock()

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
        "Peugeot 407", "Peugeot 508", "Peugeot Pars", "Peugeot Roa Petrol", "Peugeot Roa Bifuel",
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
    "other": [
        "Saipa 421P","Saipa 441P","Saipa Arya","Saipa Atlas E-normal","Saipa Atlas E Plus","Saipa Atlas G",
        "Saipa Atlas GL","Saipa Atlas L","Saipa Atlas S","Saipa Sahand E","Saipa Sahand G","Saipa Sahand G CNG",
        "Saipa Sahand S","Saipa Karvan Saipa","PARS KHODRO P90","Pride 111","Pride 131","Pride 132","Pride 141",
        "Pride Automatic","Pride Station","Pride Sedan","Pride Pickup Plus","Pride Pickup 151 Bi-fuel",
        "Pride Pickup 151 GX","Pride Pickup 151 SE","Pride Hatchback","Pride Saba GLXI","Peugeot 2008",
        "Peugeot 204","Peugeot 205","Peugeot 206","Peugeot 207i","Peugeot 301","Peugeot 304","Peugeot 306",
        "Peugeot 307","Peugeot 308","Peugeot 403","Peugeot 404","Peugeot 405","Peugeot 406","Peugeot 407",
        "Peugeot 504","Peugeot 505","Peugeot 508","Peugeot 605","Peugeot 607","Peugeot 806","Peugeot RD",
        "Peugeot RDI","Peugeot Partner","Peugeot Pars","Peugeot Limousine","Peugeot Roa Petrol",
        "Peugeot Roa Bi-fuel","Peugeot Roa Sal Bi-fuel","Peugeot RCZ","Paykan Bi-fuel(CNG)","Paykan Bi-fuel(LPG)",
        "Paykan Petrol","Paykan Pickup Petrol","Paykan Pickup CNG","Tara Automatic","Tara Manual","Tara V3",
        "Tara V1 plus","Tara v4","Tiba Hatchback","Tiba Sedan Plus","Tiba Sedan EX-normal","Tiba Sedan EX Bi-fuel",
        "Tiba Sedan LX-normal","Tiba Sedan LX Bi-fuel","Tiba Sedan SX-normal","Tiba Sedan SX Bi-fuel",
        "Dena plus turbo","Dena plus EF7 MT","Dena plus Manual 6 Turbo","Dena plus EF7P 6 Speed Manual",
        "Dena plus 6 Speed Manual","Dena plus 1700cc Automatic","Dena plus Turbo 1","Dena plus Manual 1",
        "Dena plus 1700cc Manual","Dena plus EF7 Automatic Turbo Optional","Dena plus Turbo CVT","Dena basic",
        "Runna Plus P","Runna Plus-normal","Runna Plus TU5P","Runna EL","Saina automatic","Saina manual Plus",
        "Saina manual EX","Saina manual G","Saina manual S","Saina GX","Saina GXL-normal","Saina GXL CNG",
        "Saina S","Samand Sarir","Samand Soren","Samand EL","Samand LX","Samand SE","Samand X7 Bi-fuel",
        "Shahin Plus","Shahin G CVT","Shahin GL"
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


def ensure_admin(conn):
    row = conn.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, is_active, plan, subscription_expires_at, max_monitors, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD), "admin", 1, "vip", None, 9999, datetime.now().isoformat()),
        )
        conn.commit()
        print(f"[INIT] Admin account created -> username: {ADMIN_USERNAME} password: {ADMIN_PASSWORD} (CHANGE THIS)")


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            plan TEXT DEFAULT 'free',
            subscription_expires_at TEXT,
            max_monitors INTEGER DEFAULT 1,
            telegram_chat_id TEXT,
            notify_email TEXT,
            created_at TEXT,
            last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS monitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
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
    # migrations
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(monitors)").fetchall()]
        if "track_price" not in cols:
            conn.execute("ALTER TABLE monitors ADD COLUMN track_price INTEGER DEFAULT 0")
        if "user_id" not in cols:
            conn.execute("ALTER TABLE monitors ADD COLUMN user_id INTEGER")

        cols2 = [r[1] for r in conn.execute("PRAGMA table_info(seen_ads)").fetchall()]
        if "price_num" not in cols2:
            conn.execute("ALTER TABLE seen_ads ADD COLUMN price_num INTEGER")
        if "last_checked" not in cols2:
            conn.execute("ALTER TABLE seen_ads ADD COLUMN last_checked TEXT")

        cols3 = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "telegram_chat_id" not in cols3:
            conn.execute("ALTER TABLE users ADD COLUMN telegram_chat_id TEXT")
        if "notify_email" not in cols3:
            conn.execute("ALTER TABLE users ADD COLUMN notify_email TEXT")
        if "last_login" not in cols3:
            conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
    except Exception as e:
        print("db migrate:", e)

    conn.commit()
    ensure_admin(conn)

    # assign orphan monitors (created before user system) to admin
    try:
        admin_row = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
        if admin_row:
            conn.execute("UPDATE monitors SET user_id=? WHERE user_id IS NULL", (admin_row["id"],))
            conn.commit()
    except Exception as e:
        print("orphan monitor assign error:", e)

    conn.close()


init_db()

# ====================== auth helpers ======================
def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row


def is_sub_active(user) -> bool:
    if not user:
        return False
    if user["role"] == "admin":
        return True
    if not user["is_active"]:
        return False
    exp = user["subscription_expires_at"]
    if not exp:
        return False
    try:
        return datetime.fromisoformat(exp) > datetime.now()
    except Exception:
        return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or not user["is_active"]:
            session.clear()
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or not user["is_active"]:
            return jsonify({"success": False, "error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user["role"] != "admin":
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def api_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user["role"] != "admin":
            return jsonify({"success": False, "error": "forbidden"}), 403
        return f(*args, **kwargs)
    return decorated


def subscription_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not is_sub_active(user):
            return jsonify({
                "success": False,
                "error": "subscription_expired",
                "message": "اشتراک شما فعال نیست یا منقضی شده. برای ادامه با پشتیبانی تماس بگیرید."
            }), 402
        return f(*args, **kwargs)
    return decorated


# ====================== توابع کمکی ======================
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
ASCII_DIGITS = "0123456789"


def normalize_digits(text: str) -> str:
    if not text:
        return text
    trans = {}
    for i, ch in enumerate(PERSIAN_DIGITS):
        trans[ch] = ASCII_DIGITS[i]
    for i, ch in enumerate(ARABIC_DIGITS):
        trans[ch] = ASCII_DIGITS[i]
    return "".join(trans.get(c, c) for c in text)


def parse_price(price_str: str) -> Optional[int]:
    if not price_str:
        return None
    s = normalize_digits(str(price_str)).replace(",", "").replace("٬", "")
    numbers = re.findall(r"\d+", s)
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


def get_post_description_cached(token: str) -> str:
    now = time.time()
    with DESC_CACHE_LOCK:
        cached = DESC_CACHE.get(token)
        if cached and now - cached[1] < DESC_CACHE_TTL:
            return cached[0]
    with SEARCH_SEMAPHORE:
        desc = get_post_description(token)
    with DESC_CACHE_LOCK:
        DESC_CACHE[token] = (desc, now)
    return desc


def find_matched_keywords(text: str, keywords: List[str]) -> List[str]:
    if not text or not keywords:
        return []
    t = normalize_digits(text.lower())
    return [k for k in keywords if normalize_digits(k.lower()) in t]


def has_negative_keyword(text: str, negative_keywords: List[str]) -> bool:
    if not text or not negative_keywords:
        return False
    t = normalize_digits(text.lower())
    return any(normalize_digits(k.lower()) in t for k in negative_keywords if k.strip())


def filter_negative_keywords(ads: List[Dict], negative_keywords: List[str], max_fetch: int = 25) -> List[Dict]:
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
            desc = get_post_description_cached(ad["token"])
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
            desc = get_post_description_cached(ad["token"])
            fetch += 1
            matched = find_matched_keywords(desc, keywords)
        ad["matched_keywords"] = matched
        ad["has_keyword"] = bool(matched)
    ads.sort(key=lambda x: (not x.get("has_keyword", False), -(x.get("value_score") or 0)))
    return ads


# ====================== امتیازدهی ======================
def mobile_status_score(status_text: str) -> float:
    if not status_text:
        return 1.5
    s = status_text.lower()
    if "در حد نو" in s:
        return 3.5
    if "نو" in s:
        return 4.5
    if "کارکرده" in s:
        return 1.8
    if "تعمیر" in s or "نیاز" in s:
        return 0.4
    return 1.8


def mobile_storage_score(title: str) -> float:
    t = normalize_digits((title or "").lower())
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
    t = normalize_digits((title or "").lower())
    if any(x in t for x in ["16gb", "18gb", "12gb"]):
        return 3.0
    if "8gb" in t or "8 گیگ" in t:
        return 2.5
    if "6gb" in t or "6 گیگ" in t:
        return 2.0
    if "4gb" in t or "4 گیگ" in t:
        return 1.4
    return 0.8


def mobile_value_score(ad: Dict, avg: float) -> float:
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
    return round(quality + discount * 12, 2)


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


# ====================== Divar API ======================
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


def search_divar_legacy(city_id: str, category_slug: str, page: int = 1, last_post_date: Optional[int] = None) -> Dict:
    """Fallback used by the broad default search.

    The modern widget endpoint is best for filtered queries, but Divar's normal
    category page can return many pages through this older public endpoint.
    Response is converted to the same POST_ROW-like shape used by extract_ads.
    """
    payload = {"page": page}
    if last_post_date:
        payload["last-post-date"] = last_post_date
    try:
        r = requests.post(
            f"https://api.divar.ir/v8/search/{city_id}/{category_slug}",
            headers=HEADERS,
            json=payload,
            timeout=25,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("legacy search error:", e)
        return {}


def normalize_legacy_search_data(data: Dict) -> Dict:
    widgets = []
    for item in (data.get("web_widgets") or {}).get("post_list", []) or []:
        widget_data = item.get("data") or {}
        payload = (((widget_data.get("action") or {}).get("payload")) or {})
        token = payload.get("token")
        if not token:
            continue
        # Keep enough fields for extract_ads() while preserving the raw item for fallback.
        widgets.append({
            "widget_type": "POST_ROW",
            "data": {
                "token": token,
                "title": widget_data.get("title"),
                "middle_description_text": widget_data.get("middle_description_text")
                    or item.get("description")
                    or "\n".join(widget_data.get("desc_lines") or []),
                "top_description_text": widget_data.get("top_description_text")
                    or item.get("normal_text")
                    or item.get("business_text"),
                "red_text": item.get("red_text") or widget_data.get("red_text") or "",
                "image_url": item.get("image") or widget_data.get("image_url"),
            },
        })
    return {"list_widgets": widgets}


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
        red_text = p.get("red_text") or ""
        ads.append({
            "token": token,
            "title": p.get("title"),
            "price": price_str,
            "price_num": parse_price(price_str),
            "status": p.get("top_description_text"),
            "red_text": red_text,
            "image_url": p.get("image_url"),
            "is_nardeban": "نردبان" in red_text,
            "is_shop": "فروشگاه" in red_text,
            "link": f"https://divar.ir/v/{token}",
        })
    return ads


def extract_place_ids(data: Dict) -> List[str]:
    """Collect Divar's internal pagination tokens from a search response."""
    place_ids = []
    for key in ("last_post_date", "next_cursor", "cursor"):
        value = data.get(key)
        if value is not None:
            place_ids.append(str(value))

    for w in data.get("list_widgets", []) or []:
        if w.get("widget_type") != "POST_ROW":
            continue
        p = w.get("data", {})
        for key in ("place_id", "id", "token"):
            value = p.get(key)
            if value:
                place_ids.append(str(value))
    # Keep order but remove duplicates.
    return list(dict.fromkeys(place_ids))


def build_mobile_payload(
    city_ids, brand_models=None, min_price=None, max_price=None,
    recent_ads=None, sort="sort_date", has_photo=None, has_installment=None,
    business_type="ALL", status=None, internal_storage=None, ram_memory=None,
    sim_card_slot=None, base_color=None,
):
    form = {
        "category": {"str": {"value": "mobile-phones"}},
        "status": {"repeated_string": {"value": status or ["ALL_POSSIBLE_OPTIONS"]}},
        "internal_storage": {"repeated_string": {"value": internal_storage or ["ALL_POSSIBLE_OPTIONS"]}},
        "ram_memory": {"repeated_string": {"value": ram_memory or ["ALL_POSSIBLE_OPTIONS"]}},
        "sim_card_slot": {"repeated_string": {"value": sim_card_slot or ["ALL_POSSIBLE_OPTIONS"]}},
        "base_color": {"repeated_string": {"value": base_color or ["ALL_POSSIBLE_OPTIONS"]}},
    }

    if recent_ads not in (None, ""):
        form["recent_ads"] = {"str": {"value": recent_ads}}
    if has_photo is not None:
        form["has-photo"] = {"boolean": {"value": has_photo}}
    if has_installment is not None:
        form["has_installment_sale"] = {"boolean": {"value": has_installment}}

    # brand_models=None means "do not restrict to any model"; an explicit list means filter.
    if brand_models is not None:
        form["brand_model"] = {"repeated_string": {"value": brand_models}}

    price_range = {}
    if min_price not in (None, ""):
        price_range["minimum"] = str(min_price)
    if max_price not in (None, ""):
        price_range["maximum"] = str(max_price)
    if price_range:
        form["price"] = {"number_range": price_range}

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
    city_ids, brand_models=None, min_price=None, max_price=None,
    recent_ads=None, sort="sort_date", has_photo=None, has_installment=None,
    has_video=None, year_min=None, year_max=None, usage_min=None, usage_max=None,
    body_status=None, chassis_status=None, motor_status=None, gearbox=None,
    fuel_type=None, color=None, origin=None, insurance_min=None, insurance_max=None,
):
    form = {
        "category": {"str": {"value": "light"}},
    }

    if recent_ads not in (None, ""):
        form["recent_ads"] = {"str": {"value": recent_ads}}
    if has_photo is not None:
        form["has-photo"] = {"boolean": {"value": has_photo}}
    if has_installment is not None:
        form["has_installment_sale"] = {"boolean": {"value": has_installment}}
    if has_video is not None:
        form["has-video"] = {"boolean": {"value": has_video}}

    if body_status:
        form["body_status"] = {"repeated_string": {"value": body_status}}
    if origin:
        form["brand_model_manufacturer_origin"] = {"repeated_string": {"value": origin}}
    if chassis_status:
        form["chassis_status"] = {"str": {"value": chassis_status[0]}}
    if color:
        form["color"] = {"repeated_string": {"value": color}}
    if fuel_type:
        form["fuel_type"] = {"repeated_string": {"value": fuel_type}}
    if gearbox:
        form["gearbox"] = {"str": {"value": gearbox[0]}}
    if motor_status:
        form["motor_status"] = {"str": {"value": motor_status[0]}}

    if brand_models is not None:
        form["brand_model"] = {"repeated_string": {"value": brand_models}}

    price_range = {}
    if min_price not in (None, ""):
        price_range["minimum"] = str(min_price)
    if max_price not in (None, ""):
        price_range["maximum"] = str(max_price)
    if price_range:
        form["price"] = {"number_range": price_range}

    year_range = {}
    if year_min not in (None, ""):
        year_range["minimum"] = str(year_min)
    if year_max not in (None, ""):
        year_range["maximum"] = str(year_max)
    if year_range:
        form["production-year"] = {"number_range": year_range}

    usage_range = {}
    if usage_min not in (None, ""):
        usage_range["minimum"] = str(usage_min)
    if usage_max not in (None, ""):
        usage_range["maximum"] = str(usage_max)
    if usage_range:
        form["usage"] = {"number_range": usage_range}

    insurance_range = {}
    if insurance_min not in (None, ""):
        insurance_range["minimum"] = str(insurance_min)
    if insurance_max not in (None, ""):
        insurance_range["maximum"] = str(insurance_max)
    if insurance_range:
        form["third_party_insurance_deadline"] = {"number_range": insurance_range}

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
    if len(prices) == 1:
        return prices[0]
    med = statistics.median(prices)
    if med <= 0:
        return sum(prices) / len(prices)
    filtered = [p for p in prices if med * 0.25 <= p <= med * 3.5]
    if not filtered:
        filtered = prices
    return sum(filtered) / len(filtered)


def finalize_ads(ads: List[Dict], keywords: List[str], negative_keywords: List[str]) -> List[Dict]:
    ads = filter_negative_keywords(ads, negative_keywords)
    ads = enrich_ads_with_keywords(ads, keywords)
    return ads


# ====================== worker functions (parallel per-model) ======================
def fetch_divar_pages(payload: Dict, max_pages: int = 1) -> List[Dict]:
    """Fetch multiple pages from the modern Divar widget endpoint.

    Divar's public UI paginates results; one request normally returns only one
    page (~20-25 rows). For broad/default searches we therefore request several
    pages and append them, exactly as the website does.
    """
    all_ads = []
    seen_tokens = set()
    previous_place_ids = []
    for page in range(1, max(1, int(max_pages)) + 1):
        page_payload = json.loads(json.dumps(payload, ensure_ascii=False))
        page_payload["page"] = page
        page_payload["previous_place_ids"] = previous_place_ids
        with SEARCH_SEMAPHORE:
            raw = search_divar(page_payload)
        ads = extract_ads(raw)
        if not ads:
            break
        new_count = 0
        for ad in ads:
            token = ad.get("token")
            if token and token not in seen_tokens:
                seen_tokens.add(token)
                all_ads.append(ad)
                new_count += 1
        next_ids = extract_place_ids(raw)
        if next_ids:
            previous_place_ids = next_ids
        # If Divar returns a short/final page or repeats results, stop early.
        if len(ads) < 10 or new_count == 0:
            break
    return all_ads


def fetch_legacy_pages(city_id: str, category_slug: str, max_pages: int) -> List[Dict]:
    """Fetch several pages using Divar's older public category endpoint.

    This endpoint exposes explicit `last_post_date` pagination and is the most
    reliable way to reproduce the normal Divar category listing volume.
    """
    all_ads = []
    seen_tokens = set()
    last_post_date = None
    for page in range(1, max(1, int(max_pages)) + 1):
        with SEARCH_SEMAPHORE:
            raw = search_divar_legacy(city_id, category_slug, page=page, last_post_date=last_post_date)
        ads = extract_ads(normalize_legacy_search_data(raw))
        if not ads:
            break
        last_post_date = raw.get("last_post_date") or last_post_date
        new_count = 0
        for ad in ads:
            if ad["token"] not in seen_tokens:
                seen_tokens.add(ad["token"])
                all_ads.append(ad)
                new_count += 1
        if len(ads) < 10 or new_count == 0:
            break
    return all_ads


def is_broad_unfiltered_search(category: str, recent_ads, data: Dict) -> bool:
    if recent_ads not in (None, ""):
        return False
    for key in ("has_photo", "has_installment", "has_video"):
        if data.get(key):
            return False
    for key in ("min_price", "max_price", "year_min", "year_max", "usage_min", "usage_max"):
        if data.get(key) not in (None, ""):
            return False
    for key in (
        "status", "internal_storage", "ram_memory", "sim_card_slot", "base_color",
        "body_status", "chassis_status", "motor_status", "gearbox", "fuel_type", "color", "origin",
    ):
        if data.get(key):
            return False
    if category == "mobile" and data.get("business_type") not in (None, "", "ALL"):
        return False
    return True


def build_payload_for_model(category: str, model, city_ids, recent_ads: str, data: Dict):
    """Construct a Divar payload.

    Pass model=None for the broad/default category search (like opening Divar's
    mobile or car category without selecting a model). Pass a model string to
    restrict results to that model.
    """
    brand_models = None if model is None else [model]
    if category == "mobile":
        return build_mobile_payload(
            city_ids, brand_models, recent_ads=recent_ads,
            has_photo=True if data.get("has_photo") else None,
            has_installment=True if data.get("has_installment") else None,
            business_type=data.get("business_type", "ALL"),
            min_price=data.get("min_price") or None,
            max_price=data.get("max_price") or None,
            sort=data.get("sort", "sort_date"),
            status=data.get("status") or ["ALL_POSSIBLE_OPTIONS"],
            internal_storage=data.get("internal_storage") or ["ALL_POSSIBLE_OPTIONS"],
            ram_memory=data.get("ram_memory") or ["ALL_POSSIBLE_OPTIONS"],
            sim_card_slot=data.get("sim_card_slot") or ["ALL_POSSIBLE_OPTIONS"],
            base_color=data.get("base_color") or ["ALL_POSSIBLE_OPTIONS"],
        )

    return build_car_payload(
        city_ids, brand_models, recent_ads=recent_ads,
        has_photo=True if data.get("has_photo") else None,
        has_installment=True if data.get("has_installment") else None,
        has_video=True if data.get("has_video") else None,
        min_price=data.get("min_price") or None,
        max_price=data.get("max_price") or None,
        year_min=data.get("year_min") or None,
        year_max=data.get("year_max") or None,
        usage_min=data.get("usage_min") or None,
        usage_max=data.get("usage_max") or None,
        body_status=data.get("body_status") or ["ALL_POSSIBLE_OPTIONS"],
        chassis_status=data.get("chassis_status"),
        motor_status=data.get("motor_status") or ["ALL_POSSIBLE_OPTIONS"],
        gearbox=data.get("gearbox") or ["ALL_POSSIBLE_OPTIONS"],
        fuel_type=data.get("fuel_type") or ["ALL_POSSIBLE_OPTIONS"],
        color=data.get("color") or ["ALL_POSSIBLE_OPTIONS"],
        origin=data.get("origin") or ["ALL_POSSIBLE_OPTIONS"],
        sort=data.get("sort", "sort_date"),
    )


def process_model_smart(model, category, city_ids, recent_ads, business_type, min_smart_score, max_pages=2):
    try:
        smart_data = {
            "business_type": business_type,
        }
        payload = build_payload_for_model(category, model, city_ids, recent_ads, smart_data)
        score_fn = mobile_value_score if category == "mobile" else car_value_score
        ads = [a for a in fetch_divar_pages(payload, max_pages=max_pages)
               if is_model_match(a.get("title", ""), model)]
        prices = [a["price_num"] for a in ads if a.get("price_num")]
        if not prices:
            return model, None, []
        avg = clean_avg(prices)
        scored = []
        for ad in ads:
            if not ad.get("price_num"):
                continue
            sc = score_fn(ad, avg)
            if sc >= min_smart_score:
                ad["value_score"] = sc
                ad["model_avg"] = int(avg)
                scored.append(ad)
        scored.sort(key=lambda x: x["value_score"], reverse=True)
        best = scored[:8]
        if best:
            return model, {"avg": int(avg), "count": len(best)}, best
        return model, None, []
    except Exception as e:
        print(f"smart model error {model}:", e)
        return model, None, []


def process_model_avg(model, category, city_ids, recent_ads, data, max_pages=2):
    try:
        payload = build_payload_for_model(category, model, city_ids, recent_ads, data)
        ads = [a for a in fetch_divar_pages(payload, max_pages=max_pages)
               if is_model_match(a.get("title", ""), model)]
        prices = [a["price_num"] for a in ads if a.get("price_num")]
        if not prices:
            return model, None, []
        avg = clean_avg(prices)
        picked = [a for a in ads if a.get("price_num") and (avg * 0.3) <= a["price_num"] < avg]
        return model, int(avg), picked
    except Exception as e:
        print(f"avg model error {model}:", e)
        return model, None, []


def process_model_normal(model, category, city_ids, recent_ads, data, max_pages=2):
    try:
        payload = build_payload_for_model(category, model, city_ids, recent_ads, data)
        ads = [a for a in fetch_divar_pages(payload, max_pages=max_pages)
               if is_model_match(a.get("title", ""), model)]
        return model, None, ads
    except Exception as e:
        print(f"normal model error {model}:", e)
        return model, None, []


# ====================== منطق جستجو ======================
def run_search_logic(data: dict) -> dict:
    category = data.get("category", "mobile")
    city_id = str(data.get("city", "5") or "5")
    city_ids = [city_id]
    recent_ads = data.get("recent_ads") or None
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

    if smart_search:
        model_info = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [
                ex.submit(process_model_smart, m, category, city_ids, recent_ads,
                          data.get("business_type", "ALL"), min_smart_score, 1)
                for m in models_to_search
            ]
            for fut in as_completed(futures):
                model, info, best = fut.result()
                if info:
                    model_info[model] = info
                for ad in best:
                    if ad["token"] not in seen:
                        seen.add(ad["token"])
                        all_ads.append(ad)

        all_ads = finalize_ads(all_ads, keywords, negative_keywords)
        all_ads.sort(key=lambda x: (not x.get("has_keyword", False), -(x.get("value_score") or 0)))
        return {
            "success": True, "count": len(all_ads), "ads": all_ads,
            "smart_search_enabled": True, "smart_avg_enabled": False,
            "model_info": model_info, "min_smart_score": min_smart_score,
        }

    elif smart_avg:
        model_averages = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [
                ex.submit(process_model_avg, m, category, city_ids, recent_ads, data, 1)
                for m in models_to_search
            ]
            for fut in as_completed(futures):
                model, avg, picked = fut.result()
                if avg is not None:
                    model_averages[model] = avg
                for ad in picked:
                    if ad["token"] not in seen:
                        seen.add(ad["token"])
                        all_ads.append(ad)

        all_ads = finalize_ads(all_ads, keywords, negative_keywords)
        return {
            "success": True, "count": len(all_ads), "ads": all_ads,
            "smart_search_enabled": False, "smart_avg_enabled": True,
            "model_averages": model_averages,
        }

    else:
        # When the user has not selected specific models, behave like Divar's
        # normal category page: one broad paginated query instead of hundreds of
        # tiny per-model calls. That is what returns 100+ listings by default.
        if not selected_models:
            category_slug = "mobile-phones" if category == "mobile" else "light"

            # The completely default case should match Divar's normal category page.
            # The legacy endpoint has stable pagination and best reproduces that volume.
            if is_broad_unfiltered_search(category, recent_ads, data):
                all_ads = fetch_legacy_pages(city_id, category_slug, SEARCH_RESULT_PAGES)
            else:
                payload = build_payload_for_model(
                    category, model=None, city_ids=city_ids, recent_ads=recent_ads, data=data
                )
                all_ads = fetch_divar_pages(payload, max_pages=SEARCH_RESULT_PAGES)

                # Fallback: if the modern widget endpoint does not accept `page`,
                # use Divar's public legacy category endpoint page-by-page. This is
                # the same source that powers the website's normal listing pages.
                if not all_ads:
                    all_ads = fetch_legacy_pages(city_id, category_slug, SEARCH_RESULT_PAGES)
        else:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
                futures = [
                    ex.submit(process_model_normal, m, category, city_ids, recent_ads, data, 2)
                    for m in models_to_search
                ]
                for fut in as_completed(futures):
                    model, _, ads = fut.result()
                    for ad in ads:
                        if ad["token"] not in seen:
                            seen.add(ad["token"])
                            all_ads.append(ad)

        all_ads = finalize_ads(all_ads, keywords, negative_keywords)
        return {
            "success": True, "count": len(all_ads), "ads": all_ads,
            "smart_search_enabled": False, "smart_avg_enabled": False,
        }


# ====================== نوتیف ======================
def send_email(subject: str, body: str, to_email: Optional[str] = None):
    target = to_email or NOTIFY_EMAIL
    if not target or not SMTP_USER:
        print("Email not configured")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = target
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, int(SMTP_PORT), timeout=20)
        else:
            server = smtplib.SMTP(SMTP_HOST, int(SMTP_PORT), timeout=20)
            server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, target, msg.as_string())
        server.quit()
        print("Email sent")
    except Exception as e:
        print("Email error:", e)


def send_telegram(text: str, chat_id: Optional[str] = None):
    target = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": target, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print("Telegram error:", e)


def notify(text: str, subject: str = "آگهی جدید دیوار", telegram_chat_id: Optional[str] = None, email: Optional[str] = None):
    clean = text.replace("<b>", "").replace("</b>", "").replace("<br>", "\n")
    send_email(subject, clean, to_email=email)
    send_telegram(text, chat_id=telegram_chat_id)


# ====================== Auth Routes ======================
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        if len(username) < 3:
            error = "نام کاربری باید حداقل ۳ کاراکتر باشد"
        elif len(password) < 6:
            error = "رمز عبور باید حداقل ۶ کاراکتر باشد"
        elif password != password2:
            error = "رمز عبور و تکرار آن یکسان نیستند"
        else:
            conn = get_db()
            exists = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
            if exists:
                error = "این نام کاربری قبلا ثبت شده است"
                conn.close()
            else:
                trial_end = (datetime.now() + timedelta(days=TRIAL_DAYS)).isoformat()
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, is_active, plan, subscription_expires_at, max_monitors, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (username, generate_password_hash(password), "user", 1, "trial", trial_end, 1, datetime.now().isoformat()),
                )
                conn.commit()
                uid = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]
                conn.close()
                session["user_id"] = uid
                return redirect(url_for("index"))
    if get_current_user():
        return redirect(url_for("index"))
    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            if not user["is_active"]:
                error = "حساب شما غیرفعال شده است"
                conn.close()
            else:
                conn.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.now().isoformat(), user["id"]))
                conn.commit()
                conn.close()
                session["user_id"] = user["id"]
                return redirect(url_for("index"))
        else:
            conn.close()
            error = "نام کاربری یا رمز عبور اشتباه است"
    if get_current_user():
        return redirect(url_for("index"))
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin/login", methods=["GET", "POST"])

def admin_login():
    error = None
    current = get_current_user()
    if current and current["role"] == "admin":
        return redirect(url_for("admin_page"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND role='admin'", (username,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            if not user["is_active"]:
                error = "این حساب مدیر غیرفعال شده است"
                conn.close()
            else:
                conn.execute(
                    "UPDATE users SET last_login=? WHERE id=?",
                    (datetime.now().isoformat(), user["id"]),
                )
                conn.commit()
                conn.close()
                session.clear()
                session["user_id"] = user["id"]
                return redirect(url_for("admin_page"))
        else:
            conn.close()
            error = "نام کاربری یا رمز عبور اشتباه است، یا این حساب دسترسی مدیریت ندارد"

    return render_template("admin_login.html", error=error)


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user = get_current_user()
    msg = None
    if request.method == "POST":
        action = request.form.get("action", "password")
        conn = get_db()
        if action == "password":
            cur = request.form.get("current_password") or ""
            new = request.form.get("new_password") or ""
            if check_password_hash(user["password_hash"], cur) and len(new) >= 6:
                conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), user["id"]))
                conn.commit()
                msg = "رمز عبور با موفقیت تغییر کرد"
            else:
                msg = "رمز فعلی اشتباه است یا رمز جدید خیلی کوتاه است"
        elif action == "notify":
            tg = (request.form.get("telegram_chat_id") or "").strip()
            em = (request.form.get("notify_email") or "").strip()
            conn.execute("UPDATE users SET telegram_chat_id=?, notify_email=? WHERE id=?", (tg or None, em or None, user["id"]))
            conn.commit()
            msg = "تنظیمات اعلان ذخیره شد"
        conn.close()
        user = get_current_user()
    return render_template("account.html", user=user, msg=msg, sub_active=is_sub_active(user))


# ====================== Admin Routes ======================
@app.route("/admin")
@admin_required
def admin_page():
    return render_template("admin.html")


@app.route("/api/admin/users", methods=["GET"])
@api_admin_required
def admin_list_users():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, role, is_active, plan, subscription_expires_at, max_monitors, created_at, last_login FROM users ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/admin/users", methods=["POST"])
@api_admin_required
def admin_create_user():
    data = request.json or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if len(username) < 3 or len(password) < 6:
        return jsonify({"success": False, "error": "invalid"}), 400
    role = data.get("role", "user")
    plan = data.get("plan", "free")
    days = int(data.get("days", 30) or 30)
    max_monitors = int(data.get("max_monitors", 3) or 3)
    expires = None if role == "admin" else (datetime.now() + timedelta(days=days)).isoformat()
    conn = get_db()
    if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        conn.close()
        return jsonify({"success": False, "error": "exists"}), 409
    conn.execute(
        "INSERT INTO users (username, password_hash, role, is_active, plan, subscription_expires_at, max_monitors, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (username, generate_password_hash(password), role, 1, plan, expires, max_monitors, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/admin/users/<int:uid>", methods=["PUT"])
@api_admin_required
def admin_update_user(uid):
    data = request.json or {}
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False}), 404
    plan = data.get("plan", user["plan"])
    is_active = 1 if data.get("is_active", user["is_active"]) else 0
    max_monitors = int(data.get("max_monitors", user["max_monitors"]))
    role = data.get("role", user["role"])
    expires = data.get("subscription_expires_at", user["subscription_expires_at"])
    new_password = data.get("password")
    if new_password and len(new_password) >= 6:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new_password), uid))
    conn.execute(
        "UPDATE users SET plan=?, is_active=?, max_monitors=?, role=?, subscription_expires_at=? WHERE id=?",
        (plan, is_active, max_monitors, role, expires, uid),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/admin/users/<int:uid>/extend", methods=["POST"])
@api_admin_required
def admin_extend_user(uid):
    data = request.json or {}
    days = int(data.get("days", 30) or 30)
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False}), 404
    base = datetime.now()
    if user["subscription_expires_at"]:
        try:
            cur_exp = datetime.fromisoformat(user["subscription_expires_at"])
            if cur_exp > base:
                base = cur_exp
        except Exception:
            pass
    new_exp = (base + timedelta(days=days)).isoformat()
    conn.execute("UPDATE users SET subscription_expires_at=?, is_active=1 WHERE id=?", (new_exp, uid))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "subscription_expires_at": new_exp})


@app.route("/api/admin/users/<int:uid>", methods=["DELETE"])
@api_admin_required
def admin_delete_user(uid):
    conn = get_db()
    conn.execute("DELETE FROM monitors WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM users WHERE id=? AND role != 'admin'", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ====================== Main Routes ======================
@app.route("/")
@login_required
def index():
    user = get_current_user()
    return render_template("index.html", mobile_models=MOBILE_MODELS, car_models=CAR_MODELS,
                            user=user, sub_active=is_sub_active(user))


@app.route("/search", methods=["POST"])
@api_login_required
@subscription_required
def search():
    user = get_current_user()
    now_ts = time.time()
    with LAST_SEARCH_LOCK:
        last = LAST_SEARCH.get(user["id"], 0)
        if now_ts - last < SEARCH_COOLDOWN_SECONDS:
            wait = round(SEARCH_COOLDOWN_SECONDS - (now_ts - last), 1)
            return jsonify({"success": False, "error": "cooldown", "message": f"لطفا {wait} ثانیه صبر کن و دوباره امتحان کن"}), 429
        LAST_SEARCH[user["id"]] = now_ts
    data = request.json or {}
    return jsonify(run_search_logic(data))


@app.route("/api/monitors", methods=["GET"])
@api_login_required
def list_monitors():
    user = get_current_user()
    conn = get_db()
    if user["role"] == "admin":
        rows = conn.execute("SELECT * FROM monitors ORDER BY id DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM monitors WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/monitors", methods=["POST"])
@api_login_required
@subscription_required
def create_monitor():
    user = get_current_user()
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) c FROM monitors WHERE user_id=?", (user["id"],)).fetchone()["c"]
    if user["role"] != "admin" and count >= (user["max_monitors"] or 1):
        conn.close()
        return jsonify({
            "success": False, "error": "limit_reached",
            "message": f"شما فقط مجاز به ساخت {user['max_monitors']} مانیتور هستید."
        }), 403

    data = request.json or {}
    name = data.get("name") or "مانیتور بدون نام"
    category = data.get("category", "mobile")
    settings = data.get("settings") or {}
    track_price = 1 if data.get("track_price") else 0
    conn.execute(
        "INSERT INTO monitors (user_id, name, category, settings_json, is_active, track_price, created_at) VALUES (?,?,?,?,?,?,?)",
        (user["id"], name, category, json.dumps(settings, ensure_ascii=False), 1, track_price, datetime.now().isoformat()),
    )
    conn.commit()
    mid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({"success": True, "id": mid})


def _own_monitor_or_admin(conn, user, mid):
    row = conn.execute("SELECT * FROM monitors WHERE id=?", (mid,)).fetchone()
    if not row:
        return None
    if user["role"] != "admin" and row["user_id"] != user["id"]:
        return None
    return row


@app.route("/api/monitors/<int:mid>/toggle", methods=["POST"])
@api_login_required
def toggle_monitor(mid):
    user = get_current_user()
    conn = get_db()
    row = _own_monitor_or_admin(conn, user, mid)
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
    user = get_current_user()
    conn = get_db()
    row = _own_monitor_or_admin(conn, user, mid)
    if not row:
        conn.close()
        return jsonify({"success": False}), 404
    conn.execute("DELETE FROM monitors WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/history")
@api_login_required
def history():
    user = get_current_user()
    limit = int(request.args.get("limit", 100))
    conn = get_db()
    if user["role"] == "admin":
        rows = conn.execute("SELECT * FROM history ORDER BY found_at DESC LIMIT ?", (limit,)).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT h.* FROM history h
            JOIN monitors m ON m.id = h.monitor_id
            WHERE m.user_id=?
            ORDER BY h.found_at DESC LIMIT ?
            """,
            (user["id"], limit),
        ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/test-telegram", methods=["POST"])
@api_login_required
def test_telegram():
    user = get_current_user()
    send_telegram("✅ تست نوتیفیکیشن دیوار مانیتور", chat_id=user["telegram_chat_id"])
    return jsonify({"success": True})


@app.route("/api/test-email", methods=["POST"])
@api_login_required
def test_email():
    user = get_current_user()
    notify("این یک پیام تست از مانیتور دیوار است.", subject="تست نوتیف دیوار", email=user["notify_email"])
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)