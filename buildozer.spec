[app]
title = MangaTranslator
package.name = mangatranslator
package.domain = org.offline.manga
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 1.1.0
# NOTE (verified Aug 2026): kivy and pillow are intentionally left
# WITHOUT an exact version pin here. Both have compiled, NDK-cross-built
# recipes inside python-for-android — pinning a version newer than what
# p4a currently ships a recipe for can make the Android build fail
# outright. p4a's default recipe versions are what's actually tested to
# work on-device. (pypdf/pyjnius are safe to leave as-is too — pypdf is
# pure Python with no native recipe, and pyjnius always tracks p4a itself.)
# If you need a *specific* Kivy/Pillow version, first check that
# python-for-android has a matching recipe before pinning it here.
requirements = python3,kivy,pillow,pypdf,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE, INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_licenses = True
