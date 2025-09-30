#!/usr/bin/env python3
"""
EIP.GG Icarus Database Scraper - Updated with correct categories
Multi-threaded version for faster scraping

Installation:
pip install requests beautifulsoup4 lxml

Usage:
python RecipeScraping.py
"""

import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# EIP.GG category URLs - Updated to match actual website categories
CATEGORIES = {
    "ammunition": "https://eip.gg/icarus/db/ammunition/",
    "armor": "https://eip.gg/icarus/db/armor/",
    "construction_materials": "https://eip.gg/icarus/db/construction-materials/",
    "consumables": "https://eip.gg/icarus/db/consumables/",
    "deployables": "https://eip.gg/icarus/db/deployables/",
    "elements_crafted": "https://eip.gg/icarus/db/elements-crafted/",
    "elements_raw": "https://eip.gg/icarus/db/elements-raw/",
    "orbital": "https://eip.gg/icarus/db/orbital/",
    "processing": "https://eip.gg/icarus/db/processing/",
    "status_effects": "https://eip.gg/icarus/db/status-effects/",
    "tools": "https://eip.gg/icarus/db/tools/",
    "weapons": "https://eip.gg/icarus/db/weapons/",
    "work_benches": "https://eip.gg/icarus/db/work-benches/"
}

# Thread-safe counter
counter_lock = Lock()

def get_items_from_category(category_url):
    """Get all item links from a category page"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(category_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        item_links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '/icarus/db/' in href and href != category_url:
                if not href.startswith('http'):
                    href = 'https://eip.gg' + href
                
                if href not in item_links and href.endswith('/'):
                    item_links.append(href)
        
        return item_links
        
    except Exception as e:
        print(f"    [ERROR] Failed to fetch category: {e}")
        return []

def extract_item_data(item_url, quiet=True):
    """Extract item data from an EIP.GG item page"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    item_name_slug = item_url.rstrip('/').split('/')[-1]
    
    item_data = {
        "name": item_name_slug.replace('-', ' ').title(),
        "ingredients": {},
        "crafted_at": "Unknown",
        "category": "",
        "tier": 0,
        "url": item_url,
        "crafting_stations": []
    }
    
    try:
        response = requests.get(item_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        page_text = soup.get_text()
        
        # Extract crafting station
        crafted_match = re.search(r'Crafted at\s+(.+?)(?:\.|$|\n)', page_text, re.IGNORECASE)
        if crafted_match:
            station = crafted_match.group(1).strip()
            item_data['crafted_at'] = station
            item_data['crafting_stations'] = [station]
        
        # Extract required materials (allow multi-line)
        materials_match = re.search(r'Required Materials[:\s]+(.+?)(?:\.\s|\n\n|$)', page_text, re.IGNORECASE | re.DOTALL)
        if materials_match:
            materials_text = materials_match.group(1).strip()
            materials_text = ' '.join(materials_text.split())
            
            material_pattern = r'([A-Za-z\s\-]+)\s*\((\d+)\)'
            for material_match in re.finditer(material_pattern, materials_text):
                material_name = material_match.group(1).strip()
                quantity = int(material_match.group(2))
                item_data['ingredients'][material_name] = quantity
        
        # Extract tier
        tier_match = re.search(r'(?:Tech\s+)?Tier\s+(\d+)', page_text, re.IGNORECASE)
        if tier_match:
            item_data['tier'] = int(tier_match.group(1))
        
        # Get proper item name
        title_elem = soup.find('h1') or soup.find('title')
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            title_text = re.split(r'\s*[-–|]\s*(?:ICARUS|EIP|Gaming)', title_text)[0].strip()
            if title_text and len(title_text) < 100:
                item_data['name'] = title_text
        
        return item_data
        
    except Exception as e:
        if not quiet:
            print(f"      [ERROR] {item_url}: {e}")
        return item_data

def scrape_all_items(output_dir="icarus_data", max_workers=5):
    """Scrape all items from EIP.GG using multiple threads"""
    
    print("="*70)
    print("  EIP.GG ICARUS DATABASE SCRAPER (MULTI-THREADED)")
    print("="*70)
    print(f"\nUsing {max_workers} threads for faster scraping")
    print("Scraping from https://eip.gg/icarus/db/\n")
    
    os.makedirs(output_dir, exist_ok=True)
    
    all_items = {}
    total_items = 0
    failed_items = 0
    
    # Process each category
    for category_key, category_url in CATEGORIES.items():
        print(f"\n{'='*70}")
        print(f"PROCESSING: {category_key.upper()}")
        print(f"{'='*70}")
        
        all_items[category_key] = []
        
        # Get all item links
        print(f"Fetching item list from {category_url}...")
        item_links = get_items_from_category(category_url)
        
        if not item_links:
            print(f"  No items found")
            continue
        
        print(f"Found {len(item_links)} items. Scraping...")
        
        # Use ThreadPoolExecutor for parallel scraping
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(extract_item_data, url, quiet=True): url 
                for url in item_links
            }
            
            # Process completed tasks
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    item_data = future.result()
                    if item_data:
                        item_data["category"] = category_key
                        all_items[category_key].append(item_data)
                        
                        with counter_lock:
                            total_items += 1
                            completed += 1
                            
                        # Progress indicator
                        if completed % 10 == 0 or completed == len(item_links):
                            print(f"  Progress: {completed}/{len(item_links)} items", end='\r')
                    else:
                        failed_items += 1
                        
                except Exception as e:
                    print(f"\n  [ERROR] {url}: {e}")
                    failed_items += 1
        
        print(f"\n  Completed: {completed}/{len(item_links)} items")
    
    # Save files
    print(f"\n{'='*70}")
    print("SAVING JSON FILES")
    print(f"{'='*70}")
    
    for category_key, items in all_items.items():
        if not items:
            continue
        
        filepath = os.path.join(output_dir, f"{category_key}.json")
        
        # Convert category key to display name
        display_name = category_key.replace('_', ' ').title()
        
        data = {
            "category": display_name,
            "count": len(items),
            "items": sorted(items, key=lambda x: x['name'])
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  {category_key}.json ({len(items)} items)")
    
    # Save summary
    summary = {
        "total_items": total_items,
        "failed_items": failed_items,
        "categories": {k: len(v) for k, v in all_items.items() if v},
        "scrape_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://eip.gg/icarus/db/"
    }
    
    summary_path = os.path.join(output_dir, "_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print("SCRAPING COMPLETE")
    print(f"{'='*70}")
    print(f"Total items: {total_items}")
    print(f"Failed: {failed_items}")
    print(f"Output: {output_dir}/")
    print(f"{'='*70}")

def test_single_item(item_url=None):
    """Test scraping a single item"""
    
    if not item_url:
        item_url = "https://eip.gg/icarus/db/00-buckshot-shell/"
    
    print(f"Testing: {item_url}")
    print("="*70)
    
    item_data = extract_item_data(item_url, quiet=False)
    
    print(f"\nResults:")
    print(json.dumps(item_data, indent=2))

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_url = sys.argv[2] if len(sys.argv) > 2 else None
        test_single_item(test_url)
    else:
        print("\nThis will scrape all items from eip.gg/icarus/db/")
        print("Using 5 concurrent threads for faster scraping")
        print("Estimated time: 10-20 minutes")
        confirm = input("\nContinue? (yes/no): ").strip().lower()
        
        if confirm == "yes":
            scrape_all_items(max_workers=5)
        else:
            print("Aborted.")