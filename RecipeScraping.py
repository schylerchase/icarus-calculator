#!/usr/bin/env python3
"""
Enhanced Icarus Wiki Scraper - FIXED crafting station detection
"""

import json
import os
import re
import time
import requests
import argparse
from bs4 import BeautifulSoup

BASE_URL = "https://icarus.fandom.com"

def find_crafting_station(soup, page_text):
    """Find the crafting station - IMPROVED VERSION"""
    
    # Pattern 1: Most common format: "are crafted at the [STATION] with"
    match = re.search(r'are crafted at the ([A-Z][a-zA-Z\s]+?)(?:\s+with|\.|$)', page_text, re.IGNORECASE)
    if match:
        station = match.group(1).strip()
        print(f"      ✓ Crafted at: {station}")
        return station
    
    # Pattern 2: "crafted at the [STATION]" or "crafted in the [STATION]"
    match = re.search(r'crafted (?:at|in) the ([A-Z][a-zA-Z\s]+?Bench|[A-Z][a-zA-Z\s]+?Menu|[A-Z][a-zA-Z\s]+?Station|[A-Z][a-zA-Z\s]+?Furnace|[A-Z][a-zA-Z\s]+?Forge|Character[^.]*?Crafting[^.]*?Menu)', page_text, re.IGNORECASE)
    if match:
        station = match.group(1).strip()
        # Clean up "Character Crafting menu" to just "Character"
        if 'character' in station.lower():
            station = "Character"
        print(f"      ✓ Crafted at: {station}")
        return station
    
    # Pattern 3: Look for station names with specific keywords
    station_patterns = [
        r'(Ammunition Bench)',
        r'(Machining Bench)',
        r'(Anvil Bench)',
        r'(Fabricator)',
        r'(Character Crafting)',
        r'(Mortar and Pestle)',
        r'(Concrete Furnace)',
        r'(Electric Furnace)',
        r'(Stone Furnace)',
        r'(Forge)',
        r'(Crafting Menu)',
    ]
    
    for pattern in station_patterns:
        if re.search(pattern, page_text, re.IGNORECASE):
            station = re.search(pattern, page_text, re.IGNORECASE).group(1)
            print(f"      Found station (pattern 3): {station}")
            return station
    
    # Pattern 4: Check infobox
    infobox = soup.find('aside', class_='portable-infobox') or soup.find('table', class_='infobox')
    if infobox:
        infobox_text = infobox.get_text()
        for row in infobox.find_all(['div', 'tr']):
            row_text = row.get_text()
            # Look for rows that contain crafting info
            if 'craft' in row_text.lower():
                match = re.search(r'([A-Z][a-zA-Z\s]+?Bench|[A-Z][a-zA-Z\s]+?Station|[A-Z][a-zA-Z\s]+?Menu|Character)', row_text)
                if match:
                    station = match.group(1).strip()
                    print(f"      Found station (infobox): {station}")
                    return station
    
    print(f"      Could not find crafting station")
    return "Unknown"

def parse_table_ingredients(table, item_name):
    """Extract ingredients from a single table - handles two formats"""
    ingredients = {}
    
    headers = table.find_all(['th'])
    header_texts = [h.get_text().strip().lower() for h in headers]
    
    print(f"        DEBUG: All headers found: {header_texts}")
    
    has_amount_header = any('amount' in h for h in header_texts)
    has_material_header = any(h in ['material', 'resource', 'materials'] for h in header_texts)
    
    print(f"        Headers: Amount={has_amount_header}, Material/Resource={has_material_header}")
    
    # FORMAT 1: Standard Amount | Material/Resource table
    if has_amount_header and has_material_header:
        # Find the material column index
        material_col_idx = next((i for i, h in enumerate(header_texts) if h in ['material', 'resource', 'materials']), 1)
        
        rows = table.find_all('tr')[1:]
        print(f"        Format 1: Processing {len(rows)} rows")
        
        for row_idx, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            
            if len(cells) >= 2:
                amount_text = cells[0].get_text(strip=True)
                amount_match = re.search(r'(\d+)', amount_text)
                
                if not amount_match:
                    continue
                
                amount = int(amount_match.group(1))
                
                material_cell = cells[material_col_idx]
                material_link = material_cell.find('a')
                
                if material_link:
                    material_name = material_link.get('title', material_link.get_text(strip=True))
                else:
                    material_name = material_cell.get_text(strip=True)
                
                material_name = re.sub(r'\d+', '', material_name).strip()
                material_name = re.sub(r'[×x]', '', material_name).strip()
                
                if len(material_name) > 2 and amount > 0:
                    ingredients[material_name] = amount
                    print(f"          {amount}x {material_name}")
    
    else:
        print(f"        ✗ Unrecognized table format")
    
    print(f"        ✓ Extracted {len(ingredients)} ingredients")
    return ingredients

def extract_talent_info(page_text):
    """Extract talent name and effect"""
    talent_info = {'name': '', 'effect': ''}
    
    patterns = [
        r'With the talent \[([^\]]+)\].*?(-?\d+%[^.]+)',
        r'talent \[([^\]]+)\][^\n]*?Prospectors.*?(-?\d+%[^.]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
        if match:
            talent_info['name'] = match.group(1).strip()
            talent_info['effect'] = match.group(2).strip()
            break
    
    return talent_info

def parse_crafting_section(soup, page_text, item_name):
    """Parse crafting section - IMPROVED"""
    
    recipes_data = {
        'base_recipe': {'ingredients': {}, 'crafted_at': 'Unknown'},
        'talent_recipes': []
    }
    
    # Detect batch crafting
    batch_size = 1
    batch_match = re.search(r'Crafted in batches of (\d+)', page_text, re.IGNORECASE)
    if batch_match:
        batch_size = int(batch_match.group(1))
        print(f"      Batch crafting detected: {batch_size}x per craft")
    
    # Extract talent info
    talent_info = extract_talent_info(page_text)
    has_talent = bool(talent_info['name'])
    if has_talent:
        print(f"      Talent detected: {talent_info['name']} - {talent_info['effect']}")
    
    # Find crafting tables
    all_tables = soup.find_all('table')
    crafting_tables = []
    
    for table in all_tables:
        table_text = table.get_text().lower()
        if any(word in table_text for word in ['amount', 'material']):
            # Make sure it's not a stats comparison table
            if 'damage' not in table_text or 'craft' in table_text:
                crafting_tables.append(table)
    
    print(f"      Found {len(crafting_tables)} crafting table(s)")
    
    if not crafting_tables:
        return recipes_data
    
    # Parse tables
    for idx, table in enumerate(crafting_tables):
        ingredients = parse_table_ingredients(table, item_name)
        
        if not ingredients:
            continue
        
        # Calculate per-unit costs
        per_unit_ingredients = {}
        for material, amount in ingredients.items():
            per_unit = amount / batch_size
            per_unit_ingredients[material] = int(per_unit) if per_unit == int(per_unit) else round(per_unit, 2)
        
        print(f"      Table {idx+1}: {len(per_unit_ingredients)} ingredients")
        for mat, amt in per_unit_ingredients.items():
            print(f"        → {amt}x {mat}")
        
        # Assign to base or talent recipe
        if idx == 0:
            recipes_data['base_recipe']['ingredients'] = per_unit_ingredients
        elif idx == 1 and has_talent:
            # Compare costs to determine which is which
            first_total = sum(recipes_data['base_recipe']['ingredients'].values())
            second_total = sum(per_unit_ingredients.values())
            
            if second_total > first_total:
                # Second table is base (no talent), first was talent
                print(f"      Swapping: Table 1 has talent bonus (lower cost)")
                talent_recipe = recipes_data['base_recipe'].copy()
                talent_recipe['talent_name'] = talent_info['name']
                talent_recipe['talent_effect'] = talent_info['effect']
                
                recipes_data['base_recipe']['ingredients'] = per_unit_ingredients
                recipes_data['talent_recipes'].append(talent_recipe)
            else:
                # Second table is talent version
                print(f"      Table 2 has talent bonus (lower cost)")
                talent_recipe = {
                    'ingredients': per_unit_ingredients,
                    'crafted_at': 'Unknown',
                    'talent_name': talent_info['name'],
                    'talent_effect': talent_info['effect']
                }
                recipes_data['talent_recipes'].append(talent_recipe)
    
    # Find crafting station - THIS IS THE FIXED VERSION
    crafted_at = find_crafting_station(soup, page_text)
    recipes_data['base_recipe']['crafted_at'] = crafted_at
    
    for talent_recipe in recipes_data['talent_recipes']:
        talent_recipe['crafted_at'] = crafted_at
    
    return recipes_data

def extract_item_data(page_url, quiet=True):
    """Extract comprehensive item data from a Fandom wiki page"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Extract item name from URL
    item_name = page_url.split('/wiki/')[-1].replace('_', ' ')
    
    item_data = {
        "name": item_name,
        "url": page_url,
        "description": "",
        "item_type": "unknown",
        "ingredients": {},
        "crafted_at": "Unknown",
        "tier": 0,
        "stats": {},
        "category": "",
        "harvested_from": [],
        "research_cost": None,
        "purchase_cost": None
    }
    
    try:
        response = requests.get(page_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # FIX: Get page text FIRST before using it
        page_text = soup.get_text()
        
        # Get page title
        title_elem = soup.find('h1', class_='page-header__title')
        if title_elem:
            item_data['name'] = title_elem.get_text(strip=True)
        
        # Extract description from first paragraph
        content = soup.find('div', class_='mw-parser-output')
        if content:
            # Get only the first actual paragraph, skip empty ones
            for p in content.find_all('p', recursive=False):
                desc = p.get_text(strip=True)
                # Only use paragraphs that are actual descriptions
                if desc and len(desc) > 20 and len(desc) < 500:
                    if not re.search(r'(Category|Statistics|Weight|Durability|Attributes|Prerequisites)', desc):
                        item_data['description'] = desc
                        break
        
        # Extract infobox data
        infobox_data = extract_infobox_data(soup)
        
        # Parse infobox fields
        for key, value in infobox_data.items():
            if 'tier' in key:
                tier_match = re.search(r'(\d+)', value)
                if tier_match:
                    item_data['tier'] = int(tier_match.group(1))
            elif 'damage' in key:
                item_data['stats']['damage'] = value
            elif 'armor' in key:
                item_data['stats']['armor'] = value
            elif 'weight' in key:
                item_data['stats']['weight'] = value
            elif 'durability' in key:
                item_data['stats']['durability'] = value
            elif 'type' in key or 'category' in key:
                item_data['category'] = value.lower()
        
        # Extract crafting recipe - NOW page_text is defined!
        ingredients, crafted_at = parse_crafting_table(soup, page_text)
        
        if ingredients:
            item_data['ingredients'] = ingredients
            if item_data['item_type'] == 'unknown':
                item_data['item_type'] = 'craftable'
        
        if crafted_at != "Unknown":
            item_data['crafted_at'] = crafted_at
            if item_data['item_type'] == 'unknown':
                item_data['item_type'] = 'craftable'
        
        # Look for harvesting info
        if any(word in page_text.lower() for word in ['harvested', 'foraged', 'gathered', 'mined']):
            item_data['item_type'] = 'harvestable'
            
            # Try to extract locations
            harvest_match = re.search(r'(?:harvested|found|gathered) (?:from|in|at)\s+([^.]+)', page_text, re.IGNORECASE)
            if harvest_match:
                locations = harvest_match.group(1).strip()
                item_data['harvested_from'] = [loc.strip() for loc in re.split(r',|and', locations)]
        
        # Look for orbital/workshop info
        if 'workshop' in page_text.lower() and ('exotic' in page_text.lower() or 'orbital' in page_text.lower()):
            research_match = re.search(r'research.*?(\d+)', page_text, re.IGNORECASE)
            if research_match:
                item_data['research_cost'] = int(research_match.group(1))
                item_data['item_type'] = 'orbital'
            
            purchase_match = re.search(r'(?:cost|price).*?(\d+)', page_text, re.IGNORECASE)
            if purchase_match:
                item_data['purchase_cost'] = int(purchase_match.group(1))
                if item_data['item_type'] == 'unknown':
                    item_data['item_type'] = 'orbital'
        
        # Only mark as orbital if we actually found costs
        if item_data['item_type'] == 'orbital' and not (item_data['research_cost'] or item_data['purchase_cost']):
            item_data['item_type'] = 'unknown'
        
        # Determine type from categories
        categories = []
        for cat_link in soup.find_all('a', href=re.compile(r'/wiki/Category:')):
            cat_name = cat_link.get_text(strip=True).lower()
            categories.append(cat_name)
        
        if item_data['item_type'] == 'unknown':
            if any('weapon' in cat for cat in categories):
                item_data['item_type'] = 'weapon'
            elif any('armor' in cat for cat in categories):
                item_data['item_type'] = 'armor'
            elif any('tool' in cat for cat in categories):
                item_data['item_type'] = 'tool'
            elif any('consumable' in cat for cat in categories):
                item_data['item_type'] = 'consumable'
            elif any('resource' in cat for cat in categories):
                item_data['item_type'] = 'resource'
        
        return item_data
        
    except Exception as e:
        if not quiet:
            print(f"  [ERROR] {page_url}: {e}")
        return item_data

def update_existing_jsons(data_dir="icarus_data"):
    """Update existing JSON files"""
    
    print("="*70)
    print("  UPDATING EXISTING JSON FILES")
    print("="*70)
    
    json_files = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.json') and file not in ['index.json', 'all_items.json', '_summary.json']:
                json_files.append(os.path.join(root, file))
    
    print(f"\nFound {len(json_files)} item files")
    
    updated_count = 0
    skipped_count = 0
    
    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            needs_update = False
            
            # Convert old format
            if 'ingredients' in existing_data and 'base_recipe' not in existing_data:
                existing_data['base_recipe'] = {
                    'ingredients': existing_data.get('ingredients', {}),
                    'crafted_at': existing_data.get('crafted_at', 'Unknown')
                }
                needs_update = True
            
            if 'base_recipe' not in existing_data:
                existing_data['base_recipe'] = {'ingredients': {}, 'crafted_at': 'Unknown'}
            
            # Check if needs updating
            if not existing_data['base_recipe'].get('ingredients'):
                needs_update = True
            elif existing_data['base_recipe'].get('crafted_at') == 'Unknown':
                needs_update = True
            elif existing_data.get('item_type') == 'unknown':
                needs_update = True
            
            if needs_update and existing_data.get('url'):
                print(f"\n  Updating: {existing_data['name']}")
                new_data = extract_item_data(existing_data['url'], existing_data, quiet=False)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(new_data, f, indent=2, ensure_ascii=False)
                
                print(f"    ✓ Saved")
                updated_count += 1
                time.sleep(0.5)
            else:
                skipped_count += 1
                
        except Exception as e:
            print(f"  [ERROR] {filepath}: {e}")
    
    print(f"\n{'='*70}")
    print(f"  COMPLETE: Updated {updated_count}, Skipped {skipped_count}")
    print("="*70)

def test_ammunition_scraping():
    """Test the scraper"""
    
    test_items = [
        ("9mm Round", "https://icarus.fandom.com/wiki/9mm_Round"),
        ("Stone Arrow", "https://icarus.fandom.com/wiki/Stone_Arrow"),
        ("Steel Arrow", "https://icarus.fandom.com/wiki/Steel_Arrow"),
    ]
    
    print("="*70)
    print("  TESTING SCRAPER")
    print("="*70)
    
    for item_name, url in test_items:
        print(f"\n{'='*70}")
        print(f"Testing: {item_name}")
        print("="*70)
        
        data = extract_item_data(url, quiet=False)
        
        print(f"\n✅ RESULTS:")
        print(f"  Name: {data['name']}")
        print(f"  Type: {data['item_type']}")
        print(f"  Base Recipe:")
        print(f"    Crafted at: {data['base_recipe']['crafted_at']}")
        print(f"    Ingredients: {data['base_recipe']['ingredients']}")
        
        if data['talent_recipes']:
            print(f"  Talent Recipes: {len(data['talent_recipes'])}")
            for tr in data['talent_recipes']:
                print(f"    - {tr['talent_name']}: {tr['talent_effect']}")
                print(f"      Crafted at: {tr['crafted_at']}")
                print(f"      Ingredients: {tr['ingredients']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Icarus Wiki Scraper')
    parser.add_argument('--update', action='store_true', help='Update existing JSON files')
    parser.add_argument('--test', action='store_true', help='Test scraping')
    
    args = parser.parse_args()
    
    if args.test:
        test_ammunition_scraping()
    elif args.update:
        update_existing_jsons()
    else:
        print("Usage:")
        print("  python RecipeScraping.py --test      # Test scraping")
        print("  python RecipeScraping.py --update    # Update JSONs")