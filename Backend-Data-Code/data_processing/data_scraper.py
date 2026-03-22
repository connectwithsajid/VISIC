import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import settings
from data_processing.data_writer import save_council_file


BASE_URL = settings.BASE_URL
PAGE_URL = settings.PAGE_URL
HEADERS = {"User-Agent": settings.USER_AGENT}
REQUEST_DELAY = float(getattr(settings, "REQUEST_DELAY", 1.5))


def normalize(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_text_by_label(soup, label_text):
    label = soup.find(
        lambda tag: hasattr(tag, "get_text")
        and normalize(tag.get_text()) == label_text
        and tag.get("class") == ["reclabel"]
    )

    if not label:
        return ""

    value = label.find_next_sibling("div", class_="rectext")
    if value:
        return normalize(value.get_text(" ", strip=True))

    return ""


def parse_main_fields(soup):
    data = {}

    data["title"] = get_text_by_label(soup, "Title")
    data["start_date"] = get_text_by_label(soup, "Date Received / Introduced")
    data["last_changed_date"] = get_text_by_label(soup, "Last Changed Date")
    data["end_date"] = get_text_by_label(soup, "Expiration Date")
    data["council_district"] = get_text_by_label(soup, "Council District")
    data["council_member_mover"] = get_text_by_label(soup, "Mover")
    data["second_council_member"] = get_text_by_label(soup, "Second")
    data["mover_seconder_comment"] = get_text_by_label(soup, "Mover/Seconder Comment")

    ref_label = soup.find(
        lambda tag: hasattr(tag, "get_text")
        and normalize(tag.get_text()) == "Reference Numbers"
        and tag.get("class") == ["reclabel"]
    )

    if ref_label:
        ref_value = ref_label.find_next_sibling("div", class_="rectext")
        data["reference_numbers"] = normalize(ref_value.get_text(" ", strip=True)) if ref_value else ""
    else:
        data["reference_numbers"] = ""

    return data


def extract_showtip_id(img_tag):
    if not img_tag or not img_tag.has_attr("onclick"):
        return ""

    match = re.search(r"TagToTip\('([^']+)'", img_tag["onclick"])
    return match.group(1) if match else ""


def extract_doc_from_showtip(soup, showtip_id):
    if not showtip_id:
        return {"doc_title": "", "doc_url": "", "doc_date": ""}

    tip_div = soup.find("div", id=showtip_id)
    if not tip_div:
        return {"doc_title": "", "doc_url": "", "doc_date": ""}

    link = tip_div.find("a", href=True)
    if not link:
        return {"doc_title": "", "doc_url": "", "doc_date": ""}

    tr = link.find_parent("tr")
    tds = tr.find_all("td") if tr else []

    doc_title = normalize(link.get_text(" ", strip=True))
    doc_url = urljoin(BASE_URL, link["href"])
    doc_date = normalize(tds[1].get_text(" ", strip=True)) if len(tds) > 1 else ""

    return {
        "doc_title": doc_title,
        "doc_url": doc_url,
        "doc_date": doc_date,
    }


def parse_file_activities(soup):
    activities = []

    label_div = soup.find(
        "div",
        class_="reclabel",
        string=lambda s: s and normalize(s) == "File Activities",
    )

    if label_div:
        table = label_div.find_next("table", class_="inscrolltbl")
    else:
        table = soup.find("table", class_="inscrolltbl")

    if not table:
        return activities

    for tr in table.find_all("tr"):
        if tr.find("th"):
            continue

        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        activity_date = normalize(tds[0].get_text(" ", strip=True))
        activity_text = normalize(tds[1].get_text(" ", strip=True))

        img = tds[2].find("img") if len(tds) > 2 else None
        icon_src = urljoin(BASE_URL, img["src"]) if img and img.has_attr("src") else ""
        showtip_id = extract_showtip_id(img)
        doc_info = extract_doc_from_showtip(soup, showtip_id)

        if not activity_date and not activity_text:
            continue

        activities.append(
            {
                "date": activity_date,
                "activity": activity_text,
                "icon_src": icon_src,
                "showtip_id": showtip_id,
                "doc_title": doc_info["doc_title"],
                "doc_url": doc_info["doc_url"],
                "doc_date": doc_info["doc_date"],
            }
        )

    return activities


def parse_online_documents(soup):
    documents = []

    online_docs_section = soup.find("div", id="CFI_OnlineDocsContent")
    if not online_docs_section:
        return documents

    rows = online_docs_section.find_all("tr")
    for tr in rows:
        if tr.find("th"):
            continue

        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        link = tds[0].find("a", href=True)
        if not link:
            continue

        title = normalize(link.get_text(" ", strip=True))
        url = urljoin(BASE_URL, link["href"])
        doc_date = normalize(tds[1].get_text(" ", strip=True))

        documents.append(
            {
                "text": title,
                "url": url,
                "date": doc_date,
            }
        )

    return documents

def parse_vote_info(soup):
    vote_info = {}

    vote_section = soup.find("div", id="CFI_VotesContent")
    if not vote_section:
        return vote_info

    rows = vote_section.find_all("tr")
    for row in rows:
        tds = row.find_all("td")
        if len(tds) != 2:
            continue

        label = normalize(tds[0].get_text(" ", strip=True)).rstrip(":")
        value = normalize(tds[1].get_text(" ", strip=True))

        if label:
            vote_info[label] = value

    return vote_info


def parse_vote_members(soup):
    members = []

    vote_section = soup.find("div", id="CFI_VotesContent")
    if not vote_section:
        return members

    tables = vote_section.find_all("table", class_="inscrolltbl")
    if not tables:
        return members

    member_table = tables[-1]

    for tr in member_table.find_all("tr"):
        if tr.find("th"):
            continue

        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        members.append(
            {
                "member_name": normalize(tds[0].get_text(" ", strip=True)),
                "cd": normalize(tds[1].get_text(" ", strip=True)),
                "vote": normalize(tds[2].get_text(" ", strip=True)),
            }
        )

    return members



def parse_project_movers(soup):
    movers = []

    mover_value = soup.find(
        lambda tag: hasattr(tag, "get_text")
        and normalize(tag.get_text()) == "Mover"
        and tag.get("class") == ["reclabel"]
    )

    if mover_value:
        mover_container = mover_value.find_next_sibling("div", class_="rectext")
        if mover_container:
            for div in mover_container.find_all("div"):
                name = normalize(div.get_text(" ", strip=True))
                if name:
                    movers.append({
                        "name": name,
                        "district": None,
                        "role": "primary",
                    })

    second_value = soup.find(
        lambda tag: hasattr(tag, "get_text")
        and normalize(tag.get_text()) == "Second"
        and tag.get("class") == ["reclabel"]
    )

    if second_value:
        second_container = second_value.find_next_sibling("div", class_="rectext")
        if second_container:
            for div in second_container.find_all("div"):
                name = normalize(div.get_text(" ", strip=True))
                if name:
                    movers.append({
                        "name": name,
                        "district": None,
                        "role": "secondary",
                    })

    return movers


def scrape_page(url):
    soup = get_soup(url)

    main = parse_main_fields(soup)
    main["file_activities"] = parse_file_activities(soup)
    main["attachments"] = parse_online_documents(soup)
    main["vote_info"] = parse_vote_info(soup)
    main["vote_members"] = parse_vote_members(soup)
    main["project_movers"] = parse_project_movers(soup)

    return main


def load_cf_list(path):
    seen = set()
    result = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            cf = line.strip()
            if not cf or cf.startswith("#"):
                continue
            if cf in seen:
                continue
            seen.add(cf)
            result.append(cf)

    return result


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cf_file_path = os.path.join(base_dir, "cf_list.txt")
    print("Looking for CF file at:", cf_file_path)

    cf_numbers = load_cf_list(cf_file_path)

    for cf_number in cf_numbers:
        print(f"Processing CF: {cf_number}")

        page_url = f"{PAGE_URL}{cf_number}"
        data = scrape_page(page_url)

        print("JSON data:", data)
        save_council_file(cf_number, data)

        print(f"Finished CF: {cf_number}")
        time.sleep(REQUEST_DELAY)


if __name__ == "__main__":
    main()