"""
Egg Price Crawler
A web crawler to extract egg prices and item names from New Zealand retail stores.
"""

import json
import logging
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


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EggCrawler:
    """Main crawler class for extracting egg prices from retail websites."""
    
    def __init__(self):
        """Initialize the crawler with default settings."""
        self.results: List[Dict[str, str]] = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
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
    crawler = EggCrawler()
    
    try:
        # Crawl all websites
        results = crawler.crawl_all()
        
        # Save results to JSON
        output_file = crawler.save_to_json()
        
        # Print all results to console
        print_results(results)
        
        # Print file location
        print(f"Results saved to: {output_file}\n")
        
    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}")
        raise


if __name__ == "__main__":
    main()

