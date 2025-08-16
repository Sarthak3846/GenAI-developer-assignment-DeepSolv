from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup
import json
import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse

app = FastAPI(title="Shopify Store Insights Fetcher")

class BrandInsights(BaseModel):
    website_url: str
    product_catalog: List[dict] = []
    hero_products: List[dict] = []
    privacy_policy: Optional[str] = None
    return_policy: Optional[str] = None
    faqs: List[dict] = []
    social_handles: dict = {}
    contact_details: dict = {}
    brand_context: Optional[str] = None
    important_links: dict = {}

class WebsiteRequest(BaseModel):
    website_url: HttpUrl

class ShopifyInsightsFetcher:
    def __init__(self):
        self.session = requests.Session()
        # basically we're pretending to be a real browser here so websites don't block us
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_insights(self, url: str) -> BrandInsights:
        try:
            # this checks if the website is actually working first
            response = self.session.get(url, timeout=10)
            if response.status_code == 404:
                raise HTTPException(status_code=401, detail="Website not found")
            response.raise_for_status()
            
            insights = BrandInsights(website_url=url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # now let's grab all the important stuff from the store
            insights.product_catalog = self._get_product_catalog(url)
            
            # this gets the featured products from the main page
            insights.hero_products = self._get_hero_products(soup)
            
            # finding those policy pages
            insights.privacy_policy = self._get_policy_link(soup, url, 'privacy')
            insights.return_policy = self._get_policy_link(soup, url, 'return')
            
            # digging for FAQs
            insights.faqs = self._get_faqs(soup, url)
            
            # social media 
            insights.social_handles = self._get_social_handles(soup)
            
            # finding ways to contact them
            insights.contact_details = self._get_contact_details(soup)
            
            # what's this brand about?
            insights.brand_context = self._get_brand_context(soup)
            
            # other useful links we can find
            insights.important_links = self._get_important_links(soup, url)
            
            return insights
            
        except requests.exceptions.RequestException:
            raise HTTPException(status_code=500, detail="Error fetching website data")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def _get_product_catalog(self, url: str) -> List[dict]:
        try:
            # mostly every shopify store has /products.json
            products_url = urljoin(url, '/products.json')
            response = self.session.get(products_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                products = []
                for product in data.get('products', []):
                    # just grabbing the basic stuff we need from each product
                    products.append({
                        'id': product.get('id'),
                        'title': product.get('title'),
                        'handle': product.get('handle'),
                        'product_type': product.get('product_type'),
                        'vendor': product.get('vendor'),
                        'tags': product.get('tags', '').split(',') if product.get('tags') else []
                    })
                return products
        except:
            # if something goes wrong, just return empty list
            pass
        return []
    
    def _get_hero_products(self, soup: BeautifulSoup) -> List[dict]:
        hero_products = []
        # we're looking for common ways shopify sites display products on their homepage
        product_selectors = [
            '.product-item', '.product-card', '.featured-product',
            '[data-product-id]', '.product', '.grid-product__content'
        ]
        
        for selector in product_selectors:
            products = soup.select(selector)
            if products:
                # let's grab the first few products we find
                for product in products[:5]:
                    title_elem = product.find(['h2', 'h3', 'h4', '.product-title'])
                    if title_elem:
                        hero_products.append({
                            'title': title_elem.get_text(strip=True),
                            'selector_used': selector
                        })
                break  # once we find products with one selector, we're done
        return hero_products
    
    def _get_policy_link(self, soup: BeautifulSoup, base_url: str, policy_type: str) -> Optional[str]:
        # this will hunt for policy links on the page
        keywords = {
            'privacy': ['privacy', 'privacy policy'],
            'return': ['return', 'refund', 'return policy', 'refund policy']
        }
        
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True).lower()
            href = link['href'].lower()
            
            # basically checking if any of our keywords match the link text or URL
            for keyword in keywords.get(policy_type, []):
                if keyword in link_text or keyword in href:
                    return urljoin(base_url, link['href'])
        return None
    
    def _get_faqs(self, soup: BeautifulSoup, base_url: str) -> List[dict]:
        faqs = []
        
        # first let's see if there's a dedicated FAQ page
        faq_link = None
        for link in soup.find_all('a', href=True):
            if 'faq' in link.get_text(strip=True).lower() or 'faq' in link['href'].lower():
                faq_link = urljoin(base_url, link['href'])
                break
        
        # if we find an FAQ page, let's scrape it
        if faq_link:
            try:
                faq_response = self.session.get(faq_link, timeout=10)
                faq_soup = BeautifulSoup(faq_response.content, 'html.parser')
                
                # this looks for common FAQ patterns on the page
                qa_pairs = faq_soup.find_all(['details', '.faq-item', '.accordion-item'])
                for qa in qa_pairs[:5]:  # just grab the first 5 so we don't go crazy
                    question = qa.find(['summary', '.question', 'h3', 'h4'])
                    answer = qa.find(['.answer', '.content', 'p'])
                    if question and answer:
                        faqs.append({
                            'question': question.get_text(strip=True),
                            'answer': answer.get_text(strip=True)[:200] + '...'  # keep it short
                        })
            except:
                # if something breaks, just move on
                pass
        
        return faqs
    
    def _get_social_handles(self, soup: BeautifulSoup) -> dict:
        social_handles = {}
        # these patterns will help us extract usernames from social media URLs
        social_patterns = {
            'instagram': r'instagram\.com/([^/\s?]+)',
            'facebook': r'facebook\.com/([^/\s?]+)',
            'twitter': r'twitter\.com/([^/\s?]+)',
            'tiktok': r'tiktok\.com/@([^/\s?]+)'
        }
        
        # basically going through all links and seeing if any are social media
        for link in soup.find_all('a', href=True):
            href = link['href']
            for platform, pattern in social_patterns.items():
                match = re.search(pattern, href)
                if match and platform not in social_handles:
                    social_handles[platform] = match.group(1)  # this gives us the username
        
        return social_handles
    
    def _get_contact_details(self, soup: BeautifulSoup) -> dict:
        contact_details = {}
        text = soup.get_text()
        
        # this regex will find email addresses in the page text
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            contact_details['emails'] = list(set(emails[:3]))  # just keep the first 3 unique ones
        
        # this is a basic phone number finder - not perfect but does the job
        phone_pattern = r'[\+]?[1-9]?[\d\s\-\(\)]{10,15}'
        phones = re.findall(phone_pattern, text)
        if phones:
            contact_details['phones'] = list(set([p.strip() for p in phones[:3]]))
        
        return contact_details
    
    def _get_brand_context(self, soup: BeautifulSoup) -> Optional[str]:
        # let's hunt for the "about us" type sections
        about_selectors = ['.about', '#about', '.brand-story', '.our-story']
        
        for selector in about_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                # keep it reasonable length so we don't get a novel
                return text[:300] + '...' if len(text) > 300 else text
        
        # if we can't find an about section, this will give us the meta description instead
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            return meta_desc.get('content', '')[:300]
        
        return None
    
    def _get_important_links(self, soup: BeautifulSoup, base_url: str) -> dict:
        important_links = {}
        
        # these are the types of links people usually care about
        link_keywords = {
            'contact': ['contact', 'contact us'],
            'track_order': ['track', 'order', 'track order', 'order tracking'],
            'blog': ['blog', 'news', 'articles']
        }
        
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True).lower()
            href = link['href']
            
            # basically matching link text with our keywords
            for key, keywords in link_keywords.items():
                if key not in important_links:  # don't overwrite if we already found one
                    for keyword in keywords:
                        if keyword in link_text:
                            important_links[key] = urljoin(base_url, href)
                            break
        
        return important_links

# this creates our fetcher instance that does all the heavy lifting
fetcher = ShopifyInsightsFetcher()

@app.post("/fetch-insights", response_model=BrandInsights)
async def fetch_store_insights(request: WebsiteRequest):
    """give this a shopify URL and get back all the details"""
    return fetcher.fetch_insights(str(request.website_url))

@app.get("/")
async def root():
    return {"message": "Shopify Store Insights Fetcher API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    # this will start the server on localhost:8000
    uvicorn.run(app, host="0.0.0.0", port=8000)