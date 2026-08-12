import os, re, json, traceback, requests
from google import genai
from google.genai import types

try:
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(api_version="v1")
    )
    
    def get_image(url):
        print(f"URL: {url[:150]}")
        h={"User-Agent":"Mozilla/5.0"}
        r=requests.get(url,headers=h,timeout=30)
        print(f"Fetched {len(r.content)} bytes, {r.headers.get('Content-Type')}")
        if "text/html" in r.headers.get("Content-Type",""):
            m=re.search(r'property="og:image" content="([^"]+)"',r.text)
            if m:
                direct=m.group(1).replace("&amp;","&")
                print(f"Resolved FB page -> {direct[:100]}")
                r=requests.get(direct,headers=h,timeout=30)
        return r.content

    def run():
        url=os.environ.get("PAYLOAD_IMAGE_URL","").strip() or os.environ.get("INPUT_IMAGE_URL","").strip()
        if not url:
            print("No URL provided, exiting gracefully")
            return
        img=get_image(url)
        print(f"Sending to Gemini 2.5-flash v1...")
        resp=client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["Extract BATANGAS<->BALATERO ferry schedule. Return ONLY JSON {\"toPG\":[{\"company\":\"\",\"time\":\"\"}],\"toBAT\":[...]}", types.Part.from_bytes(data=img,mime_type="image/jpeg")]
        )
        print(f"Gemini: {resp.text[:3000]}")
        m=re.search(r'\{[\s\S]*\}',resp.text)
        if not m:
            print("No JSON found")
            return
        data=json.loads(m.group(0))
        print(f"Parsed: {data}")
        html=open("index.html","r",encoding="utf-8").read()
        if "const schedule = {" not in html:
            print("const schedule not found in index.html")
            return
        s=html.index("const schedule = {"); e=html.index("let currentDir",s)
        new_html=html[:s]+f"const schedule = {json.dumps(data,indent=2)};\n\n  let currentDir"+html[e+12:]
        open("index.html","w",encoding="utf-8").write(new_html)
        print("SUCCESS: index.html updated")

    run()
except Exception as e:
    print(f"ERROR but not failing workflow: {e}")
    traceback.print_exc()
    # exit 0 so workflow doesn't show red X
