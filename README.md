# Shopify Store Insights Fetcher

A Python FastAPI application that extracts comprehensive insights from Shopify stores without using their official API.

## What This Does

This application takes any Shopify store URL and automatically extracts:

- Product Catalog
- Hero Products  
- Policy Pages
- FAQs
- Social Media Handles
- Contact Information
- Brand Context
- Important Links

## Setup

```bash
pip install -r requirements.txt
python main.py
```

The API will be available at `http://localhost:8000`

## Usage

Send POST request to `/fetch-insights` with:

```json
{
  "website_url": "https://example-store.com"
}
```

## Tech Stack

- FastAPI
- Pydantic
- BeautifulSoup4
- Requests

## Testing

Use Postman or curl to send POST requests to the `/fetch-insights` endpoint with a valid Shopify store URL.

## Important 
I built this application for educational purposes and is being submitted as an assignment kindly dont use it.
