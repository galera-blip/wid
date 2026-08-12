import os
import re
import json
import requests
from google import genai
from google.genai import types

# Initialize official google-genai client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def get_direct_image_payload(url):
    """
    Downloads image bytes and dynamically resolves Facebook photo pages
    to direct image sources. Returns a tuple: (image_bytes, mime_type).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        content_type = res.headers.get("Content-Type", "").lower()
        
        # If passed URL is a Facebook HTML page, extract the raw image source
        if "text/html" in content_type:
            direct_url = None
            
            # Strategy A: OpenGraph Image Meta Tag (Most reliable on FB)
            og_match = re.search(r'property="og:image"\s+content="([^"]+)"', res.text)
            if og_match:
                direct_url = og_match.group(1).replace("&amp;", "&")
            
            # Strategy B: Fallback regex for scontent CDN links
            if not direct_url:
                scontent_match = re.search(r'https://scontent[^"\\]+', res.text)
                if scontent_match:
                    direct_url = scontent_match.group(0).replace("\\/", "/").replace("&amp;", "&")

            if direct_url:
                print(f"Resolved FB Page to Direct CDN Image: {direct_url[:60]}...")
                img_res = requests.get(direct_url, headers=headers, timeout=15)
                return img_res.content, img_res.headers.get("Content-Type", "image/jpeg").split(";")[0]
            else:
                print(f"Could not resolve direct image URL from HTML page: {url}")
                return None, None
                
        # If it's already a direct image URL (.jpg, .png, .webp)
        return res.content, content_type.split(";")[0]

    except Exception as e:
        print(f"Failed to fetch image: {e}")
        return None, None

def parse_schedule_from_image(image_url, default_company):
    """Extracts schedules from flyer image using Gemini 2.0 Flash."""
    try:
        img_bytes, mime_type = get_direct_image_payload(image_url)
        if not img_bytes:
            return None

        # Standardize fallback mime-type
        if not mime_type or "image" not in mime_type:
            mime_type = "image/jpeg"

        prompt = f"""
        Analyze this ferry schedule flyer image.

        STRICT RULES:
        1. Extract the ferry operator/company name from the graphic header if present. Default to "{default_company}" if not specified.
        2. ONLY extract schedules for routes between "BATANGAS PORT" and "BALATERO PORT" (Puerto Galera).
        3. "BALATERO TO BATANGAS" maps to "toBAT".
        4. "BATANGAS TO BALATERO" maps to "toPG".
        5. If a trip is marked "CANCELLED" or "SUSPENDED", set "status": "CANCELLED" and "note": "CANCELLED TODAY".
        6. Default "type": "Fastcraft". Extract vessel name (e.g. PTERIPPUS 1, ISLAND WATER 1) if available.

        Return ONLY raw JSON in this structure:
        {{
          "toPG": [
            {{"company": "OPERATOR NAME", "type": "Fastcraft", "vessel": "VESSEL NAME", "time": "12:45 PM", "status": "SCHEDULED", "note": ""}}
          ],
          "toBAT": [
            {{"company": "OPERATOR NAME", "type": "Fastcraft", "vessel": "VESSEL NAME", "time": "10:00 AM", "status": "SCHEDULED", "note": ""}}
          ]
        }}
        """

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                prompt,
                types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
            ]
        )

        match = re.search(r'\{[\s\S]*\}', response.text)
        if match:
            return json.loads(match.group(0))
        else:
            print(f"Could not parse JSON from Gemini response: {response.text}")
            return None

    except Exception as err:
        print(f"Error parsing image with Gemini AI: {err}")
        return None

def update_index_html(fresh_schedule):
    """Rewrites index.html with the new extracted schedule."""
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    json_str = json.dumps(fresh_schedule, indent=2)

    updated_html = re.sub(
        r'const schedule = \{[\s\S]*?\};',
        f'const schedule = {json_str};',
        html
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(updated_html)

if __name__ == "__main__":
    combined_schedule = {"toPG": [], "toBAT": []}

    payload_url = os.environ.get("PAYLOAD_IMAGE_URL", "").strip()
    manual_url = os.environ.get("INPUT_IMAGE_URL", "").strip()
    target_url = payload_url or manual_url

    if target_url:
        print(f"Processing flyer image payload: {target_url}")
        data = parse_schedule_from_image(target_url, "Galerian Water Transport Services")
        if data:
            combined_schedule["toPG"].extend(data.get("toPG", []))
            combined_schedule["toBAT"].extend(data.get("toBAT", []))

    if combined_schedule["toPG"] or combined_schedule["toBAT"]:
        update_index_html(combined_schedule)
        print("index.html successfully updated with live schedules!")
    else:
        print("No updates processed.")
