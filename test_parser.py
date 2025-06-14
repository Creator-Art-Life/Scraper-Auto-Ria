import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

def test_parse_bmw_page():
    url = "https://auto.ria.com/uk/auto_bmw_x6_38365738.html"
    
    # Use the same headers as in the main script
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'Cookie': 'chk=1; __utmc=79960839; __utmz=79960839.1749807882.1.1.utmcsr=google|utmccn=(organic)|utmcmd=organic|utmctr=(not%20provided); showNewFeatures=7; extendedSearch=1; informerIndex=1; _gcl_au=1.1.696652926.1749807882; _504c2=http://10.42.12.49:3000; _ga=GA1.1.76946374.1749807883; _fbp=fb.1.1749807883050.284932067592788166; gdpr=[2,3]; ui=d166f29f660ec9a4; showNewNextAdvertisement=-10; PHPSESSID=eyJ3ZWJTZXNzaW9uQXZhaWxhYmxlIjp0cnVlLCJ3ZWJQZXJzb25JZCI6MCwid2ViQ2xpZW50SWQiOjM1MTMxODQ5MjcsIndlYkNsaWVudENvZGUiOjE3MTIyNDUxNTYsIndlYkNsaWVudENvb2tpZSI6ImQxNjZmMjlmNjYwZWM5YTQiLCJfZXhwaXJlIjoxNzQ5ODk0NDU3NTA4LCJfbWF4QWdlIjo4NjQwMDAwMH0=; _gcl_au=1.1.696652926.1749807882; __utma=79960839.52955078.1749807882.1749807882.1749888108.2; ria_sid=85621522490013; test_new_features=471; advanced_search_test=42; PHPSESSID=yUVRySHhF47tGqsLEO9GHZLcJq2osvFu; __gads=ID=357ddd82150197a9:T=1749808075:RT=1749890584:S=ALNI_MaYlNw99vGLw5YT57y-3ottkquT8Q; __gpi=UID=0000111e88d3917e:T=1749808075:RT=1749890584:S=ALNI_MYWVbPkvTknD00UY6C0HqFhclQz5w; __eoi=ID=28993b5efa9c0aeb:T=1749808075:RT=1749890584:S=AA-AfjapKWw5csLyi8WbFzcgx7_9; _ga=GA1.1.76946374.1749807883; _clck=124xdts%7C2%7Cfwr%7C0%7C1991; PSP_ID=d6374a6a63b8471567eadc00172e0f0346120a00cde02eb39884db30b0e0cf3313065153; __utmb=79960839.28.10.1749888108; jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1IjoiMTMwNjUxNTMiLCJpYXQiOjE3NDk4OTA2NzksImV4cCI6MTc0OTk3NzA3OX0.bfPkCvRMbzO0Wpx3W1GzqzDTWj3mFMX1lEX8xSYzRs8; FCNEC=%5B%5B%22AKsRol94amvT-sh5pLyQYesxeeqh1ANcAcZv1RruzC5qZWVCeTeRaIYxbKu_zBQ7aUm588xj0OtMrcuHk5D3YHJSRQvi47uuxqB0jkpAJJ9BoaRGHVxoB0ZDsmO0ivZYfN_Tg6ESvQl4AeyAVIW9MfScExiJNTOfGQ%3D%3D%22%5D%5D; _clsk=8eewh6%7C1749890696753%7C5%7C1%7Ci.clarity.ms%2Fcollect; _ga_R4TCZEVX9J=GS2.1.s1749890610$o1$g1$t1749890703$j33$l0$h0; _ga_KGL740D7XD=GS2.1.s1749888109$o2$g1$t1749890899$j60$l0$h2072563748'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("=== TESTING SELLER NAME PARSING ===")
        
        # Test seller name parsing
        seller_tag = soup.find('a', class_='sellerPro')
        if seller_tag:
            seller_name_text = seller_tag.get_text(strip=True)
            if seller_name_text:
                seller_name = seller_name_text
            else:
                # If no text, check for img tag with alt or title attribute
                img_in_seller = seller_tag.find('img')
                if img_in_seller:
                    seller_name_from_alt = img_in_seller.get('alt') or img_in_seller.get('title')
                    if seller_name_from_alt:
                        seller_name = seller_name_from_alt.strip()
                    else:
                        seller_name = "None (from img alt/title fallback)"
                else:
                    seller_name = "None (no img in sellerPro)"
            
            seller_href = seller_tag.get('href')
            print(f"Found sellerPro tag: {seller_tag}")
            print(f"Seller name: '{seller_name}'")
            print(f"Seller href: '{seller_href}'")
        else:
            print("No sellerPro tag found")
            
            # Try fallback
            potential_seller_name_tag = soup.find(['div', 'span', 'p'], class_=re.compile(r'(seller|user|author)[-_]name|contact-person', re.IGNORECASE))
            if potential_seller_name_tag:
                print(f"Found fallback seller tag: {potential_seller_name_tag}")
            else:
                print("No fallback seller tag found")
        
        print("\n=== TESTING IMAGE PARSING ===")
        
        # Test image parsing
        picture_tag = soup.find('picture')
        if picture_tag:
            print(f"Found picture tag: {picture_tag}")
            
            # Look for source with webp
            source_tag = picture_tag.find('source', type='image/webp')
            if source_tag:
                srcset = source_tag.get('srcset')
                print(f"Found webp source srcset: {srcset}")
                if srcset:
                    srcset_urls = srcset.split(',')
                    if srcset_urls:
                        relative_url = srcset_urls[0].strip().split(' ')[0]
                        full_url = urljoin("https://auto.ria.com", relative_url)
                        print(f"Extracted image URL: {full_url}")
            else:
                print("No webp source found in picture tag")
                
            # Check img tag as fallback
            img_tag = picture_tag.find('img')
            if img_tag:
                img_src = img_tag.get('src')
                print(f"Found img tag src: {img_src}")
        else:
            print("No picture tag found")
            
            # Check for any source tags with webp
            all_sources = soup.find_all('source', type='image/webp')
            print(f"Found {len(all_sources)} webp source tags total")
            for i, source in enumerate(all_sources[:3]):  # Show first 3
                print(f"Source {i+1}: {source}")
                
        print("\n=== TESTING ALTERNATIVE IMAGE SELECTORS ===")
        
        # Try different selectors for images
        img_tags = soup.find_all('img')
        print(f"Found {len(img_tags)} img tags total")
        
        # Look for images with car-related URLs
        for img in img_tags[:10]:  # Check first 10
            src = img.get('src') or img.get('data-src')
            if src and ('photo' in src or 'cdn' in src) and 'left-panel' not in src:
                print(f"Potential car image: {src}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_parse_bmw_page() 