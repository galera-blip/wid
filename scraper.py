import os
import re
import json
import requests
import google.generativeai as genai

# Configure Gemini AI using the repository secret
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Direct Facebook Page URLs
PAGES = [
    {"company": "Galerian Water Transport Services", "url": "https://www.facebook.com/profile.php?id=61556530050083"},
    {"company": "Island Water", "url": "https://www.facebook.com/islandwater.ph"}
]

def get_latest_post_image(page_url):
    """Converts standard FB URL to mbasic and fetches the latest photo post URL."""
    try:
        clean_path = page_url.rstrip("/").split("/")[-1]
        mbasic_url = f"https://mbasic.facebook.com/{clean_path}"
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(mbasic_url, headers=headers, timeout=10)
        
        match = re.search(r'href="([^"]*photo\.php[^"]*)"', res.text)
        if match:
            photo_page_url = "https://mbasic.facebook.com" + match.group(1).replace("&amp;", "&")
            photo_res = requests.get(photo_page_url, headers=headers, timeout=10)
            
            img_match = re.search(r'src="([^"]*scontent[^"]*)"', photo_res.text)
            if img_match:
                return img_match.group(1).replace("&amp;", "&")
    except Exception as e:
        print(f"Could not fetch image for {page_url}: {e}")
    return None

def parse_schedule_from_image(image_url, default_company):
    """Sends flyer image to Gemini Vision AI with explicit cancellation tracking."""
    try:
        img_data = requests.get(image_url, timeout=15).content
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Analyze this ferry schedule flyer image.
        
        STRICT EXTRACTION RULES:
        1. ONLY extract schedules for routes between "BATANGAS PORT" and "BALATERO PORT" (Puerto Galera).
        2. "BALATERO TO BATANGAS" maps to "toBAT".
        3. "BATANGAS TO BALATERO" maps to "toPG".
        4. DO NOT ignore cancelled trips! If a trip schedule stamp says "CANCELLED", "SUSPENDED", or "NO TRIP", extract the time anyway and add:
           - "status": "CANCELLED"
           - "note": "CANCELLED TODAY" (or specific reason if stated)
        5. If a trip is running normally, set "status": "SCHEDULED" and "note": "".
        6. Extract the vessel name (e.g., PTERIPPUS 1) into the "vessel" key. Use "{default_company}" as default company if not specified.

        Return ONLY raw JSON in this structure:
        {{
          "date": "Extracted date on poster (e.g. August 9, 2026)",
          "toPG": [
            {{
              "company": "{default_company}",
              "vessel": "PTERIPPUS 1",
              "time": "9:45 AM",
              "status": "CANCELLED",
              "note": "CANCELLED TODAY"
            }}
          ],
          "toBAT": [
            {{
              "company": "{default_company}",
              "vessel": "PTERIPPUS 1",
              "time": "6:00 AM",
              "status": "CANCELLED",
              "note": "CANCELLED TODAY"
            }}
          ]
        }}
        """
        
        response = model.generate_content([
            prompt, 
            {"mime_type": "image/jpeg", "data": img_data}
        ])
        
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as err:
        print(f"Error parsing image with Gemini AI: {err}")
        return None

def update_index_html(fresh_schedule):
    """Rewrites index.html JS data block to include updated schedules and cancellation notes."""
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

    for page in PAGES:
        image_url = get_latest_post_image(page["url"])
        if image_url:
            data = parse_schedule_from_image(image_url, page["company"])
            if data:
                combined_schedule["toPG"].extend(data.get("toPG", []))
                combined_schedule["toBAT"].extend(data.get("toBAT", []))

    if combined_schedule["toPG"] or combined_schedule["toBAT"]:
        update_index_html(combined_schedule)
        print("index.html successfully updated with live schedules and statuses!")
    else:
        print("No new updates found or error occurred.")
