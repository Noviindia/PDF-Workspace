#!/bin/bash
# PDF Workspace - APK Build Script
# Builds the Android APK using Buildozer

set -e

echo "================================"
echo "  PDF Workspace - APK Builder"
echo "================================"
echo ""

# Check if Buildozer is installed
if ! command -v buildozer &> /dev/null; then
    echo "❌ Buildozer is not installed."
    echo "   Install it with: pip install buildozer"
    echo "   Also install: pip install cython"
    exit 1
fi

# Check for Android SDK/NDK
echo "📱 Building Android APK..."
echo ""

# Clean previous builds (optional)
if [ "$1" = "clean" ]; then
    echo "🧹 Cleaning previous builds..."
    buildozer android clean
    echo ""
fi

# Build debug APK
echo "🔨 Building debug APK..."
echo "   This may take 15-30 minutes on first run (downloads SDK/NDK)."
echo ""

buildozer android debug

echo ""
echo "================================"
echo "  Build Complete!"
echo "================================"
echo ""
echo "📦 APK location: bin/"
ls -la bin/*.apk 2>/dev/null || echo "   (APK files will be in the bin/ directory)"
echo ""
echo "📲 To install on a connected device:"
echo "   adb install bin/pdfworkspace-*.apk"
echo ""
echo "🔍 To install on an emulator:"
echo "   Start an Android emulator first, then run the adb install command."
echo ""
