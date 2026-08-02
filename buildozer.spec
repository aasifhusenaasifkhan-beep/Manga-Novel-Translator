[app]

# (str) Title of your application
title = MangaTranslator

# (str) Package name
package.name = mangatranslator

# (str) Package domain (needed for android packaging)
package.domain = org.offline.manga

# (str) Source code directory where main.py lives
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,kv,atlas,txt

# (str) Application versioning
version = 1.1.0

# (list) Application requirements
# FIX: Added 'android' recipe so 'from android.permissions import ...' in main.py works without crashing on phone!
requirements = python3,kivy,pillow,pypdf,pyjnius,android

# (str) Supported orientation (portrait, landscape or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions required by the app
android.permissions = READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE, INTERNET

# (int) Target Android API (API 33 for Android 13+)
android.api = 33

# (int) Minimum API required (Android 7.0+)
android.minapi = 24

# (str) Android NDK version to use
android.ndk = 25b

# (list) The Android architectures to build for (64-bit + 32-bit)
android.archs = arm64-v8a, armeabi-v7a

# (bool) Accept SDK licenses automatically
android.accept_sdk_licenses = True

# (bool) Enable AndroidX support (Required for Android API 33+)
android.enable_androidx = True

# (str) Bootstrap to use for android build
p4a.bootstrap = sdl2


[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug with command output)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = false, 1 = true)
warn_on_root = 1
