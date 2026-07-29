# 📦 MeshyDownloader — Direct `.glb` Extraction from Meshy.ai

[![License: CC0](https://img.shields.io/badge/License-CC0_1.0-lightgrey.svg?style=flat-square)](LICENSE)
[![Language](https://img.shields.io/badge/Python-3.10+-blue.svg?style=flat-square&logo=python&logoColor=white)](#)
[![Platform](https://img.shields.io/badge/Platform-Windows_10%2F11-lightgrey.svg?style=flat-square)](#)
[![Key Dependency](https://img.shields.io/badge/websockets-11.0+-green.svg?style=flat-square)](#)

Extracts and downloads decrypted `.glb` 3D models directly from public Meshy.ai share links. It resolves headless browser detection and intercepts the decryption process inside the browser web worker to capture the model file in real-time.

---

## 📖 Table of Contents
- [Key Features](#-key-features)
- [System Architecture](#%EF%B8%8F-system-architecture)
- [Quick Setup & Installation](#-quick-setup--installation)
- [How to Use](#-how-to-use)
- [File Structure](#-file-structure)
- [License](#-license)

---

## Key Features

- **Custom Dark UI**: Provides a modern dark-themed user interface built using optimized Tkinter.
- **Decrypted GLB Extraction**: Intercepts the decryption logic inside the browser's web worker to extract the raw `.glb` files.
- **Anti-Bot Bypass**: Automatically masks the headless Chrome browser environment (clearing the `navigator.webdriver` fingerprint) to bypass anti-bot challenges.
- **Real-time Log Console**: Monitors network requests, browser messages, and download status in a dedicated logger window.
- **Single-Click Installer**: Offers an easy-to-use, pre-packaged Inno Setup installer that handles execution setup on Windows.

---

## System Architecture

The following diagram illustrates the application's headless browser injection and worker-spy pipeline.

`mermaid
graph TD
    User["User Input: Share URL"] --> GUI["Tkinter GUI Dashboard"]
    GUI --> Trigger["Launch Headless Chrome (Remote Debugging: 9222)"]
    Trigger --> Inject["Inject worker-spy.js (On New Document)"]
    Inject --> Navigate["Navigate to Meshy.ai Share Link"]
    Navigate --> Spy{"Intercept Web Worker Message"}
    Spy -->|ArrayBuffer Detected| Capture["Capture & Base64 Encode GLB Buffer"]
    Spy -->|Wait / Idle| Navigate
    Capture --> Save["Save to Selected Directory as .glb"]
    Save --> Terminate["Terminate Chrome & Clean Profile"]
    Terminate --> Success["Display Success Notification"]

    classDef default fill:#0f172a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef process fill:#1e1b4b,stroke:#a855f7,stroke-width:2px,color:#fff;
    class Trigger,Inject,Navigate,Spy,Capture,Save,Terminate process;
`

---

## 🚀 Quick Setup & Installation

### Prerequisites (Zero-Dependency Setup)
This guide assumes a clean machine with **no pre-installed tools**.

```cmd
winget install --id Python.Python.3.10 -e --accept-source-agreements --accept-package-agreements
winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
```

🔍 **Verification Command**:
```cmd
python --version
```
*Expected Output*: `Python 3.10.x`

### Clone & Install
```bash
git clone https://github.com/IamOumarIbrahim/MeshyDownloader.git
cd MeshyDownloader
pip install websockets
```

### Run
```bash
python meshy_downloader.py
```

---

## How to Use

1. Launch **MeshyDownloader** from your desktop shortcut or via Python CLI.
2. Paste a public Meshy.ai shared model link (e.g., https://www.meshy.ai/s/8QkxPa) in the **Meshy.ai Model URL** field.
3. Select the desired destination folder.
4. Click **Extract & Download Model** to begin. The log console will update in real-time as the download finishes.

```bash
# Example command
python meshy_downloader.py
```

---

## File Structure

MeshyDownloader/
├── installer.iss - Inno Setup compiler configuration
├── meshy_downloader.py - Main Tkinter GUI application
├── decrypt.js - Node.js script to run WASM model decryption locally
├── download_and_inspect.py - Python script to inspect .meshy encrypted file headers
├── find_button.py - Script to locate specific UI targets on the page
├── trace_outgoing.py - Python CLI tool to inspect worker messages in detail
└── README.md - Project documentation

---

## 📄 License
This repository is licensed under the [CC0 1.0 Universal (CC0 1.0) Public Domain Dedication](LICENSE).
