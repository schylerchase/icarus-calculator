#!/usr/bin/env python3
"""
Build script to combine all individual JSON files into a single bundle
Run this before deploying to GitHub Pages
"""

import json
from pathlib import Path

def build_bundle():
    """Combine all JSON files into a single recipes_bundle.json"""
    
    data_dir = Path("icarus_data")
    output_file = data_dir / "recipes_bundle.json"
    
    all_recipes = {}
    
    print("🔨 Building recipe bundle...")
    print("=" * 60)
    
    # Get all subdirectories
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
                    
            except Exception as e:
                print(f"⚠️  Error loading {json_file}: {e}")
    
    # Write bundle
    print(f"\n📦 Writing bundle with {len(all_recipes)} recipes...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_recipes, f, separators=(',', ':'))  # Minified
    
    # Get file sizes
    bundle_size = output_file.stat().st_size
    bundle_size_mb = bundle_size / (1024 * 1024)
    
    print(f"✅ Bundle created: {output_file}")
    print(f"📊 Size: {bundle_size_mb:.2f} MB ({bundle_size:,} bytes)")
    print(f"📝 Recipes: {len(all_recipes)}")
    print("=" * 60)
    
    # Create a compressed version if possible
    try:
        import gzip
        compressed_file = data_dir / "recipes_bundle.json.gz"
        with open(output_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb', compresslevel=9) as f_out:
                f_out.writelines(f_in)
        
        compressed_size = compressed_file.stat().st_size
        compressed_size_mb = compressed_size / (1024 * 1024)
        compression_ratio = (1 - compressed_size / bundle_size) * 100
        
        print(f"✅ Compressed bundle: {compressed_file}")
        print(f"📊 Compressed size: {compressed_size_mb:.2f} MB ({compressed_size:,} bytes)")
        print(f"🗜️  Compression: {compression_ratio:.1f}% smaller")
        print("=" * 60)
    except ImportError:
        print("ℹ️  gzip not available - skipping compression")
    
    print("\n✨ Build complete! Deploy icarus_data/ to GitHub Pages")
    print("💡 The calculator will now load instantly!")

if __name__ == "__main__":
    build_bundle()