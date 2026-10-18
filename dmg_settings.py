# -*- coding: utf-8 -*-
# Настройки красивого DMG для dmgbuild. Параметры передаются из build_mac.sh через -D.
import os

application = defines.get("app", "dist/Haven Lands Launcher.app")   # noqa: F821 (defines даёт dmgbuild)
background = defines.get("bg", "assets/dmg_background.png")          # noqa: F821
app_name = os.path.basename(application)

format = "UDZO"
filesystem = "HFS+"
files = [application]
symlinks = {"Applications": "/Applications"}
icon = "assets/icon.icns"                       # иконка смонтированного диска

# Окно 660x400, иконки по краям стрелки из фона
window_rect = ((200, 140), (660, 400))
default_view = "icon-view"
icon_size = 128
text_size = 13
icon_locations = {app_name: (180, 185), "Applications": (480, 185)}

show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
