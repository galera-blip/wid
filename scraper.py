import os, re, json, requests
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def get_image_bytes(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    if "text/html" in r.headers.get("Content-Type",""):
        m = re.search(r'property="og:image" content="([^"]+)"', r.text)
        if m:
            r = requests.get(m.group(1).replace("&amp;","&"), headers=headers, timeout=20)
    return r.content

def parse_image(url):
    img = get_image_bytes(url)
    model = genai.GenerativeModel("gemini-2.5-flash")
    resp = model.generate_content([
        "Extract ferry schedule Batangas <-> Balatero. Return ONLY JSON {\"toPG\":[{\"company\":\"\",\"type\":\"Fastcraft\",\"vessel\":\"\",\"time\":\"12:45 PM\",\"status\":\"SCHEDULED\",\"note\":\"\"}],\"toBAT\":[...]}",
        {"mime_type":"image/jpeg","data":img}
    ])
    print(resp.text)
    m = re.search(r'\{[\s\S]*\}', resp.text)
    return json.loads(m.group(0)) if m else None

def update_html(data):
    with open("index.html","r",encoding="utf-8") as f:
        html=f.read()
    start=html.index("const schedule = {")
    end=html.index("let currentDir", start)
    new=f"const schedule = {json.dumps(data,indent=6)};\n\n  let currentDir"
    with open("index.html","w",encoding="utf-8") as f:
        f.write(html[:start]+new+html[end+12:])
    print("Updated!")

url = os.environ.get("PAYLOAD_IMAGE_URL","").strip() or os.environ.get("INPUT_IMAGE_URL","").strip()
print(f"URL: {url[:80]}")
data = parse_image(url) if url else None
if data:
    update_html(data)
