#!/bin/bash
# Заливает проект на GitHub через терминал (так .git, .github и .gitignore точно попадают в репозиторий).
# Использование:  bash push_to_github.sh https://github.com/ВАШ_ЛОГИН/haven-lands-launcher.git
set -e
cd "$(dirname "$0")"
URL="${1:?Укажите адрес репозитория: bash push_to_github.sh https://github.com/логин/репозиторий.git}"

[ -d .git ] || git init -b main
git add -A
git update-index --chmod=+x build_mac.sh push_to_github.sh 2>/dev/null || true
git -c user.name="${GIT_NAME:-$(git config user.name || echo dev)}" \
    -c user.email="${GIT_EMAIL:-$(git config user.email || echo dev@example.com)}" \
    commit -m "Haven Lands Launcher" || echo "Нечего коммитить — продолжаю"
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$URL"
git push -u origin main || { echo "В репозитории уже есть свой README — перезаписываю его."; git push -u origin main --force; }
echo "Готово. Откройте вкладку Actions в репозитории."
