#!/usr/bin/env python3
"""
Icarus Fandom Wiki Database Scraper - ENHANCED VERSION
Comprehensive scraper with update mode, multiple recipe support, and parallel processing

Installation:
pip install requests beautifulsoup4 lxml

Usage:
python RecipeScraping.py              # Full scrape (discovers all pages)
python RecipeScraping.py --update     # Update existing files only
"""

import json
import os
import re
import time
import argparse
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from pathlib import Path

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
            
            # Find category members
            category_content = soup.find('div', class_='category-page__members')
            
            members_found = 0
            if category_content:
                for link in category_content.find_all('a', class_='category-page__member-link'):
                    href = link.get('href', '')
                    if href and '/wiki/' in href:
                        if href.startswith('http'):
                            full_url = href
                        elif href.startswith('/'):
                            full_url = BASE_URL + href
                        else:
                            full_url = BASE_URL + '/' + href
                        
                        if 'Category:' in full_url:
                            subcategories.add(full_url)
                        elif not any(x in full_url for x in ['File:', 'Special:', 'User:', 'Talk:']):
                            all_pages.add(full_url)
                            members_found += 1
            
            print(f"✓ Found {members_found} items")
            
            # Look for "next page" link
            next_link = soup.find('a', class_='category-page__pagination-next')
            if next_link and next_link.get('href'):
                next_href = next_link['href']
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
    
    # Also scan main database pages
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
            content = soup.find('div', class_='mw-parser-output')
            if content:
                for link in content.find_all('a', href=True):
                    href = link['href']
                    if '/wiki/' in href and not any(x in href for x in ['Category:', 'File:', 'Special:', 'Talk:', 'User:']):
                        if href.startswith('http'):
                            full_url = href
                        elif href.startswith('/'):
                            full_url = BASE_URL + href
                        else:
                            full_url = BASE_URL + '/' + href
                        
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
    
    infobox = soup.find('aside', class_='portable-infobox') or soup.find('table', class_='infobox')
    
    if infobox:
        for row in infobox.find_all(['div', 'tr']):
            label_elem = row.find(['h3', 'th', 'div'], class_=re.compile('label|header'))
            value_elem = row.find(['div', 'td'], class_=re.compile('value|data'))
            
            if label_elem and value_elem:
                label = label_elem.get_text(strip=True)
                value = value_elem.get_text(strip=True)
                
                if label and value:
                    infobox_data[label.lower()] = value
    
    return infobox_data

def parse_crafting_tables(soup, page_text):
    """
    Extract ALL crafting recipes from tables - supports multiple recipes with talents
    Returns list of recipe dictionaries
    """
    
    recipes = []
    
    # Look for all tables on the page
    for table in soup.find_all('table'):
        table_text = table.get_text().lower()
        
        # Check if it's a crafting/recipe table
        if not any(word in table_text for word in ['craft', 'recipe', 'materials', 'required', 'ingredients', 'amount']):
            continue
        
        recipe = {
            "ingredients": {},
            "output_quantity": 1,
            "talent": None
        }
        
        # Check for talent requirement (look in text before table)
        prev_elements = []
        prev = table.find_previous()
        
        # Look back at previous 3 elements
        for _ in range(3):
            if prev:
                prev_elements.append(prev.get_text() if hasattr(prev, 'get_text') else str(prev))
                prev = prev.find_previous()
        
        prev_text = ' '.join(prev_elements)
        
        # Check for talent patterns
        talent_patterns = [
            (r'talent[:\s]+([A-Z][^.\n]{5,50})', 1),
            (r'with[:\s]+([A-Z][a-zA-Z\s:]+)\s+talent', 1),
            (r'([A-Z][a-zA-Z\s:]+)\s+reduces', 1),
            (r'Pistol Proficiency', 0),
            (r'Rifle Proficiency', 0),
            (r'Shotgun Proficiency', 0),
            (r'Ammunition:\s*Munitions', 0),
            (r'Ammunition:\s*Freebies', 0)
        ]
        
        for pattern, group in talent_patterns:
            match = re.search(pattern, prev_text, re.IGNORECASE)
            if match:
                if group == 0:
                    recipe["talent"] = match.group(0)
                else:
                    recipe["talent"] = match.group(group).strip()
                break
        
        # Parse ingredients from table rows
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        has_amount_col = 'amount' in headers
        
        rows = table.find_all('tr')[1:]  # Skip header
        
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) < 2:
                continue
            
            # Try to find amount and material
            amount_val = None
            material_names = []
            
            for i, cell in enumerate(cols):
                cell_text = cell.get_text(strip=True)
                
                # Check if this cell contains a quantity
                qty_match = re.search(r'^(\d+)\s*×?$|^(\d+)
"""
Icarus Wiki Scraper - Updates existing JSON files without overwriting manual edits
Handles multiple recipes (with and without talents)
"""

import json
import requests
from bs4 import BeautifulSoup
import os
import time
from pathlib import Path

BASE_URL = "https://icarus.fandom.com"
DATA_DIR = Path("icarus_data")

def clean_text(text):
    """Clean up text from wiki"""
    if not text:
        return ""
    return text.strip().replace('\n', ' ').replace('\r', '')

def parse_recipe_table(soup, item_name):
    """Parse recipe tables from wiki page - handles multiple recipes with talents"""
    recipes = []
    
    # Find all recipe tables
    tables = soup.find_all('table', class_='article-table')
    
    for table in tables:
        # Check if this is a crafting table
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        if 'Amount' not in headers and 'Material' not in headers:
            continue
            
        recipe = {
            "ingredients": {},
            "output_quantity": 1,
            "talent": None
        }
        
        # Check for talent requirement (usually in text before table)
        prev_text = ""
        prev_elem = table.find_previous('p')
        if prev_elem:
            prev_text = prev_elem.get_text()
            if "talent" in prev_text.lower():
                # Extract talent name
                if "Pistol Proficiency" in prev_text:
                    recipe["talent"] = "Pistol Proficiency"
                elif "Munitions" in prev_text:
                    recipe["talent"] = "Ammunition: Munitions"
                # Add more talent patterns as needed
        
        # Parse ingredients from table
        rows = table.find_all('tr')[1:]  # Skip header
        output_qty = None
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                # First column is quantity
                qty_text = cols[0].get_text(strip=True)
                try:
                    qty = int(qty_text)
                except:
                    continue
                
                # Second column contains material links
                materials = cols[1].find_all('a')
                if materials:
                    for mat_link in materials:
                        mat_name = mat_link.get('title', mat_link.get_text(strip=True))
                        if mat_name and mat_name not in recipe["ingredients"]:
                            recipe["ingredients"][mat_name] = qty
                else:
                    # If no output quantity found yet, this might be it
                    if output_qty is None and len(cols) == 1:
                        try:
                            output_qty = int(qty_text)
                        except:
                            pass
        
        if recipe["ingredients"]:
            if output_qty:
                recipe["output_quantity"] = output_qty
            recipes.append(recipe)
    
    return recipes if recipes else None

def scrape_item_page(item_name, url):
    """Scrape an item's wiki page"""
    try:
        print(f"  Fetching: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            "name": item_name,
            "url": url
        }
        
        # Extract description
        desc_elem = soup.find('div', {'data-source': 'description'})
        if not desc_elem:
            # Try finding first paragraph in content
            content = soup.find('div', class_='mw-parser-output')
            if content:
                first_p = content.find('p')
                if first_p:
                    data["description"] = clean_text(first_p.get_text())
        else:
            data["description"] = clean_text(desc_elem.get_text())
        
        # Parse recipes (may be multiple with talents)
        recipes = parse_recipe_table(soup, item_name)
        if recipes:
            if len(recipes) == 1:
                # Single recipe - use old format
                data["ingredients"] = recipes[0]["ingredients"]
                data["output_quantity"] = recipes[0].get("output_quantity", 1)
            else:
                # Multiple recipes - use new format
                data["recipes"] = recipes
        
        # Extract crafted_at from infobox
        infobox = soup.find('aside', class_='portable-infobox')
        if infobox:
            for row in infobox.find_all('div', class_='pi-item'):
                label = row.find('h3', class_='pi-data-label')
                value = row.find('div', class_='pi-data-value')
                
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = clean_text(value.get_text())
                    
                    if 'crafted' in label_text:
                        data["crafted_at"] = value_text
                    elif 'tier' in label_text:
                        try:
                            data["tier"] = int(value_text.replace('Tier ', ''))
                        except:
                            pass
                    elif 'weight' in label_text:
                        if "stats" not in data:
                            data["stats"] = {}
                        data["stats"]["weight"] = value_text
        
        # Try to determine item category from page categories
        categories = soup.find_all('a', href=lambda x: x and '/wiki/Category:' in x)
        for cat in categories:
            cat_name = cat.get_text(strip=True)
            if cat_name and cat_name != "Community content":
                data["category"] = cat_name
                break
        
        return data
        
    except Exception as e:
        print(f"  ERROR scraping {item_name}: {e}")
        return None

def should_update_field(existing_value, new_value):
    """Determine if a field should be updated"""
    if existing_value is None or existing_value == "":
        return True
    if str(existing_value).lower() == "unknown":
        return True
    if existing_value == {}:
        return True
    return False

def update_json_file(file_path, scraped_data):
    """Update existing JSON file with scraped data, preserving manual edits"""
    try:
        # Load existing data
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        updated = False
        
        # Update only unknown/empty fields
        for key, new_value in scraped_data.items():
            if key == "name" or key == "url":
                # Always update these
                existing_data[key] = new_value
                continue
            
            if key not in existing_data:
                existing_data[key] = new_value
                updated = True
                print(f"    Added field: {key}")
            elif should_update_field(existing_data.get(key), new_value):
                existing_data[key] = new_value
                updated = True
                print(f"    Updated field: {key}")
        
        if updated:
            # Save back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            print(f"  ✓ Updated: {file_path}")
            return True
        else:
            print(f"  ✓ No updates needed: {file_path}")
            return False
            
    except Exception as e:
        print(f"  ERROR updating {file_path}: {e}")
        return False

def process_directory(directory):
    """Process all JSON files in a directory"""
    updated_count = 0
    error_count = 0
    skipped_count = 0
    
    json_files = list(directory.glob("*.json"))
    print(f"\nProcessing {len(json_files)} files in {directory.name}/")
    
    for json_file in json_files:
        try:
            # Load existing JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            item_name = data.get("name")
            if not item_name:
                print(f"⚠ Skipping {json_file.name}: No name field")
                skipped_count += 1
                continue
            
            # Check if needs updating
            needs_update = (
                should_update_field(data.get("crafted_at"), None) or
                should_update_field(data.get("ingredients"), None) or
                should_update_field(data.get("description"), None)
            )
            
            if not needs_update:
                print(f"✓ {item_name}: Already complete")
                skipped_count += 1
                continue
            
            print(f"\n📝 {item_name}")
            
            # Get URL or construct it
            url = data.get("url")
            if not url:
                # Construct wiki URL from name
                wiki_name = item_name.replace(" ", "_")
                url = f"{BASE_URL}/wiki/{wiki_name}"
            
            # Scrape the page
            scraped_data = scrape_item_page(item_name, url)
            
            if scraped_data:
                if update_json_file(json_file, scraped_data):
                    updated_count += 1
            else:
                error_count += 1
            
            # Be nice to the wiki server
            time.sleep(1)
            
        except Exception as e:
            print(f"ERROR processing {json_file}: {e}")
            error_count += 1
    
    return updated_count, skipped_count, error_count

def main():
    """Main scraper function"""
    print("🚀 ICARUS Wiki Scraper - Update Mode")
    print("=" * 60)
    print("This will update existing JSON files with missing data")
    print("Manual edits will be preserved")
    print("=" * 60)
    
    if not DATA_DIR.exists():
        print(f"❌ Data directory not found: {DATA_DIR}")
        return
    
    total_updated = 0
    total_skipped = 0
    total_errors = 0
    
    # Process each subdirectory
    for subdir in DATA_DIR.iterdir():
        if subdir.is_dir():
            updated, skipped, errors = process_directory(subdir)
            total_updated += updated
            total_skipped += skipped
            total_errors += errors
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  ✓ Updated: {total_updated}")
    print(f"  ⊘ Skipped: {total_skipped}")
    print(f"  ✗ Errors: {total_errors}")
    print("=" * 60)

if __name__ == "__main__":
    main()
, cell_text)
                if qty_match:
                    amount_val = int(qty_match.group(1) or qty_match.group(2))
                    continue
                
                # Extract material names from links
                links = cell.find_all('a')
                for link in links:
                    mat_name = link.get('title') or link.get_text(strip=True)
                    if mat_name and len(mat_name) > 1:
                        # Clean material name
                        mat_name = re.sub(r'\d+\s*×?\s*', '', mat_name).strip()
                        if mat_name and mat_name not in ['', 'x', 'X']:
                            material_names.append(mat_name)
            
            # Add ingredients
            if amount_val and material_names:
                for mat_name in material_names:
                    recipe["ingredients"][mat_name] = amount_val
        
        # Check if we found any ingredients
        if recipe["ingredients"]:
            # Try to find output quantity
            output_match = re.search(r'(?:output|yields?|produces?|crafts?)[:\s]+(\d+)', prev_text, re.IGNORECASE)
            if output_match:
                recipe["output_quantity"] = int(output_match.group(1))
            
            recipes.append(recipe)
    
    # If we found multiple recipes, make sure at least one doesn't have a talent
    # (for base recipe)
    if len(recipes) > 1:
        has_base = any(r["talent"] is None for r in recipes)
        if not has_base:
            # Mark the first one as base
            recipes[0]["talent"] = None
    
    return recipes if recipes else None

def parse_crafting_station(soup, page_text):
    """Extract crafting station/location"""
    
    crafted_at = "Unknown"
    
    # Method 1: Look for text patterns
    craft_patterns = [
        r'Crafted (?:at|in|using)[:\s]+([^.\n]+)',
        r'(?:Made|Built|Created) at[:\s]+([^.\n]+)',
        r'Requires[:\s]+([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge|Fabricator|Printer))',
        r'Station[:\s]+([^.\n]+)',
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
                if 'craft' in row_text or 'station' in row_text or 'made' in row_text:
                    value = row.get_text(strip=True)
                    for word in ['bench', 'station', 'furnace', 'forge', 'fabricator', 'printer', 'character']:
                        if word in value.lower():
                            match = re.search(r'([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge|Fabricator|Printer|Character))', value)
                            if match:
                                crafted_at = match.group(1).strip()
                                break
                    if crafted_at != "Unknown":
                        break
    
    return crafted_at

def extract_item_data(page_url, quiet=True):
    """Extract comprehensive item data from a Fandom wiki page"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    item_name = page_url.split('/wiki/')[-1].replace('_', ' ')
    
    item_data = {
        "name": item_name,
        "url": page_url,
        "description": "",
        "item_type": "unknown",
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
                if desc and len(desc) > 20 and len(desc) < 1000:
                    if not re.search(r'(Category|Statistics|Weight|Durability|Attributes|Prerequisites)', desc):
                        item_data['description'] = desc
                        break
        
        # Extract infobox data
        infobox_data = extract_infobox_data(soup)
        
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
        
        # Extract crafting recipes (may be multiple with talents!)
        recipes = parse_crafting_tables(soup, page_text)
        
        if recipes:
            if len(recipes) == 1:
                # Single recipe - use old format
                item_data['ingredients'] = recipes[0]['ingredients']
                item_data['output_quantity'] = recipes[0].get('output_quantity', 1)
            else:
                # Multiple recipes - use new format
                item_data['recipes'] = recipes
            
            if item_data['item_type'] == 'unknown':
                item_data['item_type'] = 'craftable'
        
        # Extract crafting station
        crafted_at = parse_crafting_station(soup, page_text)
        if crafted_at != "Unknown":
            item_data['crafted_at'] = crafted_at
            if item_data['item_type'] == 'unknown':
                item_data['item_type'] = 'craftable'
        
        # Look for harvesting info
        if any(word in page_text.lower() for word in ['harvested', 'foraged', 'gathered', 'mined']):
            item_data['item_type'] = 'harvestable'
            
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
        
        # Only mark as orbital if we found costs
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

def should_update_field(existing_value, new_value):
    """Determine if a field should be updated"""
    if existing_value is None or existing_value == "":
        return True
    if str(existing_value).lower() == "unknown":
        return True
    if existing_value == {}:
        return True
    return False

def update_existing_file(filepath, scraped_data):
    """Update existing JSON file, preserving manual edits"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        updated = False
        
        for key, new_value in scraped_data.items():
            if key in ["name", "url"]:
                existing_data[key] = new_value
                continue
            
            if key not in existing_data:
                existing_data[key] = new_value
                updated = True
            elif should_update_field(existing_data.get(key), new_value):
                existing_data[key] = new_value
                updated = True
        
        if updated:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            return True
        return False
            
    except Exception as e:
        print(f"  ERROR updating {filepath}: {e}")
        return False

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
        "misc": []
    }
    
    for item in items:
        name_lower = item['name'].lower()
        item_type = item.get('item_type', 'unknown')
        category = item.get('category', '').lower()
        
        categorized = False
        
        # Building - Furniture (benches, stations, etc.)
        if not categorized and any(word in name_lower for word in ['bench', 'table', 'chair', 'bed', 'furnace', 'forge', 'station', 'storage', 'chest', 'fabricator', 'printer', 'stove']):
            categories['building_furniture'].append(item)
            categorized = True
        
        # Building - Structures
        if not categorized and any(word in name_lower for word in ['wall', 'floor', 'roof', 'ramp', 'door', 'window', 'stairs', 'foundation', 'pillar', 'beam', 'corner', 'ceiling']):
            categories['building_structures'].append(item)
            categorized = True
        
        # Ammunition
        if not categorized and any(word in name_lower for word in ['bullet', 'shell', 'arrow', 'ammo', 'cartridge', 'round', 'bolt', 'javelin']):
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
        if not categorized and (item_type == 'armor' or any(word in name_lower for word in ['armor', 'helmet', 'boots', 'gloves', 'suit', 'vest', 'envirosuit'])):
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
        if not categorized and any(word in name_lower for word in ['medicine', 'bandage', 'paste', 'cure', 'antibiotic', 'syringe', 'pill', 'tonic']):
            categories['consumables_medicine'].append(item)
            categorized = True
        
        # Resources - Raw
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
        
        if not categorized:
            categories['misc'].append(item)
    
    return {k: v for k, v in categories.items() if v}

def update_mode(data_dir="icarus_data"):
    """Update existing files without full scrape"""
    
    print("="*70)
    print("UPDATE MODE - Updating existing files only")
    print("="*70)
    
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"\n✗ Data directory not found: {data_dir}")
        return
    
    # Find all JSON files
    all_files = []
    for subdir in data_path.iterdir():
        if subdir.is_dir():
            all_files.extend(list(subdir.glob("*.json")))
    
    print(f"\nFound {len(all_files)} JSON files to update")
    
    # Filter files that need updating
    files_to_update = []
    for filepath in all_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            needs_update = (
                should_update_field(data.get("crafted_at"), None) or
                should_update_field(data.get("ingredients"), None) or
                should_update_field(data.get("description"), None) or
                data.get("url")  # Always try to update if we have a URL
            )
            
            if needs_update:
                files_to_update.append((filepath, data))
        except Exception as e:
            print(f"⚠️  Error reading {filepath}: {e}")
    
    print(f"Found {len(files_to_update)} files that need updating\n")
    
    if not files_to_update:
        print("✓ All files are up to date!")
        return
    
    # Update files
    updated_count = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        
        for filepath, existing_data in files_to_update:
            url = existing_data.get("url")
            if not url:
                # Try to construct URL from name
                item_name = existing_data.get("name", filepath.stem)
                url = f"{BASE_URL}/wiki/{item_name.replace(' ', '_')}"
            
            future = executor.submit(extract_item_data, url, quiet=True)
            futures[future] = (filepath, existing_data)
        
        for future in as_completed(futures):
            filepath, existing_data = futures[future]
            
            try:
                scraped_data = future.result()
                
                if scraped_data and update_existing_file(filepath, scraped_data):
                    updated_count += 1
                    print(f"✓ Updated: {filepath.name}")
                else:
                    print(f"⊘ No changes: {filepath.name}")
                    
            except Exception as e:
                print(f"✗ Error: {filepath.name} - {e}")
    
    print(f"\n{'='*70}")
    print(f"✓ UPDATE COMPLETE")
    print(f"{'='*70}")
    print(f"Updated: {updated_count}/{len(files_to_update)} files")

def full_scrape(output_dir="icarus_data", max_workers=5):
    """Full scrape with discovery"""
    
    print("="*70)
    print("  ICARUS FANDOM WIKI SCRAPER - FULL MODE")
    print("="*70)
    
    # Phase 1: Discover
    item_pages = discover_all_item_pages()
    
    if not item_pages:
        print("\n✗ No pages discovered!")
        return
    
    # Phase 2: Scrape
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
    
    # Create directories
    for category in items_by_category.keys():
        category_dir = os.path.join(output_dir, category)
        os.makedirs(category_dir, exist_ok=True)
    
    # Save individual files
    print("\n📄 Saving individual item files...")
    items_saved = 0
    
    for category, items in sorted(items_by_category.items()):
        category_dir = os.path.join(output_dir, category)
        
        for item in items:
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
    
    # Create manifest
    print("\n📋 Creating manifest...")
    manifest = []
    for category, items in sorted(items_by_category.items()):
        for item in items:
            safe_name = re.sub(r'[^\w\s-]', '', item['name'])
            safe_name = re.sub(r'[-\s]+', '_', safe_name).lower()
            manifest.append(f"{category}/{safe_name}.json")
    
    with open(os.path.join(output_dir, "manifest.json"), 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"  ✓ manifest.json ({len(manifest)} files)")
    
    # Summary
    summary = {
        "total_items": len(all_items),
        "failed_items": failed,
        "categories": {k: len(v) for k, v in sorted(items_by_category.items())},
        "scrape_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://icarus.fandom.com"
    }
    
    with open(os.path.join(output_dir, "_summary.json"), 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print("✅ SCRAPING COMPLETE!")
    print("="*70)
    print(f"Total items: {len(all_items)}")
    print(f"Failed: {failed}")
    print("\n💡 Next step: Run 'python build_bundle.py' to create the bundle file")
    print("="*70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Icarus Wiki Scraper')
    parser.add_argument('--update', action='store_true', help='Update existing files only (no discovery)')
    parser.add_argument('--workers', type=int, default=5, help='Number of parallel workers')
    
    args = parser.parse_args()
    
    if args.update:
        update_mode()
    else:
        print("\nICARUS FANDOM WIKI SCRAPER")
        print("This will scrape items from icarus.fandom.com")
        print("\nEstimated time: 10-20 minutes")
        
        confirm = input("\nContinue? (yes/no): ").strip().lower()
        
        if confirm == "yes":
            full_scrape(max_workers=args.workers)
        else:
            print("Aborted.")#!/usr/bin/env python3
"""
Icarus Wiki Scraper - Updates existing JSON files without overwriting manual edits
Handles multiple recipes (with and without talents)
"""

import json
import requests
from bs4 import BeautifulSoup
import os
import time
from pathlib import Path

BASE_URL = "https://icarus.fandom.com"
DATA_DIR = Path("icarus_data")

def clean_text(text):
    """Clean up text from wiki"""
    if not text:
        return ""
    return text.strip().replace('\n', ' ').replace('\r', '')

def parse_recipe_table(soup, item_name):
    """Parse recipe tables from wiki page - handles multiple recipes with talents"""
    recipes = []
    
    # Find all recipe tables
    tables = soup.find_all('table', class_='article-table')
    
    for table in tables:
        # Check if this is a crafting table
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        if 'Amount' not in headers and 'Material' not in headers:
            continue
            
        recipe = {
            "ingredients": {},
            "output_quantity": 1,
            "talent": None
        }
        
        # Check for talent requirement (usually in text before table)
        prev_text = ""
        prev_elem = table.find_previous('p')
        if prev_elem:
            prev_text = prev_elem.get_text()
            if "talent" in prev_text.lower():
                # Extract talent name
                if "Pistol Proficiency" in prev_text:
                    recipe["talent"] = "Pistol Proficiency"
                elif "Munitions" in prev_text:
                    recipe["talent"] = "Ammunition: Munitions"
                # Add more talent patterns as needed
        
        # Parse ingredients from table
        rows = table.find_all('tr')[1:]  # Skip header
        output_qty = None
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                # First column is quantity
                qty_text = cols[0].get_text(strip=True)
                try:
                    qty = int(qty_text)
                except:
                    continue
                
                # Second column contains material links
                materials = cols[1].find_all('a')
                if materials:
                    for mat_link in materials:
                        mat_name = mat_link.get('title', mat_link.get_text(strip=True))
                        if mat_name and mat_name not in recipe["ingredients"]:
                            recipe["ingredients"][mat_name] = qty
                else:
                    # If no output quantity found yet, this might be it
                    if output_qty is None and len(cols) == 1:
                        try:
                            output_qty = int(qty_text)
                        except:
                            pass
        
        if recipe["ingredients"]:
            if output_qty:
                recipe["output_quantity"] = output_qty
            recipes.append(recipe)
    
    return recipes if recipes else None

def scrape_item_page(item_name, url):
    """Scrape an item's wiki page"""
    try:
        print(f"  Fetching: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            "name": item_name,
            "url": url
        }
        
        # Extract description
        desc_elem = soup.find('div', {'data-source': 'description'})
        if not desc_elem:
            # Try finding first paragraph in content
            content = soup.find('div', class_='mw-parser-output')
            if content:
                first_p = content.find('p')
                if first_p:
                    data["description"] = clean_text(first_p.get_text())
        else:
            data["description"] = clean_text(desc_elem.get_text())
        
        # Parse recipes (may be multiple with talents)
        recipes = parse_recipe_table(soup, item_name)
        if recipes:
            if len(recipes) == 1:
                # Single recipe - use old format
                data["ingredients"] = recipes[0]["ingredients"]
                data["output_quantity"] = recipes[0].get("output_quantity", 1)
            else:
                # Multiple recipes - use new format
                data["recipes"] = recipes
        
        # Extract crafted_at from infobox
        infobox = soup.find('aside', class_='portable-infobox')
        if infobox:
            for row in infobox.find_all('div', class_='pi-item'):
                label = row.find('h3', class_='pi-data-label')
                value = row.find('div', class_='pi-data-value')
                
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = clean_text(value.get_text())
                    
                    if 'crafted' in label_text:
                        data["crafted_at"] = value_text
                    elif 'tier' in label_text:
                        try:
                            data["tier"] = int(value_text.replace('Tier ', ''))
                        except:
                            pass
                    elif 'weight' in label_text:
                        if "stats" not in data:
                            data["stats"] = {}
                        data["stats"]["weight"] = value_text
        
        # Try to determine item category from page categories
        categories = soup.find_all('a', href=lambda x: x and '/wiki/Category:' in x)
        for cat in categories:
            cat_name = cat.get_text(strip=True)
            if cat_name and cat_name != "Community content":
                data["category"] = cat_name
                break
        
        return data
        
    except Exception as e:
        print(f"  ERROR scraping {item_name}: {e}")
        return None

def should_update_field(existing_value, new_value):
    """Determine if a field should be updated"""
    if existing_value is None or existing_value == "":
        return True
    if str(existing_value).lower() == "unknown":
        return True
    if existing_value == {}:
        return True
    return False

def update_json_file(file_path, scraped_data):
    """Update existing JSON file with scraped data, preserving manual edits"""
    try:
        # Load existing data
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        updated = False
        
        # Update only unknown/empty fields
        for key, new_value in scraped_data.items():
            if key == "name" or key == "url":
                # Always update these
                existing_data[key] = new_value
                continue
            
            if key not in existing_data:
                existing_data[key] = new_value
                updated = True
                print(f"    Added field: {key}")
            elif should_update_field(existing_data.get(key), new_value):
                existing_data[key] = new_value
                updated = True
                print(f"    Updated field: {key}")
        
        if updated:
            # Save back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            print(f"  ✓ Updated: {file_path}")
            return True
        else:
            print(f"  ✓ No updates needed: {file_path}")
            return False
            
    except Exception as e:
        print(f"  ERROR updating {file_path}: {e}")
        return False

def process_directory(directory):
    """Process all JSON files in a directory"""
    updated_count = 0
    error_count = 0
    skipped_count = 0
    
    json_files = list(directory.glob("*.json"))
    print(f"\nProcessing {len(json_files)} files in {directory.name}/")
    
    for json_file in json_files:
        try:
            # Load existing JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            item_name = data.get("name")
            if not item_name:
                print(f"⚠ Skipping {json_file.name}: No name field")
                skipped_count += 1
                continue
            
            # Check if needs updating
            needs_update = (
                should_update_field(data.get("crafted_at"), None) or
                should_update_field(data.get("ingredients"), None) or
                should_update_field(data.get("description"), None)
            )
            
            if not needs_update:
                print(f"✓ {item_name}: Already complete")
                skipped_count += 1
                continue
            
            print(f"\n📝 {item_name}")
            
            # Get URL or construct it
            url = data.get("url")
            if not url:
                # Construct wiki URL from name
                wiki_name = item_name.replace(" ", "_")
                url = f"{BASE_URL}/wiki/{wiki_name}"
            
            # Scrape the page
            scraped_data = scrape_item_page(item_name, url)
            
            if scraped_data:
                if update_json_file(json_file, scraped_data):
                    updated_count += 1
            else:
                error_count += 1
            
            # Be nice to the wiki server
            time.sleep(1)
            
        except Exception as e:
            print(f"ERROR processing {json_file}: {e}")
            error_count += 1
    
    return updated_count, skipped_count, error_count

def main():
    """Main scraper function"""
    print("🚀 ICARUS Wiki Scraper - Update Mode")
    print("=" * 60)
    print("This will update existing JSON files with missing data")
    print("Manual edits will be preserved")
    print("=" * 60)
    
    if not DATA_DIR.exists():
        print(f"❌ Data directory not found: {DATA_DIR}")
        return
    
    total_updated = 0
    total_skipped = 0
    total_errors = 0
    
    # Process each subdirectory
    for subdir in DATA_DIR.iterdir():
        if subdir.is_dir():
            updated, skipped, errors = process_directory(subdir)
            total_updated += updated
            total_skipped += skipped
            total_errors += errors
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  ✓ Updated: {total_updated}")
    print(f"  ⊘ Skipped: {total_skipped}")
    print(f"  ✗ Errors: {total_errors}")
    print("=" * 60)

if __name__ == "__main__":
    main()
, cell_text)
"""
Icarus Wiki Scraper - Updates existing JSON files without overwriting manual edits
Handles multiple recipes (with and without talents)
"""

import json
import requests
from bs4 import BeautifulSoup
import os
import time
from pathlib import Path

BASE_URL = "https://icarus.fandom.com"
DATA_DIR = Path("icarus_data")

def clean_text(text):
    """Clean up text from wiki"""
    if not text:
        return ""
    return text.strip().replace('\n', ' ').replace('\r', '')

def parse_recipe_table(soup, item_name):
    """Parse recipe tables from wiki page - handles multiple recipes with talents"""
    recipes = []
    
    # Find all recipe tables
    tables = soup.find_all('table', class_='article-table')
    
    for table in tables:
        # Check if this is a crafting table
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        if 'Amount' not in headers and 'Material' not in headers:
            continue
            
        recipe = {
            "ingredients": {},
            "output_quantity": 1,
            "talent": None
        }
        
        # Check for talent requirement (usually in text before table)
        prev_text = ""
        prev_elem = table.find_previous('p')
        if prev_elem:
            prev_text = prev_elem.get_text()
            if "talent" in prev_text.lower():
                # Extract talent name
                if "Pistol Proficiency" in prev_text:
                    recipe["talent"] = "Pistol Proficiency"
                elif "Munitions" in prev_text:
                    recipe["talent"] = "Ammunition: Munitions"
                # Add more talent patterns as needed
        
        # Parse ingredients from table
        rows = table.find_all('tr')[1:]  # Skip header
        output_qty = None
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                # First column is quantity
                qty_text = cols[0].get_text(strip=True)
                try:
                    qty = int(qty_text)
                except:
                    continue
                
                # Second column contains material links
                materials = cols[1].find_all('a')
                if materials:
                    for mat_link in materials:
                        mat_name = mat_link.get('title', mat_link.get_text(strip=True))
                        if mat_name and mat_name not in recipe["ingredients"]:
                            recipe["ingredients"][mat_name] = qty
                else:
                    # If no output quantity found yet, this might be it
                    if output_qty is None and len(cols) == 1:
                        try:
                            output_qty = int(qty_text)
                        except:
                            pass
        
        if recipe["ingredients"]:
            if output_qty:
                recipe["output_quantity"] = output_qty
            recipes.append(recipe)
    
    return recipes if recipes else None

def scrape_item_page(item_name, url):
    """Scrape an item's wiki page"""
    try:
        print(f"  Fetching: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            "name": item_name,
            "url": url
        }
        
        # Extract description
        desc_elem = soup.find('div', {'data-source': 'description'})
        if not desc_elem:
            # Try finding first paragraph in content
            content = soup.find('div', class_='mw-parser-output')
            if content:
                first_p = content.find('p')
                if first_p:
                    data["description"] = clean_text(first_p.get_text())
        else:
            data["description"] = clean_text(desc_elem.get_text())
        
        # Parse recipes (may be multiple with talents)
        recipes = parse_recipe_table(soup, item_name)
        if recipes:
            if len(recipes) == 1:
                # Single recipe - use old format
                data["ingredients"] = recipes[0]["ingredients"]
                data["output_quantity"] = recipes[0].get("output_quantity", 1)
            else:
                # Multiple recipes - use new format
                data["recipes"] = recipes
        
        # Extract crafted_at from infobox
        infobox = soup.find('aside', class_='portable-infobox')
        if infobox:
            for row in infobox.find_all('div', class_='pi-item'):
                label = row.find('h3', class_='pi-data-label')
                value = row.find('div', class_='pi-data-value')
                
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = clean_text(value.get_text())
                    
                    if 'crafted' in label_text:
                        data["crafted_at"] = value_text
                    elif 'tier' in label_text:
                        try:
                            data["tier"] = int(value_text.replace('Tier ', ''))
                        except:
                            pass
                    elif 'weight' in label_text:
                        if "stats" not in data:
                            data["stats"] = {}
                        data["stats"]["weight"] = value_text
        
        # Try to determine item category from page categories
        categories = soup.find_all('a', href=lambda x: x and '/wiki/Category:' in x)
        for cat in categories:
            cat_name = cat.get_text(strip=True)
            if cat_name and cat_name != "Community content":
                data["category"] = cat_name
                break
        
        return data
        
    except Exception as e:
        print(f"  ERROR scraping {item_name}: {e}")
        return None

def should_update_field(existing_value, new_value):
    """Determine if a field should be updated"""
    if existing_value is None or existing_value == "":
        return True
    if str(existing_value).lower() == "unknown":
        return True
    if existing_value == {}:
        return True
    return False

def update_json_file(file_path, scraped_data):
    """Update existing JSON file with scraped data, preserving manual edits"""
    try:
        # Load existing data
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        updated = False
        
        # Update only unknown/empty fields
        for key, new_value in scraped_data.items():
            if key == "name" or key == "url":
                # Always update these
                existing_data[key] = new_value
                continue
            
            if key not in existing_data:
                existing_data[key] = new_value
                updated = True
                print(f"    Added field: {key}")
            elif should_update_field(existing_data.get(key), new_value):
                existing_data[key] = new_value
                updated = True
                print(f"    Updated field: {key}")
        
        if updated:
            # Save back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            print(f"  ✓ Updated: {file_path}")
            return True
        else:
            print(f"  ✓ No updates needed: {file_path}")
            return False
            
    except Exception as e:
        print(f"  ERROR updating {file_path}: {e}")
        return False

def process_directory(directory):
    """Process all JSON files in a directory"""
    updated_count = 0
    error_count = 0
    skipped_count = 0
    
    json_files = list(directory.glob("*.json"))
    print(f"\nProcessing {len(json_files)} files in {directory.name}/")
    
    for json_file in json_files:
        try:
            # Load existing JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            item_name = data.get("name")
            if not item_name:
                print(f"⚠ Skipping {json_file.name}: No name field")
                skipped_count += 1
                continue
            
            # Check if needs updating
            needs_update = (
                should_update_field(data.get("crafted_at"), None) or
                should_update_field(data.get("ingredients"), None) or
                should_update_field(data.get("description"), None)
            )
            
            if not needs_update:
                print(f"✓ {item_name}: Already complete")
                skipped_count += 1
                continue
            
            print(f"\n📝 {item_name}")
            
            # Get URL or construct it
            url = data.get("url")
            if not url:
                # Construct wiki URL from name
                wiki_name = item_name.replace(" ", "_")
                url = f"{BASE_URL}/wiki/{wiki_name}"
            
            # Scrape the page
            scraped_data = scrape_item_page(item_name, url)
            
            if scraped_data:
                if update_json_file(json_file, scraped_data):
                    updated_count += 1
            else:
                error_count += 1
            
            # Be nice to the wiki server
            time.sleep(1)
            
        except Exception as e:
            print(f"ERROR processing {json_file}: {e}")
            error_count += 1
    
    return updated_count, skipped_count, error_count

def main():
    """Main scraper function"""
    print("🚀 ICARUS Wiki Scraper - Update Mode")
    print("=" * 60)
    print("This will update existing JSON files with missing data")
    print("Manual edits will be preserved")
    print("=" * 60)
    
    if not DATA_DIR.exists():
        print(f"❌ Data directory not found: {DATA_DIR}")
        return
    
    total_updated = 0
    total_skipped = 0
    total_errors = 0
    
    # Process each subdirectory
    for subdir in DATA_DIR.iterdir():
        if subdir.is_dir():
            updated, skipped, errors = process_directory(subdir)
            total_updated += updated
            total_skipped += skipped
            total_errors += errors
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  ✓ Updated: {total_updated}")
    print(f"  ⊘ Skipped: {total_skipped}")
    print(f"  ✗ Errors: {total_errors}")
    print("=" * 60)

if __name__ == "__main__":
    main()
, cell_text)
                if qty_match:
                    amount_val = int(qty_match.group(1) or qty_match.group(2))
                    continue
                
                # Extract material names from links
                links = cell.find_all('a')
                for link in links:
                    mat_name = link.get('title') or link.get_text(strip=True)
                    if mat_name and len(mat_name) > 1:
                        # Clean material name
                        mat_name = re.sub(r'\d+\s*×?\s*', '', mat_name).strip()
                        if mat_name and mat_name not in ['', 'x', 'X']:
                            material_names.append(mat_name)
            
            # Add ingredients
            if amount_val and material_names:
                for mat_name in material_names:
                    recipe["ingredients"][mat_name] = amount_val
        
        # Check if we found any ingredients
        if recipe["ingredients"]:
            # Try to find output quantity
            output_match = re.search(r'(?:output|yields?|produces?|crafts?)[:\s]+(\d+)', prev_text, re.IGNORECASE)
            if output_match:
                recipe["output_quantity"] = int(output_match.group(1))
            
            recipes.append(recipe)
    
    # If we found multiple recipes, make sure at least one doesn't have a talent
    # (for base recipe)
    if len(recipes) > 1:
        has_base = any(r["talent"] is None for r in recipes)
        if not has_base:
            # Mark the first one as base
            recipes[0]["talent"] = None
    
    return recipes if recipes else None

def parse_crafting_station(soup, page_text):
    """Extract crafting station/location"""
    
    crafted_at = "Unknown"
    
    # Method 1: Look for text patterns
    craft_patterns = [
        r'Crafted (?:at|in|using)[:\s]+([^.\n]+)',
        r'(?:Made|Built|Created) at[:\s]+([^.\n]+)',
        r'Requires[:\s]+([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge|Fabricator|Printer))',
        r'Station[:\s]+([^.\n]+)',
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
                if 'craft' in row_text or 'station' in row_text or 'made' in row_text:
                    value = row.get_text(strip=True)
                    for word in ['bench', 'station', 'furnace', 'forge', 'fabricator', 'printer', 'character']:
                        if word in value.lower():
                            match = re.search(r'([A-Z][a-zA-Z\s]+(?:Bench|Station|Furnace|Forge|Fabricator|Printer|Character))', value)
                            if match:
                                crafted_at = match.group(1).strip()
                                break
                    if crafted_at != "Unknown":
                        break
    
    return crafted_at

def extract_item_data(page_url, quiet=True):
    """Extract comprehensive item data from a Fandom wiki page"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    item_name = page_url.split('/wiki/')[-1].replace('_', ' ')
    
    item_data = {
        "name": item_name,
        "url": page_url,
        "description": "",
        "item_type": "unknown",
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
                if desc and len(desc) > 20 and len(desc) < 1000:
                    if not re.search(r'(Category|Statistics|Weight|Durability|Attributes|Prerequisites)', desc):
                        item_data['description'] = desc
                        break
        
        # Extract infobox data
        infobox_data = extract_infobox_data(soup)
        
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
        
        # Extract crafting recipes (may be multiple with talents!)
        recipes = parse_crafting_tables(soup, page_text)
        
        if recipes:
            if len(recipes) == 1:
                # Single recipe - use old format
                item_data['ingredients'] = recipes[0]['ingredients']
                item_data['output_quantity'] = recipes[0].get('output_quantity', 1)
            else:
                # Multiple recipes - use new format
                item_data['recipes'] = recipes
            
            if item_data['item_type'] == 'unknown':
                item_data['item_type'] = 'craftable'
        
        # Extract crafting station
        crafted_at = parse_crafting_station(soup, page_text)
        if crafted_at != "Unknown":
            item_data['crafted_at'] = crafted_at
            if item_data['item_type'] == 'unknown':
                item_data['item_type'] = 'craftable'
        
        # Look for harvesting info
        if any(word in page_text.lower() for word in ['harvested', 'foraged', 'gathered', 'mined']):
            item_data['item_type'] = 'harvestable'
            
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
        
        # Only mark as orbital if we found costs
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

def should_update_field(existing_value, new_value):
    """Determine if a field should be updated"""
    if existing_value is None or existing_value == "":
        return True
    if str(existing_value).lower() == "unknown":
        return True
    if existing_value == {}:
        return True
    return False

def update_existing_file(filepath, scraped_data):
    """Update existing JSON file, preserving manual edits"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        updated = False
        
        for key, new_value in scraped_data.items():
            if key in ["name", "url"]:
                existing_data[key] = new_value
                continue
            
            if key not in existing_data:
                existing_data[key] = new_value
                updated = True
            elif should_update_field(existing_data.get(key), new_value):
                existing_data[key] = new_value
                updated = True
        
        if updated:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            return True
        return False
            
    except Exception as e:
        print(f"  ERROR updating {filepath}: {e}")
        return False

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
        "misc": []
    }
    
    for item in items:
        name_lower = item['name'].lower()
        item_type = item.get('item_type', 'unknown')
        category = item.get('category', '').lower()
        
        categorized = False
        
        # Building - Furniture (benches, stations, etc.)
        if not categorized and any(word in name_lower for word in ['bench', 'table', 'chair', 'bed', 'furnace', 'forge', 'station', 'storage', 'chest', 'fabricator', 'printer', 'stove']):
            categories['building_furniture'].append(item)
            categorized = True
        
        # Building - Structures
        if not categorized and any(word in name_lower for word in ['wall', 'floor', 'roof', 'ramp', 'door', 'window', 'stairs', 'foundation', 'pillar', 'beam', 'corner', 'ceiling']):
            categories['building_structures'].append(item)
            categorized = True
        
        # Ammunition
        if not categorized and any(word in name_lower for word in ['bullet', 'shell', 'arrow', 'ammo', 'cartridge', 'round', 'bolt', 'javelin']):
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
        if not categorized and (item_type == 'armor' or any(word in name_lower for word in ['armor', 'helmet', 'boots', 'gloves', 'suit', 'vest', 'envirosuit'])):
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
        if not categorized and any(word in name_lower for word in ['medicine', 'bandage', 'paste', 'cure', 'antibiotic', 'syringe', 'pill', 'tonic']):
            categories['consumables_medicine'].append(item)
            categorized = True
        
        # Resources - Raw
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
        
        if not categorized:
            categories['misc'].append(item)
    
    return {k: v for k, v in categories.items() if v}

def update_mode(data_dir="icarus_data"):
    """Update existing files without full scrape"""
    
    print("="*70)
    print("UPDATE MODE - Updating existing files only")
    print("="*70)
    
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"\n✗ Data directory not found: {data_dir}")
        return
    
    # Find all JSON files
    all_files = []
    for subdir in data_path.iterdir():
        if subdir.is_dir():
            all_files.extend(list(subdir.glob("*.json")))
    
    print(f"\nFound {len(all_files)} JSON files to update")
    
    # Filter files that need updating
    files_to_update = []
    for filepath in all_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            needs_update = (
                should_update_field(data.get("crafted_at"), None) or
                should_update_field(data.get("ingredients"), None) or
                should_update_field(data.get("description"), None) or
                data.get("url")  # Always try to update if we have a URL
            )
            
            if needs_update:
                files_to_update.append((filepath, data))
        except Exception as e:
            print(f"⚠️  Error reading {filepath}: {e}")
    
    print(f"Found {len(files_to_update)} files that need updating\n")
    
    if not files_to_update:
        print("✓ All files are up to date!")
        return
    
    # Update files
    updated_count = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        
        for filepath, existing_data in files_to_update:
            url = existing_data.get("url")
            if not url:
                # Try to construct URL from name
                item_name = existing_data.get("name", filepath.stem)
                url = f"{BASE_URL}/wiki/{item_name.replace(' ', '_')}"
            
            future = executor.submit(extract_item_data, url, quiet=True)
            futures[future] = (filepath, existing_data)
        
        for future in as_completed(futures):
            filepath, existing_data = futures[future]
            
            try:
                scraped_data = future.result()
                
                if scraped_data and update_existing_file(filepath, scraped_data):
                    updated_count += 1
                    print(f"✓ Updated: {filepath.name}")
                else:
                    print(f"⊘ No changes: {filepath.name}")
                    
            except Exception as e:
                print(f"✗ Error: {filepath.name} - {e}")
    
    print(f"\n{'='*70}")
    print(f"✓ UPDATE COMPLETE")
    print(f"{'='*70}")
    print(f"Updated: {updated_count}/{len(files_to_update)} files")

def full_scrape(output_dir="icarus_data", max_workers=5):
    """Full scrape with discovery"""
    
    print("="*70)
    print("  ICARUS FANDOM WIKI SCRAPER - FULL MODE")
    print("="*70)
    
    # Phase 1: Discover
    item_pages = discover_all_item_pages()
    
    if not item_pages:
        print("\n✗ No pages discovered!")
        return
    
    # Phase 2: Scrape
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
    
    # Create directories
    for category in items_by_category.keys():
        category_dir = os.path.join(output_dir, category)
        os.makedirs(category_dir, exist_ok=True)
    
    # Save individual files
    print("\n📄 Saving individual item files...")
    items_saved = 0
    
    for category, items in sorted(items_by_category.items()):
        category_dir = os.path.join(output_dir, category)
        
        for item in items:
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
    
    # Create manifest
    print("\n📋 Creating manifest...")
    manifest = []
    for category, items in sorted(items_by_category.items()):
        for item in items:
            safe_name = re.sub(r'[^\w\s-]', '', item['name'])
            safe_name = re.sub(r'[-\s]+', '_', safe_name).lower()
            manifest.append(f"{category}/{safe_name}.json")
    
    with open(os.path.join(output_dir, "manifest.json"), 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"  ✓ manifest.json ({len(manifest)} files)")
    
    # Summary
    summary = {
        "total_items": len(all_items),
        "failed_items": failed,
        "categories": {k: len(v) for k, v in sorted(items_by_category.items())},
        "scrape_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://icarus.fandom.com"
    }
    
    with open(os.path.join(output_dir, "_summary.json"), 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print("✅ SCRAPING COMPLETE!")
    print("="*70)
    print(f"Total items: {len(all_items)}")
    print(f"Failed: {failed}")
    print("\n💡 Next step: Run 'python build_bundle.py' to create the bundle file")
    print("="*70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Icarus Wiki Scraper')
    parser.add_argument('--update', action='store_true', help='Update existing files only (no discovery)')
    parser.add_argument('--workers', type=int, default=5, help='Number of parallel workers')
    
    args = parser.parse_args()
    
    if args.update:
        update_mode()
    else:
        print("\nICARUS FANDOM WIKI SCRAPER")
        print("This will scrape items from icarus.fandom.com")
        print("\nEstimated time: 10-20 minutes")
        
        confirm = input("\nContinue? (yes/no): ").strip().lower()
        
        if confirm == "yes":
            full_scrape(max_workers=args.workers)
        else:
            print("Aborted.")#!/usr/bin/env python3
"""
Icarus Wiki Scraper - Updates existing JSON files without overwriting manual edits
Handles multiple recipes (with and without talents)
"""

import json
import requests
from bs4 import BeautifulSoup
import os
import time
from pathlib import Path

BASE_URL = "https://icarus.fandom.com"
DATA_DIR = Path("icarus_data")

def clean_text(text):
    """Clean up text from wiki"""
    if not text:
        return ""
    return text.strip().replace('\n', ' ').replace('\r', '')

def parse_recipe_table(soup, item_name):
    """Parse recipe tables from wiki page - handles multiple recipes with talents"""
    recipes = []
    
    # Find all recipe tables
    tables = soup.find_all('table', class_='article-table')
    
    for table in tables:
        # Check if this is a crafting table
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        if 'Amount' not in headers and 'Material' not in headers:
            continue
            
        recipe = {
            "ingredients": {},
            "output_quantity": 1,
            "talent": None
        }
        
        # Check for talent requirement (usually in text before table)
        prev_text = ""
        prev_elem = table.find_previous('p')
        if prev_elem:
            prev_text = prev_elem.get_text()
            if "talent" in prev_text.lower():
                # Extract talent name
                if "Pistol Proficiency" in prev_text:
                    recipe["talent"] = "Pistol Proficiency"
                elif "Munitions" in prev_text:
                    recipe["talent"] = "Ammunition: Munitions"
                # Add more talent patterns as needed
        
        # Parse ingredients from table
        rows = table.find_all('tr')[1:]  # Skip header
        output_qty = None
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                # First column is quantity
                qty_text = cols[0].get_text(strip=True)
                try:
                    qty = int(qty_text)
                except:
                    continue
                
                # Second column contains material links
                materials = cols[1].find_all('a')
                if materials:
                    for mat_link in materials:
                        mat_name = mat_link.get('title', mat_link.get_text(strip=True))
                        if mat_name and mat_name not in recipe["ingredients"]:
                            recipe["ingredients"][mat_name] = qty
                else:
                    # If no output quantity found yet, this might be it
                    if output_qty is None and len(cols) == 1:
                        try:
                            output_qty = int(qty_text)
                        except:
                            pass
        
        if recipe["ingredients"]:
            if output_qty:
                recipe["output_quantity"] = output_qty
            recipes.append(recipe)
    
    return recipes if recipes else None

def scrape_item_page(item_name, url):
    """Scrape an item's wiki page"""
    try:
        print(f"  Fetching: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            "name": item_name,
            "url": url
        }
        
        # Extract description
        desc_elem = soup.find('div', {'data-source': 'description'})
        if not desc_elem:
            # Try finding first paragraph in content
            content = soup.find('div', class_='mw-parser-output')
            if content:
                first_p = content.find('p')
                if first_p:
                    data["description"] = clean_text(first_p.get_text())
        else:
            data["description"] = clean_text(desc_elem.get_text())
        
        # Parse recipes (may be multiple with talents)
        recipes = parse_recipe_table(soup, item_name)
        if recipes:
            if len(recipes) == 1:
                # Single recipe - use old format
                data["ingredients"] = recipes[0]["ingredients"]
                data["output_quantity"] = recipes[0].get("output_quantity", 1)
            else:
                # Multiple recipes - use new format
                data["recipes"] = recipes
        
        # Extract crafted_at from infobox
        infobox = soup.find('aside', class_='portable-infobox')
        if infobox:
            for row in infobox.find_all('div', class_='pi-item'):
                label = row.find('h3', class_='pi-data-label')
                value = row.find('div', class_='pi-data-value')
                
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    value_text = clean_text(value.get_text())
                    
                    if 'crafted' in label_text:
                        data["crafted_at"] = value_text
                    elif 'tier' in label_text:
                        try:
                            data["tier"] = int(value_text.replace('Tier ', ''))
                        except:
                            pass
                    elif 'weight' in label_text:
                        if "stats" not in data:
                            data["stats"] = {}
                        data["stats"]["weight"] = value_text
        
        # Try to determine item category from page categories
        categories = soup.find_all('a', href=lambda x: x and '/wiki/Category:' in x)
        for cat in categories:
            cat_name = cat.get_text(strip=True)
            if cat_name and cat_name != "Community content":
                data["category"] = cat_name
                break
        
        return data
        
    except Exception as e:
        print(f"  ERROR scraping {item_name}: {e}")
        return None

def should_update_field(existing_value, new_value):
    """Determine if a field should be updated"""
    if existing_value is None or existing_value == "":
        return True
    if str(existing_value).lower() == "unknown":
        return True
    if existing_value == {}:
        return True
    return False

def update_json_file(file_path, scraped_data):
    """Update existing JSON file with scraped data, preserving manual edits"""
    try:
        # Load existing data
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        
        updated = False
        
        # Update only unknown/empty fields
        for key, new_value in scraped_data.items():
            if key == "name" or key == "url":
                # Always update these
                existing_data[key] = new_value
                continue
            
            if key not in existing_data:
                existing_data[key] = new_value
                updated = True
                print(f"    Added field: {key}")
            elif should_update_field(existing_data.get(key), new_value):
                existing_data[key] = new_value
                updated = True
                print(f"    Updated field: {key}")
        
        if updated:
            # Save back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            print(f"  ✓ Updated: {file_path}")
            return True
        else:
            print(f"  ✓ No updates needed: {file_path}")
            return False
            
    except Exception as e:
        print(f"  ERROR updating {file_path}: {e}")
        return False

def process_directory(directory):
    """Process all JSON files in a directory"""
    updated_count = 0
    error_count = 0
    skipped_count = 0
    
    json_files = list(directory.glob("*.json"))
    print(f"\nProcessing {len(json_files)} files in {directory.name}/")
    
    for json_file in json_files:
        try:
            # Load existing JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            item_name = data.get("name")
            if not item_name:
                print(f"⚠ Skipping {json_file.name}: No name field")
                skipped_count += 1
                continue
            
            # Check if needs updating
            needs_update = (
                should_update_field(data.get("crafted_at"), None) or
                should_update_field(data.get("ingredients"), None) or
                should_update_field(data.get("description"), None)
            )
            
            if not needs_update:
                print(f"✓ {item_name}: Already complete")
                skipped_count += 1
                continue
            
            print(f"\n📝 {item_name}")
            
            # Get URL or construct it
            url = data.get("url")
            if not url:
                # Construct wiki URL from name
                wiki_name = item_name.replace(" ", "_")
                url = f"{BASE_URL}/wiki/{wiki_name}"
            
            # Scrape the page
            scraped_data = scrape_item_page(item_name, url)
            
            if scraped_data:
                if update_json_file(json_file, scraped_data):
                    updated_count += 1
            else:
                error_count += 1
            
            # Be nice to the wiki server
            time.sleep(1)
            
        except Exception as e:
            print(f"ERROR processing {json_file}: {e}")
            error_count += 1
    
    return updated_count, skipped_count, error_count

def main():
    """Main scraper function"""
    print("🚀 ICARUS Wiki Scraper - Update Mode")
    print("=" * 60)
    print("This will update existing JSON files with missing data")
    print("Manual edits will be preserved")
    print("=" * 60)
    
    if not DATA_DIR.exists():
        print(f"❌ Data directory not found: {DATA_DIR}")
        return
    
    total_updated = 0
    total_skipped = 0
    total_errors = 0
    
    # Process each subdirectory
    for subdir in DATA_DIR.iterdir():
        if subdir.is_dir():
            updated, skipped, errors = process_directory(subdir)
            total_updated += updated
            total_skipped += skipped
            total_errors += errors
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"  ✓ Updated: {total_updated}")
    print(f"  ⊘ Skipped: {total_skipped}")
    print(f"  ✗ Errors: {total_errors}")
    print("=" * 60)

if __name__ == "__main__":
    main()