"""
Egg Price Crawler
A web crawler to extract egg prices and item names from New Zealand retail stores.
"""

import json
import logging
import os
import re
import time
from typing import List, Dict, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import firebase_admin
from firebase_admin import credentials, firestore


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EggCrawler:
    """Main crawler class for extracting egg prices from retail websites."""
    
    def __init__(self, firebase_service_account_path: Optional[str] = None):
        """
        Initialize the crawler with default settings.
        
        Args:
            firebase_service_account_path: Path to Firebase service account JSON key file.
                                          If None, checks FIREBASE_SERVICE_ACCOUNT environment variable.
        """
        self.results: List[Dict[str, str]] = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Initialize Firebase if service account path is provided
        self.db = None
        self.firebase_initialized = False
        if firebase_service_account_path or os.getenv('FIREBASE_SERVICE_ACCOUNT'):
            self._init_firebase(firebase_service_account_path)
    
    def _init_firebase(self, service_account_path: Optional[str] = None):
        """
        Initialize Firebase Admin SDK.
        
        Args:
            service_account_path: Path to service account JSON key file.
        """
        try:
            # Get path from parameter or environment variable
            if not service_account_path:
                service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT')
            
            if not service_account_path or not os.path.exists(service_account_path):
                logger.warning(f"Firebase service account key not found at: {service_account_path}")
                logger.warning("Firebase upload will be skipped. Set FIREBASE_SERVICE_ACCOUNT environment variable or pass path to __init__")
                return
            
            # Initialize Firebase only if not already initialized
            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase initialized successfully")
            
            # Get Firestore client
            self.db = firestore.client()
            self.firebase_initialized = True
            logger.info("Firestore client ready")
            
        except Exception as e:
            logger.error(f"Error initializing Firebase: {e}")
            logger.error("Firebase upload will be skipped")
            self.firebase_initialized = False
    
    def get_selenium_driver(self) -> webdriver.Chrome:
        """
        Create and return a configured Selenium Chrome driver.
        
        Returns:
            webdriver.Chrome: Configured Chrome driver instance
        """
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    def extract_woolworths_product(self, product_element: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Extract product name and price from a Woolworths product element.
        
        Args:
            product_element: BeautifulSoup element containing product information
        
        Returns:
            Optional[Dict[str, str]]: Dictionary with store, item_name, and price, or None if invalid
        """
        try:
            # Extract product name - Woolworths specific selectors
            name = None
            name_elem = (
                product_element.find(['h2', 'h3', 'h4', 'a'], class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower() or 'heading' in x.lower())) or
                product_element.find(['a'], href=True) or
                product_element.find(['h2', 'h3', 'h4'])
            )
            
            if name_elem:
                name = name_elem.get_text(strip=True)
            
            # If name is too short or generic, try to find text with "egg" in it
            if not name or len(name) < 5 or name.lower() in ['special', 'sale', 'new']:
                # Look for any text containing "egg"
                all_text = product_element.get_text()
                lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                for line in lines:
                    if 'egg' in line.lower() and len(line) > 10:
                        name = line
                        break
            
            if not name or len(name) < 5:
                return None
            
            # Clean up name - remove price information and extra text
            # Remove patterns like "$X.XX / 1ea", "Was $X.XX", "Save $X.XX", etc.
            name = re.sub(r'\$[\d,]+\.?\d{2}\s*/.*?$', '', name)  # Remove "$X.XX / 1ea" at end
            name = re.sub(r'\s*Was\s*\$[\d,]+\.?\d{2}.*?$', '', name)  # Remove "Was $X.XX..."
            name = re.sub(r'\s*Save\s*\$[\d,]+\.?\d{2}.*?$', '', name)  # Remove "Save $X.XX..."
            name = re.sub(r'\s*\$[\d,]+\.?\d{2}.*?$', '', name)  # Remove any remaining "$X.XX..." at end
            name = name.strip()
            
            # Extract price - look for $X.XX pattern (unit price, usually the first one)
            price = None
            full_text = product_element.get_text()
            
            # Find all price patterns in the element
            price_patterns = re.findall(r'\$[\d,]+\.?\d{2}', full_text)
            if price_patterns:
                # Take the first price that looks like a unit price (usually between $0.50 and $2.00)
                for p in price_patterns:
                    price_num = float(p.replace('$', '').replace(',', ''))
                    if 0.30 <= price_num <= 2.00:  # Unit prices are typically in this range
                        price = p
                        break
                # If no unit price found, use the first one
                if not price:
                    price = price_patterns[0]
            else:
                # Try alternative patterns
                alt_patterns = re.findall(r'[\$]?[\d]+\.[\d]{2}', full_text)
                if alt_patterns:
                    price = f"${alt_patterns[0].replace('$', '')}"
            
            if not price:
                return None
            
            return {
                "store": "Woolworths",
                "item_name": name,
                "price": price
            }
        
        except Exception as e:
            logger.debug(f"Error extracting Woolworths product data: {e}")
            return None
    
    def extract_paknsave_product(self, product_element: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Extract product name and price from a Pak'nSave product element.
        
        Args:
            product_element: BeautifulSoup element containing product information
        
        Returns:
            Optional[Dict[str, str]]: Dictionary with store, item_name, and price, or None if invalid
        """
        try:
            # Extract product name - Pak'nSave specific selectors
            name = None
            name_elem = (
                product_element.find(['h2', 'h3', 'h4', 'a'], class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower() or 'heading' in x.lower())) or
                product_element.find(['a'], href=True) or
                product_element.find(['h2', 'h3', 'h4'])
            )
            
            if name_elem:
                name = name_elem.get_text(strip=True)
            
            # Clean up name - remove size numbers at the end if they're separate
            if name:
                # Remove trailing patterns like " - 6" or "12pk - 7"
                name = re.sub(r'\s*-\s*\d+\s*$', '', name)
                name = name.strip()
            
            if not name or len(name) < 5:
                return None
            
            # Extract price - Pak'nSave uses specific price classes
            price = None
            full_text = product_element.get_text()
            
            # Look for price patterns - Pak'nSave usually has $X.XX format
            price_patterns = re.findall(r'\$[\d,]+\.?\d{2}', full_text)
            if price_patterns:
                price = price_patterns[0]
            else:
                # Try to find price in specific elements
                price_elem = (
                    product_element.find(['span', 'div'], class_=lambda x: x and 'price' in x.lower()) or
                    product_element.find(['span', 'div'], string=lambda x: x and '$' in str(x))
                )
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_match = re.search(r'\$[\d,]+\.?\d{2}', price_text)
                    if price_match:
                        price = price_match.group()
            
            # If still no price, skip this product (don't want size numbers)
            if not price or not re.search(r'\$', price):
                return None
            
            return {
                "store": "Pak'nSave",
                "item_name": name,
                "price": price
            }
        
        except Exception as e:
            logger.debug(f"Error extracting Pak'nSave product data: {e}")
            return None
    
    def crawl_woolworths(self) -> List[Dict[str, str]]:
        """
        Crawl egg prices from Woolworths New Zealand website.
        
        Returns:
            List[Dict[str, str]]: List of dictionaries containing item name and price
        """
        logger.info("Starting Woolworths crawl...")
        url = "https://www.woolworths.co.nz/shop/searchproducts?search=Eggs"
        results = []
        
        driver = None
        try:
            driver = self.get_selenium_driver()
            driver.get(url)
            
            # Wait for products to load
            time.sleep(3)
            
            # Try to find product elements
            # Woolworths uses dynamic content, so we need to wait for elements
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='product'], [class*='Product'], [data-testid*='product']"))
                )
            except Exception as e:
                logger.warning(f"Timeout waiting for products: {e}")
            
            # Parse the page
            soup = BeautifulSoup(driver.page_source, 'lxml')
            
            # Common selectors for Woolworths product listings
            product_selectors = [
                'div[class*="product"]',
                'div[class*="Product"]',
                'article[class*="product"]',
                '[data-testid*="product"]',
                '.product-tile',
                '.product-item'
            ]
            
            products = []
            for selector in product_selectors:
                products = soup.select(selector)
                if products:
                    logger.info(f"Found {len(products)} products using selector: {selector}")
                    break
            
            if not products:
                # Fallback: look for any elements containing price patterns
                logger.info("Trying fallback method to find products...")
                products = soup.find_all(['div', 'article', 'li'], class_=lambda x: x and ('egg' in x.lower() or 'product' in x.lower()))
            
            for product in products[:30]:  # Limit to first 30 products
                product_data = self.extract_woolworths_product(product)
                if product_data and 'egg' in product_data['item_name'].lower():
                    results.append(product_data)
                    logger.info(f"Found: {product_data['item_name']} - {product_data['price']}")
            
            if not results:
                logger.warning("No products found on Woolworths. The page structure may have changed.")
            
        except Exception as e:
            logger.error(f"Error crawling Woolworths: {e}")
        finally:
            if driver:
                driver.quit()
        
        logger.info(f"Woolworths crawl completed. Found {len(results)} products.")
        return results
    
    def crawl_paknsave(self) -> List[Dict[str, str]]:
        """
        Crawl egg prices from Pak'nSave New Zealand website.
        
        Returns:
            List[Dict[str, str]]: List of dictionaries containing item name and price
        """
        logger.info("Starting Pak'nSave crawl...")
        url = "https://www.paknsave.co.nz/shop/search?pg=1&q=egg"
        results = []
        
        driver = None
        try:
            driver = self.get_selenium_driver()
            driver.get(url)
            
            # Wait for products to load
            time.sleep(3)
            
            # Wait for product elements
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='product'], [class*='Product'], [data-testid*='product']"))
                )
            except Exception as e:
                logger.warning(f"Timeout waiting for products: {e}")
            
            # Parse the page
            soup = BeautifulSoup(driver.page_source, 'lxml')
            
            # Common selectors for Pak'nSave product listings
            product_selectors = [
                'div[class*="product"]',
                'div[class*="Product"]',
                'article[class*="product"]',
                '[data-testid*="product"]',
                '.product-tile',
                '.product-item',
                'li[class*="product"]'
            ]
            
            products = []
            for selector in product_selectors:
                products = soup.select(selector)
                if products:
                    logger.info(f"Found {len(products)} products using selector: {selector}")
                    break
            
            if not products:
                # Fallback: look for any elements containing price patterns
                logger.info("Trying fallback method to find products...")
                products = soup.find_all(['div', 'article', 'li'], class_=lambda x: x and ('egg' in x.lower() or 'product' in x.lower()))
            
            for product in products[:30]:  # Limit to first 30 products
                product_data = self.extract_paknsave_product(product)
                if product_data and 'egg' in product_data['item_name'].lower():
                    results.append(product_data)
                    logger.info(f"Found: {product_data['item_name']} - {product_data['price']}")
            
            if not results:
                logger.warning("No products found on Pak'nSave. The page structure may have changed.")
        
        except Exception as e:
            logger.error(f"Error crawling Pak'nSave: {e}")
        finally:
            if driver:
                driver.quit()
        
        logger.info(f"Pak'nSave crawl completed. Found {len(results)} products.")
        return results
    
    def crawl_all(self) -> List[Dict[str, str]]:
        """
        Crawl all configured websites and collect egg prices.
        
        Returns:
            List[Dict[str, str]]: Combined list of all egg products with prices
        """
        logger.info("Starting crawl of all websites...")
        all_results = []
        
        # Crawl Woolworths
        woolworths_results = self.crawl_woolworths()
        all_results.extend(woolworths_results)
        
        # Small delay between crawls
        time.sleep(2)
        
        # Crawl Pak'nSave
        paknsave_results = self.crawl_paknsave()
        all_results.extend(paknsave_results)
        
        self.results = all_results
        logger.info(f"Total products found: {len(all_results)}")
        return all_results
    
    def save_to_json(self, filename: Optional[str] = None) -> str:
        """
        Save the crawled results to a JSON file.
        
        Args:
            filename: Optional filename. If not provided, uses timestamp-based name.
        
        Returns:
            str: Path to the saved JSON file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"egg_prices_{timestamp}.json"
        
        output_data = {
            "crawl_date": datetime.now().isoformat(),
            "total_products": len(self.results),
            "products": self.results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {filename}")
        return filename
    
    def upload_to_firebase(self, collection_name: str = "egg_prices") -> int:
        """
        Upload crawled results to Firebase Firestore.
        Updates existing documents or creates new ones based on store + item_name.
        
        Args:
            collection_name: Name of the Firestore collection to store data in.
        
        Returns:
            int: Number of documents successfully uploaded/updated
        """
        if not self.firebase_initialized or not self.db:
            logger.warning("Firebase not initialized. Skipping upload.")
            return 0
        
        if not self.results:
            logger.warning("No results to upload to Firebase.")
            return 0
        
        try:
            import hashlib
            crawl_date = datetime.now()
            uploaded_count = 0
            updated_count = 0
            
            logger.info(f"Uploading {len(self.results)} products to Firebase collection '{collection_name}'...")
            
            # Upload each product as a separate document
            for product in self.results:
                try:
                    store = product.get("store", "")
                    item_name = product.get("item_name", "")
                    
                    # Create a unique document ID from store + item_name
                    # Using hash to handle special characters and create consistent IDs
                    doc_id_string = f"{store}_{item_name}".lower().strip()
                    doc_id = hashlib.md5(doc_id_string.encode('utf-8')).hexdigest()
                    
                    # Create document data with egg name, price, store, and crawl date
                    doc_data = {
                        "store": store,
                        "item_name": item_name,
                        "price": product.get("price", ""),
                        "last_crawl_date": crawl_date,
                        "last_crawl_timestamp": firestore.SERVER_TIMESTAMP,
                        "created_at": firestore.SERVER_TIMESTAMP  # Only set on creation
                    }
                    
                    # Check if document exists
                    doc_ref = self.db.collection(collection_name).document(doc_id)
                    doc = doc_ref.get()
                    
                    if doc.exists:
                        # Update existing document (preserve created_at)
                        existing_data = doc.to_dict()
                        if "created_at" in existing_data:
                            doc_data["created_at"] = existing_data["created_at"]
                        doc_ref.update(doc_data)
                        updated_count += 1
                        logger.debug(f"Updated: {item_name} from {store}")
                    else:
                        # Create new document
                        doc_ref.set(doc_data)
                        uploaded_count += 1
                        logger.debug(f"Created: {item_name} from {store}")
                    
                except Exception as e:
                    logger.error(f"Error uploading product '{product.get('item_name', 'unknown')}': {e}")
                    continue
            
            total_count = uploaded_count + updated_count
            logger.info(f"Successfully processed {total_count} products: {uploaded_count} new, {updated_count} updated")
            return total_count
            
        except Exception as e:
            logger.error(f"Error uploading to Firebase: {e}")
            return 0


def print_results(results: List[Dict[str, str]]):
    """
    Print all results in a formatted table to the console.
    
    Args:
        results: List of product dictionaries
    """
    if not results:
        print("\nNo products found.")
        return
    
    print(f"\n{'='*80}")
    print(f"{'EGG PRICE CRAWL RESULTS':^80}")
    print(f"{'='*80}")
    print(f"\nTotal products found: {len(results)}\n")
    
    # Group by store
    woolworths_products = [p for p in results if p['store'] == 'Woolworths']
    paknsave_products = [p for p in results if p['store'] == "Pak'nSave"]
    
    # Print Woolworths products
    if woolworths_products:
        print(f"{'─'*80}")
        print(f"WOOLWORTHS ({len(woolworths_products)} products)")
        print(f"{'─'*80}")
        for i, product in enumerate(woolworths_products, 1):
            name = product['item_name'][:60] + "..." if len(product['item_name']) > 60 else product['item_name']
            price = product['price']
            print(f"{i:2d}. {name:<60} {price:>10}")
        print()
    
    # Print Pak'nSave products
    if paknsave_products:
        print(f"{'─'*80}")
        print(f"PAK'NSAVE ({len(paknsave_products)} products)")
        print(f"{'─'*80}")
        for i, product in enumerate(paknsave_products, 1):
            name = product['item_name'][:60] + "..." if len(product['item_name']) > 60 else product['item_name']
            price = product['price']
            print(f"{i:2d}. {name:<60} {price:>10}")
        print()
    
    print(f"{'='*80}\n")


def main():
    """Main execution function."""
    # Initialize crawler with Firebase (service account path from env var or default)
    service_account_path = os.getenv('FIREBASE_SERVICE_ACCOUNT', 'serviceAccountKey.json')
    crawler = EggCrawler(firebase_service_account_path=service_account_path)
    
    try:
        # Crawl all websites
        results = crawler.crawl_all()
        
        # Save results to JSON (overwrite same file each time)
        output_file = crawler.save_to_json("egg_prices.json")
        
        # Upload to Firebase if initialized
        if crawler.firebase_initialized:
            processed_count = crawler.upload_to_firebase()
            if processed_count > 0:
                print(f"✓ Successfully processed {processed_count} products in Firebase\n")
            else:
                print("⚠ No products were uploaded to Firebase\n")
        
        # Print all results to console
        print_results(results)
        
        # Print file location
        print(f"Results saved to: {output_file}\n")
        
    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}")
        raise


if __name__ == "__main__":
    main()

