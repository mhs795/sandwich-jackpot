[app]
title = Sandwich Jackpot
package.name = sandwichjackpot
package.domain = org.sandwichjackpot

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0.0

requirements = python3,kivy==2.3.0,anthropic,plyer,certifi,charset-normalizer,urllib3,httpcore,httpx,anyio,sniffio,h11,idna

orientation = portrait
fullscreen = 0

android.permissions = CAMERA,INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 26
android.ndk = 25b
android.accept_sdk_license = True

android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
