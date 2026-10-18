# Haven Lands Launcher — сборка установщиков

Что получается на выходе:

| Платформа | Файл | Что это |
|---|---|---|
| macOS | `dist/Haven-Lands-Launcher-1.0.0-arm64.dmg` | красивый образ: окно с фоном и стрелкой, перетащил в Applications |
| Windows | `dist/Haven-Lands-Launcher-Setup-1.0.0.exe` | установщик: Далее → Установить → Готово, ярлыки, удаление через «Приложения» |

Иконка берётся из `assets/logo.png`. Если захотите заменить логотип: положите новый `assets/logo.png`
и выполните `python3 tools/make_assets.py` (нужен `pip install pillow`) — пересоздадутся `.icns`, `.ico`, фон DMG и картинки установщика.

---

## 1. Собрать DMG на Mac

Собирать нужно на Mac. Архитектура DMG = архитектура вашего Mac (M1/M2/M3/M4 → `arm64`, Intel → `x86_64`).

```bash
cd haven-lands-launcher
chmod +x build_mac.sh
./build_mac.sh                 # версия 1.0.0
VERSION=1.2.0 ./build_mac.sh   # или своя версия
```

Результат: `dist/Haven Lands Launcher.app` и `dist/Haven-Lands-Launcher-<версия>-<arch>.dmg`.
Нужны Python 3 (у вас стоит из Homebrew) и интернет, чтобы скачать зависимости. Другой Python: `PYTHON=python3.11 ./build_mac.sh`.

### Первый запуск у других людей (важно)
Без платной подписи Apple (Developer ID, $99/год) macOS предупреждает о приложениях из интернета. Это нормально для сборки без подписи:

- macOS 15 и новее: открыть приложение → «Готово» → *Системные настройки → Конфиденциальность и безопасность → Всё равно открыть*.
- или в Терминале: `xattr -cr "/Applications/Haven Lands Launcher.app"`.

Чтобы предупреждения не было совсем, нужен Developer ID и нотаризация:
```bash
CODESIGN_IDENTITY="Developer ID Application: Ваше Имя (TEAMID)" ./build_mac.sh
xcrun notarytool submit dist/*.dmg --keychain-profile "notary" --wait
xcrun stapler staple dist/*.dmg
```

---

## 2. Собрать .exe и установщик (с Mac)

**Напрямую на Mac собрать .exe нельзя**: PyInstaller не умеет собирать под другую систему, а Wine для этого ненадёжен.
Три рабочих способа, от самого простого:

### Способ A — GitHub Actions (рекомендую, ничего ставить не нужно)
1. Создайте репозиторий на github.com (можно приватный) и загрузите в него **содержимое** папки `haven-lands-launcher`
   (чтобы `build_win.bat` и `.github/` лежали в корне репозитория).
2. Откройте вкладку **Actions → Build installers → Run workflow**, укажите версию.
3. Через 5–10 минут внизу страницы запуска, в разделе **Artifacts**, появятся:
   - `windows-installer` — `Haven-Lands-Launcher-Setup-<версия>.exe`
   - `macos-dmg-macos-15` — DMG для Apple Silicon
   - `macos-dmg-macos-15-intel` — DMG для Intel Mac

   Если создать тег (`git tag v1.0.0 && git push --tags`), файлы сами прикрепятся к Release.

### Способ B — Windows в виртуальной машине (Parallels / UTM / VMware Fusion)
В Windows установите **Python 3.11 (64-bit)** — отметьте «Add python.exe to PATH» — и **Inno Setup 6** (jrsoftware.org/isdl.php),
скопируйте папку проекта и запустите двойным кликом `build_win.bat`.
На Mac с Apple Silicon это Windows 11 ARM: сборка получится для ARM, а большинству пользователей нужен x64 — поэтому лучше способ A.

### Способ C — любой Windows-компьютер
То же самое, что в способе B.

Результат `build_win.bat`: `dist\Haven-Lands-Launcher-Setup-<версия>.exe` (установщик) и `dist\Haven Lands Launcher\Haven Lands Launcher.exe` (без установки).

### Что делает установщик
- ставит в `%LOCALAPPDATA%\Programs\Haven Lands Launcher` без запроса прав администратора (можно выбрать «для всех»);
- ярлык в меню «Пуск» + галочка «ярлык на рабочем столе»;
- русский и английский язык мастера;
- при обновлении поверх старой версии сам закроет запущенный лаунчер и откроет заново;
- деинсталлятор в «Параметры → Приложения». Данные лаунчера и установленные им программы (`%LOCALAPPDATA%\AppLauncher`) при удалении не трогаются;
- Microsoft Edge WebView2 лаунчер при первом запуске проверит и предложит поставить сам (так было и раньше).

Без подписи кода Windows SmartScreen покажет «Windows защитила ваш компьютер» → «Подробнее» → «Выполнить в любом случае».
Это убирается только покупкой сертификата подписи кода.

---

## Структура
```
main.py, engine.py, ui/        сам лаунчер
assets/                        иконки (icon.icns, icon.ico), фон DMG, картинки установщика
build_mac.sh, dmg_settings.py  сборка .app и DMG
build_win.bat                  сборка .exe и установщика
installer/HavenLandsLauncher.iss  скрипт установщика Inno Setup
tools/make_assets.py           генерация иконок из logo.png
.github/workflows/build.yml    автосборка на GitHub
```
