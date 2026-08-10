import os
import re
import json
import requests
import google.generativeai as genai

# Configure Gemini AI using the repository secret
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

PAGES = [
    {"company": "Galerian Water", "username": "galerianwatertransport"},
    {"company": "Island Water", "username": "islandwaterph"}
]

def get_latest_post_image(username):
    """Fetches the latest public image post URL from the target Facebook page."""
    try:
        url = f"https://mbasic.facebook.com/{username}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=10)
        
        # Search for photo links in page source
        match = re.search(r'href="([^"]*photo\.php[^"]*)"', res.text)
        if match:
            photo_page_url = "https://mbasic.facebook.com" + match.group(1).replace("&amp;", "&")
            photo_res = requests.get(photo_page_url, headers=headers, timeout=10)
            
            # Extract image source URL
            img_match = re.search(r'src="([^"]*scontent[^"]*)"', photo_res.text)
            if img_match:
                return img_match.group(1).replace("&amp;", "&")
    except Exception as e:
        print(f"Could not fetch image for {username}: {e}")
    return None

def parse_schedule_from_image(image_url):
    """Sends the flyer image to Gemini Vision AI to extract structured JSON data."""
    try:
        img_data = requests.get(image_url, timeout=15).content
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """
        Analyze this ferry schedule flyer image.
        
        STRICT RULES:
        1. ONLY extract schedules specifically for routes between "BATANGAS" and "BALATERO" (Puerto Galera).
        2. IGNORE all other routes (Calapan, Coron, El Nido, Caticlan, etc.).
        3. If the flyer indicates a trip is CANCELLED or SUSPENDED, include a "note" key with value "CANCELLED TODAY".
        
        Return ONLY valid raw JSON with no markdown formatting wrapping, strictly structured like this:
        {
          "toPG": [
            {"type": "Fastcraft", "company": "Company Name", "time": "6:30 AM"}
          ],
          "toBAT": [
            {"type": "Fastcraft", "company": "Company Name", "time": "6:00 AM"}
          ]
        }
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
    """Rewrites index.html so both plain HTML/JS reflect the updated schedule."""
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    json_str = json.dumps(fresh_schedule, indent=2)
    
    # Replaces the `const schedule = { ... };` block inside index.html
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
        image_url = get_latest_post_image(page["username"])
        if image_url:
            data = parse_schedule_from_image(image_url)
            if data:
                combined_schedule["toPG"].extend(data.get("toPG", []))
                combined_schedule["toBAT"].extend(data.get("toBAT", []))

    if combined_schedule["toPG"] or combined_schedule["toBAT"]:
        update_index_html(combined_schedule)
        print("index.html successfully updated with live schedules!")
    else:
        print("No new updates found or error occurred.")
