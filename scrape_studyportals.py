import csv
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    print("Starting undetected-chromedriver...")
    # Add version_main=146 to fix the driver version mismatch with your local Chrome
    return uc.Chrome(options=options, version_main=146)

def get_soup(driver, url, wait_time=5):
    """Helper function to load a page and return its BeautifulSoup representation"""
    driver.get(url)
    time.sleep(wait_time) # Wait for Cloudflare/JS to render
    return BeautifulSoup(driver.page_source, 'html.parser')

def extract_program_links(soup, base_url):
    """LEVEL 3: Extract links pointing to individual program pages."""
    links = set()
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        # Depending on the specific portal, links might contain /studies/ or /study-programme/
        if '/studies/' in href or '/study-programme/' in href:
            links.add(urljoin(base_url, href))
    return list(links)

def scrape_program_details(driver, course_url):
    """LEVEL 3/4: Visit Program Page (Course) and extract structured fields."""
    print(f"  -> [SCRAPING] Details from {course_url}...")
    soup = get_soup(driver, course_url, wait_time=5)
    
    data = {
        'URL': course_url,
        'Course': 'N/A',
        'Degree': 'N/A',
        'University': 'N/A',
        'Tuition Fee': 'N/A',
        'City': 'N/A',
        'Country': 'N/A',
        'Duration': 'N/A',
    }
    
    try:
        # Course Title and University
        h1 = soup.find('h1')
        if h1:
            study_title = h1.find(class_='StudyTitle')
            if study_title:
                # the a tag usually contains the actual title
                a_tag = study_title.find('a', title=True)
                if a_tag:
                    data['Course'] = a_tag['title']
                else:
                    data['Course'] = study_title.get_text(separator=' ', strip=True).split(maxsplit=1)[0] if study_title.get_text(strip=True).count(study_title.get_text(strip=True)[:10]) > 1 else study_title.get_text(strip=True)
            else:
                data['Course'] = h1.get_text(strip=True)
                
            org_name = h1.find(class_='OrganisationName')
            if org_name:
                data['University'] = org_name.get_text(strip=True)
            
        # Infer Degree from URL or Title
        title_lower = data['Course'].lower()
        if 'bachelor' in title_lower or 'bsc' in title_lower or 'ba ' in title_lower:
            data['Degree'] = 'Bachelor'
        elif 'master' in title_lower or 'msc' in title_lower or 'ma ' in title_lower:
            data['Degree'] = 'Master'
        elif 'phd' in title_lower or 'doctor' in title_lower:
            data['Degree'] = 'PhD'
        elif 'bachelorsportal' in course_url or '/bachelor' in course_url:
            data['Degree'] = 'Bachelor'

        # University extraction based on general class matching if missing
        if data['University'] == 'N/A':
            uni_elem = soup.find(class_=lambda x: x and 'university' in x.lower())
            if uni_elem:
                 data['University'] = uni_elem.get_text(strip=True)
             
        # Robust Full-text scan for dynamic details (Fees, Duration, Location)
        all_text_blocks = list(soup.stripped_strings)
        for i, text in enumerate(all_text_blocks):
            lower_text = text.lower()
            
            # Find Tuition Fees
            if lower_text in ['tuition fee', 'tuition fees'] and data['Tuition Fee'] == 'N/A':
                # Grab next few tokens looking for a valid fee amount
                candidates = all_text_blocks[i+1 : i+6]
                fee_string = " ".join(candidates[:3]) # e.g. "4,510,613 NPR / year"
                if '/' in fee_string or any(char.isdigit() for char in fee_string) or any(c in fee_string for c in ['€', '$', '£']):
                    data['Tuition Fee'] = fee_string.replace('\xa0', ' ')
            
            # Find Duration
            if lower_text == 'duration' and data['Duration'] == 'N/A':
                # e.g., "3 years" or "Full-time 36 months"
                candidates = all_text_blocks[i+1 : i+3]
                if 'year' in candidates[0].lower() or 'month' in candidates[0].lower() or 'day' in candidates[0].lower():
                    data['Duration'] = candidates[0].replace('\xa0', ' ')
                elif len(candidates) > 1 and ('year' in candidates[1].lower() or 'month' in candidates[1].lower()):
                    data['Duration'] = f"{candidates[0]} {candidates[1]}".replace('\xa0', ' ')

            # Find Location
            if lower_text == 'campus location':
                loc_string = all_text_blocks[i+1]
                # Could be "Adelaide, Australia" or "1 cities in Australia"
                if ',' in loc_string:
                    parts = loc_string.split(',')
                    data['City'] = parts[0].strip()
                    data['Country'] = parts[-1].strip()
                elif ' in ' in loc_string:
                    data['Country'] = loc_string.split(' in ')[-1].strip()
                else:
                    data['Country'] = loc_string
    except Exception as e:
        print(f"Error parsing details: {e}")
        
    return data

def main():
    output_file = 'studyportals_programs_data_50_150.csv'
    
    # -------------------------
    # SCRAPING FLOW CONFIGURED
    # -------------------------
    # LEVEL 1: Start -> Search Page
    base_portal_url = "https://www.bachelorsportal.com"
    search_base_url = f"{base_portal_url}/search/bachelor"
    
    driver = setup_driver()
    all_extracted_data = []
    
    # Increased limits to scrape all available data. 
    # Change max_pages_to_scrape if you want to scrape fewer pages.
    # Note: A full scrape of thousands of pages will take a significant amount of time.
    start_page = 1
    end_page = 150
    # We no longer limit links_to_scrape, will scrape all valid programs found per page
    
    try:
        # LEVEL 2: Loop -> Pagination
        for page_num in range(start_page, end_page + 1):
            page_url = f"{search_base_url}?page={page_num}"
            print(f"\n[LEVEL 1 & 2] Navigating to Search Page {page_num}: {page_url}")
            
            soup = get_soup(driver, page_url, wait_time=8)
            
            # LEVEL 3: Extract -> Program Links
            program_links = extract_program_links(soup, base_portal_url)
            print(f"Found {len(program_links)} program links on page {page_num}.")
            
            # Stop if no more programs are found on the search page (end of pagination)
            if not program_links:
                print("No more program links found. Reached the end of available results.")
                break
            
            # Scrape ALL links found on this page
            for link in program_links:
                details = scrape_program_details(driver, link)
                all_extracted_data.append(details)
                print(f"    [SAVED] {details['Course']} | {details['University']} | {details['Tuition Fee']}")
                
            # Periodically write to the file to save progress during a long scrape
            if all_extracted_data:
                keys = all_extracted_data[0].keys()
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    dict_writer = csv.DictWriter(f, fieldnames=keys)
                    dict_writer.writeheader()
                    dict_writer.writerows(all_extracted_data)
                
        print(f"\n[SUCCESS] Pipeline complete. Saved {len(all_extracted_data)} courses to {output_file}.")
    
    except Exception as e:
        print(f"\n[ERROR] Scraping stopped unexpectedly: {e}")
        # Save whatever we have collected so far on error
        if all_extracted_data:
            keys = all_extracted_data[0].keys()
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(all_extracted_data)
            print(f"Saved {len(all_extracted_data)} courses before exiting.")
            
    finally:
        try:
            driver.quit()
        except Exception:
            pass # Ignore the WinError 6 handle invalid on script shutdown

if __name__ == "__main__":
    main()
