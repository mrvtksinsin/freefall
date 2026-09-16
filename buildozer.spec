[app]
title = FREEFALL
package.name = freefall
package.domain = com.freefall.game

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,ttf,wav,mp3,ogg
source.exclude_exts = spec,md
version = 1.2
version.regex = __version__ = ['"]([^'"]*)['"]
version.filename = %(source.dir)s/main.py

requirements = python3,pygame==2.6.1
orientation = portrait
fullscreen = 0
# Gerekli izinler (save için gerek yok ama genel)
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.accept_sdk_license_agreements = True
# portrait + sensor
android.manifest.orientation = portrait
# icon / presplash (varsa)
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png
# p4a bootstrap sdl2 (pygame uyumlu)
p4a.bootstrap = sdl2
p4a.port = 5000

[buildozer]
log_level = 2
warn_on_root = 1
