# Meshy.ai GLB Model Extractor

A utility to extract and download decrypted `.glb` 3D models directly from public Meshy.ai share links (e.g. `https://www.meshy.ai/s/8QkxPa`).

## Features
- **Decrypted GLB Extraction**: Intercepts the decryption process inside the browser web worker to capture the final decrypted `ArrayBuffer` as a base64 string, then saves it as a clean `.glb` file.
- **Anti-bot Bypass**: Resolves headless browser fingerprinting (removes `navigator.webdriver` fingerprint) so that Meshy's Cloudflare/anti-bot protection passes seamlessly.
- **Tkinter GUI**: Built-in simple and responsive user interface to paste share links, choose save directories, and monitor the extraction log in real-time.
- **Precompiled Executable**: Includes a standalone compiled `MeshyDownloader.exe` executable for Windows users to run without needing a Python environment.

---

## How It Works
When you click **Extract & Download Model**:
1. The tool spins up a headless Chrome instance with remote debugging enabled.
2. It registers a custom script on document creation to spy on the web worker decryption logic of Meshy's site.
3. The headless Chrome navigates to your provided share URL.
4. As soon as the page decrypts the model inside its web worker, our worker-spy interceptor captures the raw decrypted model buffer.
5. The model is downloaded directly to your specified folder, and Chrome is automatically closed.

---

## Getting Started

### Using the Precompiled Executable (Windows)
1. Double-click `MeshyDownloader.exe`.
2. Paste your Meshy.ai share link into the input field.
3. Choose a save directory.
4. Click **Extract & Download Model**.

*Note: Google Chrome must be installed on your system.*

### Running from Python Source
1. Make sure you have Python 3.10+ installed.
2. Install the required `websockets` dependency:
   ```bash
   pip install websockets
   ```
3. Run the application:
   ```bash
   python meshy_downloader.py
   ```

---

## Development & Utility Files
The repository includes auxiliary development scripts used during exploration:
- `meshy_downloader.py`: Main Tkinter GUI application.
- `decrypt.js`: Node.js script to run WASM model decryption locally.
- `download_and_inspect.py`: Python script to inspect `.meshy` encrypted file headers.
- `find_button.py`: Script to locate specific UI targets on the page.
- `trace_outgoing.py`: Python CLI tool to inspect worker messages in detail via DevTools protocol.
