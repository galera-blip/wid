import os
import re
import json
import requests
from google import genai
from google.genai import types

# Initialize official google-genai client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

PAGES = [
    {"company": "Galerian Water Transport Services", "url": "https://www.facebook.com/profile.php?id=61556530050083"},
    {"company": "Island Water", "url": "https://www.facebook.com/islandwater.ph"}
]

def get_direct_image_bytes(url):
    """Downloads raw image bytes and resolves HTML photo pages if needed."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    res = requests.get(url, headers=headers, timeout=15)
    
    # If the URL is a Facebook HTML photo page rather than a direct image link
    if "text/html" in res.headers.get("Content-Type", ""):
        match = re.search(r'src="([^"]*scontent[^"]*)"', res.text)
        if match:
            direct_url = match.group(1).replace("&amp;", "&")
            return requests.get(direct_url, headers=headers, timeout=15).content
        else:
            print(f"Could not extract direct image URL from HTML page: {url}")
            return None
            
    return res.content

def parse_schedule_from_image(image_url, default_company):
    """Sends flyer image to Gemini AI to extract schedules."""
    try:
        img_bytes = get_direct_image_bytes(image_url)
        if not img_bytes:
            return None

        prompt = f"""
        Analyze this ferry schedule flyer image.

        STRICT RULES:
        1. ONLY extract schedules for routes between "BATANGAS PORT" and "BALATERO PORT" (Puerto Galera).
        2. "BALATERO TO BATANGAS" maps to "toBAT".
        3. "BATANGAS TO BALATERO" maps to "toPG".
        4. If a trip is marked "CANCELLED" or "SUSPENDED", set "status": "CANCELLED" and "note": "CANCELLED TODAY".
        5. Default "type": "Fastcraft". Extract vessel name (e.g. PTERIPPUS 1) if available.

        Return ONLY raw JSON in this structure:
        {{
          "toPG": [
            {{"company": "{default_company}", "type": "Fastcraft", "vessel": "PTERIPPUS 1", "time": "12:45 PM", "status": "SCHEDULED", "note": ""}}
          ],
          "toBAT": [
            {{"company": "{default_company}", "type": "Fastcraft", "vessel": "PTERIPPUS 1", "time": "10:00 AM", "status": "SCHEDULED", "note": ""}}
          ]
        }}
        """

        # Updated to active model string & modern google-genai SDK
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=img_bytes,
                    mime_type="image/jpeg"
                )
            ]
        )

        match = re.search(r'\{[\s\S]*\}', response.text)
        if match:
            return json.loads(match.group(0))
        else:
            print(f"Could not extract JSON from response: {response.text}")
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
        print(f"Processing incoming flyer image: {target_url}")
        data = parse_schedule_from_image(target_url, "Galerian Water Transport Services")
        if data:
            combined_schedule["toPG"].extend(data.get("toPG", []))
            combined_schedule["toBAT"].extend(data.get("toBAT", []))

    if combined_schedule["toPG"] or combined_schedule["toBAT"]:
        update_index_html(combined_schedule)
        print("index.html successfully updated with live schedules!")
    else:
        print("No updates processed.")
