#!/usr/bin/env python3
"""
Icarus Fandom Wiki Database Scraper
Comprehensive scraper for https://icarus.fandom.com/

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

BASE_URL = "https://icarus.fandom.com"

# Known category pages on Fandom
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

def get_category_members(category_url, max_pages=20):
    """Get all pages from a Fandom category, including subcategories"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    all_pages = set()
    subcategories = set()
    current_url = category_url
    visited = set()
    
    for page_num in range(max_pages):
        if current_url in visited:
            break
            
        visited.add(current_url)
        
        print(f"   Fetching page {page_num + 1}...", end=' ')
        
        try:
            response = requests.get(current_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find category members - Fandom uses specific div classes
            category_content = soup.find('div', class_='category-page__members')
            
            members_found = 0
            if category_content:
                # Find all links to wiki pages
                for link in category_content.find_all('a', class_='category-page__member-link'):
                    href = link.get('href', '')
                    if href and '/wiki/' in href:
                        # Handle both relative and absolute URLs
                        if href.startswith('http'):
                            full_url = href
                        elif href.startswith('/'):
                            full_url = BASE_URL + href
                        else:
                            full_url = BASE_URL + '/' + href
                        
                        # Check if it's a subcategory or an item
                        if 'Category:' in full_url:
                            subcategories.add(full_url)
                        elif not any(x in full_url for x in ['File:', 'Special:', 'User:', 'Talk:']):
                            all_pages.add(full_url)
                            members_found += 1
            
            print(f"✓ Found {members_found} items")
            
            # Look for "next page" link in pagination
            next_link = soup.find('a', class_='category-page__pagination-next')
            if next_link and next_link.get('href'):
                next_href = next_link['href']
                # Handle both relative and absolute URLs
                if next_href.startswith('http'):
                    current_url = next_href
                elif next_href.startswith('/'):
                    current_url = BASE_URL + next_href
                else:
                    current_url = BASE_URL + '/' + next_href
            else:
                break
                
        except Exception as e:
            print(f"✗ Error: {str(e)[:100]}")
            print(f"   Problem URL: {current_url}")
            break
        
        time.sleep(0.5)
    
    # Recursively get subcategories
    if subcategories:
        print(f"   Found {len(subcategories)} subcategories, crawling...")
        for subcat_url in subcategories:
            subcat_name = subcat_url.split('Category:')[-1]
            print(f"   → Subcategory: {subcat_name}")
            subcat_pages, _ = get_category_members(subcat_url, max_pages=10)
            all_pages.update(subcat_pages)
    
    return list(all_pages), list(subcategories)

def discover_all_item_pages():
    """Phase 1: Discover all item pages from categories"""
    
    print("="*70)
    print("PHASE 1: DISCOVERING ITEM PAGES FROM CATEGORIES")
    print("="*70)
    
    all_item_pages = set()
    
    for category_name, category_url in CATEGORY_URLS.items():
        print(f"\n📂 Scanning category: {category_name}")
        print(f"   URL: {category_url}")
        
        pages, subcats = get_category_members(category_url)
        
        if pages:
            all_item_pages.update(pages)
            print(f"   ✓ Total found: {len(pages)} pages")
        else:
            print(f"   ✗ No pages found")
        
        time.sleep(0.5)
    
    # Also try to find item lists from main pages
    print(f"\n📂 Scanning main database pages...")
    main_pages = [
        (f"{BASE_URL}/wiki/Items", "Items"),
        (f"{BASE_URL}/wiki/Weapons", "Weapons"),
        (f"{BASE_URL}/wiki/Tools", "Tools"),
        (f"{BASE_URL}/wiki/Armor", "Armor"),
        (f"{BASE_URL}/wiki/Resources", "Resources"),
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for page_url, page_name in main_pages:
        try:
            print(f"   Checking {page_name}...", end=' ')
            response = requests.get(page_url, headers=headers, timeout=30)
            soup = BeautifulSoup(response.content, 'lxml')
            
            found_count = 0
            # Find all wiki links in content area (not just tables)
            content = soup.find('div', class_='mw-parser-output')
            if content:
                for link in content.find_all('a', href=True):
                    href = link['href']
                    if '/wiki/' in href and not any(x in href for x in ['Category:', 'File:', 'Special:', 'Talk:', 'User:']):
                        # Handle both relative and absolute URLs
                        if href.startswith('http'):
                            full_url = href
                        elif href.startswith('/'):
                            full_url = BASE_URL + href
                        else:
                            full_url = BASE_URL + '/' + href
                        
                        # Only add if it looks like an item page (not a main page)
                        path = full_url.split('/wiki/')[-1]
                        if path and path not in ['Items', 'Weapons', 'Tools', 'Armor', 'Resources', 'Crafting']:
                            all_item_pages.add(full_url)
                            found_count += 1
            
            print(f"✓ {found_count} items")
            time.sleep(0.5)
        except Exception as e:
            print(f"✗ Error: {str(e)[:50]}")
    
    print(f"\n{'='*70}")
    print(f"✓ PHASE 1 COMPLETE")
    print(f"{'='*70}")
    print(f"Total unique pages discovered: {len(all_item_pages)}")
    
    # Save discovered URLs
    with open('discovered_pages.json', 'w') as f:
        json.dump(sorted(list(all_item_pages)), f, indent=2)
    print(f"💾 Saved to discovered_pages.json")
    
    return list(all_item_pages)

def extract_infobox_data(soup):
    """Extract data from Fandom infobox"""
    
    infobox_data = {}
    
    # Find infobox (common class names in Fandom)
    infobox = soup.find('aside', class_='portable-infobox') or soup.find('table', class_='infobox')
    
    if infobox:
        # Extract all data rows
        for row in infobox.find_all(['div', 'tr']):
            # Look for label-value pairs
            label_elem = row.find(['h3', 'th', 'div'], class_=re.compile('label|header'))
            value_elem = row.find(['div', 'td'], class_=re.compile('value|data'))
            
            if label_elem and value_elem:
                label = label_elem.get_text(strip=True)
                value = value_elem.get_text(strip=True)
                
                if label and value:
                    infobox_data[label.lower()] = value
    
    return infobox_data

def parse_crafting_table(soup, page_text):
    """Extract crafting recipe from tables and text"""
    
    ingredients = {}
    crafted_at = "Unknown"
    
    # Method 1: Look for crafting tables
    for table in soup.find_all('table'):
        table_text = table.get_text().lower()
        
        # Check if it's a crafting/recipe table
        if any(word in table_text for word in ['craft', 'recipe', 'materials', 'required', 'ingredients']):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                
                if len(cells) >= 2:
                    # Try different cell combinations
                    for i in range(len(cells) - 1):
                        item_cell = cells[i]
                        
                        # Look for quantity in current or next cells
                        for j in range(i, min(i + 2, len(cells))):
                            quantity_text = cells[j].get_text(strip=True)
                            quantity_match = re.search(r'(\d+)', quantity_text)
                            
                            if quantity_match:
                                quantity = int(quantity_match.group(1))
                                item_name = item_cell.get_text(strip=True)
                                
                                # Clean up item name (remove quantities, icons, etc.)
                                item_name = re.sub(r'\d+', '', item_name).strip()
                                item_name = re.sub(r'×', '', item_name).strip()
                                
                                if len(item_name) > 2 and quantity > 0:
                                    ingredients[item_name] = quantity
                                break
    
    # Method 2: Look for text patterns for crafting station
    craft_patterns = [
        r'Crafted (?:at|in|using)[:\s]+([^.\n]+)',
        r'(?:Made|Built|Created) at[:\s]+([^.\n]+)',
        r'Requires[:\s]+([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge))',
        r'Station[:\s]+([^.\n]+)',
    ]
    
    for pattern in craft_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            station = match.group(1).strip()
            # Clean up the station name
            station = re.sub(r'\s+', ' ', station)
            if len(station) < 50 and any(word in station.lower() for word in ['bench', 'station', 'furnace', 'forge', 'fabricator', 'printer']):
                crafted_at = station
                break
    
    # Method 3: Look in infobox for crafting station
    if crafted_at == "Unknown":
        infobox = soup.find('aside', class_='portable-infobox') or soup.find('table', class_='infobox')
        if infobox:
            for row in infobox.find_all(['div', 'tr']):
                row_text = row.get_text().lower()
                if 'craft' in row_text or 'station' in row_text or 'made' in row_text:
                    value = row.get_text(strip=True)
                    # Extract station name
                    for word in ['bench', 'station', 'furnace', 'forge', 'fabricator', 'printer']:
                        if word in value.lower():
                            # Extract the full station name
                            match = re.search(r'([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge|Fabricator|Printer))', value)
                            if match:
                                crafted_at = match.group(1).strip()
                                break
                    if crafted_at != "Unknown":
                        break
    
    # Method 4: Look for "Prerequisite" section which often contains crafting station
    prereq_match = re.search(r'Prerequisite[:\s]+([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge))', page_text)
    if prereq_match and crafted_at == "Unknown":
        crafted_at = prereq_match.group(1).strip()
    
    return ingredients, crafted_at

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
        "purchase_cost": None,
        "base_recipe": {
            "ingredients": {},
            "crafted_at": "Unknown"
        }
    }
    
    try:
        response = requests.get(page_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Get page title
        title_elem = soup.find('h1', class_='page-header__title')
        if title_elem:
            item_data['name'] = title_elem.get_text(strip=True)
        
        # Extract description from first paragraph - FIXED
        content = soup.find('div', class_='mw-parser-output')
        if content:
            # Get only the first actual paragraph, skip empty ones
            for p in content.find_all('p', recursive=False):
                # Use separator=' ' to preserve spaces between elements
                desc = p.get_text(separator=' ', strip=True)
                
                # Only use paragraphs that are actual descriptions (not too short, not infobox text)
                if desc and len(desc) > 20 and len(desc) < 500:
                    # Skip if it looks like infobox data (has lots of category/stat words)
                    if not re.search(r'(Category|Statistics|Weight|Durability|Attributes|Prerequisites)', desc):
                        # Clean up the description - FIXED
                        # Remove reference links like "can be viewedhere" or "see here" at the end
                        desc = re.sub(r'\s*A list of [^.]+can be viewed\s*here\.?\s*$', '', desc, flags=re.IGNORECASE)
                        desc = re.sub(r'\s*[Ss]ee\s+here\.?\s*$', '', desc)
                        desc = re.sub(r'\s*[Vv]iewed?\s*here\.?\s*$', '', desc)
                        # Remove any trailing "here." or "here" at the end of sentences
                        desc = re.sub(r'\s+here\.?\s*$', '.', desc)
                        # Clean up multiple spaces
                        desc = re.sub(r'\s+', ' ', desc)
                        
                        item_data['description'] = desc.strip()
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
        
        # Get full page text for pattern matching
        page_text = soup.get_text()
        
        # Extract crafting recipe
        ingredients, crafted_at = parse_crafting_table(soup, page_text)
        
        if ingredients:
            item_data['ingredients'] = ingredients
            item_data['base_recipe']['ingredients'] = ingredients
            if item_data['item_type'] == 'unknown':
                item_data['item_type'] = 'craftable'
        
        if crafted_at != "Unknown":
            item_data['crafted_at'] = crafted_at
            item_data['base_recipe']['crafted_at'] = crafted_at
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
        is_workshop_item = False
        
        # Check for workshop/orbital keywords
        if 'workshop' in page_text.lower():
            # Look for phrases that indicate it's a workshop item
            workshop_phrases = [
                'purchased from the workshop',
                'crafted in the workshop',
                'researched and then crafted in the workshop',
                'unlocked in the workshop',
                'purchased and equipped'
            ]
            
            if any(phrase in page_text.lower() for phrase in workshop_phrases):
                is_workshop_item = True
            elif 'exotic' in page_text.lower() or 'orbital' in page_text.lower():
                is_workshop_item = True
        
        if is_workshop_item:
            # Try to extract research cost
            research_match = re.search(r'research.*?cost.*?(\d+)', page_text, re.IGNORECASE)
            if research_match:
                item_data['research_cost'] = int(research_match.group(1))
                item_data['item_type'] = 'orbital'
            
            # Try to extract purchase/crafting cost  
            purchase_match = re.search(r'(?:crafting|purchase|cost|price).*?(?:cost)?.*?(\d+)', page_text, re.IGNORECASE)
            if purchase_match and not research_match:  # Don't double-count research cost
                item_data['purchase_cost'] = int(purchase_match.group(1))
                if item_data['item_type'] == 'unknown':
                    item_data['item_type'] = 'orbital'
            
            # If we found workshop phrases but no costs, still mark as workshop
            if not item_data['research_cost'] and not item_data['purchase_cost']:
                item_data['crafted_at'] = 'Workshop'
                item_data['base_recipe']['crafted_at'] = 'Workshop'
                if item_data['item_type'] == 'unknown':
                    item_data['item_type'] = 'orbital'
        
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

def categorize_items(items):
    """Intelligently categorize items"""
    
    categories = {
        "weapons_melee": [],
        "weapons_ranged": [],
        "ammunition": [],
        "armor_clothing": [],
        "tools": [],
        "building_structures": [],
        "building_furniture": [],
        "consumables_food": [],
        "consumables_medicine": [],
        "resources_raw": [],
        "resources_processed": [],
        "deployables": [],
        "orbital_items": [],
        "misc": []
    }
    
    for item in items:
        name_lower = item['name'].lower()
        item_type = item.get('item_type', 'unknown')
        category = item.get('category', '').lower()
        desc_lower = item.get('description', '').lower()
        
        categorized = False
        
        # Orbital - ONLY if has research/purchase cost
        if item_type == 'orbital' and (item.get('research_cost') or item.get('purchase_cost')):
            categories['orbital_items'].append(item)
            categorized = True
        
        # Building - Furniture (benches, stations, etc.) - CHECK THIS FIRST
        if not categorized and any(word in name_lower for word in ['bench', 'table', 'chair', 'bed', 'furnace', 'forge', 'station', 'storage', 'chest', 'fabricator', 'printer']):
            categories['building_furniture'].append(item)
            categorized = True
        
        # Building - Structures (walls, floors, roofs, etc.)
        if not categorized and any(word in name_lower for word in ['wall', 'floor', 'roof', 'ramp', 'door', 'window', 'stairs', 'foundation', 'pillar', 'beam', 'corner', 'ceiling']):
            categories['building_structures'].append(item)
            categorized = True
        
        # Ammunition
        if not categorized and any(word in name_lower for word in ['bullet', 'shell', 'arrow', 'ammo', 'cartridge', 'round']):
            categories['ammunition'].append(item)
            categorized = True
        
        # Weapons - Melee
        if not categorized and any(word in name_lower for word in ['knife', 'spear', 'sword', 'axe', 'pickaxe', 'machete', 'blade', 'hammer']):
            if 'arrow' not in name_lower:
                categories['weapons_melee'].append(item)
                categorized = True
        
        # Weapons - Ranged
        if not categorized and any(word in name_lower for word in ['bow', 'rifle', 'pistol', 'shotgun', 'gun', 'crossbow']):
            categories['weapons_ranged'].append(item)
            categorized = True
        
        # Armor
        if not categorized and (item_type == 'armor' or any(word in name_lower for word in ['armor', 'helmet', 'boots', 'gloves', 'suit', 'vest'])):
            categories['armor_clothing'].append(item)
            categorized = True
        
        # Tools
        if not categorized and (item_type == 'tool' or any(word in name_lower for word in ['drill', 'saw', 'wrench', 'scanner', 'lantern', 'torch', 'radar'])):
            categories['tools'].append(item)
            categorized = True
        
        # Consumables - Food
        if not categorized and any(word in name_lower for word in ['meat', 'fish', 'berry', 'berries', 'bread', 'soup', 'stew', 'cooked', 'raw', 'food']):
            categories['consumables_food'].append(item)
            categorized = True
        
        # Consumables - Medicine
        if not categorized and any(word in name_lower for word in ['medicine', 'bandage', 'paste', 'cure', 'antibiotic', 'syringe']):
            categories['consumables_medicine'].append(item)
            categorized = True
        
        # Resources - Raw (harvestable)
        if not categorized and (item_type == 'harvestable' or any(word in name_lower for word in ['ore', 'wood', 'stone', 'fiber', 'hide', 'bone', 'stick'])):
            if 'ingot' not in name_lower and 'refined' not in name_lower:
                categories['resources_raw'].append(item)
                categorized = True
        
        # Resources - Processed
        if not categorized and any(word in name_lower for word in ['ingot', 'refined', 'leather', 'rope', 'fabric', 'steel', 'iron', 'copper']):
            categories['resources_processed'].append(item)
            categorized = True
        
        # Deployables
        if not categorized and any(word in name_lower for word in ['turret', 'trap', 'beacon', 'mine', 'deployable']):
            categories['deployables'].append(item)
            categorized = True
        
        # Check category field if still not categorized
        if not categorized:
            if 'building' in category:
                categories['building_structures'].append(item)
                categorized = True
            elif 'furniture' in category:
                categories['building_furniture'].append(item)
                categorized = True
            elif 'weapon' in category:
                categories['weapons_melee'].append(item)
                categorized = True
        
        if not categorized:
            categories['misc'].append(item)
    
    return {k: v for k, v in categories.items() if v}

def scrape_all_items(output_dir="icarus_data", max_workers=5):
    """Main scraping function"""
    
    print("="*70)
    print("  ICARUS FANDOM WIKI SCRAPER")
    print("="*70)
    
    # Phase 1: Discover pages
    item_pages = discover_all_item_pages()
    
    if not item_pages:
        print("\n✗ No pages discovered!")
        return
    
    # Phase 2: Scrape all pages
    print(f"\n{'='*70}")
    print("PHASE 2: SCRAPING ITEM DATA")
    print("="*70)
    print(f"\nScraping {len(item_pages)} pages with {max_workers} threads...\n")
    
    os.makedirs(output_dir, exist_ok=True)
    
    all_items = []
    completed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(extract_item_data, url, quiet=True): url 
            for url in item_pages
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                item_data = future.result()
                if item_data:
                    all_items.append(item_data)
                    completed += 1
                    
                    if completed % 25 == 0 or completed == len(item_pages):
                        print(f"  Progress: {completed}/{len(item_pages)} ({(completed/len(item_pages)*100):.1f}%)", end='\r')
                else:
                    failed += 1
                    
            except Exception as e:
                print(f"\n  [ERROR] {url}: {e}")
                failed += 1
    
    print(f"\n\n✓ Scraped {completed} items\n")
    
    # Categorize and save
    print(f"{'='*70}")
    print("CATEGORIZING AND SAVING")
    print("="*70)
    
    items_by_category = categorize_items(all_items)
    
    print(f"\nOrganized into {len(items_by_category)} categories:")
    for cat_name, cat_items in sorted(items_by_category.items()):
        print(f"  • {cat_name.replace('_', ' ').title()}: {len(cat_items)} items")
    
    # Save files
    print(f"\n{'='*70}")
    print("SAVING FILES")
    print("="*70)
    
    # Create directory structure
    for category in items_by_category.keys():
        category_dir = os.path.join(output_dir, category)
        os.makedirs(category_dir, exist_ok=True)
    
    # Save individual item files
    print("\n📄 Saving individual item files...")
    items_saved = 0
    
    for category, items in sorted(items_by_category.items()):
        category_dir = os.path.join(output_dir, category)
        
        for item in items:
            # Create safe filename from item name
            safe_name = re.sub(r'[^\w\s-]', '', item['name'])
            safe_name = re.sub(r'[-\s]+', '_', safe_name).lower()
            filename = f"{safe_name}.json"
            filepath = os.path.join(category_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(item, f, indent=2, ensure_ascii=False)
            
            items_saved += 1
        
        if items_saved % 50 == 0:
            print(f"  Saved {items_saved}/{len(all_items)} items...", end='\r')
    
    print(f"  ✓ Saved {items_saved} individual item files")
    
    # Save category collection files
    print("\n📦 Saving category collection files...")
    for category, items in sorted(items_by_category.items()):
        filepath = os.path.join(output_dir, f"{category}.json")
        display_name = category.replace('_', ' ').title()
        
        data = {
            "category": display_name,
            "count": len(items),
            "items": sorted(items, key=lambda x: x['name'])
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ {category}.json ({len(items)} items)")
    
    # Save master index with metadata only (no full item data)
    print("\n📋 Creating master index...")
    index = {
        "total_items": len(all_items),
        "categories": {},
        "items_index": []
    }
    
    for category, items in sorted(items_by_category.items()):
        index["categories"][category] = {
            "count": len(items),
            "display_name": category.replace('_', ' ').title()
        }
        
        for item in items:
            safe_name = re.sub(r'[^\w\s-]', '', item['name'])
            safe_name = re.sub(r'[-\s]+', '_', safe_name).lower()
            
            index["items_index"].append({
                "name": item['name'],
                "category": category,
                "file": f"{category}/{safe_name}.json",
                "type": item.get('item_type', 'unknown'),
                "tier": item.get('tier', 0),
                "url": item.get('url', '')
            })
    
    # Sort index by name
    index["items_index"] = sorted(index["items_index"], key=lambda x: x['name'])
    
    index_path = os.path.join(output_dir, "index.json")
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"  ✓ index.json (master index with {len(all_items)} items)")
    
    # Save complete dataset (for backwards compatibility)
    complete_filepath = os.path.join(output_dir, "all_items.json")
    with open(complete_filepath, 'w', encoding='utf-8') as f:
        json.dump({
            "total_items": len(all_items),
            "items": sorted(all_items, key=lambda x: x['name'])
        }, f, indent=2, ensure_ascii=False)
    print(f"  ✓ all_items.json (complete dataset)")
    
    # Summary
    summary = {
        "total_items": len(all_items),
        "failed_items": failed,
        "categories": {k: len(v) for k, v in sorted(items_by_category.items())},
        "scrape_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://icarus.fandom.com",
        "structure": {
            "individual_files": f"{len(all_items)} files in category subfolders",
            "category_collections": f"{len(items_by_category)} category JSON files",
            "master_index": "index.json with item metadata and file paths"
        }
    }
    
    with open(os.path.join(output_dir, "_summary.json"), 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"  ✓ _summary.json")
    
    print(f"\n{'='*70}")
    print("✅ SCRAPING COMPLETE!")
    print("="*70)
    print(f"Total items: {len(all_items)}")
    print(f"Failed: {failed}")
    print(f"\n📁 File Structure:")
    print(f"  icarus_data/")
    print(f"    ├── index.json (master index)")
    print(f"    ├── all_items.json (complete dataset)")
    print(f"    ├── _summary.json (statistics)")
    for category in sorted(items_by_category.keys()):
        item_count = len(items_by_category[category])
        print(f"    ├── {category}.json ({item_count} items)")
        print(f"    └── {category}/ ({item_count} individual files)")
    print("="*70)

if __name__ == "__main__":
    print("\nICARUS FANDOM WIKI SCRAPER")
    print("This will scrape items from icarus.fandom.com")
    print("\nEstimated time: 10-20 minutes")
    
    confirm = input("\nContinue? (yes/no): ").strip().lower()
    
    if confirm == "yes":
        scrape_all_items(max_workers=5)
    else:
        print("Aborted.")