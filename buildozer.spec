[app]
title = MangaTranslator
package.name = mangatranslator
package.domain = org.offline.manga
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 1.0.0
requirements = python3,kivy,opencv,pillow,numpy,pymupdf
orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a