import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
from scraper.config import Config


def fetch_html_with_requests(session, url):
    try:
        response = session.get(url, headers=Config.COMMON_HEADERS)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url} with requests: {e}")
        return None

def collect_ad_urls_from_page(session, page_url):
    html_content = fetch_html_with_requests(session, page_url)
    if not html_content:
        return [], None # Return empty list of urls and no next page url

    soup = BeautifulSoup(html_content, 'html.parser')
    ad_urls = []

    # Try to find ads using the structure for the initial page
    catalog_search_at_div = soup.find('div', class_='span8 box-panel', id='catalogSearchAT')
    if catalog_search_at_div:
        ad_links = catalog_search_at_div.find_all('a', class_='address')
        for link in ad_links:
            href = link.get('href')
            if href:
                ad_urls.append(href)
    else:
        # If not found, try to find ads using the structure for subsequent pages
        search_results_div = soup.find('div', id='searchResults')
        if search_results_div:
            # The provided HTML snippet shows section with class 'ticket-item new__ticket' containing the address link
            # We need to find the actual 'a' tag with class 'address' within these sections
            ad_sections = search_results_div.find_all('section', class_=re.compile(r'ticket-item'))
            for section in ad_sections:
                link = section.find('a', class_='address')
                if link:
                    href = link.get('href')
                    if href:
                        ad_urls.append(href)

    next_page_url = None
    next_page_link = soup.find('a', class_='page-link js-next')
    if next_page_link:
        next_page_url = next_page_link.get('href')

    return ad_urls, next_page_url

# New function to get phone numbers via API
def get_phone_from_ria(session, ad_url):
    # Fetch the ad page HTML first to get hash and expires
    response = session.get(ad_url, headers=Config.COMMON_HEADERS)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    scripts = soup.find_all('script')
    
    hash_val = None
    expires_val = None

    # First, try to find hash and expires in data attributes of script tags
    script_with_data_attrs = soup.find('script', attrs={'data-hash': True, 'data-expires': True})
    if script_with_data_attrs:
        hash_val = script_with_data_attrs.get('data-hash')
        expires_val = script_with_data_attrs.get('data-expires')

    # If not found in data attributes, try to find in script content (existing logic)
    if not hash_val or not expires_val:
        for script in scripts:
            if script.string:
                # Corrected regex for hash and expires
                hash_match = re.search(r'''hash["']?\s*:\s*["']([^'"]+)''', script.string)
                expires_match = re.search(r'''expires["']?\s*:\s*(\d+)''', script.string)
                
                if hash_match and expires_match:
                    hash_val = hash_match.group(1)
                    expires_val = expires_match.group(1)
                    break # Found, no need to continue searching scripts
    
    # Alternative places to find hash if not found in scripts (e.g., data-attributes on button)
    if not hash_val:
        phone_button = soup.find('button', {'data-hash': True})
        if phone_button:
            hash_val = phone_button.get('data-hash')
            # If hash is found here without expires, we might need to make an assumption or find expires elsewhere.
            # For now, if expires is still None, the API call will likely fail, as it's a required parameter.
    
    if hash_val and expires_val:
        ad_id_match = re.search(r'_(\d+)\.html', ad_url)
        if ad_id_match:
            ad_id = ad_id_match.group(1)
            phone_url = f"https://auto.ria.com/users/phones/{ad_id}?hash={hash_val}&expires={expires_val}"
            
            try:
                phone_response = session.get(phone_url, headers=Config.COMMON_HEADERS)
                phone_response.raise_for_status() # Raise HTTP errors
                phone_json = phone_response.json()
                
                extracted_phones = []
                if isinstance(phone_json, dict) and 'phones' in phone_json:
                    for item in phone_json['phones']:
                        if isinstance(item, str):
                            extracted_phones.append(item)
                        elif isinstance(item, dict) and 'phoneFormatted' in item: # Corrected key
                            extracted_phones.append(item['phoneFormatted'])
                elif isinstance(phone_json, list):
                    for item in phone_json:
                        if isinstance(item, str):
                            extracted_phones.append(item)
                
                return extracted_phones
            except requests.exceptions.RequestException as e:
                print(f"Error fetching phone API for {ad_url}: {e}")
            except json.JSONDecodeError:
                print(f"Error decoding phone API JSON for {ad_url}")
        else:
            print(f"Could not extract ad_id from URL: {ad_url}")
    else:
        print(f"Hash or expires not found for {ad_url}. Cannot fetch phone via API.")
    
    return [] # Return empty list if phones cannot be retrieved


def parse_ad_page(url, html_content, session):
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    data = {
        "url": url,
        "title": None,
        "price_usd": None,
        "odometer": None,
        "username": None,
        "phone_number": None,
        "image_url": None,
        "images_count": None,
        "car_number": None,
        "car_vin": None
    }

    # 1. URL (already have it)
    # 2. Title
    title_tag = soup.find('h1', class_='head')
    if title_tag:
        data["title"] = title_tag.get_text(strip=True)
    else:
        # Alternative: New format title
        title_alt = soup.find('div', class_='common-text size-16-20 titleS fw-bold mb-4')
        if title_alt:
            data["title"] = title_alt.get_text(strip=True)

    # 3. Price USD
    price_tag = soup.find('strong', class_='')
    if price_tag:
        price_text = price_tag.get_text(strip=True)
        print(f"DEBUG: Found price_tag with text: '{price_text}'")
        # Remove non-numeric characters except dot and convert to int
        cleaned_price = re.sub(r'[^\d.]', '', price_text)
        print(f"DEBUG: Cleaned price: '{cleaned_price}'")
        try:
            data["price_usd"] = int(float(cleaned_price)) # Convert to float first to handle decimals, then to int
            print(f"DEBUG: Successfully parsed price: {data['price_usd']}")
        except ValueError:
            print(f"DEBUG: ValueError when parsing price: '{cleaned_price}'")
            data["price_usd"] = None
    else:
        print("DEBUG: No price_tag with class='' found")
        # Alternative: New format price
        price_alt = soup.find('span', class_='common-text titleM c-green')
        if price_alt:
            price_text = price_alt.get_text(strip=True)
            print(f"DEBUG: Found price_alt with text: '{price_text}'")
            cleaned_price = re.sub(r'[^\d.]', '', price_text)
            print(f"DEBUG: Cleaned alt price: '{cleaned_price}'")
            try:
                data["price_usd"] = int(float(cleaned_price))
                print(f"DEBUG: Successfully parsed alt price: {data['price_usd']}")
            except ValueError:
                print(f"DEBUG: ValueError when parsing alt price: '{cleaned_price}'")
                data["price_usd"] = None
        else:
            print("DEBUG: No price_alt with class='common-text titleM c-green' found")
    
    # Additional price detection method if previous methods failed
    if data["price_usd"] is None:
        print("DEBUG: Price still None, trying additional methods...")
        # Look for price in strong tag with green color styling
        price_strong_green = soup.find('strong', class_='common-text ws-pre-wrap titleL')
        if price_strong_green:
            style = price_strong_green.get('style', '')
            print(f"DEBUG: Found strong with titleL class, style: '{style}'")
            if 'green' in style.lower() or 'var(--green)' in style:
                price_text = price_strong_green.get_text(strip=True)
                print(f"DEBUG: Found green strong with text: '{price_text}'")
                # Remove non-numeric characters except dot and convert to int
                cleaned_price = re.sub(r'[^\d.]', '', price_text)
                print(f"DEBUG: Cleaned green price: '{cleaned_price}'")
                try:
                    data["price_usd"] = int(float(cleaned_price))
                    print(f"DEBUG: Successfully parsed green price: {data['price_usd']}")
                except ValueError:
                    print(f"DEBUG: ValueError when parsing green price: '{cleaned_price}'")
                    data["price_usd"] = None
            else:
                print("DEBUG: Strong tag found but no green color in style")
        else:
            print("DEBUG: No strong tag with 'common-text ws-pre-wrap titleL' class found")
        
        # If still not found, try any strong tag with green color in style
        if data["price_usd"] is None:
            print("DEBUG: Searching all strong tags for green color...")
            strong_tags = soup.find_all('strong')
            print(f"DEBUG: Found {len(strong_tags)} strong tags total")
            for i, strong_tag in enumerate(strong_tags):
                style = strong_tag.get('style', '')
                text = strong_tag.get_text(strip=True)
                print(f"DEBUG: Strong tag {i+1}: style='{style}', text='{text}'")
                if 'green' in style.lower() or 'var(--green)' in style:
                    price_text = strong_tag.get_text(strip=True)
                    print(f"DEBUG: Found green strong tag with text: '{price_text}'")
                    # Check if text contains currency symbols or price indicators
                    if '$' in price_text or '₴' in price_text or '€' in price_text or re.search(r'\d+.*\d+', price_text):
                        print(f"DEBUG: Text contains currency or price pattern")
                        cleaned_price = re.sub(r'[^\d.]', '', price_text)
                        print(f"DEBUG: Cleaned final price: '{cleaned_price}'")
                        try:
                            data["price_usd"] = int(float(cleaned_price))
                            print(f"DEBUG: Successfully parsed final price: {data['price_usd']}")
                            break
                        except ValueError:
                            print(f"DEBUG: ValueError when parsing final price: '{cleaned_price}'")
                            continue
                    else:
                        print(f"DEBUG: Text doesn't contain currency or price pattern")
            
            if data["price_usd"] is None:
                print("DEBUG: All price parsing methods failed")
        else:
            print(f"DEBUG: Price found via green strong method: {data['price_usd']}")
    else:
        print(f"DEBUG: Price found via primary methods: {data['price_usd']}")

    # 4. Odometer
    odometer_div = soup.find('div', class_='base-information bold')
    if odometer_div:
        odometer_text = odometer_div.get_text(strip=True)
        odometer_match = re.search(r'(\d+)\s*тис\.\s*км', odometer_text)
        if odometer_match:
            try:
                # Convert "95 тыс. км" to 95000
                data["odometer"] = int(odometer_match.group(1)) * 1000
            except ValueError:
                data["odometer"] = None
        else:
            # Try to extract pure number if "тыс. км" is not present (e.g., for new cars)
            pure_num_match = re.search(r'(\d+)', odometer_text)
            if pure_num_match:
                try:
                    data["odometer"] = int(pure_num_match.group(1))
                except ValueError:
                    data["odometer"] = None
            else:
                data["odometer"] = None
    else:
        # Alternative: New format odometer - look for mileage icon and text
        odometer_elements = soup.find_all('div', class_='structure-row ai-center gap-8 flex-1')
        for element in odometer_elements:
            text = element.get_text(strip=True)
            if 'км' in text:
                odometer_match = re.search(r'(\d+)\s*тис\.\s*км', text)
                if odometer_match:
                    try:
                        data["odometer"] = int(odometer_match.group(1)) * 1000
                    except ValueError:
                        data["odometer"] = None
                else:
                    pure_num_match = re.search(r'(\d+)', text)
                    if pure_num_match:
                        try:
                            data["odometer"] = int(pure_num_match.group(1))
                        except ValueError:
                            data["odometer"] = None
                break

    # 5. Username
    seller_tag = soup.find('a', class_='sellerPro')
    if seller_tag:
        # First try to get text content
        username_text = seller_tag.get_text(strip=True)
        if username_text:
            data["username"] = username_text
        else:
            # If no text, check for img tag with alt or title attribute
            img_in_seller = seller_tag.find('img')
            if img_in_seller:
                username_from_alt = img_in_seller.get('alt') or img_in_seller.get('title')
                if username_from_alt:
                    data["username"] = username_from_alt.strip()
                else:
                    data["username"] = None
            else:
                data["username"] = None
    else:
        # NEW SECOND FALLBACK: Look for username in 'seller_info_area' structure
        seller_info_area_div = soup.find('div', class_='seller_info_area')
        if seller_info_area_div:
            seller_info_name_div = seller_info_area_div.find('div', class_='seller_info_name bold')
            if seller_info_name_div:
                data["username"] = seller_info_name_div.get_text(strip=True)
            else:
                data["username"] = None
        else:
            # ORIGINAL SECOND FALLBACK (now third): Look for other common elements that might contain seller name
            potential_username_tag = soup.find(['div', 'span', 'p'], class_=re.compile(r'(seller|user|author)[-_]name|contact-person', re.IGNORECASE))
            if potential_username_tag:
                username_text = potential_username_tag.get_text(strip=True)
                if username_text:
                    data["username"] = username_text
                else:
                    data["username"] = None
            else:
                data["username"] = None

    # 6. Phone Number (Now using API call and taking the first one as BIGINT)
    phones_list = get_phone_from_ria(session, url)
    if phones_list:
        # Take the first phone number and clean it to a pure digit string
        first_phone = phones_list[0]
        cleaned_phone = re.sub(r'[^\d]', '', first_phone)
        try:
            data["phone_number"] = int(cleaned_phone) # Convert to BIGINT
        except ValueError:
            data["phone_number"] = None
    else:
        data["phone_number"] = None

    # 7. Image URL
    data["image_url"] = None

    # Look for actual car photos first (not generic images)
    img_tags = soup.find_all('img')
    for img in img_tags:
        src = img.get('src') or img.get('data-src')
        if src and ('photosnew' in src or 'cdn' in src) and 'left-panel' not in src and 'avatar' not in src:
            # Found a potential car image
            data["image_url"] = urljoin("https://auto.ria.com", src)
            break

    # If no car image found, try the picture tag approach as fallback
    if not data["image_url"]:
        picture_tag = soup.find('picture')
        if picture_tag:
            # Prioritize source with type='image/webp' from srcset
            source_tag = picture_tag.find('source', type='image/webp')
            if source_tag and source_tag.get('srcset'):
                srcset_urls = source_tag.get('srcset').split(',')
                if srcset_urls:
                    relative_url = srcset_urls[0].strip().split(' ')[0]
                    # Skip generic images
                    if 'left-panel' not in relative_url and 'avatar' not in relative_url:
                        data["image_url"] = urljoin("https://auto.ria.com", relative_url)
            
            # Fallback to img tag's src if webp source not found or empty
            if not data["image_url"]:
                img_tag = picture_tag.find('img')
                if img_tag and img_tag.get('src'):
                    relative_url = img_tag.get('src')
                    if 'left-panel' not in relative_url and 'avatar' not in relative_url:
                        data["image_url"] = urljoin("https://auto.ria.com", relative_url)
                elif img_tag and img_tag.get('data-src'):
                    relative_url = img_tag.get('data-src')
                    if 'left-panel' not in relative_url and 'avatar' not in relative_url:
                        data["image_url"] = urljoin("https://auto.ria.com", relative_url)

    # 8. Images Count
    images_count_link = soup.find('a', class_='show-all link-dotted')
    if images_count_link:
        text = images_count_link.get_text(strip=True)
        match = re.search(r'\d+', text)
        if match:
            try:
                data["images_count"] = int(match.group(0))
            except ValueError:
                data["images_count"] = None

    # 9. Car Number
    car_number_span = soup.find('span', class_='state-num ua')
    if car_number_span:
        popup_span = car_number_span.find('span', class_='popup')
        if popup_span:
            popup_span.extract() # Remove the popup text
        data["car_number"] = car_number_span.get_text(strip=True)
    else:
        # Alternative: New format car number
        car_number_alt = soup.find('div', class_='car-number ua')
        if car_number_alt:
            car_number_text = car_number_alt.find('span', class_='common-text ws-pre-wrap badge')
            if car_number_text:
                data["car_number"] = car_number_text.get_text(strip=True)

    # 10. Car VIN
    car_vin_span = soup.find('span', class_='label-vin')
    if not car_vin_span:
        car_vin_span = soup.find('span', class_='vin-code')

    if car_vin_span:
        car_vin_text_raw = car_vin_span.get_text(strip=True)
        car_vin_pattern = r'[A-HJ-NPR-Z0-9]{17}'
        match = re.search(car_vin_pattern, car_vin_text_raw, re.IGNORECASE)
        if match:
            data["car_vin"] = match.group(0)
        else:
            # If a VIN-like pattern isn't found, keep the raw text if it's there
            data["car_vin"] = car_vin_text_raw
    else:
        # Alternative: Look for VIN badge in new format
        car_vin_badges = soup.find_all('span', class_='common-badge contrast medium')
        for badge in car_vin_badges:
            badge_text = badge.get_text(strip=True)
            if 'VIN' in badge_text or 'Перевірений VIN' in badge_text:
                # VIN verification badge found, but actual VIN might be elsewhere
                # Look for VIN in nearby elements or data attributes
                # For now, setting to None if not explicitly found in a VIN field
                data["car_vin"] = None
                break

    return data 