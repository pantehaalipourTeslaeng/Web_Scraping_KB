# supermicro_complete.py  ← ONLY RUN THIS ONE
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from urllib.parse import urljoin

BASE_URL = "https://portal.supermicro.com"
KB_HOME = f"{BASE_URL}/sites/IT/ITKnowledgeBase/SitePages/Home.aspx"
OUTPUT = "Supermicro_Complete_KB_2025.pdf"

# Chrome options
options = Options()
options.add_argument("--headless")           # Remove this line if you want to see the browser
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")

# PDF styles — NO CONFLICTS
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='CategoryHeader', fontSize=24, alignment=TA_CENTER, spaceAfter=40, textColor='#1e40af', fontName='Helvetica-Bold'))
styles.add(ParagraphStyle(name='ArticleTitle',   fontSize=15, spaceBefore=16, spaceAfter=8, leftIndent=20, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle(name='ArticleBody',    fontSize=10.5, leading=13, spaceAfter=10, leftIndent=40))
styles.add(ParagraphStyle(name='CodeBlock', fontName='Courier', fontSize=9, leftIndent=50, spaceBefore=5, spaceAfter=5))

def load_all_content(driver):
    while True:
        buttons = driver.find_elements(By.XPATH, "//a[contains(text(),'View all') or contains(text(),'Load more')] | //button[contains(text(),'Load')]")
        if not buttons:
            break
        for btn in buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(3)
            except:
                continue
        time.sleep(2)  # Additional wait after clicking all buttons in an iteration

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
all_articles = []

try:
    print("Opening Supermicro IT Knowledge Base...")
    driver.get(KB_HOME)
    time.sleep(12)
    load_all_content(driver)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    categories = []
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True)
        if text and 4 < len(text) < 90:
            url = urljoin(BASE_URL, a['href'])
            if '/sites/IT/ITKnowledgeBase/' in url and url not in [c['url'] for c in categories]:
                categories.append({"name": text, "url": url})

    print(f"\nFound {len(categories)} categories — starting full scrape...\n")

    for i, cat in enumerate(categories, 1):
        print(f"[{i}/{len(categories)}] {cat['name']}")
        driver.get(cat['url'])
        time.sleep(8)
        load_all_content(driver)

        page_soup = BeautifulSoup(driver.page_source, 'html.parser')
        article_links = set()

        for a in page_soup.find_all('a', href=True):
            title = a.get_text(strip=True)
            href = a['href']
            if href and ('DispForm.aspx?ID=' in href or '/SitePages/' in href) and title and len(title) > 8:
                full_url = urljoin(BASE_URL, href)
                article_links.add((title, full_url))

        print(f"    → {len(article_links)} articles in this category")

        for title, url in article_links:
            try:
                driver.get(url)
                time.sleep(3)
                load_all_content(driver)
                art = BeautifulSoup(driver.page_source, 'html.parser')
                main = art.find('div', id='DeltaPlaceHolderMain') or art.body
                content_parts = []
                for elem in main.find_all(['p', 'li', 'td', 'h1', 'h2', 'h3', 'h4', 'pre', 'code', 'ul', 'ol']):
                    text = elem.get_text(strip=True)
                    if len(text) > 10 and '©' not in text:
                        if elem.name in ['pre', 'code']:
                            content_parts.append(('code', text))
                        elif elem.name in ['ul', 'ol']:
                            items = [li.get_text(strip=True) for li in elem.find_all('li') if len(li.get_text(strip=True)) > 10]
                            content_parts.append(('list', items))
                        else:
                            content_parts.append(('text', text))
                if content_parts:
                    all_articles.append({
                        "category": cat["name"],
                        "title": title,
                        "content_parts": content_parts
                    })
            except:
                continue

        print(f"    Total collected: {len(all_articles)} articles\n")

    # Sort articles within categories
    from collections import defaultdict
    categorized_articles = defaultdict(list)
    for art in all_articles:
        categorized_articles[art["category"]].append(art)
    for cat in categorized_articles:
        categorized_articles[cat].sort(key=lambda x: x["title"])

    # Generate TOC
    toc = [Paragraph("Table of Contents", styles['CategoryHeader']), Spacer(1, 20)]
    for cat in sorted(categorized_articles.keys()):
        toc.append(Paragraph(cat, styles['ArticleTitle']))
        for art in categorized_articles[cat]:
            toc.append(Paragraph(art["title"], styles['ArticleBody']))
        toc.append(Spacer(1, 10))

    # === Generate PDF ===
    doc = SimpleDocTemplate(OUTPUT, pagesize=letter, topMargin=80, leftMargin=50, rightMargin=50)
    story = [
        Paragraph("Supermicro IT Knowledge Base — COMPLETE OFFLINE ARCHIVE", 
                  ParagraphStyle(name='Big', fontSize=30, alignment=TA_CENTER, spaceAfter=50, textColor='#1e40af')),
        Paragraph(f"Generated: {time.strftime('%Y-%m-%d %H:%M')} | {len(all_articles)} articles", styles['Normal']),
        PageBreak()
    ] + toc + [PageBreak()]

    for cat in sorted(categorized_articles.keys()):
        story.append(Paragraph(cat, styles['CategoryHeader']))
        story.append(Spacer(1, 30))
        for art in categorized_articles[cat]:
            article_content = [Paragraph(art["title"], styles['ArticleTitle'])]
            for part_type, content in art["content_parts"]:
                if part_type == 'text':
                    article_content.append(Paragraph(content.replace("\n", "<br/>"), styles['ArticleBody']))
                elif part_type == 'code':
                    article_content.append(Paragraph(content.replace("\n", "<br/>"), styles['CodeBlock']))
                elif part_type == 'list':
                    article_content.append(ListFlowable([ListItem(Paragraph(item, styles['ArticleBody'])) for item in content]))
            story.append(KeepTogether(article_content))
            story.append(Spacer(1, 16))
        story.append(PageBreak())

    doc.build(story)
    print(f"\nSUCCESS! Full PDF created: {OUTPUT}")
    print(f"   → {len(all_articles)} real articles saved")

finally:
    driver.quit()
    print("Browser closed.")
