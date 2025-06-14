import json
import os
import datetime

DUMP_DIR = "dumps"

def save_data_to_json(all_ads_data):
    if not os.path.exists(DUMP_DIR):
        os.makedirs(DUMP_DIR)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(DUMP_DIR, f"all_ads_data_{timestamp}.json")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_ads_data, f, ensure_ascii=False, indent=4)
    print(f"All collected data saved to {filename}") 