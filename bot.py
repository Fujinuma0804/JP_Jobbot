import os, time, json, schedule, logging, traceback
from browser import get_lancers_jobs, get_cw_jobs, get_description, submit_bid
from dotenv import load_dotenv
from browser import login
from notifySlack import notify_slack
from translate import translate_to_english, is_japanese_text
from update_sheet import update_google_sheet
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver import Chrome

TARGET_URLS_Lancers = {
    "Lancers_web":    "https://www.lancers.jp/work/search/web?open=1",
    "Lancers_system": "https://www.lancers.jp/work/search/system?open=1",
    "Lancers_AI":     "https://www.lancers.jp/work/search/system/ai?open=1",
    "Lancers_Android": "https://www.lancers.jp/work/search/system/smartphoneapp?open=1"
}

TARGET_URLS_CW = {
    "CW_web": "https://crowdworks.jp/public/jobs/search?category_id=230&order=new",
    "CW_system": "https://crowdworks.jp/public/jobs/search?category_id=226&order=new",
    "CW_AI": "https://crowdworks.jp/public/jobs/search?category_id=311&order=new",
    "CW_Android": "https://crowdworks.jp/public/jobs/search?category_id=242&order=new"
}

if not os.path.exists('seen.json'):
    with open('seen.json','w') as f: f.write('[]')

def load_seen():
    if not os.path.exists("seen.json"):
        return [] 

    with open("seen.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data  # adjust based on your structure
        except json.JSONDecodeError:
            return []  # fallback for empty or invalid JSON

def save_seen(data):
    with open("seen.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def job_check(driver, index):  
    print(f"{index} Checking for new jobs...")
    seen = load_seen()

    new = []
    # Get Lancers jobs with error handling
    for dtype, url in TARGET_URLS_Lancers.items():
        try:
            jobs = get_lancers_jobs(driver, url, dtype)
            new.extend(jobs)
        except Exception as e:
            print(f"⚠️ Error fetching {dtype} jobs: {e}")
            logging.error(f"⚠️ Error fetching {dtype} jobs: {e}")
            continue
    
    # Get Crowdworks jobs with error handling
    for dtype, url in TARGET_URLS_CW.items():
        try:
            jobs = get_cw_jobs(driver, url, dtype)
            new.extend(jobs)
        except Exception as e:
            print(f"⚠️ Error fetching {dtype} jobs: {e}")
            logging.error(f"⚠️ Error fetching {dtype} jobs: {e}")
            continue

    jobs_to_update = []  # Collect jobs to send to Google Sheets
    added_job_ids = set()  # Track job IDs to prevent duplicates

    for job in new:
        dtype, jid, job_type, title, price, url = job["dtype"], job["id"], job["type"], job["title"], job["price"], job["url"]

        if not any(item["id"] == jid for item in seen) and jid not in added_job_ids:
            if is_japanese_text(title):
                title = translate_to_english(title)
            print("✨NEW JOB✨")
            print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Type: {dtype}")
            print(f"ID: {jid}")
            print(f"Price: {price}")
            print(f"Job Type: {job_type}")
            print(f"Title: {title}")
            print(f"URL: {url}")
            print("-----------------------------------------------")
            
            notify_slack(dtype, price, title, url)

            # Add job to the list for Google Sheets
            jobs_to_update.append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "dtype": dtype,
                "url": url,
                "price": price,
                "title": title,
            })

            # Add job to the seen list
            seen.append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "dtype": dtype, 
                "id": jid, 
                "type": job_type,
                "title": title, 
                "url": url,
                "price": price,
            })

            # Mark this job ID as added
            added_job_ids.add(jid)

    # Save seen jobs
    save_seen(seen)

    # Update Google Sheets with new jobs (only send new ones, not all seen jobs)
    if jobs_to_update:
        print(f"Updating Google Sheets with {len(jobs_to_update)} jobs...")
        update_google_sheet(jobs_to_update)
    else:
        print("No new jobs to update in Google Sheets.")

    print(f"{index} checked")

def create_proxy_auth_extension(proxy_address, username, password):
    """
    Creates a Chrome extension for proxy authentication.
    """
    import zipfile
    import os

    # Extract host and port from proxy address
    proxy_host, proxy_port = proxy_address.split(":")

    # Manifest file for the Chrome extension
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Authentication",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """

    # Background script for the Chrome extension
    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{proxy_host}",
                port: parseInt("{proxy_port}")
            }},
            bypassList: ["localhost"]
        }}
    }};
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
    chrome.webRequest.onAuthRequired.addListener(
        function(details) {{
            return {{
                authCredentials: {{
                    username: "{username}",
                    password: "{password}"
                }}
            }};
        }},
        {{urls: ["<all_urls>"]}},
        ["blocking"]
    );
    """

    # Create the extension file
    plugin_file = "proxy_auth_plugin.zip"
    with zipfile.ZipFile(plugin_file, "w") as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)

    return plugin_file

def init_driver_with_proxy():
    """
    Initializes the Selenium WebDriver with proxy settings from the .env file.
    """
    # Load proxy details from .env
    proxy_address = os.getenv("proxy_address")
    proxy_username = os.getenv("proxy_username")
    proxy_password = os.getenv("proxy_password")

    if not proxy_address or not proxy_username or not proxy_password:
        raise ValueError("Proxy details are missing in the .env file.")

    # Chrome options
    chrome_options = ChromeOptions()
    chrome_options.add_argument(f"--proxy-server=http://{proxy_address}")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    # Add proxy authentication extension
    plugin_file = create_proxy_auth_extension(proxy_address, proxy_username, proxy_password)
    chrome_options.add_extension(plugin_file)

    # Initialize WebDriver
    driver = Chrome(options=chrome_options)
    return driver

def main():
    load_dotenv()
    # logging.basicConfig(filename='bidbot.log', level=logging.INFO, format='%(asctime)s %(message)s')

    try:
        driver = init_driver_with_proxy()  # Use the proxy-enabled driver
        login(driver, os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))

        index = [0]  # using a list to hold the mutable index

        def scheduled_job():
            try:
                job_check(driver, index)
                index[0] += 1  # increment after each run
            except Exception as e:
                print(f"❌ Error in scheduled job: {e}")
                traceback.print_exc()
                logging.error(f"❌ Error in scheduled job: {e}")
                driver.quit()
                os._exit(1)  # Force quit the program

        schedule.every(1).minutes.do(scheduled_job)

        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                logging.error(f"❌ Error in main loop: {e}")
                driver.quit()
                os._exit(1)  # Force quit the program
                
    except Exception as e:
        print(f"❌ Critical error in main: {e}")
        logging.error(f"❌ Critical error in main: {e}")
        if 'driver' in locals():
            driver.quit()
        os._exit(1)  # Force quit the program
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    main()