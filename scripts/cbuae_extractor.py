import time
import sys
import json
import csv
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

def setup_chrome_driver():
    """Configure ChromeDriver with robust options"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            return driver
        except Exception as e:
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                return driver
            except:
                return None
        
    except ImportError:
        print("ERROR: Selenium not installed")
        return None

def is_valid_rate(text):
    """Check if text is a valid exchange rate number"""
    try:
        clean_text = text.replace(' ', '').replace(',', '')
        rate = float(clean_text)
        return 0.0000001 <= rate <= 100.0
    except:
        return False

def extract_exchange_rates(target_currencies):
    """
    Extract exchange rates from CBUAE website
    
    Args:
        target_currencies: List of currency names to extract
        
    Returns:
        Dictionary of currency -> rate mappings, or None if failed
    """
    
    driver = setup_chrome_driver()
    if not driver:
        print("ERROR: ChromeDriver not available")
        return None
    
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        driver.get('https://www.centralbank.ae/en/forex-eibor/exchange-rates/')
        
        wait = WebDriverWait(driver, 20)
        time.sleep(3)
        
        # Accept cookies disclaimer if present
        try:
            agree_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Agree and continue")))
            agree_button.click()
            time.sleep(3)
            print("INFO: Disclaimer accepted")
        except:
            print("INFO: Disclaimer already accepted or not present")
        
        # Find exchange rates table
        table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        rows = table.find_elements(By.TAG_NAME, "tr")
        
        found_currencies = {}
        
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                
                if len(cells) >= 2:
                    all_texts = [cell.text.strip() for cell in cells]
                    
                    if i < 5:
                        print(f"DEBUG: Row {i}: {all_texts}")
                    
                    currency_found = None
                    rate_found = None
                    
                    for text in all_texts:
                        for target in target_currencies:
                            if target.lower() in text.lower():
                                currency_found = text
                                break
                        if currency_found:
                            break
                    
                    if currency_found:
                        for text in all_texts:
                            if is_valid_rate(text):
                                rate_found = text
                                break
                    
                    if currency_found and rate_found:
                        found_currencies[currency_found] = rate_found
                            
            except Exception as e:
                continue
        
        return found_currencies if found_currencies else None
        
    except Exception as e:
        print(f"ERROR: Extraction failed: {e}")
        return None
        
    finally:
        driver.quit()

def save_to_csv(data, filename="latest_rates.csv"):
    """Save exchange rate data to CSV format"""
    try:
        # Create data directory
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        filepath = data_dir / filename
        
        if isinstance(data, dict):
            csv_data = []
            timestamp = datetime.now(timezone.utc).isoformat()
            for currency, rate in data.items():
                csv_data.append({
                    'currency': currency,
                    'rate': rate,
                    'rate_float': float(rate),
                    'extraction_timestamp': timestamp,
                    'extraction_method': 'selenium_simple'
                })
        else:
            csv_data = data
        
        # Write CSV
        if csv_data:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = csv_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)
        
        print(f"SUCCESS: CSV saved to {filepath}")
        return str(filepath)
        
    except Exception as e:
        print(f"ERROR: Failed to save CSV: {e}")
        return None

def save_to_json(data, filename="latest_rates.json"):
    """Save exchange rate data to JSON format"""
    try:
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        filepath = data_dir / filename
        
        # Convert dict to list of dicts for JSON
        if isinstance(data, dict):
            json_data = []
            timestamp = datetime.now(timezone.utc).isoformat()
            for currency, rate in data.items():
                json_data.append({
                    'currency': currency,
                    'rate': rate,
                    'rate_float': float(rate),
                    'extraction_timestamp': timestamp,
                    'extraction_method': 'selenium_simple'
                })
        else:
            json_data = data
        
        # Write JSON
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(json_data, jsonfile, indent=2, ensure_ascii=False)
        
        print(f"SUCCESS: JSON saved to {filepath}")
        return str(filepath)
        
    except Exception as e:
        print(f"ERROR: Failed to save JSON: {e}")
        return None

def save_metadata(data, extraction_stats):
    """Save extraction metadata"""
    try:
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        metadata = {
            "last_extraction": datetime.now(timezone.utc).isoformat(),
            "extraction_method": "selenium_simple",
            "currencies_extracted": len(data) if data else 0,
            "extraction_duration_seconds": extraction_stats.get('duration', 0),
            "success": len(data) > 0 if data else False,
            "source_url": "https://www.centralbank.ae/en/forex-eibor/exchange-rates/",
            "extractor_version": "1.0.0",
            "target_currencies": extraction_stats.get('target_currencies', []),
            "notes": f"Extracted {len(data)} currencies successfully" if data else "Extraction failed"
        }
        
        filepath = data_dir / "metadata.json"
        
        with open(filepath, 'w', encoding='utf-8') as metafile:
            json.dump(metadata, metafile, indent=2, ensure_ascii=False)
        
        print(f"SUCCESS: Metadata saved to {filepath}")
        return str(filepath)
        
    except Exception as e:
        print(f"ERROR: Failed to save metadata: {e}")
        return None

def commit_and_push():
    """Commit changes and push to GitHub"""
    try:
        result = subprocess.run(['git', 'status'], capture_output=True, text=True)
        if result.returncode != 0:
            print("ERROR: Not in a Git repository. Run 'git init' and configure remote.")
            return False
        
        # Add files
        result = subprocess.run(['git', 'add', 'data/'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: Git add failed: {result.stderr}")
            return False
        
        # Commit
        commit_message = f"Update CBUAE rates - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        result = subprocess.run(['git', 'commit', '-m', commit_message], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            if "nothing to commit" in result.stdout:
                print("INFO: No changes to commit")
                return True
            else:
                print(f"ERROR: Git commit failed: {result.stderr}")
                return False
        
        print(f"SUCCESS: Committed changes: {commit_message}")
        
        # Push
        result = subprocess.run(['git', 'push'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("SUCCESS: Changes pushed to GitHub")
            return True
        else:
            print(f"ERROR: Git push failed: {result.stderr}")
            print("HINT: Check if remote is configured and you have push access")
            return False
            
    except Exception as e:
        print(f"ERROR: Git operation failed: {e}")
        return False

def main():
    """Main extraction function"""
    
    # Configure target currencies
    target_currencies = [
        'US Dollar',
        'Euro',
        'GB Pound', 
        'Japanese Yen',
        'Swiss Franc',
        'Canadian Dollar',
        'Brazilian Real',
        'Australian Dollar',
        'Singapore Dollar',
        'Chinese Yuan'
    ]
    
    print(f"INFO: Target currencies: {', '.join(target_currencies)}")
    
    # Record start time
    start_time = time.time()
    
    # Extract exchange rates
    print("INFO: Starting extraction...")
    extracted_data = extract_exchange_rates(target_currencies)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Prepare extraction statistics
    extraction_stats = {
        'duration': round(duration, 2),
        'target_currencies': target_currencies,
        'start_time': start_time
    }

    
    if extracted_data:
        print(f"SUCCESS: Extracted {len(extracted_data)} currencies")
        print(f"DURATION: {duration:.2f} seconds")
        print(f"TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        for currency, rate in extracted_data.items():
            print(f"  {currency}: {rate} AED")
        
        print("\nINFO: Saving data files...")
        
        # Save data files
        csv_saved = save_to_csv(extracted_data, "latest_rates.csv")
        json_saved = save_to_json(extracted_data, "latest_rates.json")
        
        # Save historical file
        today = datetime.now().strftime('%Y-%m-%d')
        historical_saved = save_to_csv(extracted_data, f"{today}_rates.csv")
        
        # Save metadata
        metadata_saved = save_metadata(extracted_data, extraction_stats)
        
        # Commit and push to GitHub
        if csv_saved and json_saved:
            print("\nINFO: Pushing to GitHub...")
            git_success = commit_and_push()
            
            if git_success:
                print("\nSUCCESS: Complete pipeline executed successfully")
                print("CSV URL: https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/data/latest_rates.csv")
            else:
                print("\nWARNING: Extraction successful but Git push failed")
                print("HINT: Verify Git repository configuration")
        
    else:
        print("ERROR: Extraction failed")
        
        # Save error metadata
        save_metadata(None, extraction_stats)
    

if __name__ == "__main__":
    main()
