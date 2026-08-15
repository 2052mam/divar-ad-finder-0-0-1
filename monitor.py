#!/usr/bin/env python3
"""
اجرا شود Cron هر ۱۰ دقیقه با:

source /home/qwamjoow/virtualenv/testt.reservira.ir/3.12/bin/activate && \
cd /home/qwamjoow/testt.reservira.ir && \
python monitor.py >> /home/qwamjoow/testt.reservira.ir/monitor.log 2>&1
"""
import json
import time
import requests
from datetime import datetime, timedelta

from app import (
    get_db,
    init_db,
    run_search_logic,
    notify,
    parse_price,
    HEADERS,
)
from config import MAX_NOTIFY_PER_RUN


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def should_check_prices_today(conn) -> bool:
    last = get_meta(conn, "last_price_check")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        return datetime.now() - last_dt >= timedelta(hours=20)
    except Exception:
        return True


def owner_is_eligible(conn, user_id) -> bool:
    """چک می‌کند صاحب مانیتور فعال و مشترک است"""
    if not user_id:
        return True  # legacy monitors without owner - allow (assigned to admin already by init_db)
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user or not user["is_active"]:
        return False
    if user["role"] == "admin":
        return True
    if not user["subscription_expires_at"]:
        return False
    try:
        return datetime.fromisoformat(user["subscription_expires_at"]) >= datetime.now()
    except Exception:
        return False


def get_owner_notify_targets(conn, user_id):
    if not user_id:
        return None, None
    user = conn.execute("SELECT telegram_chat_id, notify_email FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        return None, None
    return user["telegram_chat_id"], user["notify_email"]


def extract_price_from_post(token: str):
    for url in [
        f"https://api.divar.ir/v8/posts/{token}",
        f"https://api.divar.ir/v8/posts-v2/web/{token}",
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            data = r.json()

            def dig(obj, depth=0):
                if depth > 6:
                    return None
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and ("تومان" in v or "٬" in v or "," in v):
                            if any(ch.isdigit() for ch in v) and len(v) < 40:
                                return v
                    for v in obj.values():
                        found = dig(v, depth + 1)
                        if found:
                            return found
                elif isinstance(obj, list):
                    for i in obj:
                        found = dig(i, depth + 1)
                        if found:
                            return found
                return None

            found = dig(data)
            if found:
                return found, parse_price(found)
        except Exception as e:
            print(f"price fetch error {token}:", e)
    return None, None


def check_price_changes(conn, mon, tg_chat_id, notify_email, max_check: int = 40):
    rows = conn.execute(
        """
        SELECT token, title, price, price_num, link
        FROM seen_ads
        WHERE monitor_id=?
        ORDER BY found_at DESC
        LIMIT ?
        """,
        (mon["id"], max_check),
    ).fetchall()

    changed = []
    for row in rows:
        token = row["token"]
        try:
            new_price_str, new_price_num = extract_price_from_post(token)
            time.sleep(0.4)
            if not new_price_str or not new_price_num:
                continue

            old_num = row["price_num"]
            if old_num is None:
                conn.execute(
                    "UPDATE seen_ads SET price=?, price_num=?, last_checked=? WHERE token=?",
                    (new_price_str, new_price_num, datetime.now().isoformat(), token),
                )
                continue

            if int(new_price_num) != int(old_num):
                now = datetime.now().isoformat()
                conn.execute(
                    """
                    INSERT INTO price_changes
                    (token, monitor_id, title, old_price, new_price, link, changed_at)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (token, mon["id"], row["title"], row["price"], new_price_str, row["link"], now),
                )
                conn.execute(
                    "UPDATE seen_ads SET price=?, price_num=?, last_checked=? WHERE token=?",
                    (new_price_str, new_price_num, now, token),
                )
                changed.append({"title": row["title"], "old": row["price"], "new": new_price_str, "link": row["link"]})
        except Exception as e:
            print(f"price check item error {token}:", e)

    if changed:
        lines = [f"تغییر قیمت - {mon['name']}\n"]
        for c in changed[:MAX_NOTIFY_PER_RUN]:
            lines.append(f"• {c['title']}\nقدیم: {c['old']}\nجدید: {c['new']}\n{c['link']}\n")
        notify("\n".join(lines), subject=f"تغییر قیمت: {mon['name']}", telegram_chat_id=tg_chat_id, email=notify_email)

    return len(changed)


def run():
    init_db()
    conn = get_db()
    monitors = conn.execute("SELECT * FROM monitors WHERE is_active=1").fetchall()
    do_price_check = should_check_prices_today(conn)

    for mon in monitors:
        try:
            if not owner_is_eligible(conn, mon["user_id"]):
                print(f"Monitor {mon['id']} skipped: owner not eligible (inactive/expired)")
                continue

            tg_chat_id, notify_email = get_owner_notify_targets(conn, mon["user_id"])

            settings = json.loads(mon["settings_json"])
            settings["category"] = mon["category"]
            result = run_search_logic(settings)
            ads = result.get("ads") or []

            new_ads = []
            for ad in ads:
                token = ad.get("token")
                if not token:
                    continue
                exists = conn.execute("SELECT 1 FROM seen_ads WHERE token=?", (token,)).fetchone()
                if exists:
                    continue

                now = datetime.now().isoformat()
                price_num = ad.get("price_num")
                if price_num is None:
                    price_num = parse_price(ad.get("price"))

                conn.execute(
                    """
                    INSERT INTO seen_ads
                    (token, monitor_id, title, price, price_num, link, found_at, last_checked)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (token, mon["id"], ad.get("title"), ad.get("price"), price_num, ad.get("link"), now, now),
                )
                conn.execute(
                    """
                    INSERT INTO history
                    (monitor_id, monitor_name, token, title, price, link, matched_keywords, found_at)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (mon["id"], mon["name"], token, ad.get("title"), ad.get("price"), ad.get("link"),
                     ",".join(ad.get("matched_keywords") or []), now),
                )
                new_ads.append(ad)

            conn.commit()

            if new_ads:
                lines = [f"آگهی جدید - {mon['name']}\n"]
                for ad in new_ads[:MAX_NOTIFY_PER_RUN]:
                    score = ad.get("value_score")
                    score_txt = f" | امتیاز {score}" if score else ""
                    lines.append(f"• {ad.get('title')}{score_txt}\n{ad.get('price')}\n{ad.get('link')}\n")
                notify("\n".join(lines), subject=f"دیوار: {mon['name']}", telegram_chat_id=tg_chat_id, email=notify_email)

            track_price = 0
            try:
                track_price = int(mon["track_price"] or 0)
            except Exception:
                track_price = 0

            if track_price and do_price_check:
                print(f"Checking price changes for monitor {mon['id']} ...")
                n = check_price_changes(conn, mon, tg_chat_id, notify_email)
                conn.commit()
                print(f"Price changes found: {n}")

            time.sleep(1.5)

        except Exception as e:
            print(f"Monitor {mon['id']} error:", e)

    if do_price_check:
        set_meta(conn, "last_price_check", datetime.now().isoformat())
        conn.commit()

    conn.close()
    print(f"[{datetime.now().isoformat()}] monitor finished")


if __name__ == "__main__":
    run()