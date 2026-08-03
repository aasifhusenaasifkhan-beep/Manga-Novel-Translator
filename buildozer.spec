[app]
title = MangaTranslator
package.name = mangatranslator
package.domain = org.offline.manga
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 1.1.0

requirements = python3==3.11.9,hostpython3==3.11.9,kivy,pillow,pypdf,pyjnius

orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE, INTERNET

android.api = 33
android.minapi = 24
android.ndk = 25b

# केवल 64-bit आर्किटेक्चर – libthorvg बग से बचाव
android.archs = arm64-v8a

android.accept_sdk_licenses = True
p4a.branch = develop
