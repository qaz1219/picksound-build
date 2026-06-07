[app]
title = 乐转站
package.name = picksound_android
package.domain = com.qiugl
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,ico
source.exclude_patterns = build_apk.py,core.py,build.py
version = 5.8.6
requirements = python3,kivy
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25c
android.sdk = 33
android.allow_backup = True
android.presplash_color = #1A2A44
android.icon = icon.png
android.presplash = presplash.png
android.logcat_filters = *:S python:D

android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
