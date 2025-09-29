# ICARUS Complete Crafting Calculator

A comprehensive web-based crafting calculator for ICARUS, featuring all items from the game with intelligent resource availability checking across all three maps.

**[Launch Calculator](https://schylerchase.github.io/icarus-calculator/)**

## Features

- **800+ Items** - Complete database of all craftable items
- **3 Maps** - Olympus, Styx, and Prometheus with accurate resource availability
- **Smart Calculator** - Automatically calculates all required materials recursively
- **Availability Checking** - Shows which items can be crafted on each map
- **Shopping Cart** - Track multiple items and see combined requirements
- **Progress Tracking** - Check off materials as you gather them
- **Responsive Design** - Works on desktop and mobile

## How to Use

### Basic Usage

1. **Select your map** (Olympus, Styx, or Prometheus)
2. **Search or browse** for items you want to craft
3. **Adjust quantities** with +/- buttons
4. **Click "Add"** to add items to your shopping cart
5. **Click "Calculate"** to see complete material breakdown
6. **Check off items** as you gather them to track progress

### Filters

- **Search** - Type item names to find quickly
- **Category** - Filter by type (Tools, Weapons, Armor, Building, etc.)
- **Tier** - Filter by tech tier (0-4)
- **Map** - Switch maps to see different resource availability

### Understanding Icons

- Green checkmark - Item can be crafted on selected map
- Red X - Missing required materials on this map

## Data Coverage

All recipe data scraped from [ICARUS Fandom Wiki](https://icarus.fandom.com).

### 21 Item Categories

Ammunition | Armor | Building | Consumables | Cooking | Decoration | Deployables
Electricity Sources | Farming | Fuel Sources | Furniture | Inventory | Light Sources
Materials | Medicine | Raw Materials | Specialized Equipment | Storage | Tools | Water Sources | Weapons

## Updating Data

Recipe database updates weekly to capture game changes.

### Manual Update

# Install requirements
pip install requests beautifulsoup4 lxml

# Run scraper
python RecipeScraping.py full

# New JSON files saved to icarus_data/

Technical Stack

Frontend: React (CDN) + Vanilla JavaScript
Styling: Custom CSS (dark theme)
Data: JSON (21 category files)
Hosting: GitHub Pages
Updates: Python scraper with BeautifulSoup

Known Limitations

Ingredient variations - Some items use "Stick" vs "Sticks" inconsistently
Workshop items - Exotic crafting not included
Special recipes - Some event/DLC items may be missing
Wiki accuracy - Data quality depends on community wiki updates

Contributing
Found incorrect data?

Report issue - Open GitHub issue with details
Fix wiki - Update ICARUS Fandom Wiki
Wait - Weekly scraper will sync changes

Credits

Game: ICARUS by RocketWerkz
Data: ICARUS Fandom Wiki Community
Calculator: Community Tool

License
This is a fan-made tool. ICARUS and related content are property of RocketWerkz.
Calculator code: MIT License
