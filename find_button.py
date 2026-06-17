import re

html_file = r"C:\Users\omarb\.gemini\antigravity\brain\15da408e-1174-49f4-9358-337d966638d5\.system_generated\steps\580\content.md"

with open(html_file, "r", encoding="utf-8") as f:
    content = f.read()

print("Searching for buttons and play text...")

# Find all button elements
buttons = re.findall(r'<button[^>]*>.*?</button>', content, re.DOTALL | re.IGNORECASE)
print(f"Found {len(buttons)} button elements:")
for btn in buttons[:10]:
    # clean up formatting and print
    clean_btn = re.sub(r'\s+', ' ', btn)[:200]
    print(f"  {clean_btn}")

print("\nSearching for potential click actions or overlays...")
# Let's search for keywords like "load", "viewer", "3d", "click", "play" in tags
tags_with_text = re.findall(r'<[^>]+>[^<]*(?:load|viewer|3d|play)[^<]*</[^>]+>', content, re.IGNORECASE)
print(f"Found {len(tags_with_text)} tags containing keywords:")
for tag in tags_with_text[:15]:
    clean_tag = re.sub(r'\s+', ' ', tag)[:200]
    print(f"  {clean_tag}")
