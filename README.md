# 🎰 Sandwich Jackpot

A poker-machine style Android app that photographs your fridge and tells you
what sandwiches you can make — powered by Claude AI vision.

## How it works

1. Press **SPIN / TAKE PHOTO** → camera opens
2. Photograph the inside of your fridge
3. The reels spin while Claude analyses the image
4. Reels land on your ingredients → **JACKPOT** reveals your sandwich!

---

## Running on desktop (for testing)

```bash
cd sandwich_machine
pip install -r requirements.txt
ANTHROPIC_API_KEY=sk-ant-... python main.py
```

> **No camera on desktop?** The app enters **DEMO MODE** automatically and
> simulates a BLT result so you can preview the UI.

---

## Building the Android APK

### Prerequisites

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y python3-pip git zip unzip openjdk-17-jdk \
    build-essential libffi-dev libssl-dev autoconf libtool \
    pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake

pip install buildozer cython
```

### Build

```bash
cd sandwich_machine
buildozer android debug
```

The first build downloads the Android SDK/NDK and takes ~20 min.
The APK will be at `bin/sandwichjackpot-1.0.0-arm64-v8a-debug.apk`.

### Install on device (USB debugging enabled)

```bash
buildozer android deploy run
# or manually:
adb install bin/sandwichjackpot-*.apk
```

---

## API Key

Tap the **🔑 API KEY** button inside the app and paste your key from
[console.anthropic.com](https://console.anthropic.com).

Alternatively set it before launching:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Project layout

```
sandwich_machine/
├── main.py          ← Full app (Kivy + Claude API)
├── buildozer.spec   ← Android build config
├── requirements.txt ← Desktop pip dependencies
└── README.md
```
