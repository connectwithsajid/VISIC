# requirements:
# pip install requests beautifulsoup4
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import csv
import time
from data_processing.data_writer import save_council_file
from config import settings


BASE_URL = settings.BASE_URL 
PAGE_URL = settings.PAGE_URL
HEADERS = { "User-Agent": settings.USER_AGENT }
# cf_number = "20-1533"


def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def text_after_label(soup, label_text):
    # finds an element containing the label_text and returns the next meaningful text
    lbl = soup.find(lambda tag: tag.get_text(strip=True) == label_text)
    if not lbl:
        return None
    # often the label is followed by a sibling or next element with the value
    for sib in lbl.next_siblings:
        if getattr(sib, "get_text", None):
            t = sib.get_text(strip=True)
            if t:
                return t
        elif isinstance(sib, str) and sib.strip():
            return sib.strip()
    # fallback: look for next element
    nxt = lbl.find_next()
    return nxt.get_text(strip=True) if nxt else None

def parse_main_fields(soup):
    data = {}
    # page uses visible headings like "Title", "Date Received / Introduced", etc.
    data['title'] = text_after_label(soup, "Title")
    data['start_date'] = text_after_label(soup, "Date Received / Introduced")
    data['last_changed_date'] = text_after_label(soup, "Last Changed Date")
    data['end_date'] = text_after_label(soup, "Expiration Date")
    # Some sections are multi-line; grab by heading text and accumulating lines until next heading
    # Grab the "Reference Numbers" block by locating that heading and collecting following lines
    ref_block = soup.find(lambda tag: tag.get_text(strip=True) == "Reference Numbers")
    if ref_block:
        # collect sibling text nodes until next heading (which is usually an empty heading)
        texts = []
        for s in ref_block.next_siblings:
            if getattr(s, "name", None) and s.name.lower().startswith('h'):  # stop at next heading
                break
            t = ""
            try:
                t = s.get_text(" ", strip=True)
            except Exception:
                t = str(s).strip()
            if t:
                texts.append(t)
        data['reference_numbers'] = " | ".join(texts).strip()
    # straightforward single-value labels
    data['council_district'] = text_after_label(soup, "Council District")
    data['council_member_mover'] = text_after_label(soup, "Mover")
    data['second_council_member'] = text_after_label(soup, "Second")
    data['mover_seconder_comment'] = text_after_label(soup, "Mover/Seconder Comment")
    return data

def parse_file_activities(soup):
    activities = []

    # 1) Find the 'File Activities' label div
    label_div = soup.find("div", class_="reclabel", string=lambda s: s and s.strip() == "File Activities")
    if label_div:
        # 2) The table is inside the next sibling container (or nearby). Search forwards for the table.
        table = label_div.find_next("table", class_="inscrolltbl")
    else:
        # fallback: find any table with that class
        table = soup.find("table", class_="inscrolltbl")

    if not table:
        # nothing found — return empty list
        return activities

    # 3) Iterate rows, skip header row(s)
    rows = table.find_all("tr")
    for tr in rows:
        # Skip header row (contains <th>)
        if tr.find("th"):
            continue
        tds = tr.find_all("td")
        if not tds:
            continue
        # Defensive extraction, strip whitespace
        date_text = tds[0].get_text(" ", strip=True) if len(tds) >= 1 else ""
        activity_text = tds[1].get_text(" ", strip=True) if len(tds) >= 2 else ""
        extra_text = tds[2].get_text(" ", strip=True) if len(tds) >= 3 else ""
        # Skip rows that are entirely empty
        if not (date_text or activity_text or extra_text):
            continue
        activities.append({
            "date": date_text,
            "activity": activity_text,
            "extra": extra_text
        })
    return activities

def parse_attachments(soup):
    attachments = []
    # attachments appear as links with descriptive text like "Report from City Administrative Officer"
    # find the section where links are present (look for an anchor near 'Report' / 'Attachment')
    for a in soup.find_all("a"):
        href = a.get('href') or a.get('onclick') or ""
        text = a.get_text(" ", strip=True)
        if text and ("Report" in text or "Attachment" in text or "Draft Ordinance" in text or text.startswith("Mayor") or text.startswith("Motion")):
            link = href
            if href and not href.startswith("http"):
                link = urljoin(BASE_URL, href)
            attachments.append({"text": text, "url": link})
    # also capture those inline "Click to view online docs" images by searching nearby img alt/title
    # dedupe
    seen = set()
    deduped = []
    for att in attachments:
        key = (att['text'], att['url'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(att)
    return deduped

def scrape_page(url):
    soup = get_soup(url)
    print("raw data", soup)
    main = parse_main_fields(soup)
    main['file_activities'] = parse_file_activities(soup)
    main['attachments'] = parse_attachments(soup)
    return main


def load_cf_list(path):
    seen = set()
    result = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            cf = line.strip()
            if not cf or cf.startswith("#"):
                continue
            if cf not in seen:
                seen.add(cf)
                result.append(cf)
    return result


def main():
    # Code to write data into CSV & DB
    # perform a single scrape + save; return the saved DB id
    # data = scrape_page(PAGE_URL)
    # import json
    # print(json.dumps(data, indent=2))

    # # ensure output dir exists
    # import os
    # os.makedirs("data", exist_ok=True)

    # # save CSV of attachments (same as before)
    # with open("data/cf_20-1533_attachments.csv", "w", newline="", encoding="utf-8") as f:
    #     writer = csv.DictWriter(f, fieldnames=["text","url"])
    #     writer.writeheader()
    #     for a in data['attachments']:
    #         writer.writerow(a)

    # # save to DB via data_writer
    # saved_id = save_council_file(cf_number, data)
    # print("Saved council file id:", saved_id)
    # return saved_id

    # ------------------------------
    import os
    os.makedirs("data", exist_ok=True)

    # Read CF numbers from file
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cf_file_path = os.path.join(BASE_DIR, "cf_list.txt")
    print("Looking for CF file at:", cf_file_path)
    
    # Need to dedup
    # with open(cf_file_path, "r") as f:
    #     cf_numbers = [line.strip() for line in f if line.strip()]

    cf_numbers = load_cf_list(cf_file_path)

    # page_url = f"{PAGE_URL}{cf_number}"
    for cf_number in cf_numbers:
        print(f"Processing CF: {cf_number}")

        page_url = f"{PAGE_URL}{cf_number}"
        data = scrape_page(page_url)

        print(f"JSON data : {data}")
        # Save to DB
        save_council_file(cf_number, data)

        print(f"Finished CF: {cf_number}")
        time.sleep(1.5)



if __name__ == "__main__":
       main()
       print("Done.")
    # data = scrape_page(PAGE_URL)
    # # quick print
    # import json
    # print(json.dumps(data, indent=2))
    # # save attachments list to CSV
    # with open("data/cf_20-1533_attachments.csv", "w", newline="", encoding="utf-8") as f:
    #     import csv
    #     writer = csv.DictWriter(f, fieldnames=["text","url"])
    #     writer.writeheader()
    #     for a in data['attachments']:
    #         writer.writerow(a)
    # saved_id = save_council_file(cf_number, data)
    
    # print("Saved council file id:", saved_id)
    