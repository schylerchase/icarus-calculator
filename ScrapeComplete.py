#!/usr/bin/env python3
"""
Fixed Icarus Database Scraper
Properly extracts crafting recipes and data from the Icarus wiki

Installation:
pip install requests beautifulsoup4 lxml

Usage:
python icarus_scraper_fixed.py
"""

import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup

# Your category mappings
CATEGORY_MAPPINGS = {
    "ammunition": ["Category:Ammunition", "Category:Arrows", "Category:Bolts"],
    "weapons": ["Category:Weapons", "Category:Firearms", "Category:Bows", "Category:Crossbows", "Category:Spears", "Category:Knives"],
    "tools": ["Category:Tools"],
    "armor": ["Category:Armor", "Category:Helmets", "Category:Chest Armor", "Category:Leg Armor"],
    "building": ["Category:Building Pieces", "Category:Structural"],
    "consumables": ["Category:Consumables", "Category:Food", "Category:Drinks"],
    "medicine": ["Category:Medicine", "Category:Bandages"],
    "materials": ["Category:Materials", "Category:Crafted Resources"],
    "raw_materials": ["Category:Raw Materials", "Category:Ores", "Category:Plants"],
    "deployables": ["Category:Deployables", "Category:Crafting Benches", "Category:Furnaces"],
    "farming": ["Category:Farming", "Category:Seeds", "Category:Crops"],
    "furniture": ["Category:Furniture"],
    "decoration": ["Category:Decorations"],
    "electricity_sources": ["Category:Electricity"],
    "water_sources": ["Category:Water"],
    "fuel_sources": ["Category:Fuel"],
    "light_sources": ["Category:Lights"],
    "storage": ["Category:Storage"],
    "cooking": ["Category:Cooking"],
    "specialized_equipment": ["Category:Equipment"]
}

def get_all_pages_in_category(category_name, max_pages=500):
    """Get all pages in a wiki category using the Fandom API"""
    print(f"  Fetching pages from {category_name}...")
    
    base_url = "https://icarus.fandom.com/api.php"
    pages = []
    
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": category_name,
        "cmlimit": 500
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "query" in data and "categorymembers" in data["query"]:
            for member in data["query"]["categorymembers"]:
                title = member.get("title", "")
                # Filter out category pages, talk pages, etc.
                if not any(x in title for x in ['Category:', 'Talk:', 'File:', 'Template:']):
                    pages.append(title)
        
        print(f"    Found {len(pages)} pages")
        return pages
        
    except Exception as e:
        print(f"    [ERROR] {e}")
        return []

def extract_item_data(title):
    """Extract all relevant data for an item using BeautifulSoup"""
    
    url = f"https://icarus.fandom.com/wiki/{title.replace(' ', '_')}"
    
    item_data = {
        "name": title,
        "ingredients": {},
        "crafted_at": "Unknown",
        "category": "",
        "tier": 0,
        "url": url,
        "weight": "",
        "crafting_stations": []
    }
    
    # Use browser headers to avoid bot detection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        print(f"    Fetching: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Debug: Save HTML to file for inspection
        # with open(f"debug_{title.replace(' ', '_')}.html", 'w', encoding='utf-8') as f:
        #     f.write(soup.prettify())
        
        # Find the infobox (contains all the item data)
        infobox = soup.find('aside', class_='portable-infobox')
        
        if not infobox:
            # Try alternative infobox class
            infobox = soup.find('table', class_='infobox')
        
        if infobox:
            print(f"      ✓ Found infobox")
            
            # Extract data from infobox rows
            for section in infobox.find_all(['section', 'tr']):
                # Try multiple ways to find label and value
                label_elem = section.find(['h3', 'th'], class_=['pi-data-label', 'infobox-label'])
                if not label_elem:
                    label_elem = section.find('th')
                
                if not label_elem:
                    continue
                
                label = label_elem.get_text(strip=True).lower()
                
                # Get the value
                value_elem = section.find(['div', 'td'], class_=['pi-data-value', 'infobox-data'])
                if not value_elem:
                    value_elem = section.find('td')
                
                if not value_elem:
                    continue
                
                # Extract based on label
                if 'tier' in label or 'tech tier' in label:
                    tier_text = value_elem.get_text(strip=True)
                    tier_match = re.search(r'(\d+)', tier_text)
                    if tier_match:
                        item_data['tier'] = int(tier_match.group(1))
                        print(f"      ✓ Tier: {item_data['tier']}")
                
                elif 'weight' in label:
                    item_data['weight'] = value_elem.get_text(strip=True)
                    print(f"      ✓ Weight: {item_data['weight']}")
                
                elif 'crafted' in label or 'station' in label or 'workbench' in label:
                    # Extract crafting stations
                    stations = []
                    for link in value_elem.find_all('a'):
                        station = link.get_text(strip=True)
                        if station and station not in ['', 'Unknown']:
                            stations.append(station)
                    
                    if not stations:
                        # Try plain text
                        text = value_elem.get_text(strip=True)
                        if text and text != 'Unknown':
                            stations = [s.strip() for s in re.split(r',|;|\n', text) if s.strip()]
                    
                    if stations:
                        item_data['crafted_at'] = ', '.join(stations)
                        item_data['crafting_stations'] = stations
                        print(f"      ✓ Crafted at: {item_data['crafted_at']}")
        else:
            print(f"      ⚠️  No infobox found")
        
        # Extract crafting recipe - look for tables with recipe data
        # Find "Crafting" heading
        crafting_section = soup.find(['h2', 'h3', 'span'], 
                                     string=re.compile(r'Crafting', re.IGNORECASE))
        
        if not crafting_section:
            crafting_section = soup.find(['h2', 'h3', 'span'], id='Crafting')
        
        if crafting_section:
            print(f"      ✓ Found Crafting section")
            
            # Find parent header element
            if crafting_section.name == 'span':
                header = crafting_section.find_parent(['h2', 'h3'])
            else:
                header = crafting_section
            
            print(f"        Header element: {header.name if header else 'None'}")
            
            # Find the next table after the crafting header
            current = header.find_next_sibling() if header else None
            table_count = 0
            sibling_count = 0
            
            while current and sibling_count < 10:  # Limit to 10 siblings
                sibling_count += 1
                print(f"        Sibling {sibling_count}: <{current.name}> {current.get('class', [])} - {current.get_text(strip=True)[:50]}...")
                
                if current.name == 'table':
                    table_count += 1
                    print(f"      ✓ Found crafting table #{table_count}")
                    
                    # Parse the crafting table
                    rows = current.find_all('tr')
                    print(f"        - Table has {len(rows)} rows")
                    
                    for idx, row in enumerate(rows):
                        cells = row.find_all(['td', 'th'])
                        print(f"        - Row {idx}: {len(cells)} cells")
                        
                        if len(cells) >= 2:
                            # First cell usually has quantity
                            quantity_text = cells[0].get_text(strip=True)
                            print(f"          Quantity text: '{quantity_text}'")
                            
                            # Second cell has item name (and possibly more items)
                            links = cells[1].find_all('a', href=True)
                            print(f"          Found {len(links)} links in cell")
                            
                            for link in links:
                                href = link.get('href', '')
                                if '/wiki/' in href and not 'File:' in href:
                                    item_name = link.get_text(strip=True)
                                    print(f"          Link: {item_name} (href: {href})")
                                    
                                    # Try to extract quantity
                                    quantity_match = re.search(r'(\d+)', quantity_text)
                                    if quantity_match and item_name:
                                        quantity = int(quantity_match.group(1))
                                        if item_name not in item_data['ingredients']:
                                            item_data['ingredients'][item_name] = quantity
                                            print(f"          ✓ Added: {quantity}x {item_name}")
                                        else:
                                            item_data['ingredients'][item_name] += quantity
                                            print(f"          ✓ Updated: +{quantity}x {item_name}")
                    
                    if item_data['ingredients']:
                        print(f"      ✓ Ingredients: {item_data['ingredients']}")
                        break
                    else:
                        print(f"      ⚠️  Table #{table_count} had no parseable ingredients")
                
                elif current.name in ['h2', 'h3']:
                    # Reached next section
                    print(f"      ⚠️  Reached next section after checking {table_count} tables")
                    break
                
                # Also check if table is nested inside this element
                nested_table = current.find('table')
                if nested_table and not current.name == 'table':
                    print(f"        Found nested table inside <{current.name}>!")
                    table_count += 1
                    print(f"      ✓ Found nested crafting table #{table_count}")
                    
                    rows = nested_table.find_all('tr')
                    print(f"        - Table has {len(rows)} rows")
                    
                    for idx, row in enumerate(rows):
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            quantity_text = cells[0].get_text(strip=True)
                            links = cells[1].find_all('a', href=True)
                            
                            for link in links:
                                href = link.get('href', '')
                                if '/wiki/' in href and 'File:' not in href:
                                    item_name = link.get_text(strip=True)
                                    quantity_match = re.search(r'(\d+)', quantity_text)
                                    if quantity_match and item_name:
                                        quantity = int(quantity_match.group(1))
                                        item_data['ingredients'][item_name] = quantity
                                        print(f"          ✓ Added: {quantity}x {item_name}")
                    
                    if item_data['ingredients']:
                        print(f"      ✓ Ingredients: {item_data['ingredients']}")
                        break
                
                current = current.find_next_sibling()
        else:
            print(f"      ⚠️  No Crafting section found")
        
        # If still no ingredients, try looking for wikitable class
        if not item_data['ingredients']:
            recipe_tables = soup.find_all('table', class_=['wikitable', 'article-table'])
            for table in recipe_tables:
                # Check if this looks like a recipe table
                header_row = table.find('tr')
                if header_row:
                    headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
                    if 'amount' in headers or 'resource' in headers or 'quantity' in headers:
                        print(f"      ✓ Found recipe table by class")
                        
                        for row in table.find_all('tr')[1:]:
                            cells = row.find_all(['td', 'th'])
                            if len(cells) >= 2:
                                quantity_text = cells[0].get_text(strip=True)
                                
                                for link in cells[1].find_all('a', href=True):
                                    href = link.get('href', '')
                                    if '/wiki/' in href and 'File:' not in href:
                                        item_name = link.get_text(strip=True)
                                        quantity_match = re.search(r'(\d+)', quantity_text)
                                        if quantity_match and item_name:
                                            quantity = int(quantity_match.group(1))
                                            item_data['ingredients'][item_name] = quantity
                        
                        if item_data['ingredients']:
                            print(f"      ✓ Ingredients: {item_data['ingredients']}")
                            break
        
        return item_data
        
    except requests.exceptions.RequestException as e:
        print(f"      ✗ Network error: {e}")
        return item_data
    except Exception as e:
        print(f"      ✗ Parse error: {e}")
        import traceback
        traceback.print_exc()
        return item_data

def scrape_all_items(output_dir="icarus_data"):
    """Scrape all items from the Icarus wiki"""
    
    print("="*70)
    print("  ICARUS COMPLETE DATABASE SCRAPER (FIXED)")
    print("="*70)
    print("\nThis will fetch ALL items from the Icarus wiki")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Store all items by category
    all_items = {}
    for category_key in CATEGORY_MAPPINGS.keys():
        all_items[category_key] = []
    
    # Track statistics
    total_items = 0
    failed_items = 0
    
    # Process each category
    for category_key, wiki_categories in CATEGORY_MAPPINGS.items():
        print(f"\n{'='*70}")
        print(f"PROCESSING: {category_key.upper()}")
        print(f"{'='*70}")
        
        # Collect all page titles from this category's wiki categories
        all_page_titles = set()
        
        for wiki_category in wiki_categories:
            pages = get_all_pages_in_category(wiki_category)
            all_page_titles.update(pages)
            time.sleep(2)  # Rate limiting
        
        print(f"\nTotal unique items to process: {len(all_page_titles)}")
        
        # Process each page
        for i, page_title in enumerate(sorted(all_page_titles)):
            print(f"\n[{i+1}/{len(all_page_titles)}] {page_title}")
            
            item_data = extract_item_data(page_title)
            
            if item_data:
                item_data["category"] = category_key
                all_items[category_key].append(item_data)
                total_items += 1
            else:
                failed_items += 1
            
            # Rate limiting - be nice to Fandom
            time.sleep(2)
    
    # Save each category to its own JSON file
    print(f"\n{'='*70}")
    print("SAVING JSON FILES")
    print(f"{'='*70}")
    
    for category_key, items in all_items.items():
        if not items:
            print(f"[SKIP] {category_key}.json (no items)")
            continue
        
        filepath = os.path.join(output_dir, f"{category_key}.json")
        
        data = {
            "category": category_key.replace('_', ' ').title(),
            "count": len(items),
            "items": sorted(items, key=lambda x: x['name'])
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"[SAVED] {category_key}.json ({len(items)} items)")
    
    # Save summary
    summary = {
        "total_items": total_items,
        "failed_items": failed_items,
        "categories": {k: len(v) for k, v in all_items.items() if v},
        "scrape_date": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    summary_path = os.path.join(output_dir, "_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"Total items scraped: {total_items}")
    print(f"Failed items: {failed_items}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*70}")

def test_single_item(item_name):
    """Test scraping a single item"""
    print(f"Testing: {item_name}")
    print("="*70)
    
    item_data = extract_item_data(item_name)
    
    print(f"\nResults:")
    print(json.dumps(item_data, indent=2))

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test mode - scrape a single item
        test_item = sys.argv[2] if len(sys.argv) > 2 else "12-Gauge Buckshot Shell"
        test_single_item(test_item)
    else:
        # Full scrape
        confirm = input("\n⚠️  This will scrape ~1600 items and take 1-2 hours. Continue? (yes/no): ").strip().lower()
        if confirm == "yes":
            scrape_all_items()
        else:
            print("Aborted.")