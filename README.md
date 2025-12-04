# Egg Price Crawler

A professional web crawler system to extract egg prices and item names from major New Zealand retail stores.

## Features

- Crawls egg prices from Woolworths New Zealand and Pak'nSave New Zealand
- Extracts product names and prices
- Saves results in structured JSON format
- Comprehensive error handling and logging
- Follows Python coding standards and best practices

## Requirements

- Python 3.8 or higher
- Chrome browser (for Selenium WebDriver)

## Installation

1. Clone or download this repository

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the crawler:
```bash
python egg_crawler.py
```

The script will:
1. Crawl both websites (Woolworths and Pak'nSave)
2. Extract egg product names and prices
3. Save results to a JSON file with timestamp (e.g., `egg_prices_20231215_143022.json`)

## Output Format

The JSON output file contains:
```json
{
  "crawl_date": "2023-12-15T14:30:22.123456",
  "total_products": 15,
  "products": [
    {
      "store": "Woolworths",
      "item_name": "Free Range Eggs 12 Pack",
      "price": "$8.99"
    },
    {
      "store": "Pak'nSave",
      "item_name": "Cage Free Eggs 12 Pack",
      "price": "$7.50"
    }
  ]
}
```

## Project Structure

```
.
├── egg_crawler.py      # Main crawler script
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Code Standards

- Follows PEP 8 style guidelines
- Type hints for better code clarity
- Comprehensive docstrings
- Proper error handling and logging
- Modular class-based design

## Notes

- The crawler uses Selenium WebDriver to handle JavaScript-rendered content
- Chrome browser must be installed on your system
- The script includes delays to be respectful to the websites
- If website structures change, the selectors may need to be updated

## Troubleshooting

If you encounter issues:
1. Ensure Chrome browser is installed
2. Check your internet connection
3. Verify the websites are accessible
4. Review the log output for specific errors

