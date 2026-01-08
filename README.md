# Egg Price Crawler

A professional web crawler system to extract egg prices and item names from major New Zealand retail stores.

## Features

- Crawls egg prices from Woolworths New Zealand and Pak'nSave New Zealand
- Extracts product names and prices
- Saves results in structured JSON format
- **Automatically uploads to Firebase Firestore**
- **Automated daily runs via GitHub Actions** (every 24 hours)
- Comprehensive error handling and logging
- Follows Python coding standards and best practices

## Requirements

- Python 3.8 or higher
- Chrome browser (for Selenium WebDriver)
- Firebase project with Firestore enabled

## Installation

1. Clone or download this repository

2. Install required dependencies:
```bash
# On Windows
py -m pip install -r requirements.txt

# On Linux/Mac
pip install -r requirements.txt
```

3. Set up Firebase:
   - Download your Firebase service account key from [Firebase Console](https://console.firebase.google.com/)
   - Go to Project Settings → Service Accounts → Generate new private key
   - Save the JSON file as `serviceAccountKey.json` in the project root
   - **Important**: This file is in `.gitignore` and should never be committed!

## Usage

### Local Run

Run the crawler manually:
```bash
# On Windows
py egg_crawler.py

# On Linux/Mac
python egg_crawler.py
```

The script will:
1. Crawl both websites (Woolworths and Pak'nSave)
2. Extract egg product names and prices
3. Save results to a JSON file with timestamp (e.g., `egg_prices_20231215_143022.json`)
4. Upload data to Firebase Firestore (if configured)

### Automated Daily Runs (GitHub Actions)

The crawler is configured to run automatically every 24 hours via GitHub Actions.

#### Setup Instructions:

1. **Push your code to GitHub** (make sure `serviceAccountKey.json` is NOT committed - it's in `.gitignore`)

2. **Add Firebase credentials as GitHub Secret**:
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `FIREBASE_SERVICE_ACCOUNT_JSON`
   - Value: Copy and paste the **entire contents** of your `serviceAccountKey.json` file
   - Click "Add secret"

3. **Verify the workflow**:
   - Go to the "Actions" tab in your GitHub repository
   - The workflow will run:
     - Automatically every day at 2:00 AM UTC
     - Manually by clicking "Run workflow" on the Actions page

4. **Customize the schedule** (optional):
   - Edit `.github/workflows/daily_crawl.yml`
   - Change the cron schedule: `cron: '0 2 * * *'` (hour minute day month weekday)
   - Example: `'0 14 * * *'` = 2:00 PM UTC daily

## Output Format

### Local JSON File

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

### Firebase Firestore

Data is stored in the `egg_prices` collection with the following structure:
- **Document ID**: MD5 hash of `store_item_name` (ensures unique entries per product)
- **Fields**:
  - `store`: Store name (Woolworths or Pak'nSave)
  - `item_name`: Product name
  - `price`: Current price per egg
  - `last_crawl_date`: Last crawl timestamp
  - `last_crawl_timestamp`: Server timestamp
  - `created_at`: First crawl timestamp (preserved on updates)

**Note**: The crawler updates existing documents instead of creating duplicates, so each unique product maintains a single document with the latest price.

## Project Structure

```
.
├── egg_crawler.py                    # Main crawler script
├── requirements.txt                  # Python dependencies
├── .gitignore                        # Git ignore file (protects credentials)
├── .github/
│   └── workflows/
│       └── daily_crawl.yml          # GitHub Actions workflow for automated runs
├── serviceAccountKey.json            # Firebase credentials (NOT in git)
└── README.md                         # This file
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

### Local Run Issues

1. **"pip is not recognized"** (Windows):
   - Use `py -m pip` instead of `pip`
   - Or use `python -m pip`

2. **Firebase upload fails**:
   - Verify `serviceAccountKey.json` exists and contains valid JSON
   - Check file path is correct
   - Ensure Firebase project has Firestore enabled

3. **Selenium/Chrome errors**:
   - Ensure Chrome browser is installed
   - ChromeDriver is automatically managed by webdriver-manager
   - Check your internet connection

### GitHub Actions Issues

1. **Workflow fails to upload to Firebase**:
   - Verify the `FIREBASE_SERVICE_ACCOUNT_JSON` secret is set correctly
   - Check the Actions logs for detailed error messages
   - Ensure the JSON content was copied completely (including all brackets)

2. **Workflow doesn't run**:
   - Check if Actions are enabled in repository settings
   - Verify the cron schedule syntax
   - Check the Actions tab for any error messages

3. **Chrome installation fails in CI**:
   - The workflow automatically installs Chrome, but if issues occur, check the Actions logs

For other issues:
- Review the log output for specific errors
- Check that websites are accessible
- Verify Firebase Firestore rules allow writes from your service account

