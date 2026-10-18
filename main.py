# -*- coding: utf-8 -*-
import os, sys
import webview
import threading, time
from engine import Engine, acquire_lock, alert, ensure_webview2, data_dir

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
APP_TITLE = "Haven Lands Launcher"


class Api:
    def __init__(self, engine):
        self._e = engine

    def state(self, since=0):
        return self._e.snapshot(int(since or 0))

    def act(self, which="main"):
        self._e.act(which)

    def media(self):
        return self._e.media_payload()

    def config(self):
        return self._e.refresh_config()

    def open_url(self, url):
        self._e.open_url(url)


def main():
    lock = acquire_lock()
    flag = os.path.join(data_dir(), "update.flag")
    if lock is None:
        if "--update" in sys.argv:      # лаунчер уже открыт: просим его обновиться и выходим
            open(flag, "w").close()
        else:
            alert("Haven Lands Launcher уже запущен.")
        return
    if not ensure_webview2():
        return
    engine = Engine()
    kw = dict(js_api=Api(engine), width=1280, height=820, min_size=(980, 640), background_color="#0e0f13")
    try:
        window = webview.create_window(APP_TITLE, os.path.join(BASE, "ui", "index.html"), maximized=True, **kw)
    except TypeError:  # старая версия pywebview без maximized
        window = webview.create_window(APP_TITLE, os.path.join(BASE, "ui", "index.html"), **kw)
    engine.on_title = lambda t: window.set_title(t)
    engine.on_exit = lambda: window.destroy()
    def watch():
        # приложение нажало «Обновить», пока лаунчер открыт
        while True:
            time.sleep(1)
            if os.path.exists(flag):
                try:
                    os.remove(flag)
                    try:
                        window.restore(); window.show()
                    except Exception:
                        pass
                    engine.check()
                    if engine.s.get("action") == "update":
                        engine.act("main")
                except Exception:
                    pass

    def boot():
        engine.check()
        if "--update" in sys.argv and engine.s.get("action") == "update":
            engine.act("main")
        threading.Thread(target=watch, daemon=True).start()

    webview.start(boot)


if __name__ == "__main__":
    main()
