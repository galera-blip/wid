import os
import re
import json
import requests
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

PAGES = [
    {"company": "Galerian Water Transport Services", "url": "https://www.facebook.com/profile.php?id=61556530050083"},
    {"company": "Island Water", "url": "https://www.facebook.com/islandwater.ph"}
]

def get_latest_post_image(page_url):
    """Fallback fetch method."""
    try:
        clean_path = page_url.rstrip("/").split("/")[-1]
        mbasic_url = f"https://mbasic.facebook.com/{clean_path}?v=timeline"
        headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"}
        res = requests.get(mbasic_url, headers=headers, timeout=10)
        matches = re.findall(r'href="([^"]*photo\.php[^"]*)"', res.text)
        if matches:
            photo_page_url = "https://mbasic.facebook.com" + matches[0].replace("&amp;", "&")
            photo_res = requests.get(photo_page_url, headers=headers, timeout=10)
            img_match = re.search(r'src="([^"]*scontent[^"]*)"', photo_res.text)
            if img_match:
                return img_match.group(1).replace("&amp;", "&")
    except Exception as e:
        print(f"Could not fetch image for {page_url}: {e}")
    return None

def parse_schedule_from_image(image_url, default_company):
    """Sends flyer image to Gemini AI to extract schedules."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        img_data = requests.get(image_url, headers=headers, timeout=15).content
        
        # Upgraded to Gemini 2.5 Flash for faster & more accurate visual extraction
        model = genai.GenerativeModel('gemini-2.5-flash')
        
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
        
        response = model.generate_content([
            prompt, 
            {"mime_type": "image/jpeg", "data": img_data}
        ])
        
        # Resilient JSON Extraction
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

    # Check for direct image URLs passed via Make.com or Manual Workflow Input
    payload_url = os.environ.get("PAYLOAD_IMAGE_URL", "").strip()
    manual_url = os.environ.get("INPUT_IMAGE_URL", "").strip()
    target_url = payload_url or manual_url

    if target_url:
        print(f"Processing incoming flyer image: {target_url}")
        data = parse_schedule_from_image(target_url, "Galerian Water Transport Services")
        if data:
            combined_schedule["toPG"].extend(data.get("toPG", []))
            combined_schedule["toBAT"].extend(data.get("toBAT", []))
    else:
        for page in PAGES:
            image_url = get_latest_post_image(page["url"])
            if image_url:
                data = parse_schedule_from_image(image_url, page["company"])
                if data:
                    combined_schedule["toPG"].extend(data.get("toPG", []))
                    combined_schedule["toBAT"].extend(data.get("toBAT", []))

    if combined_schedule["toPG"] or combined_schedule["toBAT"]:
        update_index_html(combined_schedule)
        print("index.html successfully updated with live schedules!")
    else:
        print("No updates processed.")
