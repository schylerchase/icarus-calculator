#!/usr/bin/env python3
"""
EIP.GG Icarus Database Scraper - Pagination-aware Version
Properly extracts pagination links and follows them

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

BASE_URL = "https://eip.gg/icarus/db/"

# Known category pages to exclude
CATEGORY_PAGES = {
    'ammunition', 'armor', 'construction-materials', 'consumables', 
    'deployables', 'elements-crafted', 'elements-raw', 'orbital',
    'processing', 'status-effects', 'tools', 'weapons', 'work-benches'
}

counter_lock = Lock()

def get_pagination_urls(soup):
    """Extract pagination URLs from a page"""
    pagination_urls = set()
    
    # Look for pagination links - common classes: pagination, nav-links, page-numbers
    pagination = soup.find('div', class_=re.compile(r'pagination|nav-links|page-numbers'))
    
    if pagination:
        for link in pagination.find_all('a', href=True):
            href = link['href']
            if '/icarus/db/page/' in href or '/icarus/db/' in href:
                if not href.startswith('http'):
                    href = 'https://eip.gg' + href
                pagination_urls.add(href)
    
    # Also look for any link with /page/ in it
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/icarus/db/page/' in href:
            if not href.startswith('http'):
                href = 'https://eip.gg' + href
            pagination_urls.add(href)
    
    return pagination_urls

def is_item_url(url):
    """Check if a URL is an item page (not a category or pagination page)"""
    # Remove base URL
    path = url.replace('https://eip.gg/icarus/db/', '')
    
    # Exclude empty, pagination, and known category pages
    if not path or path == '/' or '/page/' in path:
        return False
    
    # Extract the slug
    slug = path.rstrip('/').split('/')[-1]
    
    # Exclude category pages
    if slug in CATEGORY_PAGES:
        return False
    
    # Must be a proper item slug (has letters/numbers/hyphens, ends with /)
    if slug and url.endswith('/'):
        return True
    
    return False

def get_items_from_page(page_url):
    """Get all item links from a specific page"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(page_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        item_links = []
        
        # Find all links that might be items
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Convert relative to absolute
            if href.startswith('/icarus/db/'):
                href = 'https://eip.gg' + href
            
            # Check if it's an item URL
            if href.startswith('https://eip.gg/icarus/db/') and is_item_url(href):
                if href not in item_links:
                    item_links.append(href)
        
        return item_links, get_pagination_urls(soup)
        
    except Exception as e:
        print(f"    [ERROR] Failed to fetch {page_url}: {e}")
        return [], set()

def discover_all_items():
    """Discover all item URLs by following pagination"""
    
    print("="*70)
    print("DISCOVERING ALL ITEMS VIA PAGINATION")
    print("="*70)
    
    all_item_urls = set()
    visited_pages = set()
    pages_to_visit = {BASE_URL}
    
    page_num = 0
    
    while pages_to_visit and page_num < 100:  # Safety limit
        page_url = pages_to_visit.pop()
        
        if page_url in visited_pages:
            continue
        
        page_num += 1
        print(f"\n[Page {page_num}] Fetching: {page_url}")
        
        visited_pages.add(page_url)
        
        item_links, pagination_links = get_items_from_page(page_url)
        
        if item_links:
            all_item_urls.update(item_links)
            print(f"  ✓ Found {len(item_links)} items on this page")
            print(f"  Total unique items: {len(all_item_urls)}")
        else:
            print(f"  ✗ No items found on this page")
        
        # Add new pagination pages to visit
        new_pages = pagination_links - visited_pages
        if new_pages:
            pages_to_visit.update(new_pages)
            print(f"  Found {len(new_pages)} new pages to visit")
        
        time.sleep(0.5)  # Be polite
    
    print(f"\n{'='*70}")
    print(f"✓ DISCOVERY COMPLETE")
    print(f"{'='*70}")
    print(f"Pages visited: {len(visited_pages)}")
    print(f"Total items found: {len(all_item_urls)}")
    
    return list(all_item_urls)

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
        
        # Extract required materials
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
        
        # Try to extract category from breadcrumbs
        breadcrumbs = soup.find('nav', class_='breadcrumb') or soup.find('div', class_='breadcrumb')
        if breadcrumbs:
            links = breadcrumbs.find_all('a')
            for link in links:
                text = link.get_text(strip=True).lower()
                if text and text not in ['home', 'icarus', 'database', 'icarus database', '']:
                    item_data['category'] = text
                    break
        
        # Fallback: look for category in page text
        if not item_data['category']:
            for category in CATEGORY_PAGES:
                if category.replace('-', ' ') in page_text.lower():
                    item_data['category'] = category.replace('-', ' ')
                    break
        
        if not item_data['category']:
            item_data['category'] = 'uncategorized'
        
        return item_data
        
    except Exception as e:
        if not quiet:
            print(f"      [ERROR] {item_url}: {e}")
        return item_data

def scrape_all_items(output_dir="icarus_data", max_workers=5):
    """Main scraping function"""
    
    print("="*70)
    print("  EIP.GG ICARUS DATABASE SCRAPER")
    print("="*70)
    print(f"\nUsing {max_workers} threads for parallel scraping")
    
    # Step 1: Discover all item URLs
    item_urls = discover_all_items()
    
    if not item_urls:
        print("\n✗ No items discovered!")
        return
    
    # Step 2: Scrape all items
    print(f"\n{'='*70}")
    print("SCRAPING ITEM DATA")
    print("="*70)
    
    os.makedirs(output_dir, exist_ok=True)
    
    all_items = []
    completed = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(extract_item_data, url, quiet=True): url 
            for url in item_urls
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                item_data = future.result()
                if item_data:
                    all_items.append(item_data)
                    
                    with counter_lock:
                        completed += 1
                        
                    if completed % 25 == 0 or completed == len(item_urls):
                        print(f"  Progress: {completed}/{len(item_urls)} items", end='\r')
                else:
                    failed += 1
                    
            except Exception as e:
                print(f"\n  [ERROR] {url}: {e}")
                failed += 1
    
    print(f"\n✓ Completed: {completed}/{len(item_urls)} items")
    
    # Step 3: Organize by category and save
    print(f"\n{'='*70}")
    print("ORGANIZING AND SAVING DATA")
    print("="*70)
    
    items_by_category = {}
    for item in all_items:
        category = item['category']
        if category not in items_by_category:
            items_by_category[category] = []
        items_by_category[category].append(item)
    
    # Save category files
    for category, items in sorted(items_by_category.items()):
        safe_category = re.sub(r'[^\w\s-]', '', category).strip()
        safe_category = re.sub(r'[-\s]+', '_', safe_category).lower()
        
        filepath = os.path.join(output_dir, f"{safe_category}.json")
        
        data = {
            "category": category.title(),
            "count": len(items),
            "items": sorted(items, key=lambda x: x['name'])
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ {safe_category}.json ({len(items)} items)")
    
    # Save complete dataset
    complete_filepath = os.path.join(output_dir, "all_items.json")
    with open(complete_filepath, 'w', encoding='utf-8') as f:
        json.dump({
            "total_items": len(all_items),
            "categories": sorted(list(items_by_category.keys())),
            "items": sorted(all_items, key=lambda x: x['name'])
        }, f, indent=2, ensure_ascii=False)
    print(f"  ✓ all_items.json ({len(all_items)} items)")
    
    # Save summary
    summary = {
        "total_items": len(all_items),
        "failed_items": failed,
        "categories": {k: len(v) for k, v in sorted(items_by_category.items())},
        "scrape_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "https://eip.gg/icarus/db/"
    }
    
    summary_path = os.path.join(output_dir, "_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print("SCRAPING COMPLETE!")
    print("="*70)
    print(f"Total items: {len(all_items)}")
    print(f"Failed: {failed}")
    print(f"Categories: {len(items_by_category)}")
    print(f"Output directory: {output_dir}/")
    print("="*70)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "diagnose":
        # Keep the diagnostic function for future use
        print("Diagnostic mode - checking page structure...")
        print("Run without arguments to start scraping.")
    else:
        print("\nThis will scrape all items from eip.gg/icarus/db/")
        print("The scraper will:")
        print("  1. Follow pagination links to discover all items")
        print("  2. Scrape each item's data in parallel")
        print("  3. Organize items by category")
        print("\nEstimated time: 10-20 minutes")
        confirm = input("\nContinue? (yes/no): ").strip().lower()
        
        if confirm == "yes":
            scrape_all_items(max_workers=5)
        else:
            print("Aborted.")