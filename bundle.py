#!/usr/bin/env python3
"""
Improved bundler that creates both a master bundle and category-specific files
that match what the HTML expects
"""

import json
from pathlib import Path
from collections import defaultdict

def build_bundles():
    """Create both master bundle and category-specific JSON files"""
    
    data_dir = Path("icarus_data")
    
    print("🔨 Building recipe bundles...")
    print("=" * 60)
    
    # Step 1: Load all individual item files from subdirectories
    all_recipes = {}
    items_by_category = defaultdict(list)
    
    # Get all subdirectories (armor_clothing, weapons_melee, etc.)
    subdirs = [d for d in data_dir.iterdir() if d.is_dir()]
    
    total_files = 0
    for subdir in subdirs:
        json_files = list(subdir.glob("*.json"))
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    item_data = json.load(f)
                
                item_name = item_data.get("name")
                if item_name:
                    all_recipes[item_name] = item_data
                    total_files += 1
                    
                    # Group by scraped category folder name
                    category = subdir.name
                    items_by_category[category].append(item_data)
                    
            except Exception as e:
                print(f"⚠️  Error loading {json_file}: {e}")
    
    print(f"✅ Loaded {total_files} items from {len(subdirs)} categories")
    
    # Step 2: Map scraped categories to HTML expected categories
    category_mapping = {
        'ammunition': ['ammunition'],
        'armor': ['armor_clothing'],
        'building': ['building_structures', 'building_furniture'],
        'consumables': ['consumables_food', 'consumables_medicine'],
        'cooking': ['consumables_food'],  # Overlap with consumables
        'deployables': ['deployables'],
        'farming': ['consumables_food'],  # Farming items
        'furniture': ['building_furniture'],
        'materials': ['resources_processed'],
        'medicine': ['consumables_medicine'],
        'raw_materials': ['resources_raw'],
        'specialized_equipment': ['tools', 'deployables'],
        'storage': ['building_furniture'],
        'tools': ['tools'],
        'weapons': ['weapons_melee', 'weapons_ranged'],
        # Additional categories from HTML
        'decoration': ['building_furniture'],
        'electricity_sources': ['building_furniture'],
        'fuel_sources': ['resources_processed'],
        'inventory': ['tools'],
        'light_sources': ['building_furniture'],
        'water_sources': ['building_furniture'],
        'orbital_items': ['orbital_items']
    }
    
    # Step 3: Create HTML-expected category files
    print(f"\n📦 Creating category files for HTML...")
    
    html_categories = {}
    for html_cat, scraped_cats in category_mapping.items():
        combined_items = []
        for scraped_cat in scraped_cats:
            if scraped_cat in items_by_category:
                combined_items.extend(items_by_category[scraped_cat])
        
        if combined_items:
            html_categories[html_cat] = {
                "category": html_cat.replace('_', ' ').title(),
                "count": len(combined_items),
                "items": sorted(combined_items, key=lambda x: x['name'])
            }
            
            # Write individual category file
            category_file = data_dir / f"{html_cat}.json"
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump(html_categories[html_cat], f, indent=2, ensure_ascii=False)
            
            print(f"  ✅ {html_cat}.json ({len(combined_items)} items)")
    
    # Step 4: Create master bundle (all recipes in one file)
    print(f"\n📦 Creating master bundle...")
    bundle_file = data_dir / "recipes_bundle.json"
    
    with open(bundle_file, 'w', encoding='utf-8') as f:
        json.dump(all_recipes, f, separators=(',', ':'))  # Minified
    
    bundle_size = bundle_file.stat().st_size
    bundle_size_mb = bundle_size / (1024 * 1024)
    
    print(f"  ✅ recipes_bundle.json")
    print(f"  📊 Size: {bundle_size_mb:.2f} MB ({bundle_size:,} bytes)")
    print(f"  📝 Recipes: {len(all_recipes)}")
    
    # Step 5: Create index file
    print(f"\n📋 Creating index...")
    index = {
        "total_items": len(all_recipes),
        "categories": {},
        "items_index": []
    }
    
    for category, data in html_categories.items():
        index["categories"][category] = {
            "count": data["count"],
            "display_name": data["category"]
        }
        
        for item in data["items"]:
            index["items_index"].append({
                "name": item['name'],
                "category": category,
                "type": item.get('item_type', 'unknown'),
                "tier": item.get('tier', 0),
                "crafted_at": item.get('crafted_at', 'Unknown')
            })
    
    index["items_index"] = sorted(index["items_index"], key=lambda x: x['name'])
    
    index_file = data_dir / "index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ index.json")
    
    # Step 6: Compress bundle
    try:
        import gzip
        compressed_file = data_dir / "recipes_bundle.json.gz"
        with open(bundle_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb', compresslevel=9) as f_out:
                f_out.writelines(f_in)
        
        compressed_size = compressed_file.stat().st_size
        compressed_size_mb = compressed_size / (1024 * 1024)
        compression_ratio = (1 - compressed_size / bundle_size) * 100
        
        print(f"\n🗜️  Compressed bundle created")
        print(f"  📊 Size: {compressed_size_mb:.2f} MB ({compressed_size:,} bytes)")
        print(f"  💾 Compression: {compression_ratio:.1f}% smaller")
    except ImportError:
        print("\nℹ️  gzip not available - skipping compression")
    
    # Summary
    print(f"\n{'='*60}")
    print("✅ BUILD COMPLETE!")
    print("="*60)
    print(f"Total items: {len(all_recipes)}")
    print(f"Category files: {len(html_categories)}")
    print(f"\n📁 Files created:")
    print(f"  • recipes_bundle.json (master bundle)")
    print(f"  • index.json (searchable index)")
    for category in sorted(html_categories.keys()):
        print(f"  • {category}.json")
    print(f"\n💡 Your HTML file can now load from:")
    print(f"  1. Individual category files (current method)")
    print(f"  2. Master bundle (faster, single request)")
    print("="*60)

if __name__ == "__main__":
    build_bundles()