from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
from selenium.webdriver.chrome.options import Options
import logging
import json
import time
from selenium.common.exceptions import TimeoutException
from translate import translate_to_english, is_japanese_text

def init_driver():
    options = Options()
    options.add_argument("--log-level=3")  # 3 = FATAL only, hides SSL warnings
    # Alternatively, disable logging switches:
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.page_load_strategy = "eager"
    # options.headless = True
    options.add_argument("--headless")
    # options.add_argument("--disable-gpu")
    # options.add_argument("--no-sandbox")
    # options.add_argument("--disable-dev-shm-usage")
    # options.add_argument("--disable-web-security")
    # options.add_argument("--disable-extensions")

    driver = webdriver.Chrome(service=Service(), options=options)

    # Set page load timeout (max seconds to wait for driver.get())
    driver.set_page_load_timeout(30000)  # e.g., 5 minutes :contentReference[oaicite:2]{index=2}

    # If you're using Selenium's internal HTTP calls:
    # try:
    #     driver.command_executor.set_timeout(30000)
    # except AttributeError:
    #     driver.command_executor._client_config._timeout = 30000  # fallback

    return driver

def login(driver, email, password):
    logging.info("Navigating to login page...")
    print("Navigating to login page...")
    driver.get("https://www.lancers.jp/user/login?ref=header_menu")

    # Fill in email and password
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "UserEmail"))
    ).send_keys(email)

    driver.find_element(By.ID, "UserPassword").send_keys(password)
    driver.find_element(By.ID, "form_submit").click()

    # Wait for URL to change to mypage
    try:
        WebDriverWait(driver, 10).until(
            lambda d: d.current_url.startswith("https://www.lancers.jp/mypage")
        )
        logging.info("✅ Login successful.")
        print("✅ Login successful.")
    except:
        logging.error("❌ Login failed or took too long.")
        print("❌ Login failed or took too long.")
        raise


def get_lancers_jobs(driver, url, dtype):
    print(f"Getting {dtype} jobs from Lancers...")
    try:
        driver.get(url)
    except TimeoutException:
        print("⚠️ Job list page load exceeded timeout, proceeding by stopping load.")
        driver.execute_script("window.stop();")

    # Wait for either job listings or no results message
    try:
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".p-search-job-medias--lancer, .p-search-job-media"))
        )
    except TimeoutException:
        print("No jobs found or page failed to load")
        return []

    jobs = []
    for card in driver.find_elements(By.CSS_SELECTOR, ".p-search-job-media.c-media.c-media--item "):
        onclick_str = card.get_attribute("onclick")
        match = None  # Initialize match variable
        if onclick_str:
            match = re.search(r"goToLjpWorkDetail\((\d+)\)", onclick_str)            
            
        if not match:
            continue

        jid = match.group(1)

        title_element = card.find_element(By.CSS_SELECTOR, ".p-search-job-media__title.c-media__title")

        title_text = title_element.get_attribute("textContent").strip()
        # Remove known tag texts if necessary (optional cleanup)
        title_lines = [line.strip() for line in title_text.split('\n') if line.strip()]
        title = title_lines[-1]  # Usually the actual title is last

        job_type = card.find_element(By.CSS_SELECTOR, ".c-badge__text").text.strip()

        # Get price range
        price_element = card.find_element(By.CSS_SELECTOR, ".p-search-job-media__price")
        price_numbers = price_element.find_elements(By.CSS_SELECTOR, ".p-search-job-media__number")
        if len(price_numbers) == 2:
            price_min = price_numbers[0].text.strip()
            price_max = price_numbers[1].text.strip()
            price_range = f"{price_min} ~ {price_max}"
        else:
            price_range = price_numbers[0].text.strip() if price_numbers else "N/A"
        
        link = f"https://www.lancers.jp/work/detail/{jid}"
        # link = card.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
        if(job_type != "求人" and job_type != "コンペ"):
            jobs.append({"dtype": dtype, "id": jid, "type": job_type, "title": title, "price": price_range, "url": link})
        else:
            continue
    print(f"Found {len(jobs)} {dtype} jobs from Lancers.")
    return jobs

def get_cw_jobs(driver, url, dtype):
    print(f"Getting {dtype} jobs from Crowdworks...")
    try:
        driver.get(url)
    except TimeoutException:
        print("⚠️ Job list page load exceeded timeout, proceeding by stopping load.")
        driver.execute_script("window.stop();")

    # Wait for the vue-container to be present with better error handling
    try:
        # Wait for vue-container element to appear
        container = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "vue-container"))
        )
    except TimeoutException:
        print(f"⚠️ Timeout waiting for Crowdworks page to load for {dtype}. Skipping this source.")
        return []
    except Exception as e:
        print(f"⚠️ Error waiting for Crowdworks page elements for {dtype}: {e}. Skipping this source.")
        return []

    # Try to find the vue-container element and wait for data attribute
    try:
        
        # Wait for data attribute to be populated (JavaScript may need time to set it)
        data_json = None
        for attempt in range(5):  # Try up to 5 times with 2 second delays
            data_json = container.get_attribute("data")
            if data_json and data_json.strip():
                break
            time.sleep(2)  # Wait 2 seconds before retrying
            container = driver.find_element(By.ID, "vue-container")  # Refresh element reference
        
        if not data_json or not data_json.strip():
            print(f"⚠️ No data attribute found in vue-container for {dtype} after waiting. Skipping this source.")
            return []
        
        data = json.loads(data_json)
    except Exception as e:
        print(f"⚠️ Error parsing Crowdworks data for {dtype}: {e}. Skipping this source.")
        return []

    # Safely extract job offers
    try:
        if "searchResult" not in data or "job_offers" not in data["searchResult"]:
            print(f"⚠️ No job_offers found in Crowdworks data for {dtype}. Skipping this source.")
            return []
        job_offers = data["searchResult"]["job_offers"]
    except Exception as e:
        print(f"⚠️ Error extracting job offers for {dtype}: {e}. Skipping this source.")
        return []

    jobs = []
    for offer in job_offers:
        try:
            job = offer["job_offer"]
            job_id = job["id"]
            title = job["title"]
            # Payment info
            payment = offer.get("payment", {})
            price_range = "discuss"
            if "fixed_price_payment" in payment:
                min_budget = payment["fixed_price_payment"].get("min_budget")
                max_budget = payment["fixed_price_payment"].get("max_budget")
                if min_budget and max_budget:
                    price_range = f"{int(min_budget)} ~ {int(max_budget)}"
                elif max_budget:
                    price_range = f"{int(max_budget)}"
            elif "hourly_payment" in payment:
                min_wage = payment["hourly_payment"].get("min_hourly_wage")
                max_wage = payment["hourly_payment"].get("max_hourly_wage")
                if min_wage and max_wage:
                    price_range = f"{int(min_wage)} ~ {int(max_wage)} (hourly)"
                elif max_wage:
                    price_range = f"{int(max_wage)} (hourly)"
            link = f"https://crowdworks.jp/public/jobs/{job_id}"
            jobs.append({
                "dtype": dtype,
                "id": job_id,
                "type": "not_specified",
                "title": title,
                "price": price_range,
                "url": link
            })
        except Exception as e:
            print(f"⚠️ Error processing individual job offer for {dtype}: {e}. Skipping this job.")
            continue
    
    print(f"Found {len(jobs)} {dtype} jobs from Crowdworks.")
    return jobs

def get_description(driver, url):
    try:
        driver.get(url)
    except TimeoutException:
        print("⚠️ Job description page load exceeded timeout, proceeding by stopping load.")
        driver.execute_script("window.stop();")

    # Get job description text
    description_element = WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".p-work-detail-lancer__postscript-description"))
    )
    description_text = description_element.get_attribute("textContent").strip()

    # Get apply URL
    apply_element = WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='propose_start']"))
    )
    apply_url = apply_element.get_attribute("href")
    
    # Generate proposal using the job info and description
    job_info = { 
        "description": description_text,
        "apply_url": apply_url
    }

    return job_info
    # proposal_text = generate_proposal(job_info)
    # # Replace selectors as needed
    # driver.find_element(By.NAME, "proposal").send_keys(proposal_text)
    # driver.find_element(By.NAME, "price").send_keys(price)
    # driver.find_element(By.NAME, "deadline").send_keys(deadline)
    # driver.find_element(By.CSS_SELECTOR, "button.send-bid").click()

def submit_bid(driver, url, proposal):
    driver.get(url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[name='proposal']")))
    driver.find_element(By.CSS_SELECTOR, "textarea[name='proposal']").send_keys(proposal)
    driver.find_element(By.CSS_SELECTOR, "button.send-bid").click()


