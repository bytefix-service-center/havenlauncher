#!/bin/bash
# Сборка Haven Lands Launcher.app и красивого DMG. Запускать на macOS.
#   ./build_mac.sh                       — обычная сборка (ad-hoc подпись)
#   VERSION=1.2.0 ./build_mac.sh         — задать версию
#   CODESIGN_IDENTITY="Developer ID Application: Имя (TEAMID)" ./build_mac.sh   — подпись Apple Developer ID
# Архитектура DMG = архитектура Mac, на котором собираешь (arm64 или x86_64).
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="Haven Lands Launcher"
BUNDLE_ID="com.havenlands.launcher"
VERSION="${VERSION:-1.0.0}"
PYTHON="${PYTHON:-python3}"
SIGN_ID="${CODESIGN_IDENTITY:--}"
ARCH="$(uname -m)"
APP="dist/$APP_NAME.app"
DMG="dist/Haven-Lands-Launcher-$VERSION-$ARCH.dmg"

[ "$(uname)" = "Darwin" ] || { echo "Этот скрипт запускается только на macOS."; exit 1; }
[ -f assets/icon.icns ] || { echo "Нет assets/icon.icns — выполните: python3 tools/make_assets.py"; exit 1; }

echo "==> 1/5  Окружение Python"
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt dmgbuild

echo "==> 2/5  Сборка $APP_NAME.app"
rm -rf build dist ./*.spec
pyinstaller --noconfirm --clean --windowed \
  --name "$APP_NAME" \
  --icon assets/icon.icns \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --add-data "ui:ui" \
  --collect-all webview --collect-all certifi \
  --hidden-import objc --hidden-import Foundation --hidden-import AppKit \
  --hidden-import WebKit --hidden-import Quartz \
  main.py
[ -d "$APP" ] || { echo "Не получилось: нет $APP"; exit 1; }

echo "==> 3/5  Информация о приложении и подпись"
PLIST="$APP/Contents/Info.plist"
setkey() {  # setkey Ключ тип значение
  /usr/libexec/PlistBuddy -c "Set :$1 $3" "$PLIST" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :$1 $2 $3" "$PLIST"
}
setkey CFBundleDisplayName string "$APP_NAME"
setkey CFBundleShortVersionString string "$VERSION"
setkey CFBundleVersion string "$VERSION"
setkey NSHumanReadableCopyright string "Haven Lands"
xattr -cr "$APP"
if [ "$SIGN_ID" = "-" ]; then
  codesign --force --deep --sign - "$APP"
else
  codesign --force --deep --options runtime --timestamp --sign "$SIGN_ID" "$APP"
fi
codesign --verify --deep --strict "$APP" && echo "    подпись в порядке"

echo "==> 4/5  Фон для DMG (Retina)"
mkdir -p build
tiffutil -cathidpicheck assets/dmg_background.png assets/dmg_background@2x.png -out build/dmg_background.tiff

echo "==> 5/5  Сборка DMG"
rm -f "$DMG"
dmgbuild -s dmg_settings.py -D app="$APP" -D bg="build/dmg_background.tiff" "$APP_NAME" "$DMG"
[ "$SIGN_ID" = "-" ] || codesign --force --sign "$SIGN_ID" --timestamp "$DMG"

echo
echo "Готово:"
echo "  $APP"
echo "  $DMG"
