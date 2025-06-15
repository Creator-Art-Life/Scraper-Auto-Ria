import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
from scraper.config import Config


async def fetch_html_with_aiohttp(session, url):
    """Асинхронное получение HTML с помощью aiohttp"""
    try:
        async with session.get(url, headers=Config.COMMON_HEADERS) as response:
            response.raise_for_status()
            return await response.text()
    except aiohttp.ClientError as e:
        print(f"Error fetching {url} with aiohttp: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching {url}: {e}")
        return None

async def collect_ad_urls_from_page(session, page_url):
    """Асинхронный сбор URL объявлений со страницы"""
    html_content = await fetch_html_with_aiohttp(session, page_url)
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

    # Дополнительно ищем ссылки на новые автомобили (newauto)
    # Ищем ссылки в карточках предложений
    proposition_links = soup.find_all('a', class_='proposition_link')
    for link in proposition_links:
        href = link.get('href')
        if href and '/newauto/' in href:
            ad_urls.append(href)
    
    # Также ищем прямые ссылки на newauto в различных контейнерах
    newauto_links = soup.find_all('a', href=re.compile(r'/newauto/auto-'))
    for link in newauto_links:
        href = link.get('href')
        if href and href not in ad_urls:
            ad_urls.append(href)

    # Ищем ссылки в списках автосалонов
    autosalon_ad_links = soup.find_all('a', href=re.compile(r'auto-.*-\d+\.html'))
    for link in autosalon_ad_links:
        href = link.get('href')
        if href and href not in ad_urls:
            # Проверяем, что это не ссылка на автосалон, а на объявление
            if '/auto-' in href and not '/autosalons/' in href:
                ad_urls.append(href)

    next_page_url = None
    next_page_link = soup.find('a', class_='page-link js-next')
    if next_page_link:
        next_page_url = next_page_link.get('href')

    return ad_urls, next_page_url

async def get_phone_from_ria(session, ad_url):
    """Асинхронное получение номера телефона через API (улучшенная версия)"""
    try:
        # Fetch the ad page HTML first to get hash and expires
        async with session.get(ad_url, headers=Config.COMMON_HEADERS) as response:
            response.raise_for_status()
            content = await response.text()
            
        soup = BeautifulSoup(content, 'html.parser')
        
        hash_val = None
        expires_val = None

        # Метод 1: Поиск в data-атрибутах элементов
        elements_with_data = soup.find_all(attrs={'data-hash': True})
        for elem in elements_with_data:
            hash_val = elem.get('data-hash')
            expires_val = elem.get('data-expires')
            if hash_val and expires_val:
                break

        # Метод 2: Поиск в JavaScript коде
        if not hash_val or not expires_val:
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    script_content = script.string
                    
                    # Различные паттерны для поиска hash и expires
                    hash_patterns = [
                        r'''hash["']?\s*:\s*["']([^'"]+)["']''',
                        r'''["']hash["']?\s*:\s*["']([^'"]+)["']''',
                        r'''hash\s*=\s*["']([^'"]+)["']''',
                        r'''data-hash\s*=\s*["']([^'"]+)["']''',
                    ]
                    
                    expires_patterns = [
                        r'''expires["']?\s*:\s*(\d+)''',
                        r'''["']expires["']?\s*:\s*(\d+)''',
                        r'''expires\s*=\s*(\d+)''',
                        r'''data-expires\s*=\s*["']?(\d+)["']?''',
                    ]
                    
                    # Ищем hash
                    if not hash_val:
                        for pattern in hash_patterns:
                            match = re.search(pattern, script_content)
                            if match:
                                hash_val = match.group(1)
                                break
                    
                    # Ищем expires
                    if not expires_val:
                        for pattern in expires_patterns:
                            match = re.search(pattern, script_content)
                            if match:
                                expires_val = match.group(1)
                                break
                    
                    # Если нашли оба значения, прекращаем поиск
                    if hash_val and expires_val:
                        break

        # Метод 3: Поиск в кнопках и ссылках с телефонами
        if not hash_val or not expires_val:
            phone_elements = soup.find_all(['button', 'a', 'span'], class_=re.compile(r'phone|contact', re.IGNORECASE))
            for elem in phone_elements:
                if not hash_val:
                    hash_val = elem.get('data-hash')
                if not expires_val:
                    expires_val = elem.get('data-expires')
                if hash_val and expires_val:
                    break

        # Метод 4: Поиск в любых элементах с data-hash или data-expires
        if not hash_val:
            hash_elem = soup.find(attrs={'data-hash': True})
            if hash_elem:
                hash_val = hash_elem.get('data-hash')
        
        if not expires_val:
            expires_elem = soup.find(attrs={'data-expires': True})
            if expires_elem:
                expires_val = expires_elem.get('data-expires')

        # Если нашли hash и expires, делаем запрос к API
        if hash_val and expires_val:
            ad_id_match = re.search(r'_(\d+)\.html', ad_url)
            if ad_id_match:
                ad_id = ad_id_match.group(1)
                phone_url = f"https://auto.ria.com/users/phones/{ad_id}?hash={hash_val}&expires={expires_val}"
                
                try:
                    async with session.get(phone_url, headers=Config.COMMON_HEADERS) as phone_response:
                        phone_response.raise_for_status()
                        phone_json = await phone_response.json()
                        
                        extracted_phones = []
                        
                        # Обрабатываем различные форматы ответа API
                        if isinstance(phone_json, dict):
                            if 'phones' in phone_json:
                                for item in phone_json['phones']:
                                    if isinstance(item, str):
                                        extracted_phones.append(item)
                                    elif isinstance(item, dict):
                                        # Пробуем различные ключи для номера телефона
                                        phone_keys = ['phoneFormatted', 'phone', 'number', 'phoneNumber']
                                        for key in phone_keys:
                                            if key in item and item[key]:
                                                extracted_phones.append(str(item[key]))
                                                break
                            elif 'phone' in phone_json:
                                extracted_phones.append(str(phone_json['phone']))
                        elif isinstance(phone_json, list):
                            for item in phone_json:
                                if isinstance(item, str):
                                    extracted_phones.append(item)
                                elif isinstance(item, dict):
                                    phone_keys = ['phoneFormatted', 'phone', 'number', 'phoneNumber']
                                    for key in phone_keys:
                                        if key in item and item[key]:
                                            extracted_phones.append(str(item[key]))
                                            break
                        
                        return extracted_phones
                        
                except aiohttp.ClientError as e:
                    print(f"Error fetching phone API for {ad_url}: {e}")
                except json.JSONDecodeError as e:
                    print(f"Error decoding phone API JSON for {ad_url}: {e}")
            else:
                print(f"Could not extract ad_id from URL: {ad_url}")
        else:
            print(f"Hash or expires not found for {ad_url}. Hash: {hash_val}, Expires: {expires_val}")
        
    except Exception as e:
        print(f"Error in get_phone_from_ria for {ad_url}: {e}")
    
    return [] # Return empty list if phones cannot be retrieved


async def parse_ad_page(url, html_content, session):
    """Асинхронный парсинг страницы объявления"""
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Определяем тип страницы по URL
    is_newauto = '/newauto/' in url
    
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

    if is_newauto:
        # Парсинг для новых автомобилей (newauto)
        return await parse_newauto_page(url, soup, session, data)
    else:
        # Парсинг для обычных объявлений
        return await parse_regular_ad_page(url, soup, session, data)


async def parse_newauto_page(url, soup, session, data):
    """Парсинг страницы нового автомобиля (newauto)"""
    
    # 1. Title - из h1 с классом auto-head_title
    title_element = soup.find('h1', class_='auto-head_title')
    if title_element:
        # Извлекаем текст из strong и div элементов
        strong_text = title_element.find('strong')
        div_text = title_element.find('div', class_='auto-head_base')
        
        title_parts = []
        if strong_text:
            title_parts.append(strong_text.get_text(strip=True))
        if div_text:
            title_parts.append(div_text.get_text(strip=True))
        
        data["title"] = " ".join(title_parts) if title_parts else None
    
    # 2. Price USD - из div с классом auto-price
    price_container = soup.find('div', class_='auto-price')
    if price_container:
        # Ищем цену в долларах
        price_text = price_container.get_text()
        # Ищем паттерн "число $"
        import re
        dollar_match = re.search(r'(\d+(?:\s*\d+)*)\s*\$', price_text.replace(' ', ''))
        if dollar_match:
            price_str = dollar_match.group(1).replace(' ', '').replace(',', '')
            try:
                data["price_usd"] = int(price_str)
            except ValueError:
                data["price_usd"] = None
    
    # 3. Odometer - для новых авто обычно 0 или небольшой пробіг
    # Ищем в комментарии автосалона или устанавливаем 0
    description_section = soup.find('section', class_='description_by_autosalon')
    if description_section:
        description_text = description_section.get_text()
        # Ищем упоминание пробега
        mileage_match = re.search(r'Пробіг\s*(\d+)\s*км', description_text)
        if mileage_match:
            try:
                data["odometer"] = int(mileage_match.group(1))
            except ValueError:
                data["odometer"] = 0
        else:
            data["odometer"] = 0
    else:
        data["odometer"] = 0
    
    # 4. Username - из информации об автосалоне
    seller_info = soup.find('div', class_='seller_info_name')
    if seller_info:
        seller_link = seller_info.find('a')
        if seller_link:
            strong_element = seller_link.find('strong', class_='name')
            if strong_element:
                # Убираем иконку верификации из текста
                username_text = strong_element.get_text(strip=True)
                data["username"] = username_text
    
    # 5. Phone Number - из кнопки с телефоном
    phone_button = soup.find('span', class_='conversion_phone_newcars')
    if phone_button:
        phone_text = phone_button.get_text(strip=True)
        # Извлекаем номер телефона и очищаем от символов
        cleaned_phone = re.sub(r'[^\d]', '', phone_text)
        if cleaned_phone:
            try:
                data["phone_number"] = int(cleaned_phone)
            except ValueError:
                data["phone_number"] = None
    
    # 6. Image URL - из галереи изображений
    # Ищем первое изображение в галерее
    gallery_slide = soup.find('div', class_='image-gallery-slide center')
    if gallery_slide:
        picture_element = gallery_slide.find('picture')
        if picture_element:
            # Приоритет webp источнику
            source_webp = picture_element.find('source', type='image/webp')
            if source_webp and source_webp.get('srcset'):
                srcset = source_webp.get('srcset')
                # Берем первый URL из srcset
                first_url = srcset.split(',')[0].strip().split(' ')[0]
                data["image_url"] = first_url
            else:
                # Fallback на img элемент
                img_element = picture_element.find('img')
                if img_element and img_element.get('src'):
                    data["image_url"] = img_element.get('src')
    
    # 7. Images Count - из лейбла с количеством фото
    photo_label = soup.find('label', class_='panoram-tab-item')
    if photo_label:
        label_text = photo_label.get_text(strip=True)
        # Извлекаем число из текста
        count_match = re.search(r'(\d+)', label_text)
        if count_match:
            try:
                data["images_count"] = int(count_match.group(1))
            except ValueError:
                data["images_count"] = None
    
    # 8. Car Number - для новых авто обычно отсутствует
    data["car_number"] = None
    
    # 9. Car VIN - ищем в секции проверки
    vin_section = soup.find('section', class_='vin_checked')
    if vin_section:
        vin_items = vin_section.find_all('li')
        for item in vin_items:
            item_text = item.get_text(strip=True)
            # Ищем VIN-подобную строку
            vin_match = re.search(r'([A-HJ-NPR-Z0-9]{17})', item_text, re.IGNORECASE)
            if vin_match:
                data["car_vin"] = vin_match.group(1)
                break
            # Также ищем частично скрытый VIN
            partial_vin_match = re.search(r'([A-HJ-NPR-Z0-9]+х[A-HJ-NPR-Z0-9]+х+\d+)', item_text, re.IGNORECASE)
            if partial_vin_match:
                data["car_vin"] = partial_vin_match.group(1)
                break
    
    return data


async def parse_regular_ad_page(url, soup, session, data):
    """Парсинг обычной страницы объявления (обновленная логика)"""
    
    # 1. URL (already have it)
    # 2. Title - обновленные селекторы
    title_tag = soup.find('h1', class_='head')
    if not title_tag:
        # Новые варианты селекторов для заголовка
        title_tag = soup.find('h1', class_='auto-head_title')
        if not title_tag:
            title_tag = soup.find('h1')
            if not title_tag:
                # Ищем в div с классами, содержащими title
                title_tag = soup.find('div', class_=re.compile(r'title|head', re.IGNORECASE))
                if not title_tag:
                    # Последний вариант - ищем любой элемент с большим текстом в начале страницы
                    potential_titles = soup.find_all(['h1', 'h2', 'div'], limit=10)
                    for elem in potential_titles:
                        text = elem.get_text(strip=True)
                        if len(text) > 10 and any(word in text.lower() for word in ['kia', 'toyota', 'bmw', 'mercedes', 'audi', 'volkswagen', 'ford', 'hyundai', 'nissan', 'honda']):
                            title_tag = elem
                            break
    
    if title_tag:
        data["title"] = title_tag.get_text(strip=True)
    else:
        # Агрессивный поиск заголовка по тексту страницы
        page_text = soup.get_text()
        # Ищем паттерны типа "Марка Модель год"
        title_patterns = [
            r'((?:Kia|Toyota|BMW|Mercedes|Audi|Volkswagen|Ford|Hyundai|Nissan|Honda|Mazda|Lexus|Renault|Peugeot|Citroën|Skoda|Seat|Volvo|Subaru|Mitsubishi|Suzuki|Infiniti|Acura|Cadillac|Chevrolet|Chrysler|Dodge|Jeep|Lincoln|Buick|GMC|Hummer|Pontiac|Saturn|Saab|Jaguar|Land Rover|Bentley|Rolls-Royce|Aston Martin|Maserati|Ferrari|Lamborghini|Porsche|McLaren|Bugatti|Koenigsegg|Pagani|Alfa Romeo|Fiat|Lancia|Mini|Smart|Dacia|Lada|UAZ|GAZ|ZAZ|Chery|Geely|BYD|Great Wall|Haval|Changan|JAC|Lifan|MG|Ssangyong|Daewoo|Hyundai|Kia)\s+[A-Za-z0-9\-\s]+(?:20\d{2}|19\d{2})?)',
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                potential_title = match.group(1).strip()
                if len(potential_title) > 5:
                    data["title"] = potential_title
                    break

    # 3. Price USD - улучшенный парсинг цены
    data["price_usd"] = None
    
    # Метод 1: Ищем цену в долларах по тексту
    price_patterns = [
        r'(\d+(?:\s*\d+)*)\s*\$',  # "19650 $"
        r'\$\s*(\d+(?:\s*\d+)*)',  # "$ 19650"
        r'(\d+(?:,\d+)*)\s*USD',   # "19,650 USD"
    ]
    
    page_text = soup.get_text()
    for pattern in price_patterns:
        matches = re.findall(pattern, page_text.replace(' ', ''))
        for match in matches:
            try:
                price_num = int(match.replace(',', '').replace(' ', ''))
                if 1000 <= price_num <= 1000000:  # Разумный диапазон цен для авто
                    data["price_usd"] = price_num
                    break
            except ValueError:
                continue
        if data["price_usd"]:
            break
    
    # Метод 2: Ищем в элементах с зеленым цветом (обычно цена)
    if not data["price_usd"]:
        green_elements = soup.find_all(['span', 'strong', 'div'], style=re.compile(r'color.*green|var\(--green\)', re.IGNORECASE))
        green_elements.extend(soup.find_all(['span', 'strong', 'div'], class_=re.compile(r'green|price', re.IGNORECASE)))
        
        for elem in green_elements:
            text = elem.get_text(strip=True)
            if '$' in text or 'USD' in text:
                price_match = re.search(r'(\d+(?:,\d+)*)', text.replace(' ', ''))
                if price_match:
                    try:
                        price_num = int(price_match.group(1).replace(',', ''))
                        if 1000 <= price_num <= 1000000:
                            data["price_usd"] = price_num
                            break
                    except ValueError:
                        continue

    # 4. Odometer - улучшенный парсинг пробега
    data["odometer"] = None
    
    # Ищем пробег по различным паттернам
    odometer_patterns = [
        r'(\d+)\s*тис\.\s*км',     # "95 тис. км"
        r'(\d+)\s*тыс\.\s*км',     # "95 тыс. км"
        r'(\d+)\s*000\s*км',       # "95 000 км"
        r'(\d+)\s*км',             # "95000 км"
    ]
    
    page_text = soup.get_text()
    for pattern in odometer_patterns:
        matches = re.findall(pattern, page_text)
        for match in matches:
            try:
                odometer_num = int(match)
                if pattern.endswith(r'тис\.\s*км') or pattern.endswith(r'тыс\.\s*км'):
                    odometer_num *= 1000  # Конвертируем тысячи в полное число
                if 0 <= odometer_num <= 1000000:  # Разумный диапазон пробега
                    data["odometer"] = odometer_num
                    break
            except ValueError:
                continue
        if data["odometer"] is not None:
            break
    
    # Альтернативный поиск в структурированных элементах
    if data["odometer"] is None:
        odometer_elements = soup.find_all(['div', 'span'], class_=re.compile(r'mileage|odometer|base-information', re.IGNORECASE))
        for elem in odometer_elements:
            text = elem.get_text(strip=True)
            if 'км' in text:
                for pattern in odometer_patterns:
                    match = re.search(pattern, text)
                    if match:
                        try:
                            odometer_num = int(match.group(1))
                            if pattern.endswith(r'тис\.\s*км') or pattern.endswith(r'тыс\.\s*км'):
                                odometer_num *= 1000
                            if 0 <= odometer_num <= 1000000:
                                data["odometer"] = odometer_num
                                break
                        except ValueError:
                            continue
                if data["odometer"] is not None:
                    break
    
    # Дополнительный поиск пробега в любом тексте на странице
    if data["odometer"] is None:
        page_text = soup.get_text()
        # Ищем пробег в формате "123 тыс. км" или "123000 км"
        odometer_text_patterns = [
            r'(\d+)\s*тис\.\s*км',
            r'(\d+)\s*тыс\.\s*км', 
            r'(\d+)\s*000\s*км',
            r'Пробіг[:\s]*(\d+)\s*тис\.\s*км',
            r'Пробіг[:\s]*(\d+)\s*тыс\.\s*км',
            r'Пробіг[:\s]*(\d+)\s*км',
        ]
        
        for pattern in odometer_text_patterns:
            matches = re.findall(pattern, page_text)
            for match in matches:
                try:
                    odometer_num = int(match)
                    if 'тис' in pattern or 'тыс' in pattern:
                        odometer_num *= 1000
                    if 1000 <= odometer_num <= 500000:  # Разумный диапазон
                        data["odometer"] = odometer_num
                        break
                except ValueError:
                    continue
            if data["odometer"] is not None:
                break

    # 5. Username - улучшенный парсинг имени продавца
    data["username"] = None
    
    # Метод 1: Классические селекторы
    username_selectors = [
        ('a', 'sellerPro'),
        ('div', 'seller_info_name'),
        ('div', 'seller-info-name'),
        ('span', 'seller-name'),
        ('div', re.compile(r'seller.*name|contact.*person', re.IGNORECASE)),
    ]
    
    for tag, class_pattern in username_selectors:
        if isinstance(class_pattern, str):
            elem = soup.find(tag, class_=class_pattern)
        else:
            elem = soup.find(tag, class_=class_pattern)
        
        if elem:
            username_text = elem.get_text(strip=True)
            if username_text and len(username_text) > 1:
                data["username"] = username_text
                break
    
    # Метод 2: Поиск по ссылкам на профили продавцов
    if not data["username"]:
        profile_links = soup.find_all('a', href=re.compile(r'/users/|/seller/|/profile/', re.IGNORECASE))
        for link in profile_links:
            text = link.get_text(strip=True)
            if text and len(text) > 1 and len(text) < 50:  # Разумная длина имени
                data["username"] = text
                break
    
    # Метод 3: Поиск в тексте страницы по паттернам
    if not data["username"]:
        page_text = soup.get_text()
        # Ищем паттерны типа "Продавець: Имя" или "Контакт: Имя"
        username_patterns = [
            r'Продавець[:\s]+([А-Яа-яA-Za-z\s]{2,30})',
            r'Контакт[:\s]+([А-Яа-яA-Za-z\s]{2,30})',
            r'Власник[:\s]+([А-Яа-яA-Za-z\s]{2,30})',
            r'Менеджер[:\s]+([А-Яа-яA-Za-z\s]{2,30})',
        ]
        
        for pattern in username_patterns:
            match = re.search(pattern, page_text)
            if match:
                potential_username = match.group(1).strip()
                # Проверяем, что это не служебный текст
                if not any(word in potential_username.lower() for word in ['показать', 'телефон', 'номер', 'контакт', 'інформація']):
                    data["username"] = potential_username
                    break

    # 6. Phone Number (Now using async API call and taking the first one as BIGINT)
    phones_list = await get_phone_from_ria(session, url)
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


async def process_ad_batch(session, ad_urls, existing_ad_urls, semaphore):
    """Асинхронная обработка пакета объявлений с ограничением количества одновременных запросов"""
    results = []
    
    async def process_single_ad(ad_url):
        async with semaphore:  # Ограничиваем количество одновременных запросов
            if ad_url in existing_ad_urls:
                print(f"⏭️  Skipping already processed ad: {ad_url}")
                return None

            print(f"🔄 Processing ad: {ad_url}")
            try:
                ad_page_html = await fetch_html_with_aiohttp(session, ad_url)
                if ad_page_html:
                    ad_data = await parse_ad_page(ad_url, ad_page_html, session)
                    if ad_data:
                        print("    --- Advertisement Data ---")
                        for key, value in ad_data.items():
                            print(f"    {key.replace('_', ' ').title()}: {value}")
                        print("    --------------------------")
                        return ad_data
                    else:
                        print(f"    ❌ Failed to parse advertisement data for {ad_url}.")
                else:
                    print(f"    ❌ Failed to fetch ad page: {ad_url}")
            except Exception as e:
                print(f"    ❌ Error processing ad {ad_url}: {e}")
            return None

    # Обрабатываем все объявления параллельно
    print(f"🚀 Starting parallel processing of {len(ad_urls)} ads...")
    tasks = [process_single_ad(ad_url) for ad_url in ad_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Фильтруем успешные результаты
    successful_results = []
    error_count = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"❌ Error processing ad {ad_urls[i]}: {result}")
            error_count += 1
        elif result is not None:
            successful_results.append(result)
    
    print(f"📊 Batch processing complete: {len(successful_results)} successful, {error_count} errors, {len(ad_urls) - len(successful_results) - error_count} skipped")
    return successful_results


# Функции совместимости для обратной совместимости с синхронным кодом
def fetch_html_with_requests(session, url):
    """Синхронная обертка для совместимости (deprecated)"""
    import warnings
    warnings.warn("fetch_html_with_requests is deprecated, use fetch_html_with_aiohttp", DeprecationWarning)
    
    import requests
    try:
        response = session.get(url, headers=Config.COMMON_HEADERS)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url} with requests: {e}")
        return None 