import urllib.request
import os

model_url = "https://api.meshy.ai/misc/cdn-models/ffe2af29-b527-4deb-bae0-d3f836446052/tasks/019ecc94-338a-7900-b17a-15723f58b518/output/model.meshy?sign=1781654400-e2a05e5c9f523006b46d59c642062682"

print(f"Downloading model from {model_url}...")
try:
    urllib.request.urlretrieve(model_url, "new_model.meshy")
    size = os.path.getsize("new_model.meshy")
    print(f"Downloaded new_model.meshy successfully! Size: {size} bytes")
    
    # Read first 128 bytes
    with open("new_model.meshy", "rb") as f:
        header = f.read(128)
        
    print("\nHeader (first 32 bytes):", header[:32])
    print("Header key candidates (bytes 10-18):", [hex(b) for b in header[10:18]])
    print("Payload start (bytes 32-40):", [hex(b) for b in header[32:40]])
except Exception as e:
    print("Failed to download or inspect:", e)
