[app]
title = MangaTranslator
package.name = mangatranslator
package.domain = org.offline.manga
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,txt,ttf
version = 1.1.0

requirements = python3,kivy,pillow,pypdf,pyjnius,android

orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE, INTERNET

android.api = 33
android.build_tools_version = 33.0.2
android.minapi = 24
android.ndk = 25b

android.archs = armeabi-v7a, arm64-v8a
android.accept_sdk_licenses = True

# 👇 ये लाइन सब ठीक कर देगी – python-for-android की develop ब्रांच इस्तेमाल करेगा
p4a.branch = develop
