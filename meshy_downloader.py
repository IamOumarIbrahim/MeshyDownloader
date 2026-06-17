"""
Meshy.ai GLB Model Extractor
Fixed version: resolves headless-detection network failure + strengthens worker spy
"""

import os
import json
import base64
import asyncio
import tempfile
import shutil
import threading
import queue
import subprocess
import urllib.request
import websockets
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# ── Theme ──────────────────────────────────────────────────────────────────────
COLOR_BG      = "#1e1e1e"
COLOR_CARD    = "#2d2d2d"
COLOR_ACCENT  = "#007aff"
COLOR_ACCENT_H= "#005ecb"
COLOR_TEXT    = "#ffffff"
COLOR_MUTED   = "#aaaaaa"
COLOR_CON_BG  = "#121212"
COLOR_CON_FG  = "#22d3ee"
COLOR_INP_BG  = "#3d3d3d"
COLOR_INP_FG  = "#ffffff"

# Realistic user-agent; must match the Chrome major version you ship
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ── Injection script (runs on every new document) ──────────────────────────────
#
# FIX A  – Remove navigator.webdriver fingerprint so Meshy's anti-bot check passes
# FIX B  – Fetch spy: logs every GLB/task/decrypt fetch for debugging
# FIX C  – captureGLB() handles the conversion once and guards against double-capture
# FIX D  – spyMsg() catches ALL ArrayBuffer shapes, not just the one hard-coded format
# FIX E  – Improved Worker hook: intercepts both .onmessage AND .addEventListener
#
INJECT_SCRIPT = r"""
(function () {
    'use strict';

    /* FIX A — remove webdriver fingerprint */
    try { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); }
    catch (_) {}

    window.__decryptedGLB = null;   // null → not ready; "ERROR:…" → failed; else base64
    console.log('[MESHY] Interceptors installed');

    /* FIX B — fetch spy (logs URLs, reports failures for debugging) */
    const _origFetch = window.fetch;
    window.fetch = async function (...args) {
        const urlStr = args[0] instanceof Request ? args[0].url : String(args[0]);
        const isInteresting = /\.glb|task|decrypt|model|asset/i.test(urlStr);
        try {
            const resp = await _origFetch.apply(this, args);
            if (isInteresting) console.log('[MESHY] fetch OK: ' + urlStr.slice(0, 120));
            return resp;
        } catch (err) {
            if (isInteresting)
                console.log('[MESHY] fetch FAIL: ' + urlStr.slice(0, 120) + ' | ' + err.message);
            throw err;
        }
    };

    /* FIX C — single capture function; ignores tiny buffers (thumbnails etc.) */
    function captureGLB(buffer) {
        if (window.__decryptedGLB) return;                      // already captured
        if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 5000) return;
        console.log('[MESHY] Captured ArrayBuffer: ' + buffer.byteLength + ' bytes');
        try {
            const reader = new FileReader();
            reader.onload  = () => {
                window.__decryptedGLB = reader.result.split(',')[1];
                console.log('[MESHY] Base64 ready: ' + window.__decryptedGLB.length + ' chars');
            };
            reader.onerror = () => { window.__decryptedGLB = 'ERROR:reader'; };
            reader.readAsDataURL(new Blob([buffer], { type: 'application/octet-stream' }));
        } catch (ex) { window.__decryptedGLB = 'ERROR:' + ex.message; }
    }

    /* FIX D — broad message spy: catches any ArrayBuffer regardless of wrapper shape */
    function spyMsg(e) {
        const d = e.data;
        if (!d) return;

        // Raw ArrayBuffer
        if (d instanceof ArrayBuffer) { captureGLB(d); return; }

        if (typeof d === 'object') {
            // Original known format: { type: 'process', success: true, data: ArrayBuffer }
            if (d.type === 'process' && d.success && d.data instanceof ArrayBuffer) {
                captureGLB(d.data); return;
            }
            // Catch any other field that holds a large ArrayBuffer
            for (const v of Object.values(d)) {
                if (v instanceof ArrayBuffer) { captureGLB(v); return; }
            }
        }
    }

    /* FIX E — Worker hook: handles both .addEventListener AND .onmessage patterns */
    const _Orig = window.Worker;

    function ProxyWorker(url, opts) {
        const w = new _Orig(url, opts);
        console.log('[MESHY] Worker: ' + url);

        // Grab raw prototype methods BEFORE we shadow them on `w`
        const _ael = _Orig.prototype.addEventListener.bind(w);
        const _rel = _Orig.prototype.removeEventListener.bind(w);

        // 1. Override addEventListener so any listener registered by the page is spied on
        w.addEventListener = function (type, fn, opts2) {
            if (type === 'message') {
                return _ael(type, function (e) { spyMsg(e); fn.call(this, e); }, opts2);
            }
            return _ael(type, fn, opts2);
        };

        // 2. Override .onmessage property via defineProperty
        //    Uses raw _ael/_rel so it doesn't double-wrap through our overridden addEventListener
        let _handler = null;
        let _spyRef  = null;
        Object.defineProperty(w, 'onmessage', {
            configurable: true,
            enumerable:   true,
            get: () => _handler,
            set (fn) {
                if (_spyRef) { _rel('message', _spyRef); _spyRef = null; }
                _handler = fn;
                if (fn) {
                    _spyRef = e => { spyMsg(e); fn.call(w, e); };
                    _ael('message', _spyRef);
                }
            }
        });

        return w;
    }

    ProxyWorker.prototype = _Orig.prototype;
    Object.setPrototypeOf(ProxyWorker, _Orig);
    window.Worker = ProxyWorker;
})();
"""


# ── Main App ───────────────────────────────────────────────────────────────────

class MeshyDownloaderApp:
    def __init__(self, root):
        self.root        = root
        self.root.title("Meshy.ai Model Downloader")
        self.root.geometry("750x600")
        self.root.configure(bg=COLOR_BG)
        self.root.minsize(700, 500)

        self.log_queue   = queue.Queue()
        self.dl_thread   = None
        self.chrome_proc = None
        self.tmp_profile = None

        self.create_widgets()
        self.check_queue()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def create_widgets(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(".",             background=COLOR_BG,   foreground=COLOR_TEXT)
        style.configure("TFrame",        background=COLOR_BG)
        style.configure("TLabel",        background=COLOR_BG,   foreground=COLOR_TEXT,
                         font=("Segoe UI", 10))
        style.configure("Title.TLabel",  font=("Segoe UI", 16, "bold"), foreground=COLOR_ACCENT)
        style.configure("Muted.TLabel",  font=("Segoe UI", 9),          foreground=COLOR_MUTED)

        main = ttk.Frame(self.root, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = ttk.Frame(main)
        hdr.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(hdr, text="MESHY.AI MODEL EXTRACTOR", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            hdr,
            text="Paste a public Meshy.ai model URL to extract and download its decrypted .glb file.",
            style="Muted.TLabel"
        ).pack(anchor=tk.W, pady=(2, 0))

        # Input card
        card = tk.Frame(main, bg=COLOR_CARD, padx=15, pady=15)
        card.pack(fill=tk.X, pady=(0, 15))
        card.columnconfigure(0, weight=1)

        tk.Label(card, text="Meshy.ai Model URL:", bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        self.url_entry = tk.Entry(card, bg=COLOR_INP_BG, fg=COLOR_INP_FG,
                                  insertbackground=COLOR_TEXT, relief=tk.FLAT,
                                  font=("Segoe UI", 10), bd=5)
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        self.url_entry.insert(0, "https://www.meshy.ai/s/8QkxPa")

        tk.Label(card, text="Save Directory:", bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=(0, 4))
        self.dir_entry = tk.Entry(card, bg=COLOR_INP_BG, fg=COLOR_INP_FG,
                                  insertbackground=COLOR_TEXT, relief=tk.FLAT,
                                  font=("Segoe UI", 10), bd=5)
        self.dir_entry.grid(row=3, column=0, sticky=tk.EW, padx=(0, 10))
        self.dir_entry.insert(0, os.path.abspath("."))
        tk.Button(card, text="Browse…", bg=COLOR_INP_BG, fg=COLOR_TEXT,
                  activebackground=COLOR_INP_BG, activeforeground=COLOR_TEXT,
                  relief=tk.FLAT, font=("Segoe UI", 9), padx=10,
                  command=self.browse_dir).grid(row=3, column=1, sticky=tk.E)

        # Download button
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(0, 15))
        self.dl_btn = tk.Button(
            btn_frame, text="Extract & Download Model",
            bg=COLOR_ACCENT, fg=COLOR_TEXT,
            activebackground=COLOR_ACCENT_H, activeforeground=COLOR_TEXT,
            relief=tk.FLAT, font=("Segoe UI", 11, "bold"), pady=8,
            command=self.start_download
        )
        self.dl_btn.pack(fill=tk.X)

        # Console
        ttk.Label(main, text="Log Console Output:", style="TLabel").pack(anchor=tk.W, pady=(0, 4))
        self.console = ScrolledText(
            main, bg=COLOR_CON_BG, fg=COLOR_CON_FG,
            insertbackground=COLOR_CON_FG, font=("Consolas", 9),
            relief=tk.FLAT, bd=5
        )
        self.console.pack(fill=tk.BOTH, expand=True)
        self.write_log("System ready. Paste a URL and click Extract.\n")

    def browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if d:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, os.path.abspath(d))

    def write_log(self, msg):
        self.console.insert(tk.END, msg)
        self.console.see(tk.END)

    def check_queue(self):
        try:
            while True:
                kind, data = self.log_queue.get_nowait()
                if kind == 'log':
                    self.write_log(data)
                elif kind == 'status':
                    self.write_log(f"[STATUS] {data}\n")
                elif kind == 'browser_console':
                    self.write_log(f"[BROWSER] {data}\n")
                elif kind == 'done':
                    self.write_log(f"\n[SUCCESS] {data}\n")
                    self.set_controls(True)
                    messagebox.showinfo("Success", f"Model saved:\n{data}")
                elif kind == 'error':
                    self.write_log(f"\n[ERROR] {data}\n")
                    self.set_controls(True)
                    messagebox.showerror("Error", f"Failed:\n{data}")
                self.log_queue.task_done()
        except queue.Empty:
            pass
        self.root.after(100, self.check_queue)

    def set_controls(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        bg    = COLOR_ACCENT if enabled else COLOR_INP_BG
        self.dl_btn.config(state=state, bg=bg)
        self.url_entry.config(state=state)
        self.dir_entry.config(state=state)

    def start_download(self):
        url  = self.url_entry.get().strip()
        sdir = self.dir_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a Meshy.ai URL.")
            return
        if not os.path.isdir(sdir):
            messagebox.showwarning("Warning", "Save directory does not exist.")
            return
        self.set_controls(False)
        self.console.delete(1.0, tk.END)
        self.write_log("Starting extraction…\n")
        self.dl_thread = threading.Thread(target=self._thread_run,
                                          args=(url, sdir), daemon=True)
        self.dl_thread.start()

    # ── Background worker ──────────────────────────────────────────────────────

    def _thread_run(self, url, sdir):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._download(url, sdir))
        except Exception as e:
            self.log_queue.put(('error', str(e)))
        finally:
            loop.close()

    async def _cdp_recv_until(self, ws, want_id, timeout=10):
        """Drain WebSocket messages (forwarding console logs) until `want_id` replies
        or `timeout` elapses. Used by debug capture, which runs outside the main poll loop."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            left = deadline - loop.time()
            if left <= 0:
                return None
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=left)
            except asyncio.TimeoutError:
                return None
            resp = json.loads(raw)
            if resp.get("method") == "Runtime.consoleAPICalled":
                args = resp["params"].get("args", [])
                msg  = " ".join(str(a.get("value", "")) for a in args)
                self.log_queue.put(('browser_console', msg))
            if resp.get("id") == want_id:
                return resp

    async def _capture_debug(self, ws, save_dir, tag):
        """Saves a screenshot + full DOM snapshot to {save_dir}/_debug/.
        Lets you SEE what the page actually looked like when decryption stalled —
        a blocking cookie/referral modal, a paywall, a captcha, a layout change, etc.
        all look identical from the log console alone, so this is the fastest way
        to tell which one you're hitting without guessing."""
        debug_dir = os.path.join(save_dir, "_debug")
        os.makedirs(debug_dir, exist_ok=True)

        try:
            await ws.send(json.dumps({
                "id": 9001, "method": "Page.captureScreenshot", "params": {"format": "png"}
            }))
            resp = await self._cdp_recv_until(ws, 9001, timeout=10)
            data = resp.get("result", {}).get("data") if resp else None
            if data:
                png_path = os.path.join(debug_dir, f"debug_{tag}.png")
                with open(png_path, "wb") as f:
                    f.write(base64.b64decode(data))
                self.log_queue.put(('status', f"Debug screenshot saved → {png_path}"))
        except Exception as e:
            self.log_queue.put(('log', f"  (debug screenshot failed: {e})\n"))

        try:
            await ws.send(json.dumps({
                "id": 9002,
                "method": "Runtime.evaluate",
                "params": {"expression": "document.documentElement.outerHTML",
                           "returnByValue": True},
            }))
            resp = await self._cdp_recv_until(ws, 9002, timeout=10)
            html = resp.get("result", {}).get("result", {}).get("value") if resp else None
            if html:
                html_path = os.path.join(debug_dir, f"debug_{tag}.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html)
                self.log_queue.put(('status', f"Debug HTML saved → {html_path}"))
        except Exception as e:
            self.log_queue.put(('log', f"  (debug HTML dump failed: {e})\n"))

    async def _download(self, url: str, save_dir: str):
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(chrome_path):
            raise FileNotFoundError(
                "Chrome not found at C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
            )

        self.log_queue.put(('status', "Launching Chrome (anti-detect, off-screen)…"))
        self.tmp_profile = tempfile.mkdtemp(prefix="meshy_chrome_")

        # ── FIX 1: NO --headless flag ──────────────────────────────────────────
        #   --headless=new fingerprints Chrome as a bot; Meshy blocks all API
        #   fetches with "TypeError: Failed to fetch", so the decrypt worker
        #   never receives data and never fires.
        #   Instead, open a real (but off-screen) window with --window-position.
        #
        # ── FIX 2: Anti-detection flags ───────────────────────────────────────
        #   --disable-blink-features=AutomationControlled   removes the
        #   navigator.webdriver=true override Chrome adds when DevTools is active.
        # ──────────────────────────────────────────────────────────────────────
        self.chrome_proc = subprocess.Popen([
            chrome_path,
            "--remote-debugging-port=9222",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",   # FIX 2
            f"--user-agent={USER_AGENT}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-infobars",
            "--window-position=-9999,0",   # off-screen; still a real window
            "--window-size=1280,720",
            # ── FIX 6: stop Chrome treating the off-screen window as backgrounded ──
            #   Windows' native window-occlusion tracking marks an off-screen window
            #   as "occluded," which throttles requestAnimationFrame and pauses any
            #   WebGL/Three.js render loop — exactly the loop that triggers GLB
            #   decryption in Meshy's viewer. Without these flags the page loads and
            #   all network calls succeed, but the 3D viewer's JS never actually runs,
            #   so the decrypt worker is never created at all.
            "--disable-features=CalculateNativeWinOcclusion",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
            f"--user-data-dir={self.tmp_profile}",
        ])

        # ── FIX 3: Retry loop instead of bare sleep(3) ────────────────────────
        ws_url = None
        for _attempt in range(20):
            await asyncio.sleep(1)
            if self.chrome_proc.poll() is not None:
                raise RuntimeError("Chrome exited immediately — check installation.")
            try:
                with urllib.request.urlopen("http://localhost:9222/json", timeout=2) as r:
                    targets = json.loads(r.read())
                pages = [t for t in targets if t.get("type") == "page"]
                if pages:
                    ws_url = pages[0]["webSocketDebuggerUrl"]
                    break
            except Exception:
                pass

        if not ws_url:
            raise RuntimeError("Could not connect to Chrome DevTools after 20 s.")
        self.log_queue.put(('status', "DevTools connected."))

        async with websockets.connect(ws_url, max_size=None) as ws:
            # Enable CDP domains + register injection
            for cmd in [
                {"id": 1, "method": "Page.enable"},
                {"id": 2, "method": "Runtime.enable"},
                {
                    "id": 3,
                    "method": "Page.addScriptToEvaluateOnNewDocument",
                    "params": {"source": INJECT_SCRIPT},
                },
            ]:
                await ws.send(json.dumps(cmd))

            self.log_queue.put(('status', f"Navigating to {url}…"))
            await ws.send(json.dumps({
                "id": 4, "method": "Page.navigate", "params": {"url": url}
            }))

            self.log_queue.put(('status', "Waiting for model decryption (up to 120 s)…"))
            glb_data = None
            debug_captured = False

            for attempt in range(60):
                await asyncio.sleep(2)

                if self.chrome_proc.poll() is not None:
                    raise RuntimeError("Chrome died unexpectedly.")

                eval_id = 100 + attempt
                await ws.send(json.dumps({
                    "id": eval_id,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "window.__decryptedGLB", "returnByValue": True},
                }))

                # ── FIX 4: Drain pending WebSocket messages with a hard deadline ──
                #   The original bare `while True: ws.recv()` could block forever if
                #   Chrome stops sending.  asyncio.wait_for enforces a 5 s cap per
                #   poll cycle so we always return to the outer loop.
                loop = asyncio.get_running_loop()
                deadline = loop.time() + 5
                while True:
                    left = deadline - loop.time()
                    if left <= 0:
                        break
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=left)
                    except asyncio.TimeoutError:
                        break

                    resp = json.loads(raw)

                    if resp.get("method") == "Runtime.consoleAPICalled":
                        args = resp["params"].get("args", [])
                        msg  = " ".join(str(a.get("value", "")) for a in args)
                        self.log_queue.put(('browser_console', msg))

                    if resp.get("id") == eval_id:
                        val = resp.get("result", {}).get("result", {}).get("value")
                        if val:
                            if str(val).startswith("ERROR:"):
                                raise RuntimeError(f"Decryption error in browser: {val}")
                            glb_data = val
                        break   # done with this poll cycle

                if glb_data:
                    self.log_queue.put(('status', "Model data captured!"))
                    break

                # ── FIX 7: mid-wait debug snapshot ────────────────────────────────
                #   If nothing has happened ~30s in, grab a screenshot + DOM dump
                #   once. If the viewer is stuck behind a popup/modal/captcha this
                #   makes it visible immediately instead of guessing from logs.
                if not debug_captured and attempt == 14:
                    debug_captured = True
                    self.log_queue.put(('status', "No data yet — capturing debug snapshot…"))
                    await self._capture_debug(ws, save_dir, "midwait")

                self.log_queue.put(('log', f"  Waiting… ({attempt + 1}/60)\n"))

            if not glb_data:
                self.log_queue.put(('status', "Timed out — capturing final debug snapshot…"))
                await self._capture_debug(ws, save_dir, "timeout")
                self.cleanup_chrome()
                raise TimeoutError(
                    "Timed out — model was not decrypted within 120 s. "
                    f"Check {os.path.join(save_dir, '_debug')} for a screenshot/HTML "
                    "snapshot of what the page looked like."
                )

            # Save file
            self.log_queue.put(('status', "Decoding and writing to disk…"))
            glb_bytes = base64.b64decode(glb_data)

            slug = ""
            if "/s/" in url:
                slug = url.split("/s/")[-1].strip("/")
            elif "id=" in url:
                slug = url.split("id=")[-1].split("&")[0]
            filename = f"meshy_model_{slug}.glb" if slug else "extracted_model.glb"
            out_path = os.path.join(save_dir, filename)

            with open(out_path, "wb") as f:
                f.write(glb_bytes)

            self.cleanup_chrome()
            self.log_queue.put(('done', out_path))

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def cleanup_chrome(self):
        if self.chrome_proc:
            try:
                self.chrome_proc.terminate()
                self.chrome_proc.wait(timeout=3)
            except Exception:
                try:
                    self.chrome_proc.kill()
                except Exception:
                    pass
            self.chrome_proc = None

        if self.tmp_profile and os.path.exists(self.tmp_profile):
            import time
            time.sleep(0.5)   # let OS release file handles
            shutil.rmtree(self.tmp_profile, ignore_errors=True)
            self.tmp_profile = None

    def on_closing(self):
        self.cleanup_chrome()
        self.root.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    app  = MeshyDownloaderApp(root)
    root.mainloop()
