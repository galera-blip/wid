import os
import re
import json
import requests
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def get_image_bytes(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        print(f"Downloaded {len(r.content)} bytes")
        ct = r.headers.get("Content-Type", "")
        if "text/html" in ct:
            m = re.search(r'property="og:image" content="([^"]+)"', r.text)
            if m:
                direct = m.group(1).replace("&amp;", "&")
                print(f"Resolved FB page to {direct[:100]}")
                r = requests.get(direct, headers=headers, timeout=20)
        return r.content, "image/jpeg"
    except Exception as e:
        print(f"Download failed: {e}")
        return None, None

def parse_image(image_url):
    img_bytes, mime = get_image_bytes(image_url)
    if not img_bytes:
        return None

    prompt = """Analyze ferry schedule flyer. Extract ONLY BATANGAS<->BALATERO routes.
BALATERO TO BATANGAS = toBAT, BATANGAS TO BALATERO = toPG
Return ONLY JSON: {"toPG": [{"company": "...", "type": "Fastcraft", "vessel": "", "time": "12:45 PM", "status": "SCHEDULED", "note": ""}], "toBAT": [...]}"""

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-preview-05-20",
        "gemini-1.5-flash"
    ]

    for model_name in models_to_try:
        try:
            print(f"Trying model: {model_name}")
            resp = client.models.generate_content(
                model=model_name,
                contents=[prompt, types.Part.from_bytes(data=img_bytes, mime_type=mime)]
            )
            print(f"Success with {model_name}: {resp.text[:400]}")
            m = re.search(r'\{[\s\S]*\}', resp.text)
            if m:
                return json.loads(m.group(0))
        except Exception as e:
            print(f"Model {model_name} failed: {e}")
            continue
    return None

def update_html(data):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    if "const schedule = {" not in html:
        print("ERROR: const schedule not found")
        return False
    json_str = json.dumps(data, indent=6)
    start = html.index("const schedule = {")
    end_marker = "let currentDir"
    end = html.index(end_marker, start)
    new_html = html[:start] + f"const schedule = {json_str};\n\n  {end_marker}" + html[end+len(end_marker):]
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)
    print("index.html updated!")
    return True

if __name__ == "__main__":
    url = os.environ.get("PAYLOAD_IMAGE_URL", "").strip() or os.environ.get("INPUT_IMAGE_URL", "").strip()
    print(f"Target URL: {url}")
    if not url:
        print("No URL provided")
        exit(0)
    data = parse_image(url)
    if data and (data.get("toPG") or data.get("toBAT")):
        update_html(data)
    else:
        print("No schedule extracted")
