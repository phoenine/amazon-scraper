#!/usr/bin/env python3
"""
Simple test script for the Amazon scraper
"""
import asyncio
import aiohttp
import json


async def test_api():
    """Test the scraper API"""
    base_url = "http://localhost:18000"

    async with aiohttp.ClientSession() as session:
        # Test health endpoint
        print("Testing health endpoint...")
        async with session.get(f"{base_url}/health") as resp:
            print(f"Health: {resp.status} - {await resp.json()}")

        # Test single ASIN scraping
        print("\nTesting single ASIN scraping...")
        test_asin = "B0CGJJJC4M"  # Example ASIN
        async with session.get(f"{base_url}/asin/{test_asin}?wait=true") as resp:
            print(f"Single ASIN: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print(f"Title: {data.get('title', 'N/A')}")
                print(f"Price: {data.get('price', 'N/A')}")
                print(f"Rating: {data.get('rating', 'N/A')}")
            else:
                print(f"Error: {await resp.text()}")

        # Test batch scraping
        print("\nTesting batch scraping...")
        batch_data = {
            "items": [
                {"asin": "B0CGJJJC4M", "marketplace": "amazon.com"},
                {"asin": "B0BZNPDHR9", "marketplace": "amazon.com"},
            ],
            "async_mode": True,
        }

        async with session.post(f"{base_url}/asin/scrape", json=batch_data) as resp:
            print(f"Batch scrape: {resp.status}")
            if resp.status == 200:
                tasks = await resp.json()
                print(f"Created {len(tasks)} tasks")
                for task in tasks:
                    print(f"Task {task['id']}: {task['asin']} - {task['status']}")
            else:
                print(f"Error: {await resp.text()}")

        # Test stats
        print("\nTesting stats endpoint...")
        async with session.get(f"{base_url}/stats") as resp:
            print(f"Stats: {resp.status} - {await resp.json()}")


if __name__ == "__main__":
    asyncio.run(test_api())
