#!/usr/bin/env python3
"""
Enhanced Icarus Wiki Scraper with Talent Support
Handles multiple recipes per item (base + talent variants)
Can update existing JSON files without overwriting manual data

Usage:
python RecipeScraping.py --update    # Update existing JSONs only
python RecipeScraping.py --full      # Full scrape (discovers new items)
"""

import json
import os
import re
import time
import requests
import argparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

BASE_URL = "https://icarus.fandom.com"

CATEGORY_URLS = {
    "items": f"{BASE_URL}/wiki/Category:Items",
    "weapons": f"{BASE_URL}/wiki/Category:Weapons",
    "armor": f"{BASE_URL}/wiki/Category:Armor",
    "tools": f"{BASE_URL}/wiki/Category:Tools",
    "consumables": f"{BASE_URL}/wiki/Category:Consumables",
    "resources": f"{BASE_URL}/wiki/Category:Resources",
    "furniture": f"{BASE_URL}/wiki/Category:Furniture",
    "deployables": f"{BASE_URL}/wiki/Category:Deployables",
    "orbital": f"{BASE_URL}/wiki/Category:Orbital_Tech",
    "structures": f"{BASE_URL}/wiki/Category:Buildable_Structures"
}

counter_lock = Lock()

def parse_crafting_tables_enhanced(soup, page_text):
    """
    Enhanced crafting table parser that extracts multiple recipes
    Returns: {
        'base_recipe': {'ingredients': {}, 'crafted_at': ''},
        'talent_recipes': [
            {'talent_name': '', 'talent_effect': '', 'ingredients': {}, 'crafted_at': ''}
        ]
    }
    """
    
    recipes_data = {
        'base_recipe': {'ingredients': {}, 'crafted_at': 'Unknown'},
        'talent_recipes': []
    }
    
    # Find all tables on the page
    all_tables = soup.find_all('table')
    crafting_tables = []
    
    for table in all_tables:
        table_text = table.get_text().lower()
        # Check if it's a crafting/recipe table
        if any(word in table_text for word in ['amount', 'material', 'craft', 'recipe', 'ingredients']):
            crafting_tables.append(table)
    
    print(f"      Found {len(crafting_tables)} potential crafting tables")
    
    # Process each crafting table
    for idx, table in enumerate(crafting_tables):
        ingredients = {}
        
        # Check if table has headers
        headers = table.find_all(['th'])
        has_amount_header = any('amount' in h.get_text().lower() for h in headers)
        has_material_header = any('material' in h.get_text().lower() for h in headers)
        
        if has_amount_header and has_material_header:
            print(f"      Table {idx+1}: Standard Amount/Material format")
            # This is a standard crafting table with Amount | Material columns
            
            rows = table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                
                if len(cells) >= 2:
                    # First cell should be amount
                    amount_text = cells[0].get_text(strip=True)
                    amount_match = re.search(r'(\d+)', amount_text)
                    
                    if amount_match:
                        amount = int(amount_match.group(1))
                        
                        # Second cell should be material name (look for links)
                        material_cell = cells[1]
                        material_link = material_cell.find('a')
                        
                        if material_link:
                            material_name = material_link.get('title', material_link.get_text(strip=True))
                        else:
                            material_name = material_cell.get_text(strip=True)
                        
                        # Clean up material name
                        material_name = re.sub(r'\d+', '', material_name).strip()
                        material_name = re.sub(r'[×x]', '', material_name).strip()
                        
                        if len(material_name) > 2 and amount > 0:
                            ingredients[material_name] = amount
                            print(f"        → {amount}x {material_name}")
        
        # Store the recipe
        if ingredients:
            if idx == 0:
                # First table is base recipe
                recipes_data['base_recipe']['ingredients'] = ingredients
                print(f"      ✓ Base recipe: {len(ingredients)} ingredients")
            else:
                # Additional tables are talent-modified recipes
                # Try to find talent info from surrounding text
                talent_info = extract_talent_info_near_table(table, page_text)
                
                talent_recipe = {
                    'talent_name': talent_info.get('name', f'Variant {idx}'),
                    'talent_effect': talent_info.get('effect', 'Unknown effect'),
                    'ingredients': ingredients,
                    'crafted_at': 'Unknown'
                }
                recipes_data['talent_recipes'].append(talent_recipe)
                print(f"      ✓ Talent recipe ({talent_info.get('name', 'Unknown')}): {len(ingredients)} ingredients")
    
    # Find crafting station
    crafted_at = find_crafting_station(soup, page_text)
    recipes_data['base_recipe']['crafted_at'] = crafted_at
    
    for talent_recipe in recipes_data['talent_recipes']:
        talent_recipe['crafted_at'] = crafted_at
    
    return recipes_data

def extract_talent_info_near_table(table, page_text):
    """Extract talent name and effect from text near the table"""
    
    talent_info = {'name': '', 'effect': ''}
    
    # Look for talent mentions in the page text
    talent_patterns = [
        r'(?:talent|with)\s+\[([^\]]+)\].*?(-?\d+%[^.]+)',
        r'With the talent ([^,]+),.*?(-?\d+%[^.]+)',
        r'([A-Z][a-zA-Z\s]+)\s+talent.*?(-?\d+%[^.]+)',
    ]
    
    for pattern in talent_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            talent_info['name'] = match.group(1).strip()
            talent_info['effect'] = match.group(2).strip()
            break
    
    return talent_info

def find_crafting_station(soup, page_text):
    """Find the crafting station for an item"""
    
    crafted_at = "Unknown"
    
    # Method 1: Look for "Crafted at" patterns in text
    craft_patterns = [
        r'Crafted (?:at|in|using)[:\s]+([^.\n]+)',
        r'(?:Made|Built|Created) at[:\s]+([^.\n]+)',
        r'Requires[:\s]+([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge|Fabricator))',
    ]
    
    for pattern in craft_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            station = match.group(1).strip()
            station = re.sub(r'\s+', ' ', station)
            if len(station) < 50 and any(word in station.lower() for word in ['bench', 'station', 'furnace', 'forge', 'fabricator', 'printer', 'character']):
                crafted_at = station
                break
    
    # Method 2: Look in infobox
    if crafted_at == "Unknown":
        infobox = soup.find('aside', class_='portable-infobox') or soup.find('table', class_='infobox')
        if infobox:
            for row in infobox.find_all(['div', 'tr']):
                row_text = row.get_text().lower()
                if 'craft' in row_text or 'station' in row_text:
                    value = row.get_text(strip=True)
                    match = re.search(r'([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge|Fabricator|Printer))', value)
                    if match:
                        crafted_at = match.group(1).strip()
                        break
    
    # Special case: ammunition is often crafted at Ammunition Bench or Machining Bench
    if crafted_at == "Unknown" and any(word in page_text.lower() for word in ['ammunition', 'ammo', 'round', 'bullet', 'shell']):
        if 'ammunition bench' in page_text.lower():
            crafted_at = "Machining Bench"
        elif 'machining bench' in page_text.lower():
            crafted_at = "Machining Bench"
    
    return crafted_at

def extract_item_data_enhanced(page_url, quiet=True):
    """Enhanced item data extraction with talent support"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    item_name = page_url.split('/wiki/')[-1].replace('_', ' ')
    
    item_data = {
        "name": item_name,
        "url": page_url,
        "description": "",
        "item_type": "unknown",
        "base_recipe": {
            "ingredients": {},
            "crafted_at": "Unknown"
        },
        "talent_recipes": [],
        "tier": 0,
        "stats": {},
        "category": "",
    }
    
    try:
        if not quiet:
            print(f"    Scraping: {item_name}")
        
        response = requests.get(page_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        page_text = soup.get_text()
        
        # Get page title
        title_elem = soup.find('h1', class_='page-header__title')
        if title_elem:
            item_data['name'] = title_elem.get_text(strip=True)
        
        # Extract description
        content = soup.find('div', class_='mw-parser-output')
        if content:
            for p in content.find_all('p', recursive=False):
                desc = p.get_text(strip=True)
                if desc and len(desc) > 20 and len(desc) < 500:
                    if not re.search(r'(Category|Statistics|Weight|Durability)', desc):
                        item_data['description'] = desc
                        break
        
        # Extract crafting data with talent support
        recipes_data = parse_crafting_tables_enhanced(soup, page_text)
        
        if recipes_data['base_recipe']['ingredients']:
            item_data['base_recipe'] = recipes_data['base_recipe']
            item_data['item_type'] = 'craftable'
        
        if recipes_data['talent_recipes']:
            item_data['talent_recipes'] = recipes_data['talent_recipes']
        
        # Determine item type from categories
        categories = []
        for cat_link in soup.find_all('a', href=re.compile(r'/wiki/Category:')):
            cat_name = cat_link.get_text(strip=True).lower()
            categories.append(cat_name)
        
        if item_data['item_type'] == 'unknown':
            if any('ammunition' in cat or 'ammo' in cat for cat in categories):
                item_data['item_type'] = 'ammunition'
            elif any('weapon' in cat for cat in categories):
                item_data['item_type'] = 'weapon'
            elif any('armor' in cat for cat in categories):
                item_data['item_type'] = 'armor'
            elif any('tool' in cat for cat in categories):
                item_data['item_type'] = 'tool'
        
        # Additional type detection from item name
        name_lower = item_data['name'].lower()
        if item_data['item_type'] == 'unknown':
            if any(word in name_lower for word in ['round', 'bullet', 'shell', 'cartridge', 'arrow', 'bolt']):
                item_data['item_type'] = 'ammunition'
        
        return item_data
        
    except Exception as e:
        if not quiet:
            print(f"      [ERROR] {e}")
        return item_data

def update_existing_jsons(data_dir="icarus_data"):
    """Update existing JSON files with missing recipe data"""
    
    print("="*70)
    print("  UPDATING EXISTING JSON FILES")
    print("="*70)
    
    # Find all JSON files
    json_files = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.json') and file not in ['index.json', 'all_items.json', '_summary.json']:
                json_files.append(os.path.join(root, file))
    
    print(f"\nFound {len(json_files)} item files to check")
    
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    
    for filepath in json_files:
        try:
            # Load existing data
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Check if it needs updating
            needs_update = False
            
            # Check if base_recipe exists and has data
            if 'base_recipe' not in existing_data:
                # Old format - convert to new format
                needs_update = True
            elif not existing_data['base_recipe'].get('ingredients'):
                needs_update = True
            elif existing_data['base_recipe'].get('crafted_at') == 'Unknown':
                needs_update = True
            
            # Check if it's marked as unknown type
            if existing_data.get('item_type') == 'unknown':
                needs_update = True
            
            if needs_update and existing_data.get('url'):
                print(f"\n  Updating: {existing_data['name']}")
                
                # Scrape fresh data
                new_data = extract_item_data_enhanced(existing_data['url'], quiet=False)
                
                # Merge data (preserve manual edits, only fill in missing info)
                if new_data['base_recipe']['ingredients'] and not existing_data.get('base_recipe', {}).get('ingredients'):
                    existing_data['base_recipe'] = new_data['base_recipe']
                    print(f"    ✓ Added base recipe")
                
                if new_data['talent_recipes'] and not existing_data.get('talent_recipes'):
                    existing_data['talent_recipes'] = new_data['talent_recipes']
                    print(f"    ✓ Added {len(new_data['talent_recipes'])} talent recipe(s)")
                
                if new_data['item_type'] != 'unknown' and existing_data.get('item_type') == 'unknown':
                    existing_data['item_type'] = new_data['item_type']
                    print(f"    ✓ Set type: {new_data['item_type']}")
                
                # Save updated data
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, indent=2, ensure_ascii=False)
                
                updated_count += 1
                time.sleep(0.5)  # Be nice to the wiki
            else:
                skipped_count += 1
                
        except Exception as e:
            print(f"  [ERROR] {filepath}: {e}")
            failed_count += 1
    
    print(f"\n{'='*70}")
    print(f"  UPDATE COMPLETE")
    print(f"{'='*70}")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped (already complete): {skipped_count}")
    print(f"  Failed: {failed_count}")
    print("="*70)

def test_ammunition_scraping():
    """Test the scraper on known ammunition items"""
    
    test_items = [
        "https://icarus.fandom.com/wiki/9mm_Round",
        "https://icarus.fandom.com/wiki/Arrow",
        "https://icarus.fandom.com/wiki/Steel_Arrow",
    ]
    
    print("="*70)
    print("  TESTING AMMUNITION SCRAPING")
    print("="*70)
    
    for url in test_items:
        print(f"\n{'='*70}")
        print(f"Testing: {url.split('/wiki/')[-1]}")
        print("="*70)
        
        data = extract_item_data_enhanced(url, quiet=False)
        
        print(f"\nResults:")
        print(f"  Name: {data['name']}")
        print(f"  Type: {data['item_type']}")
        print(f"  Base Recipe:")
        print(f"    Crafted at: {data['base_recipe']['crafted_at']}")
        print(f"    Ingredients: {data['base_recipe']['ingredients']}")
        
        if data['talent_recipes']:
            print(f"  Talent Recipes: {len(data['talent_recipes'])}")
            for tr in data['talent_recipes']:
                print(f"    - {tr['talent_name']}: {tr['talent_effect']}")
                print(f"      Ingredients: {tr['ingredients']}")
        
        print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Icarus Wiki Scraper with Talent Support')
    parser.add_argument('--update', action='store_true', help='Update existing JSON files only')
    parser.add_argument('--test', action='store_true', help='Test ammunition scraping')
    parser.add_argument('--full', action='store_true', help='Full scrape (not implemented yet)')
    
    args = parser.parse_args()
    
    if args.test:
        test_ammunition_scraping()
    elif args.update:
        update_existing_jsons()
    else:
        print("Usage:")
        print("  python RecipeScraping.py --test      # Test scraping on ammunition")
        print("  python RecipeScraping.py --update    # Update existing JSONs")
        print("  python RecipeScraping.py --full      # Full scrape (coming soon)")