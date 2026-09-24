[app]

# (str) Title of your application
title = PDF Workspace

# (str) Package name
package.name = pdfworkspace

# (str) Package domain (needed for android/ios packaging)
package.domain = org.pdfworkspace

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,ttf,otf,pdf,md,traineddata

# (list) Source files to exclude
source.exclude_exts = spec,apk,zip

# (list) List of directory to exclude
source.exclude_dirs = tests,scripts,bin,.git,__pycache__,.venv,venv,.buildozer,.pdfworkspace

# (str) Application versioning
version = 1.0.2

# (list) Application requirements
# Pin both python3 and hostpython3 to 3.11.5 (avoids Python 3.14 C-API removal of ma_version_tag)
# Pin chardet==5.2.0 (pure Python wheel, avoids x86-64 mypyc .so files on ARM64)
# DOCX export uses pure-Python OpenXML fallback in app/exporters/docx_exporter.py (no lxml needed)
requirements = python3==3.11.5,hostpython3==3.11.5,kivy,pillow,pypdf,openpyxl,et_xmlfile,pyjnius,certifi,urllib3,requests,idna,filetype

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/assets/icons/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/assets/icons/icon.png

# (str) Supported orientation (landscape, sensorLandscape, portrait, sensorPortrait, all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

#
# Android specific
#

# (list) Permissions
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 26

# (str) Android NDK version to use
android.ndk = 25b

# (str) The Android arch to build for
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) Android entry point
#android.entrypoint = org.kivy.android.PythonActivity

# (str) Full name including package path of the Java class that implements Android Activity
#android.activity_class_name = org.kivy.android.PythonActivity

# (list) Android application meta-data to set (key=value format)
#android.meta_data =

# (bool) If True, then skip trying to update the Android sdk
android.skip_update = False

# (bool) If True, then automatically accept SDK license
android.accept_sdk_license = True

# (str) The format used to package the app for release mode (aab or apk or aar).
android.release_artifact = apk

# (str) The format used to package the app for debug mode (apk or aar).
android.debug_artifact = apk

#
# Python for android (p4a) specific
#

# (str) python-for-android directory with Android 16 16KB page-size alignment patches
p4a.source_dir = /tmp/p4a

# (str) Bootstrap to use for android builds
p4a.bootstrap = sdl2

#
# iOS specific - not used for Android build
#

# (str) Path to a custom kivy-ios folder
#ios.kivy_ios_dir = ../kivy-ios

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
