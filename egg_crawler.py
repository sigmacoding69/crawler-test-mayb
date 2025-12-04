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
    
    def extract_product_data(self, product_element: BeautifulSoup, store_name: str) -> Optional[Dict[str, str]]:
        """
        Extract product name and price from a product element.
        
        Args:
            product_element: BeautifulSoup element containing product information
            store_name: Name of the store for the result
        
        Returns:
            Optional[Dict[str, str]]: Dictionary with store, item_name, and price, or None if invalid
        """
        try:
            # Extract product name - try multiple strategies
            name = None
            name_selectors = [
                (['h1', 'h2', 'h3', 'h4'], lambda x: x and ('title' in x.lower() or 'name' in x.lower())),
                (['a'], lambda x: x and ('title' in x.lower() or 'name' in x.lower())),
                (['h1', 'h2', 'h3', 'h4', 'a'], None),
                (['span', 'div'], lambda x: x and ('title' in x.lower() or 'name' in x.lower())),
            ]
            
            for tags, class_filter in name_selectors:
                name_elem = product_element.find(tags, class_=class_filter) if class_filter else product_element.find(tags)
                if name_elem:
                    name = name_elem.get_text(strip=True)
                    if name and len(name) > 3:
                        break
            
            if not name or len(name) < 3:
                return None
            
            # Extract price - try multiple strategies
            price = None
            price_selectors = [
                (['span', 'div'], lambda x: x and 'price' in x.lower()),
                (['span', 'div', 'p'], lambda x: x and ('cost' in x.lower() or 'amount' in x.lower())),
                (['*'], lambda x: x and '$' in str(x)),
            ]
            
            for tags, class_filter in price_selectors:
                price_elem = product_element.find(tags, class_=class_filter)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Check if it contains a price pattern
                    if re.search(r'[\$]?[\d,]+\.?\d*', price_text):
                        price = price_text
                        break
            
            # Fallback: search entire element text for price pattern
            if not price:
                full_text = product_element.get_text()
                price_match = re.search(r'[\$]?[\d,]+\.?\d*', full_text)
                if price_match:
                    price = price_match.group()
            
            if not price:
                return None
            
            # Validate that this is likely an egg product
            name_lower = name.lower()
            if 'egg' not in name_lower and len(name) < 10:
                # Might still be valid, but be more lenient
                pass
            
            return {
                "store": store_name,
                "item_name": name,
                "price": price
            }
        
        except Exception as e:
            logger.debug(f"Error extracting product data: {e}")
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
            
            for product in products[:20]:  # Limit to first 20 products
                product_data = self.extract_product_data(product, "Woolworths")
                if product_data:
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
            
            for product in products[:20]:  # Limit to first 20 products
                product_data = self.extract_product_data(product, "Pak'nSave")
                if product_data:
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


def main():
    """Main execution function."""
    crawler = EggCrawler()
    
    try:
        # Crawl all websites
        results = crawler.crawl_all()
        
        # Save results to JSON
        output_file = crawler.save_to_json()
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Crawl Summary")
        print(f"{'='*60}")
        print(f"Total products found: {len(results)}")
        print(f"Results saved to: {output_file}")
        print(f"\nSample results:")
        for i, product in enumerate(results[:5], 1):
            print(f"{i}. {product['item_name']} - {product['price']} ({product['store']})")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}")
        raise


if __name__ == "__main__":
    main()

