import asyncio

import httpx


async def test():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8003/status")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Total Balance: ${data['portfolio']['total_balance']}")
        else:
            print("Failed")


asyncio.run(test())
