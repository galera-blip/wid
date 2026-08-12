import os, re, json, requests
from google import genai
from google.genai import types

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options=types.HttpOptions(api_version="v1")
)

def get_image_bytes(url):
    print(f"Input URL: {url[:120]}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = requests.get(url, headers=headers, timeout=30)
    print(f"First fetch: {len(r.content)} bytes, type={r.headers.get('Content-Type')}")
    
    # If Make sent a facebook.com/photo.php link, extract the real image
    if "text/html" in r.headers.get("Content-Type","") or url.startswith("https://www.facebook.com"):
        # try og:image
        m = re.search(r'property="og:image" content="([^"]+)"', r.text)
        if m:
            direct = m.group(1).replace("&amp;","&")
            print(f"Resolved FB page to direct image: {direct[:120]}")
            r2 = requests.get(direct, headers=headers, timeout=30)
            print(f"Second fetch: {len(r2.content)} bytes")
            return r2.content
        # fallback: find scontent URL in page
        m2 = re.search(r'(https://scontent[^"]+\.jpg[^"]*)', r.text)
        if m2:
            direct = m2.group(1).replace("\\","").replace("&amp;","&")
            print(f"Found scontent in page: {direct[:120]}")
            r2 = requests.get(direct, headers=headers, timeout=30)
            return r2.content
        print("ERROR: Could not find image in FB page")
        return None
    return r.content

def parse_image(url):
    img_bytes = get_image_bytes(url)
    if not img_bytes:
        return None
    print(f"Sending {len(img_bytes)} bytes to Gemini 2.5 Flash (v1)")
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            "Extract BATANGAS <-> BALATERO ferry schedule. Return ONLY JSON {\"toPG\": [{\"company\": \"\", \"type\": \"Fastcraft\", \"time\": \"12:45 PM\", \"status\": \"SCHEDULED\", \"note\": \"\"}], \"toBAT\": [...]}",
            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        ]
    )
    print(f"Gemini raw: {resp.text[:2000]}")
    m = re.search(r'\{[\s\S]*\}', resp.text)
    return json.loads(m.group(0)) if m else None

def update_html(data):
    with open("index.html","r",encoding="utf-8") as f:
        html=f.read()
    start=html.index("const schedule = {")
    end=html.index("let currentDir", start)
    new_html = html[:start] + f"const schedule = {json.dumps(data,indent=6)};\n\n  let currentDir" + html[end+12:]
    with open("index.html","w",encoding="utf-8") as f:
        f.write(new_html)
    print("index.html updated!")

if __name__=="__main__":
    url = os.environ.get("PAYLOAD_IMAGE_URL","").strip() or os.environ.get("INPUT_IMAGE_URL","").strip()
    print(f"TARGET URL: {url}")
    if not url:
        print("No URL - Make didn't send image_url in client_payload")
        exit(0)
    data = parse_image(url)
    if data and (data.get("toPG") or data.get("toBAT")):
        update_html(data)
    else:
        print("No schedule extracted - will not push")
