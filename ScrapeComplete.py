#!/usr/bin/env python3
"""
Complete Icarus Database Scraper
Fetches ALL items from the Icarus wiki and builds a comprehensive database

Installation:
    pip install fandom-py requests beautifulsoup4
    
Usage:
    python icarus_full_scraper.py
"""

import json
import os
import re
import time
from fandom import FandomPage
import fandom


# Category mappings - which wiki categories map to which JSON files
CATEGORY_MAPPINGS = {
    "ammunition": ["Category:Ammunition", "Category:Arrows", "Category:Bolts"],
    "weapons": ["Category:Weapons", "Category:Firearms", "Category:Bows", "Category:Crossbows", 
                "Category:Spears", "Category:Knives"],
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
    """
    Get all pages in a wiki category
    
    Args:
        category_name: Name of the category (e.g., "Category:Ammunition")
        max_pages: Maximum number of pages to fetch
        
    Returns:
        list: List of page titles
    """
    
    print(f"  Fetching pages from {category_name}...")
    
    try:
        # Use fandom search to find pages in category
        # The category system in fandom-py is limited, so we'll use search
        results = fandom.search(category_name, results=max_pages)
        
        # Filter to get actual item pages (not category pages, talk pages, etc.)
        pages = []
        for result in results:
            if not any(x in result[0] for x in ['Category:', 'Talk:', 'File:', 'Template:']):
                pages.append(result[0])
        
        print(f"    Found {len(pages)} pages")
        return pages
        
    except Exception as e:
        print(f"    [ERROR] {e}")
        return []


def extract_recipe_from_page(wiki, title):
    """Extract crafting recipe from a wiki page"""
    
    try:
        page = FandomPage(wiki=wiki, title=title, language='en')
        html = page.html
        
        ingredients = {}
        
        # Look for crafting section
        crafting_pattern = r'<h2[^>]*>.*?Crafting.*?</h2>(.*?)(?=<h2|$)'
        crafting_match = re.search(crafting_pattern, html, re.DOTALL | re.IGNORECASE)
        
        if crafting_match:
            crafting_section = crafting_match.group(1)
            
            # Pattern 1: Standard table format
            row_pattern = r'<tr[^>]*>.*?<td[^>]*>(\d+)</td>.*?<a[^>]*title="([^"]+)"'
            
            for match in re.finditer(row_pattern, crafting_section, re.DOTALL):
                quantity = int(match.group(1))
                resource = match.group(2).strip()
                
                if not resource.startswith('File:') and not resource.startswith('ITEM_'):
                    ingredients[resource] = quantity
            
            # Pattern 2: Alternative format
            if not ingredients:
                alt_pattern = r'<td[^>]*>(\d+)</td>.*?<td[^>]*>.*?<a[^>]*>([^<]+)</a>'
                for match in re.finditer(alt_pattern, crafting_section, re.DOTALL):
                    try:
                        quantity = int(match.group(1))
                        resource = match.group(2).strip()
                        if resource and not resource.startswith('File:'):
                            ingredients[resource] = quantity
                    except ValueError:
                        continue
        
        return ingredients
        
    except Exception as e:
        return {}


def extract_item_data(wiki, title):
    """
    Extract all relevant data for an item
    
    Returns:
        dict: Item data including name, ingredients, crafting station, tier, etc.
    """
    
    try:
        page = FandomPage(wiki=wiki, title=title, language='en')
        html = page.html
        
        item_data = {
            "name": title,
            "ingredients": {},
            "crafted_at": "Unknown",
            "category": "",
            "tier": 0,
            "url": page.url,
            "weight": "",
            "crafting_stations": []
        }
        
        # Extract recipe
        ingredients = extract_recipe_from_page(wiki, title)
        if ingredients:
            item_data["ingredients"] = ingredients
        
        # Extract crafting station
        crafted_pattern = r'(?:Crafted at|Crafting Station)[^:]*:?\s*<[^>]*>([^<]+)</[^>]*>'
        crafted_match = re.search(crafted_pattern, html, re.IGNORECASE)
        if crafted_match:
            crafted_at = crafted_match.group(1).strip()
            item_data["crafted_at"] = crafted_at
            # Split multiple stations
            stations = [s.strip() for s in re.split(r',|;|\n', crafted_at) if s.strip()]
            item_data["crafting_stations"] = stations[:5]  # Max 5
        
        # Extract tier
        tier_pattern = r'(?:Tier|Tech Tier)[^:]*:?\s*(\d+)'
        tier_match = re.search(tier_pattern, html, re.IGNORECASE)
        if tier_match:
            item_data["tier"] = int(tier_match.group(1))
        
        # Extract weight
        weight_pattern = r'(?:Weight)[^:]*:?\s*([0-9.]+\s*[kK]?[gG])'
        weight_match = re.search(weight_pattern, html, re.IGNORECASE)
        if weight_match:
            item_data["weight"] = weight_match.group(1).strip()
        
        return item_data
        
    except Exception as e:
        print(f"    [ERROR] Failed to parse {title}: {e}")
        return None


def scrape_all_items(output_dir="icarus_data_complete"):
    """
    Scrape all items from the Icarus wiki
    
    Args:
        output_dir: Directory to save JSON files
    """
    
    print("="*70)
    print("  ICARUS COMPLETE DATABASE SCRAPER")
    print("="*70)
    print("\nThis will fetch ALL items from the Icarus wiki")
    print("Estimated time: 30-60 minutes depending on items found")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Set wiki
    fandom.set_wiki("icarus")
    
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
            time.sleep(1)  # Rate limiting
        
        print(f"\nTotal unique items to process: {len(all_page_titles)}")
        
        # Process each page
        for i, page_title in enumerate(sorted(all_page_titles)):
            print(f"[{i+1}/{len(all_page_titles)}] {page_title}...", end=" ")
            
            item_data = extract_item_data("icarus", page_title)
            
            if item_data:
                item_data["category"] = category_key
                all_items[category_key].append(item_data)
                print("[OK]")
                total_items += 1
            else:
                print("[FAILED]")
                failed_items += 1
            
            # Rate limiting - be nice to Fandom
            time.sleep(1.5)
    
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
    print(f"Summary saved to: {summary_path}")
    print(f"{'='*70}")


def discover_all_categories():
    """
    Discover all available categories on the Icarus wiki
    Useful for finding categories we might have missed
    """
    
    print("="*70)
    print("  DISCOVERING ALL CATEGORIES")
    print("="*70)
    
    fandom.set_wiki("icarus")
    
    # Search for common category terms
    category_searches = [
        "Items", "Weapons", "Tools", "Armor", "Building", "Crafting",
        "Resources", "Materials", "Food", "Medicine", "Equipment"
    ]
    
    found_categories = set()
    
    for search_term in category_searches:
        print(f"\nSearching for: {search_term}")
        results = fandom.search(f"Category:{search_term}", results=20)
        
        for result in results:
            if "Category:" in result[0]:
                found_categories.add(result[0])
                print(f"  - {result[0]}")
        
        time.sleep(1)
    
    print(f"\n{'='*70}")
    print(f"Found {len(found_categories)} categories")
    print(f"{'='*70}")
    
    return sorted(found_categories)


def main():
    """Main execution"""
    
    print("="*70)
    print("  ICARUS WIKI SCRAPER")
    print("="*70)
    
    print("\nSelect mode:")
    print("  1. Discover all categories (find what's available)")
    print("  2. Scrape all items (build complete database)")
    print("  3. Custom category scrape (specify categories)")
    
    mode = input("\nEnter mode (1/2/3): ").strip()
    
    if mode == "1":
        categories = discover_all_categories()
        
        # Save discovered categories
        with open("discovered_categories.txt", 'w') as f:
            for cat in categories:
                f.write(f"{cat}\n")
        print(f"\n[SAVED] Categories saved to discovered_categories.txt")
        
    elif mode == "2":
        output_dir = input("\nEnter output directory (default: icarus_data_complete): ").strip()
        if not output_dir:
            output_dir = "icarus_data_complete"
        
        confirm = input(f"\nThis will take 30-60 minutes. Continue? (yes/no): ").strip().lower()
        if confirm == "yes":
            scrape_all_items(output_dir)
        else:
            print("Aborted.")
            
    elif mode == "3":
        print("\nEnter categories to scrape (comma-separated):")
        print("Example: Category:Weapons, Category:Tools, Category:Armor")
        categories = input("> ").strip().split(',')
        categories = [c.strip() for c in categories]
        
        # Custom scrape logic here
        print(f"\nWould scrape: {categories}")
        print("(Custom scrape not fully implemented - use mode 2 for now)")
    
    else:
        print("Invalid mode selected.")


if __name__ == "__main__":
    main()