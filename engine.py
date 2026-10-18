# -*- coding: utf-8 -*-
"""Логика лаунчера: проверка версии, скачивание, сборка, установка."""
import base64, hashlib, json, struct, os, platform, re, shutil, socket, subprocess, sys, tarfile, threading, time, zipfile
import urllib.error, urllib.parse, urllib.request, ssl

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# ---------- настройки (версии зафиксированы) ----------
FIREBASE_PROJECT = "launcher-2f632"
FIREBASE_API_KEY = "AIzaSyBT7flJLPAZkb5VE5ezaV7nYA5eiQYTPLk"   # не секрет: защита в правилах Firestore
PY_VERSION, PY_TAG = "3.11.9", "20240415"                      # портативный Python (python-build-standalone)
PIP_FIXED = ["pywebview==5.3.2", "pyinstaller==6.10.0"]
MIN_FREE = 2 * 1024 ** 3
DATA_NAME = "AppLauncher"
STAGES = ["Скачивание", "Подготовка окружения", "Установка библиотек", "Сборка", "Установка"]
KEYS = ["download", "env", "libs", "build", "install"]
DEFAULT_SEC = [25, 90, 120, 180, 15]
LINE_SCALE = [0, 0, 40, 500, 0]
NOWIN = 0x08000000 if IS_WIN else 0


class BuildError(Exception):
    pass


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


CTX = _ctx()


def urlopen(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AppLauncher"})
    return urllib.request.urlopen(req, timeout=timeout, context=CTX)


def data_dir():
    if IS_WIN:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    else:
        base = os.path.expanduser("~/Library/Application Support")
    p = os.path.join(base, DATA_NAME)
    os.makedirs(p, exist_ok=True)
    return p


# ---------- блокировка, окна системы ----------
def acquire_lock():
    f = open(os.path.join(data_dir(), "launcher.lock"), "a+")
    try:
        if IS_WIN:
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return f


def alert(text):
    if IS_WIN:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "Haven Lands Launcher", 0x40)
    elif IS_MAC:
        subprocess.run(["osascript", "-e", f'display dialog "{text}" buttons {{"OK"}} with icon note'])


def ensure_webview2():
    """Windows: проверяет WebView2 и предлагает установить."""
    if not IS_WIN:
        return True
    import winreg
    guid = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    for root, sub in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node" + guid[8:]),
                      (winreg.HKEY_LOCAL_MACHINE, guid), (winreg.HKEY_CURRENT_USER, guid)):
        try:
            with winreg.OpenKey(root, sub) as k:
                if winreg.QueryValueEx(k, "pv")[0] not in ("", "0.0.0.0"):
                    return True
        except OSError:
            pass
    import ctypes
    if ctypes.windll.user32.MessageBoxW(0, "Для работы нужен Microsoft Edge WebView2. Установить сейчас?",
                                        "Haven Lands Launcher", 0x24) != 6:
        return False
    try:
        tmp = os.path.join(data_dir(), "webview2.exe")
        with urlopen("https://go.microsoft.com/fwlink/p/?LinkId=2124703", 60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        subprocess.run([tmp, "/silent", "/install"], creationflags=NOWIN)
        os.remove(tmp)
        return True
    except Exception as e:
        alert(f"Не удалось установить WebView2: {e}")
        return False


# ---------- помощники ----------
def safe_name(s):
    s = re.sub(r"[\\/:*?\"'<>|]", "", s or "").strip()
    return s or "App"


def install_target(name):
    if IS_MAC:
        return os.path.join(os.path.expanduser("~/Applications"), name + ".app")
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local"), name)


def launch_path(name):
    t = install_target(name)
    return os.path.join(t, name + ".exe") if IS_WIN else t


def rmtree(p):
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p, ignore_errors=True)
    elif os.path.lexists(p):
        try:
            os.remove(p)
        except OSError:
            pass


def req_names(path):
    out = []
    if os.path.isfile(path):
        for line in open(path, encoding="utf-8", errors="ignore"):
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
            if m:
                out.append(m.group(1))
    return out


MODULES_PY = r"""
import sys, json, importlib.metadata as m, importlib.util as u
skip = {"pip","setuptools","wheel","pyinstaller","tests","test","docs","examples"}
out = set()
for n in sys.argv[1:]:
    names = []
    try:
        t = m.distribution(n).read_text("top_level.txt")
        names = [x.strip() for x in (t or "").split() if x.strip()]
    except Exception:
        pass
    names = names or [n.replace("-", "_")]
    for x in names:
        x = x.split("/")[0]
        if x.startswith("_") or x.lower() in skip:
            continue
        try:
            if u.find_spec(x):
                out.add(x)
        except Exception:
            pass
print(json.dumps(sorted(out)))
"""

RTHOOK = """import os, sys
if sys.stdout is None: sys.stdout = open(os.devnull, 'w')
if sys.stderr is None: sys.stderr = open(os.devnull, 'w')
_b = getattr(sys, '_MEIPASS', None)
if _b:
    os.chdir(_b)
    if _b not in sys.path: sys.path.insert(0, _b)
"""


class Engine:
    def __init__(self):
        self.dir = data_dir()
        self._write_launcher_path()
        self.work = os.path.join(self.dir, "work")
        self.state_path = os.path.join(self.dir, "state.json")
        self._lk = threading.RLock()
        self.on_title = None
        self.on_exit = None
        self.rel = None
        self.busy = False
        self.log, self.log_base = [], 0
        self.media, self.media_ver = {}, 0
        self.config = {}
        self.s = dict(phase="checking", action="", button="", action2="", button2="", message="", appName="", version="", notes="", online=True, comingSoon=False, releaseDate="")
        self.stage, self.stage_t, self.run_t = -1, 0.0, 0.0
        self.lines, self.real = 0, None
        self.exp = list(DEFAULT_SEC)

    def _write_launcher_path(self):
        """Запоминаем, где лежит сам лаунчер, чтобы приложение могло его открыть кнопкой «Обновить»."""
        try:
            p = os.path.abspath(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])
            if IS_MAC and ".app/" in p:
                p = p[:p.index(".app/") + 4]
            with open(os.path.join(self.dir, "launcher_path.txt"), "w", encoding="utf-8") as f:
                f.write(p)
        except Exception:
            pass

    # ---------- состояние ----------
    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, st):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.state_path)

    def _set(self, **kw):
        with self._lk:
            self.s.update(kw)
        if "appName" in kw and kw["appName"] and self.on_title:
            try:
                self.on_title(kw["appName"])
            except Exception:
                pass

    def _log(self, line):
        line = line.rstrip()
        if not line:
            return
        with self._lk:
            self.log.append(line)
            if len(self.log) > 6000:
                del self.log[:1000]
                self.log_base += 1000

    # ---------- проверка версии ----------
    def _installed(self, st):
        return bool(st.get("version") and st.get("appFile") and os.path.exists(launch_path(st["appFile"])))

    @staticmethod
    def _rel_fields(f):
        def g(k):
            v = f.get(k) or {}
            for t in ("stringValue", "integerValue", "doubleValue", "timestampValue"):
                if t in v:
                    return str(v[t]).strip()
            return ""
        return {k: g(k) for k in ("appName", "version", "fileId", "notes", "sha256", "publishedAt", "publishAt", "releaseDate")}

    @staticmethod
    def _due(iso):
        import datetime as _d
        try:
            t = _d.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
            return t <= _d.datetime.now(_d.timezone.utc)
        except Exception:
            return False

    def _fetch_scheduled(self):
        base = (f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}"
                "/databases/(default)/documents/releases/scheduled")
        for url in (base, base + "?key=" + FIREBASE_API_KEY):
            try:
                with urlopen(url, 15) as r:
                    return self._rel_fields(json.loads(r.read().decode("utf-8")).get("fields", {}))
            except urllib.error.HTTPError as e:
                if e.code not in (400, 401, 403):
                    return None
            except Exception:
                return None
        return None

    def _fetch_release(self):
        base = (f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}"
                "/databases/(default)/documents/releases/latest")
        data, last = None, None
        for url in (base, base + "?key=" + FIREBASE_API_KEY):
            try:
                with urlopen(url, 15) as r:
                    data = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise BuildError("Релиз ещё не опубликован.")
                last = e
                if e.code not in (400, 401, 403):
                    raise
        if data is None:
            raise BuildError(f"Сервер версий отказал в доступе ({last.code}).")
        rel = self._rel_fields(data.get("fields", {}))
        # отложенный выпуск: если время пришло — берём его вместо latest
        try:
            sch = self._fetch_scheduled()
            if sch and sch.get("version") and sch.get("fileId") and self._due(sch.get("publishAt")):
                rel = sch
        except Exception:
            pass
        if rel["fileId"] and not rel["version"]:
            raise BuildError("В релизе не заполнена версия.")
        return rel

    def check(self):
        if self.busy:
            return
        st = self._load()
        inst = self._installed(st)
        self._set(phase="checking", action="", button="", action2="", button2="", message="")
        try:
            rel = self._fetch_release()
        except BuildError as e:
            self._set(phase="error", action="retry", button="Retry", message=str(e), online=True)
            return
        except Exception:
            if inst:
                self._set(phase="ready", action="launch", button="Open", action2="delete", button2="Delete", message="Нет связи", online=False,
                          appName=st.get("appName", ""), version=st.get("version", ""), notes=st.get("notes", ""))
            else:
                self._set(phase="error", action="retry", button="Retry", online=False,
                          message="Нет связи. Проверьте подключение к интернету.")
            return
        self.rel = rel
        self._load_media()
        if not rel["fileId"] and not inst:
            # файла нет — игра ещё не вышла
            self._set(phase="ready", action="", button="", action2="", button2="", message="", online=True,
                      appName=rel["appName"] or "Приложение", version="", notes=rel["notes"],
                      comingSoon=True, releaseDate=rel["releaseDate"])
            return
        if not rel["fileId"] and inst:
            # файл убрали, но игра уже установлена — просто даём запустить
            self._set(phase="ready", action="launch", button="Open", action2="delete", button2="Delete", message="", online=True,
                      appName=st.get("appName", "") or rel["appName"] or "Приложение", version=st.get("version", ""),
                      notes=st.get("notes", ""), comingSoon=False, releaseDate="")
            return
        self._set(comingSoon=False, releaseDate="")
        common = dict(online=True, appName=rel["appName"] or st.get("appName", "") or "Приложение", version=rel["version"],
                      notes=rel["notes"])
        if not inst:
            self._set(phase="ready", action="install", button="Get", message="", **common)
        elif st.get("version") != rel["version"]:
            self._set(phase="ready", action="update", button="Update", action2="delete", button2="Delete",
                      message=f"Нужно обновить до версии {rel['version']}", **common)
        else:
            self._set(phase="ready", action="launch", button="Open", action2="delete", button2="Delete",
                      message="", **common)

    # ---------- действия ----------
    def act(self, which="main"):
        with self._lk:
            a, busy = self.s["action2" if which == "second" else "action"], self.busy
        if busy:
            return
        if a == "delete":
            threading.Thread(target=self.uninstall, daemon=True).start()
        elif a == "launch":
            self.launch()
        elif a in ("install", "update", "retry"):
            threading.Thread(target=self._run_action, args=(a,), daemon=True).start()

    def _run_action(self, a):
        if a == "retry" or not self.rel:
            self.check()
        if self.s["action"] in ("install", "update") and self.rel:
            self._pipeline(self.rel)

    # ---------- иконка и скриншоты (из админки) ----------
    def _fetch_media(self):
        base = (f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}"
                "/databases/(default)/documents/releases/media")
        for url in (base, base + "?key=" + FIREBASE_API_KEY):
            try:
                with urlopen(url, 15) as r:
                    f = json.loads(r.read().decode("utf-8")).get("fields", {})
                out = {k: (v.get("stringValue") or "") for k, v in f.items() if "stringValue" in v}
                out["shots"] = [x.get("stringValue", "") for x in (f.get("shots", {}).get("arrayValue", {}).get("values") or [])]
                return out
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return {}
                if e.code not in (400, 401, 403):
                    return None
            except Exception:
                return None
        return None

    def _load_media(self):
        m = self._fetch_media()
        if m is not None:
            self.media = m
            self.media_ver += 1

    # ---------- оформление и события (из админки) ----------
    def _fx(self, v):
        """Firestore Value -> обычное значение Python."""
        if "stringValue" in v: return v["stringValue"]
        if "integerValue" in v: return int(v["integerValue"])
        if "doubleValue" in v: return v["doubleValue"]
        if "booleanValue" in v: return v["booleanValue"]
        if "timestampValue" in v: return v["timestampValue"]
        if "arrayValue" in v: return [self._fx(x) for x in v["arrayValue"].get("values", [])]
        if "mapValue" in v: return {k: self._fx(x) for k, x in v["mapValue"].get("fields", {}).items()}
        return None

    def refresh_config(self):
        base = (f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}"
                "/databases/(default)/documents/releases/config")
        for url in (base, base + "?key=" + FIREBASE_API_KEY):
            try:
                with urlopen(url, 15) as r:
                    f = json.loads(r.read().decode("utf-8")).get("fields", {})
                self.config = {k: self._fx(v) for k, v in f.items()}
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    self.config = {}
                    break
                if e.code not in (400, 401, 403):
                    break
            except Exception:
                break
        return self.config

    def open_url(self, url):
        if isinstance(url, str) and re.match(r"https?://", url.strip(), re.I):
            import webbrowser
            webbrowser.open(url.strip())

    def media_payload(self):
        m = self.media or {}
        ic = m.get("p256") or m.get("p512") or ""
        return {"icon": "data:image/png;base64," + ic if ic else "",
                "shots": [x for x in m.get("shots", []) if x]}

    def _write_icons(self, src):
        """Собирает icon.ico / icon.icns из PNG-размеров, загруженных в админке (если в проекте своих нет)."""
        try:
            m = self.media or self._fetch_media() or {}
            png = {int(k[1:]): base64.b64decode(v) for k, v in m.items() if re.fullmatch(r"p\d+", k) and v}
            if IS_MAC:
                dst, items = os.path.join(src, "icon.icns"), [(b"ic07", 128), (b"ic08", 256), (b"ic09", 512)]
                if os.path.exists(dst) or not all(n in png for _, n in items):
                    return
                body = b"".join(t + struct.pack(">I", len(png[n]) + 8) + png[n] for t, n in items)
                with open(dst, "wb") as f:
                    f.write(b"icns" + struct.pack(">I", len(body) + 8) + body)
            else:
                dst, sizes = os.path.join(src, "icon.ico"), [n for n in (16, 32, 64, 128, 256) if n in png]
                if os.path.exists(dst) or not sizes:
                    return
                off, ent, data = 6 + 16 * len(sizes), b"", b""
                for n in sizes:
                    w = 0 if n >= 256 else n
                    ent += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(png[n]), off + len(data))
                    data += png[n]
                with open(dst, "wb") as f:
                    f.write(struct.pack("<HHH", 0, 1, len(sizes)) + ent + data)
            self._log("Иконка приложения создана")
        except Exception as e:
            self._log(f"Иконка пропущена: {e}")

    # ---------- удаление ----------
    def uninstall(self):
        with self._lk:
            if self.busy:
                return
            self.busy = True
        self._set(phase="checking", action="", button="", action2="", button2="", message="")
        try:
            st = self._load()
            name = st.get("appFile", "")
            if name:
                target = install_target(name)
                self._kill(name, target)
                rmtree(target)
                if IS_WIN:
                    ps = ("foreach($p in @([Environment]::GetFolderPath('Desktop'),"
                          "(Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs'))){"
                          "Remove-Item -LiteralPath (Join-Path $p '" + name + ".lnk') -ErrorAction SilentlyContinue}")
                    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                                   capture_output=True, creationflags=NOWIN)
            for k in ("version", "appFile", "notes", "installedAt"):
                st.pop(k, None)
            self._save(st)
        except Exception as e:
            self._log(f"ОШИБКА удаления: {e}")
        finally:
            with self._lk:
                self.busy = False
        self.check()

    def launch(self):
        st = self._load()
        p = launch_path(st.get("appFile", ""))
        if not os.path.exists(p):
            self._set(phase="error", action="retry", button="Retry", message="Приложение не найдено.")
            return
        if IS_MAC:
            subprocess.Popen(["open", p])
        else:
            os.startfile(p)

    # ---------- снимок для интерфейса ----------
    def snapshot(self, since=0):
        with self._lk:
            s = dict(self.s)
            s["stages"] = STAGES
            s["mediaVer"] = self.media_ver
            s["error"] = s["phase"] == "error"
            idx, frac, pct, elapsed, eta = -1, 0.0, None, 0, None
            if self.busy and self.stage >= 0:
                idx = self.stage
                now = time.time()
                exp = max(1.0, self.exp[idx])
                frac = min(0.96, (now - self.stage_t) / exp)
                if LINE_SCALE[idx] and self.lines:
                    frac = max(frac, min(0.96, (1 - 1 / (1 + self.lines / LINE_SCALE[idx])) * 0.95))
                if self.real is not None:
                    frac = self.real
                    pct = int(frac * 100)
                eta = (1 - frac) * exp + sum(self.exp[idx + 1:])
                elapsed = now - self.run_t
            s.update(stageIdx=idx, stageFrac=frac, pct=pct, elapsed=int(elapsed),
                     eta=None if eta is None else int(eta),
                     stageName=STAGES[idx] if idx >= 0 else "")
            if self.busy:
                s["phase"] = "running"
            i = max(0, since - self.log_base)
            s["log"] = self.log[i:]
            s["logTotal"] = self.log_base + len(self.log)
            return s

    # ---------- конвейер ----------
    def _begin(self, i, expect=None):
        with self._lk:
            self.stage, self.stage_t, self.lines, self.real = i, time.time(), 0, None
            if expect is not None:
                self.exp[i] = expect
        self._log(f"== {STAGES[i]}")

    def _pipeline(self, rel):
        st = self._load()
        hist = st.get("stages", {})
        with self._lk:
            self.busy = True
            self.exp = [float(hist.get(k) or DEFAULT_SEC[i]) for i, k in enumerate(KEYS)]
            self.run_t = time.time()
            self.log, self.log_base = [], 0
        self._set(phase="running", action="", button="", action2="", button2="", message="")
        durs = {}
        try:
            rmtree(self.work)
            os.makedirs(self.work)
            ctx = {}
            t = time.time(); self._begin(0)
            self._stage_download(rel, ctx)
            durs["download"] = time.time() - t

            t = time.time()
            ready = os.path.exists(self._py()) and os.path.exists(self._venv_py())
            self._begin(1, 3 if ready else None)
            did = self._stage_env()
            if did:
                durs["env"] = time.time() - t

            t = time.time(); self._begin(2)
            self._stage_libs(ctx)
            durs["libs"] = time.time() - t

            t = time.time(); self._begin(3)
            self._stage_build(ctx)
            durs["build"] = time.time() - t

            t = time.time(); self._begin(4)
            self._stage_install(ctx)
            durs["install"] = time.time() - t

            st = self._load()
            st.update(version=rel["version"], appName=rel["appName"] or ctx["name"], appFile=ctx["name"],
                      notes=rel["notes"], installedAt=time.strftime("%Y-%m-%d %H:%M:%S"))
            st.setdefault("stages", {}).update({k: round(v, 1) for k, v in durs.items()})
            self._save(st)
            self._log("Готово")
            with self._lk:
                self.busy = False
            self._set(phase="ready", action="launch", button="Open", action2="delete", button2="Delete", online=True,
                      appName=st["appName"], version=rel["version"], notes=rel["notes"],
                      message="")
        except Exception as e:
            self._log(f"ОШИБКА: {e}")
            with self._lk:
                self.busy = False
            self._set(phase="error", action="retry", button="Retry", message=self._human(e))
        finally:
            with self._lk:
                self.busy = False
                self.stage = -1
            rmtree(self.work)

    def _human(self, e):
        if isinstance(e, BuildError):
            return str(e)
        if isinstance(e, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError)):
            return "Обрыв сети. Проверьте интернет и повторите."
        if isinstance(e, OSError) and getattr(e, "errno", None) == 28:
            return "Недостаточно места на диске."
        if isinstance(e, PermissionError):
            return "Нет доступа к файлам. Закройте приложение и повторите."
        return f"Непредвиденная ошибка: {e}"

    # ---------- 1. скачивание ----------
    def _stage_download(self, rel, ctx):
        if platform.machine().lower() in ("arm64", "aarch64") and IS_WIN:
            raise BuildError("Поддерживается только Windows x64.")
        free = shutil.disk_usage(self.dir).free
        if free < MIN_FREE:
            raise BuildError("Недостаточно места: нужно не менее 2 ГБ.")
        dest = os.path.join(self.work, "project.zip")
        self._log("Скачивание project.zip")
        r = self._open_drive(rel["fileId"])
        total = int(r.headers.get("Content-Length") or 0)
        got, h = 0, hashlib.sha256()
        with open(dest, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b); h.update(b); got += len(b)
                if total:
                    with self._lk:
                        self.real = min(1.0, got / total)
        if total and got < total:
            raise BuildError("Загрузка оборвалась. Повторите.")
        if not zipfile.is_zipfile(dest):
            raise BuildError("Google Drive вернул не архив. Проверьте доступ к файлу.")
        want = (rel.get("sha256") or "").lower()
        if want and h.hexdigest() != want:
            os.remove(dest)
            raise BuildError("Контрольная сумма файла не совпала. Файл отброшен.")
        src = os.path.join(self.work, "src")
        with zipfile.ZipFile(dest) as z:
            z.extractall(src)
        rmtree(os.path.join(src, "__MACOSX"))
        os.remove(dest)
        items = [i for i in os.listdir(src) if not i.startswith(".")]
        if len(items) == 1 and os.path.isdir(os.path.join(src, items[0])) and not os.path.exists(os.path.join(src, "main.py")):
            src = os.path.join(src, items[0])
        cfg = {}
        p = os.path.join(src, "app.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8-sig") as f:
                cfg = json.load(f)
        ctx["src"] = src
        ctx["name"] = safe_name(cfg.get("name") or rel.get("appName") or "App")
        ctx["entry"] = cfg.get("entry") or "main.py"
        if not os.path.isfile(os.path.join(src, ctx["entry"])):
            raise BuildError(f"В архиве нет точки входа {ctx['entry']}.")
        self._write_icons(src)
        self._log(f"Проект: {ctx['name']}, вход {ctx['entry']}")

    def _open_drive(self, fid):
        url = "https://drive.usercontent.google.com/download?" + urllib.parse.urlencode(
            {"id": fid, "export": "download", "confirm": "t"})
        fail = "Google Drive не отдаёт файл: проверьте доступ по ссылке или лимит скачиваний."
        r = urlopen(url, 60)
        if "text/html" in r.headers.get("Content-Type", ""):
            html = r.read().decode("utf-8", "replace")
            m = re.search(r'<form[^>]+action="([^"]+)"', html)
            if not m:
                raise BuildError(fail)
            act = m.group(1).replace("&amp;", "&")
            params = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', html))
            r = urlopen(act + ("&" if "?" in act else "?") + urllib.parse.urlencode(params), 60)
            if "text/html" in r.headers.get("Content-Type", ""):
                raise BuildError(fail)
        return r

    # ---------- 2. окружение ----------
    def _py(self):
        d = os.path.join(self.dir, "python")
        return os.path.join(d, "python.exe") if IS_WIN else os.path.join(d, "bin", "python3")

    def _venv_py(self):
        d = os.path.join(self.dir, "venv")
        return os.path.join(d, "Scripts", "python.exe") if IS_WIN else os.path.join(d, "bin", "python")

    def _stage_env(self):
        did = False
        if not os.path.exists(self._py()):
            did = True
            m = platform.machine().lower()
            if IS_WIN:
                triple = "x86_64-pc-windows-msvc-shared"
            else:
                triple = "aarch64-apple-darwin" if m in ("arm64", "aarch64") else "x86_64-apple-darwin"
            name = f"cpython-{PY_VERSION}+{PY_TAG}-{triple}-install_only.tar.gz"
            base = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PY_TAG}/"
            arc = os.path.join(self.work, "python.tar.gz")
            self._log("Скачивание портативного Python")
            h = hashlib.sha256()
            with urlopen(base + urllib.parse.quote(name), 120) as r, open(arc, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b); h.update(b)
            with urlopen(base + "SHA256SUMS", 60) as r:
                sums = r.read().decode("utf-8", "replace")
            want = next((l.split()[0] for l in sums.splitlines() if l.strip().endswith(name)), "")
            if not want or want.lower() != h.hexdigest():
                raise BuildError("Контрольная сумма Python не совпала.")
            ex = os.path.join(self.work, "pyx")
            with tarfile.open(arc) as t:
                try:
                    t.extractall(ex, filter="fully_trusted")
                except TypeError:
                    t.extractall(ex)
            rmtree(os.path.join(self.dir, "python"))
            shutil.move(os.path.join(ex, "python"), os.path.join(self.dir, "python"))
            os.remove(arc)
        venv = os.path.join(self.dir, "venv")
        ok = os.path.exists(self._venv_py()) and subprocess.run(
            [self._venv_py(), "-c", "import sys"], capture_output=True, creationflags=NOWIN).returncode == 0
        if not ok:
            did = True
            rmtree(venv)
            self._log("Создание виртуального окружения")
            self._run([self._py(), "-m", "venv", venv])
        return did

    # ---------- 3. библиотеки ----------
    def _env(self):
        e = dict(os.environ)
        e.update(PYTHONUNBUFFERED="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONIOENCODING="utf-8")
        for k in ("PYTHONHOME", "PYTHONPATH"):
            e.pop(k, None)
        return e

    def _run(self, cmd, cwd=None, count=False):
        p = subprocess.Popen(cmd, cwd=cwd, env=self._env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
        for line in p.stdout:
            self._log(line)
            if count:
                with self._lk:
                    self.lines += 1
        p.wait()
        if p.returncode:
            raise BuildError(f"Команда завершилась с ошибкой ({p.returncode}). Подробности в журнале.")

    def _stage_libs(self, ctx):
        py = self._venv_py()
        self._run([py, "-m", "pip", "install", "--prefer-binary", "--no-input"] + PIP_FIXED, count=True)
        req = os.path.join(ctx["src"], "requirements.txt")
        names = req_names(req)
        if os.path.isfile(req):
            self._run([py, "-m", "pip", "install", "--prefer-binary", "--no-input", "-r", req], count=True)
        out = subprocess.run([py, "-c", MODULES_PY, "pywebview"] + names, capture_output=True, text=True,
                             env=self._env(), creationflags=NOWIN).stdout.strip().splitlines()
        try:
            ctx["modules"] = json.loads(out[-1]) if out else ["webview"]
        except Exception:
            ctx["modules"] = ["webview"]
        self._log("Модули для сборки: " + ", ".join(ctx["modules"]))

    # ---------- 4. сборка ----------
    def _stage_build(self, ctx):
        src, name, entry = ctx["src"], ctx["name"], ctx["entry"]
        dist, bld, spec = (os.path.join(self.work, d) for d in ("dist", "build", "spec"))
        hook = os.path.join(self.work, "rthook.py")
        with open(hook, "w", encoding="utf-8") as f:
            f.write(RTHOOK)
        sep = ";" if IS_WIN else ":"
        a = [self._venv_py(), "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", name,
             "--distpath", dist, "--workpath", bld, "--specpath", spec, "--runtime-hook", hook, "--paths", src]
        for m in dict.fromkeys(["webview"] + ctx.get("modules", [])):
            a += ["--collect-all", m]
        if IS_WIN:
            a += ["--collect-all", "pythonnet", "--collect-all", "clr_loader", "--hidden-import", "clr"]
        else:
            for m in ("objc", "Foundation", "AppKit", "WebKit", "Quartz"):
                a += ["--hidden-import", m]
            a += ["--osx-bundle-identifier", "app." + re.sub(r"[^a-z0-9]", "", name.lower() or "app")]
        icon = os.path.join(src, "icon.icns" if IS_MAC else "icon.ico")
        if os.path.isfile(icon):
            a += ["--icon", icon]
        skip = {entry, "requirements.txt", "app.json", "icon.icns", "icon.ico", "__pycache__"}
        for item in sorted(os.listdir(src)):
            if item in skip or item.startswith("."):
                continue
            p = os.path.join(src, item)
            a += ["--add-data", f"{p}{sep}{item if os.path.isdir(p) else '.'}"]
        a.append(os.path.join(src, entry))
        self._run(a, cwd=self.work, count=True)
        out = os.path.join(dist, name + ".app") if IS_MAC else os.path.join(dist, name)
        if not os.path.exists(out) or (IS_WIN and not os.path.exists(os.path.join(out, name + ".exe"))):
            raise BuildError("Сборка не создала приложение. Подробности в журнале.")
        ctx["built"] = out

    # ---------- 5. установка ----------
    def _stage_install(self, ctx):
        name, built = ctx["name"], ctx["built"]
        target = install_target(name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        new, old = target + ".new", target + ".old"
        rmtree(new); rmtree(old)
        shutil.copytree(built, new, symlinks=True)
        if IS_MAC:
            subprocess.run(["xattr", "-cr", new], capture_output=True)
            r = subprocess.run(["codesign", "--force", "--deep", "--sign", "-", new], capture_output=True, text=True)
            if r.returncode:
                self._log(r.stderr)
                raise BuildError("Не удалось подписать приложение.")
        self._kill(name, target)
        try:
            if os.path.exists(target):
                os.rename(target, old)
            os.rename(new, target)
        except OSError:
            if os.path.exists(old) and not os.path.exists(target):
                os.rename(old, target)
            raise BuildError("Не удалось заменить приложение. Закройте его и повторите.")
        rmtree(old)
        if IS_WIN:
            self._shortcuts(name, target)

    def _kill(self, name, target):
        try:
            if IS_WIN:
                subprocess.run(["taskkill", "/F", "/T", "/IM", name + ".exe"], capture_output=True, creationflags=NOWIN)
            else:
                subprocess.run(["pkill", "-f", os.path.join(target, "Contents", "MacOS")], capture_output=True)
            time.sleep(1)
        except Exception:
            pass

    def _shortcuts(self, name, target):
        exe = os.path.join(target, name + ".exe")
        ps = ("$w=New-Object -ComObject WScript.Shell;"
              "foreach($p in @([Environment]::GetFolderPath('Desktop'),"
              "(Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs'))){"
              "$s=$w.CreateShortcut((Join-Path $p '" + name + ".lnk'));"
              "$s.TargetPath='" + exe + "';$s.WorkingDirectory='" + target + "';$s.Save()}")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, creationflags=NOWIN)
