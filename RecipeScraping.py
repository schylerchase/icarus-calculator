#!/usr/bin/env python3
"""
Complete Recursive ICARUS Wiki Scraper
- Handles nested subcategories (Building Pieces, etc.)
- Verifies all strategies work
- Cleans up unused data
- Provides accurate item counts
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import sys
from urllib.parse import urljoin, quote
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompleteIcarusScraper:
    def __init__(self, output_dir='icarus_data', max_workers=8):
        self.base_url = "https://icarus.fandom.com"
        self.api_url = "https://icarus.fandom.com/api.php"
        self.output_dir = output_dir
        self.max_workers = max_workers
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.recipes = {}
        self.processed_items = set()
        self.discovered_categories = set()
        self.lock = threading.Lock()
        
        # Stats for verification
        self.stats = {
            'strategy1_items': 0,
            'strategy2_items': 0,
            'strategy3_items': 0,
            'total_unique': 0
        }
        
        # All 21 required categories
        self.categories = {
            'ammunition': [], 'armor': [], 'building': [], 'consumables': [],
            'cooking': [], 'decoration': [], 'deployables': [], 'electricity_sources': [],
            'farming': [], 'fuel_sources': [], 'furniture': [], 'inventory': [],
            'light_sources': [], 'materials': [], 'medicine': [], 'raw_materials': [],
            'specialized_equipment': [], 'storage': [], 'tools': [], 'water_sources': [],
            'weapons': []
        }
        
        logger.info(f"Initialized scraper - output: {os.path.abspath(output_dir)}")

    def get_category_members_api(self, category_name, depth=0, max_depth=3):
        """Get all members recursively, handling nested subcategories"""
        if depth > max_depth:
            return [], []
        
        all_members = []
        all_subcategories = []
        
        params = {
            'action': 'query',
            'list': 'categorymembers',
            'cmtitle': f'Category:{category_name}',
            'cmlimit': 500,
            'format': 'json'
        }
        
        continue_token = None
        
        while True:
            if continue_token:
                params['cmcontinue'] = continue_token
            
            try:
                response = self.session.get(self.api_url, params=params, timeout=10)
                data = response.json()
                
                if 'query' in data and 'categorymembers' in data['query']:
                    for member in data['query']['categorymembers']:
                        if member['ns'] == 0:  # Main namespace (actual items)
                            all_members.append({
                                'name': member['title'],
                                'pageid': member['pageid']
                            })
                        elif member['ns'] == 14:  # Category namespace (subcategory)
                            subcat_name = member['title'].replace('Category:', '')
                            all_subcategories.append(subcat_name)
                
                if 'continue' in data and 'cmcontinue' in data['continue']:
                    continue_token = data['continue']['cmcontinue']
                else:
                    break
                    
            except Exception as e:
                logger.error(f"API error for {category_name}: {e}")
                break
            
            time.sleep(0.1)
        
        logger.info(f"{'  ' * depth}Category:{category_name} - {len(all_members)} items, {len(all_subcategories)} subcats")
        
        # Recursively process subcategories
        for subcat in all_subcategories:
            if subcat not in self.discovered_categories:
                self.discovered_categories.add(subcat)
                sub_members, sub_subcats = self.get_category_members_api(subcat, depth + 1, max_depth)
                all_members.extend(sub_members)
                all_subcategories.extend(sub_subcats)
        
        return all_members, all_subcategories

    def scrape_category_page_html(self, category_name):
        """Scrape category page HTML for items (Strategy 3)"""
        items = []
        url = f"{self.base_url}/wiki/Category:{category_name}"
        
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for category members in the page
            member_divs = soup.find_all('div', class_='category-page__member')
            for div in member_divs:
                link = div.find('a', class_='category-page__member-link')
                if link and 'href' in link.attrs:
                    href = link['href']
                    if href.startswith('/wiki/') and ':' not in href:
                        item_name = link.get_text(strip=True)
                        if item_name:
                            items.append({
                                'name': item_name,
                                'url': urljoin(self.base_url, href),
                                'source': 'strategy3_html'
                            })
            
            # Also check for mw-category links
            category_group = soup.find('div', {'id': 'mw-pages'})
            if category_group:
                links = category_group.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    if href.startswith('/wiki/') and ':' not in href:
                        item_name = link.get_text(strip=True)
                        if item_name:
                            items.append({
                                'name': item_name,
                                'url': urljoin(self.base_url, href),
                                'source': 'strategy3_html'
                            })
            
            logger.info(f"Strategy 3 HTML: Found {len(items)} items on Category:{category_name}")
            
        except Exception as e:
            logger.error(f"Error scraping category page {category_name}: {e}")
        
        return items

    def scrape_list_page(self, url):
        """Scrape list pages like Water_Sources (Strategy 2)"""
        items = []
        
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find main content
            content = soup.find('div', {'class': 'mw-parser-output'})
            if not content:
                return items
            
            # Find all links in lists and regular content
            for element in content.find_all(['ul', 'ol', 'p', 'div']):
                for link in element.find_all('a', href=True):
                    href = link['href']
                    # Filter for wiki article links only
                    if href.startswith('/wiki/') and ':' not in href and '#' not in href:
                        item_name = link.get_text(strip=True)
                        # Filter out navigation/category links
                        if item_name and len(item_name) > 2 and not item_name.lower().startswith(('category', 'file', 'template')):
                            items.append({
                                'name': item_name,
                                'url': urljoin(self.base_url, href),
                                'source': 'strategy2_list'
                            })
            
            logger.info(f"Strategy 2 List: Found {len(items)} items on {url}")
            
        except Exception as e:
            logger.error(f"Error scraping list page {url}: {e}")
        
        return items

    def discover_all_items(self):
        """Comprehensive item discovery with all three strategies"""
        all_items_dict = {}  # Use dict to track unique items by name
        
        # === STRATEGY 1: API with Deep Recursion ===
        logger.info("=" * 60)
        logger.info("STRATEGY 1: API Category Discovery (with deep recursion)")
        logger.info("=" * 60)
        
        main_categories = [
            'Items',
            'Equippable_Items',
            'Building_Pieces',  # This has many subcategories!
            'Tools',
            'Weapons',
            'Armor',
            'Consumables',
            'Medicine',
            'Deployables',
            'Furniture',
            'Materials',
            'Resources',
            'Food',
            'Ammunition',
            'Water_Sources',
            'Electricity_Sources',
            'Light_Sources',
            'Storage',
            'Farming'
        ]
        
        for cat in main_categories:
            if cat not in self.discovered_categories:
                self.discovered_categories.add(cat)
                members, _ = self.get_category_members_api(cat, depth=0, max_depth=4)  # Go deeper!
                for member in members:
                    if member['name'] not in all_items_dict:
                        all_items_dict[member['name']] = {
                            'name': member['name'],
                            'url': f"{self.base_url}/wiki/{quote(member['name'].replace(' ', '_'))}",
                            'category': cat,
                            'source': 'strategy1_api'
                        }
                time.sleep(0.3)
        
        self.stats['strategy1_items'] = len(all_items_dict)
        logger.info(f"Strategy 1 collected: {self.stats['strategy1_items']} unique items")
        
        # === STRATEGY 2: List Pages ===
        logger.info("=" * 60)
        logger.info("STRATEGY 2: Special List Pages")
        logger.info("=" * 60)
        
        list_pages = [
            ('https://icarus.fandom.com/wiki/Water_Sources', 'Water_Sources'),
            ('https://icarus.fandom.com/wiki/Building', 'Building_Pieces'),
            ('https://icarus.fandom.com/wiki/Cooking', 'Food'),
            ('https://icarus.fandom.com/wiki/Crafting', 'Materials'),
            ('https://icarus.fandom.com/wiki/Mining', 'Resources'),
            ('https://icarus.fandom.com/wiki/Items_Index', 'Items'),
            ('https://icarus.fandom.com/wiki/Deployables', 'Deployables'),
            ('https://icarus.fandom.com/wiki/Tools', 'Tools'),
            ('https://icarus.fandom.com/wiki/Weapons', 'Weapons')
        ]
        
        strategy2_count = 0
        for page_url, default_cat in list_pages:
            items = self.scrape_list_page(page_url)
            for item in items:
                if item['name'] not in all_items_dict and item['name'] not in self.processed_items:
                    item['category'] = default_cat
                    all_items_dict[item['name']] = item
                    strategy2_count += 1
            time.sleep(0.3)
        
        self.stats['strategy2_items'] = strategy2_count
        logger.info(f"Strategy 2 added: {strategy2_count} new items")
        
        # === STRATEGY 3: HTML Category Page Scraping ===
        logger.info("=" * 60)
        logger.info("STRATEGY 3: HTML Category Page Scraping")
        logger.info("=" * 60)
        
        important_categories = [
            'Building_Pieces',
            'Tools',
            'Weapons',
            'Deployables',
            'Armor',
            'Consumables',
            'Materials',
            'Resources'
        ]
        
        strategy3_count = 0
        for cat in important_categories:
            items = self.scrape_category_page_html(cat)
            for item in items:
                if item['name'] not in all_items_dict and item['name'] not in self.processed_items:
                    item['category'] = cat
                    all_items_dict[item['name']] = item
                    strategy3_count += 1
            time.sleep(0.3)
        
        self.stats['strategy3_items'] = strategy3_count
        logger.info(f"Strategy 3 added: {strategy3_count} new items")
        
        # Convert to list and update processed items
        all_items = list(all_items_dict.values())
        for item in all_items:
            self.processed_items.add(item['name'])
        
        self.stats['total_unique'] = len(all_items)
        
        logger.info("=" * 60)
        logger.info(f"TOTAL DISCOVERY SUMMARY:")
        logger.info(f"  Strategy 1 (API): {self.stats['strategy1_items']} items")
        logger.info(f"  Strategy 2 (Lists): {self.stats['strategy2_items']} new items")
        logger.info(f"  Strategy 3 (HTML): {self.stats['strategy3_items']} new items")
        logger.info(f"  Total Unique Items: {self.stats['total_unique']}")
        logger.info("=" * 60)
        
        return all_items

    def extract_recipe_table(self, soup):
        """Extract ingredients from recipe tables"""
        ingredients = {}
        
        tables = soup.find_all('table')
        
        for table in tables:
            headers_text = ' '.join([th.get_text(strip=True).lower() for th in table.find_all('th')])
            
            if 'amount' in headers_text and 'resource' in headers_text:
                rows = table.find_all('tr')[1:]
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        cell_texts = [c.get_text(strip=True) for c in cells]
                        
                        amount = None
                        resource = None
                        
                        for i, text in enumerate(cell_texts):
                            clean_text = text.replace(',', '').replace('.', '')
                            if clean_text.isdigit():
                                amount = int(text.replace(',', ''))
                                # Resource is likely adjacent
                                for j in [i-1, i+1]:
                                    if 0 <= j < len(cell_texts):
                                        potential = cell_texts[j].strip()
                                        if potential and potential.lower() not in ['amount', 'resource', 'total', '']:
                                            resource = potential
                                            break
                                break
                        
                        if amount and resource:
                            ingredients[resource] = amount
        
        return ingredients

    def extract_infobox_portable(self, soup):
        """Extract infobox data"""
        data = {}
        
        infobox = soup.find('aside', class_='portable-infobox')
        if not infobox:
            return data
        
        items = infobox.find_all('div', {'class': 'pi-item'})
        
        for item in items:
            label_elem = item.find('h3', {'class': 'pi-data-label'})
            value_elem = item.find('div', {'class': 'pi-data-value'})
            
            if label_elem and value_elem:
                label = label_elem.get_text(strip=True)
                
                links = value_elem.find_all('a')
                if links:
                    value = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]
                else:
                    value = value_elem.get_text(strip=True)
                
                label_lower = label.lower()
                
                if 'category' in label_lower:
                    data['wiki_category'] = value if isinstance(value, str) else ', '.join(value)
                elif 'tier' in label_lower:
                    data['tech_tier'] = value if isinstance(value, str) else ', '.join(value)
                elif 'crafted' in label_lower or 'bench' in label_lower:
                    if isinstance(value, list):
                        data['crafting_stations'] = value
                    else:
                        data['crafting_stations'] = [v.strip() for v in str(value).split(',') if v.strip()]
                elif 'weight' in label_lower:
                    data['weight'] = value if isinstance(value, str) else ', '.join(value)
        
        return data

    def detect_category_from_data(self, item_name, wiki_category, crafting_stations):
        """Detect which of our 21 categories this item belongs to"""
        name_lower = item_name.lower()
        wiki_cat_lower = wiki_category.lower() if wiki_category else ""
        stations_lower = ' '.join(crafting_stations).lower() if crafting_stations else ""
        
        # Enhanced detection rules
        rules = {
            'ammunition': ['arrow', 'bolt', 'round', 'shell', 'ammo', 'bullet', 'cartridge'],
            'armor': ['armor', 'helmet', 'chest', 'boots', 'gloves', 'suit', 'vest', 'pants', 'clothing'],
            'building': ['foundation', 'wall', 'roof', 'door', 'floor', 'beam', 'ramp', 'stairs', 'window', 'halfpiece', 'halfpitch', 'ladder', 'railing', 'trapdoor'],
            'consumables': ['bladder', 'oxygen bladder', 'waterskin'],
            'cooking': ['cooked', 'grilled', 'barbecue', 'barbeque', 'roasted', 'smoked', 'dried', 'soup', 'stew', 'meal', 'salad', 'pie', 'bread'],
            'decoration': ['decorative', 'trophy', 'rug', 'painting'],
            'deployables': ['bench', 'furnace', 'station', 'processor', 'refinery', 'extractor', 'mixer', 'dehumidifier', 'composter'],
            'electricity_sources': ['battery', 'solar panel', 'generator', 'power cell'],
            'farming': ['seed', 'seedling', 'crop', 'fertilizer', 'planter'],
            'fuel_sources': ['biofuel can', 'fuel can'],
            'furniture': ['chair', 'table', 'bed', 'desk', 'bookshelf', 'dresser', 'nightstand', 'couch'],
            'inventory': ['backpack', 'pouch', 'bag'],
            'light_sources': ['torch', 'flashlight', 'headlamp', 'lamp', 'lantern', 'floodlight'],
            'materials': ['ingot', 'screw', 'wire', 'paste', 'mix', 'bloom', 'bar', 'composite', 'epoxy', 'nail', 'rope', 'glass'],
            'medicine': ['bandage', 'pill', 'medicine', 'antibiotic', 'tonic', 'cure', 'anti-'],
            'raw_materials': ['ore', 'wood', 'stone', 'bone', 'leather', 'fur', 'stick', 'fiber', 'clay', 'coal', 'sulfur'],
            'specialized_equipment': ['detector', 'scanner', 'radar', 'attachment', 'module'],
            'storage': ['storage', 'chest', 'crate', 'box', 'container', 'locker', 'dropbox', 'refrigerator'],
            'tools': ['pickaxe', 'axe', 'knife', 'hammer', 'sickle', 'shovel', 'chainsaw', 'drill'],
            'water_sources': ['water tank', 'reservoir', 'purifier', 'water pump', 'water borer', 'rainwater'],
            'weapons': ['bow', 'rifle', 'spear', 'gun', 'pistol', 'shotgun', 'crossbow', 'sword']
        }
        
        for category, keywords in rules.items():
            for keyword in keywords:
                if keyword in name_lower or keyword in wiki_cat_lower or keyword in stations_lower:
                    return category
        
        # Special handling
        if 'food' in wiki_cat_lower or any(w in stations_lower for w in ['barbecue', 'smoker', 'grill']):
            return 'cooking'
        
        if any(w in name_lower for w in ['canteen', 'thermos']):
            return 'consumables'
        
        if 'building' in wiki_cat_lower:
            return 'building'
        
        return 'raw_materials'

    def extract_item_data(self, item_info):
        """Extract complete data for a single item"""
        try:
            name = item_info['name']
            url = item_info['url']
            
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            infobox_data = self.extract_infobox_portable(soup)
            ingredients = self.extract_recipe_table(soup)
            
            crafting_stations = infobox_data.get('crafting_stations', [])
            if crafting_stations:
                crafting_stations = [s for s in crafting_stations if s and s.strip()]
                crafting_stations = list(dict.fromkeys(crafting_stations))
                crafted_at = ', '.join(crafting_stations)
            else:
                crafted_at = 'Character' if not ingredients else 'Unknown'
            
            wiki_category = infobox_data.get('wiki_category', '')
            detected_category = self.detect_category_from_data(name, wiki_category, crafting_stations)
            
            tier = 0
            if 'tech_tier' in infobox_data:
                tier_match = re.search(r'(\d+)', infobox_data['tech_tier'])
                if tier_match:
                    tier = int(tier_match.group(1))
            
            if tier == 0:
                tier_map = {
                    'character': 1, 'crafting bench': 2, 'anvil bench': 2,
                    'machining bench': 3, 'fabricator': 4
                }
                for station, t in tier_map.items():
                    if station in crafted_at.lower():
                        tier = t
                        break
            
            item_data = {
                'name': name,
                'ingredients': ingredients,
                'crafted_at': crafted_at,
                'category': detected_category,
                'tier': tier,
                'url': url
            }
            
            if 'weight' in infobox_data:
                item_data['weight'] = infobox_data['weight']
            if crafting_stations:
                item_data['crafting_stations'] = crafting_stations
            
            with self.lock:
                self.recipes[name] = item_data
            
            return f"✓ {name} ({detected_category})"
            
        except Exception as e:
            logger.error(f"Error processing {item_info.get('name', 'unknown')}: {e}")
            return f"✗ {item_info.get('name', 'unknown')}"

    def scrape_parallel(self, items, max_items=None):
        """Scrape items in parallel"""
        if max_items:
            items = items[:max_items]
        
        total = len(items)
        logger.info(f"Starting parallel scrape of {total} items...")
        
        start_time = time.time()
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.extract_item_data, item): item for item in items}
            
            for future in as_completed(futures):
                result = future.result()
                completed += 1
                
                if completed % 50 == 0 or completed == total:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%) - "
                          f"{rate:.1f} items/sec - ETA: {eta:.0f}s")
        
        logger.info(f"Completed in {time.time() - start_time:.1f}s - {len(self.recipes)} items scraped")

    def categorize_items(self):
        """Organize items into 21 categories"""
        for category in self.categories:
            self.categories[category] = []
        
        for item in self.recipes.values():
            category = item.get('category', 'raw_materials')
            if category in self.categories:
                self.categories[category].append(item)
            else:
                self.categories['raw_materials'].append(item)

    def save_all_files(self):
        """Save all 21 category JSON files and cleanup"""
        logger.info("Saving categorized files...")
        
        for category, items in self.categories.items():
            filename = os.path.join(self.output_dir, f"{category}.json")
            sorted_items = sorted(items, key=lambda x: x['name']) if items else []
            
            data = {
                'category': category.replace('_', ' ').title(),
                'count': len(sorted_items),
                'items': sorted_items
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            if len(sorted_items) > 0:
                logger.info(f"✓ Saved {len(sorted_items)} items to {category}.json")
            else:
                logger.info(f"✓ Created empty {category}.json")
        
        # Save summary with stats
        summary = {
            'total_items': len(self.recipes),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'discovery_stats': self.stats,
            'categories_discovered': len(self.discovered_categories),
            'categories': {cat: len(items) for cat, items in self.categories.items()},
        }
        
        with open(os.path.join(self.output_dir, 'summary.json'), 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info("=" * 60)
        logger.info(f"✓ Complete! Saved {len(self.recipes)} total items")
        logger.info(f"✓ Categories with items: {sum(1 for items in self.categories.values() if items)}/21")
        logger.info(f"✓ All JSON files created in: {os.path.abspath(self.output_dir)}")
        logger.info("=" * 60)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'full'
    
    scraper = CompleteIcarusScraper(max_workers=10)
    
    if mode == 'test':
        logger.info("=== TEST MODE (50 items) ===")
        items = scraper.discover_all_items()
        scraper.scrape_parallel(items, max_items=50)
        scraper.categorize_items()
        scraper.save_all_files()
    
    elif mode == 'medium':
        logger.info("=== MEDIUM MODE (300 items) ===")
        items = scraper.discover_all_items()
        scraper.scrape_parallel(items, max_items=300)
        scraper.categorize_items()
        scraper.save_all_files()
    
    else:  # full
        logger.info("=== FULL SCRAPE ===")
        items = scraper.discover_all_items()
        scraper.scrape_parallel(items)
        scraper.categorize_items()
        scraper.save_all_files()

if __name__ == "__main__":
    main()