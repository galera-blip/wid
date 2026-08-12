import os, re, json, requests
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(api_version="v1"))

url = (os.environ.get("PAYLOAD_IMAGE_URL","") or os.environ.get("INPUT_IMAGE_URL","")).strip()
print(f"URL: {url[:120]}")
if not url:
    print("No URL"); exit(0)

h={"User-Agent":"Mozilla/5.0"}
r=requests.get(url,headers=h,timeout=30)
print(f"Downloaded {len(r.content)} bytes")
img_bytes=r.content

print("Calling Gemini 2.0-flash...")
resp=client.models.generate_content(
    model="gemini-2.0-flash",
    contents=[
        "Extract ferry schedule. Return ONLY JSON like {\"toPG\":[{\"company\":\"Montenegro\",\"time\":\"7:30 AM\"}],\"toBAT\":[...]}",
        types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
    ]
)
print(resp.text[:2000])
m=re.search(r'\{[\s\S]*\}', resp.text)
data=json.loads(m.group(0))
print(f"Parsed {len(data.get('toPG',[]))} + {len(data.get('toBAT',[]))} trips")

html=open("index.html","r",encoding="utf-8").read()
s=html.index("const schedule = {"); e=html.index("let currentDir", s)
open("index.html","w",encoding="utf-8").write(html[:s]+f"const schedule = {json.dumps(data,indent=2)};\n\n  let currentDir"+html[e+12:])
print("DONE - index.html updated")
