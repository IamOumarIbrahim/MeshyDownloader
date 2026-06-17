import subprocess
import time
import urllib.request
import json
import asyncio
import websockets
import os

async def main():
    print("Starting Chrome...")
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    temp_profile_dir = tempfile_dir = os.path.abspath("chrome_profile_trace")
    
    # Launch Chrome
    chrome_proc = subprocess.Popen([
        chrome_path,
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-gpu",
        "--no-sandbox",
        "--user-data-dir=" + temp_profile_dir
    ])
    
    await asyncio.sleep(3)
    
    try:
        req = urllib.request.urlopen("http://localhost:9222/json")
        targets = json.loads(req.read().decode('utf-8'))
        ws_url = targets[0]['webSocketDebuggerUrl']
        print("Connected. WS:", ws_url)
    except Exception as e:
        print("Failed to connect:", e)
        chrome_proc.terminate()
        return

    # Log script that hooks postMessage as well!
    log_script = """
    (function() {
        window.__workerMessages = [];
        
        const _OrigWorker = window.Worker;
        window.Worker = function MeshyWorkerProxy(scriptURL, options) {
            const w = new _OrigWorker(scriptURL, options);
            
            function logMsg(data, direction) {
                try {
                    let info = {
                        direction: direction,
                        type: data ? data.type : null,
                        keys: data ? Object.keys(data) : []
                    };
                    if (data && data.type === 'authorize') {
                        info.hostname = data.hostname;
                        info.timestamp = data.timestamp;
                        info.signature = data.signature;
                    }
                    window.__workerMessages.push(info);
                } catch(ex) {
                    window.__workerMessages.push({error: ex.toString()});
                }
            }

            // Hook postMessage (outgoing)
            const _origPM = w.postMessage.bind(w);
            w.postMessage = function(message, transfer) {
                logMsg(message, 'out');
                return _origPM(message, transfer);
            };

            // Hook onmessage (incoming)
            const proto = Object.getPrototypeOf(w);
            const desc = Object.getOwnPropertyDescriptor(proto, 'onmessage');
            if (desc && desc.set) {
                Object.defineProperty(w, 'onmessage', {
                    configurable: true,
                    get() { return desc.get ? desc.get.call(w) : undefined; },
                    set(fn) {
                        desc.set.call(w, function(e) {
                            logMsg(e.data, 'in');
                            return fn.call(this, e);
                        });
                    }
                });
            }
            
            // Hook addEventListener (incoming)
            const _origAEL = w.addEventListener.bind(w);
            w.addEventListener = function(type, listener, opts) {
                if (type === 'message') {
                    return _origAEL(type, function(e) {
                        logMsg(e.data, 'in');
                        return listener.call(this, e);
                    }, opts);
                }
                return _origAEL(type, listener, opts);
            };
            
            return w;
        };
        window.Worker.prototype = _OrigWorker.prototype;
    })();
    """

    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Runtime.enable"}))
        
        await ws.send(json.dumps({
            "id": 3,
            "method": "Page.addScriptToEvaluateOnNewDocument",
            "params": {"source": log_script}
        }))
        
        # Navigate to the working link first to capture successful authorize!
        print("Navigating to working page...")
        await ws.send(json.dumps({
            "id": 4,
            "method": "Page.navigate",
            "params": {"url": "https://www.meshy.ai/s/8QkxPa"}
        }))
        
        # Poll window.__workerMessages
        for attempt in range(15):
            await asyncio.sleep(2)
            eval_req = {
                "id": 100 + attempt,
                "method": "Runtime.evaluate",
                "params": {"expression": "window.__workerMessages", "returnByValue": True}
            }
            await ws.send(json.dumps(eval_req))
            while True:
                resp = json.loads(await ws.recv())
                
                # Print console events
                if resp.get('method') == 'Runtime.consoleAPICalled':
                    args = resp.get('params', {}).get('args', [])
                    msg_text = " ".join([str(arg.get('value', '')) for arg in args])
                    print(f"[Browser Console] {msg_text}")
                    
                if resp.get('id') == eval_req['id']:
                    res = resp.get('result', {}).get('result', {})
                    val = res.get('value')
                    print(f"\n--- Worker Messages (Attempt {attempt+1}): {val} ---")
                    if isinstance(val, list):
                        for msg in val:
                            print(msg)
                    break

    chrome_proc.terminate()
    chrome_proc.wait()
    shutil_rmtree = lambda p: os.path.exists(p) and shutil.rmtree(p, ignore_errors=True)
    import shutil
    shutil_rmtree(temp_profile_dir)
    print("Chrome stopped.")

if __name__ == "__main__":
    asyncio.run(main())
