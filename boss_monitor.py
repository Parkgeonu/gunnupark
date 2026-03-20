import time
import winsound
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import threading
import pystray
from PIL import Image, ImageDraw, ImageFont

URL = "http://34.22.110.42:5000/"
POLL_INTERVAL = 15

notified = {}


def create_tray_icon():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill="#6c3483")
    draw.text((20, 16), "B", fill="white", font=ImageFont.load_default(size=32))
    return img


def _beep_warning5():
    winsound.Beep(600, 200)
    time.sleep(0.08)
    winsound.Beep(900, 400)


def _beep_warning1():
    for _ in range(3):
        winsound.Beep(800, 250)
        time.sleep(0.08)


def _beep_spawn():
    for freq in [1000, 1200, 1000, 1200, 1400]:
        winsound.Beep(freq, 180)
        time.sleep(0.05)


def play_sound(fn):
    threading.Thread(target=fn, daemon=True).start()


def get_bosses():
    try:
        r = requests.get(URL, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        bosses = []
        table = soup.find("table")
        if not table:
            return bosses
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) >= 2:
                name = cols[0].get_text(strip=True)
                spawn_time = cols[1].get_text(strip=True)
                if re.match(r"^\d{2}:\d{2}$", spawn_time):
                    bosses.append((name, spawn_time))
        return bosses
    except Exception:
        return []


def minutes_until(time_str):
    cur = datetime.now()
    h, m = map(int, time_str.split(":"))
    spawn = cur.replace(hour=h, minute=m, second=0, microsecond=0)
    if spawn < cur - timedelta(minutes=2):
        spawn += timedelta(days=1)
    return (spawn - cur).total_seconds() / 60


def check(icon):
    bosses = get_bosses()
    for name, spawn_time in bosses:
        key = f"{name}_{spawn_time}"
        if key not in notified:
            notified[key] = set()

        mins = minutes_until(spawn_time)

        if 4.5 <= mins <= 5.5 and 5 not in notified[key]:
            notified[key].add(5)
            play_sound(_beep_warning5)
            icon.notify(f"★ 5분 후 등장\n{name}  ({spawn_time})", "보스 알림")

        elif 0.5 <= mins <= 1.5 and 1 not in notified[key]:
            notified[key].add(1)
            play_sound(_beep_warning1)
            icon.notify(f"★★ 1분 후 등장!\n{name}  ({spawn_time})", "보스 알림")

        elif -0.5 <= mins <= 0.5 and 0 not in notified[key]:
            notified[key].add(0)
            play_sound(_beep_spawn)
            icon.notify(f"★★★ 보스 등장!!\n{name}  ({spawn_time})", "보스 알림")


def monitor_loop(icon):
    while True:
        check(icon)
        time.sleep(POLL_INTERVAL)


def on_quit(icon, item):
    icon.stop()


if __name__ == "__main__":
    image = create_tray_icon()
    menu = pystray.Menu(
        pystray.MenuItem("보스 알림 모니터", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("종료", on_quit),
    )
    icon = pystray.Icon("보스알림", image, "보스 알림 모니터", menu)
    threading.Thread(target=monitor_loop, args=(icon,), daemon=True).start()
    icon.run()
