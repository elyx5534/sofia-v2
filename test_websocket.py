import asyncio
import json

import websockets


async def test_websocket():
    uri = "ws://localhost:8006/ws/portfolio"
    print("Connecting to WebSocket...")

    async with websockets.connect(uri) as websocket:
        print("Connected! Waiting for updates...")

        # Receive 3 updates
        for i in range(3):
            message = await websocket.recv()
            data = json.loads(message)
            print(f"\nUpdate {i+1}:")
            print(f"  Balance: ${data['data']['balance']:.2f}")
            print(f"  Daily P&L: ${data['data']['daily_pnl']:.2f}")
            print(f"  Positions: {len(data['data']['positions'])}")

        print("\nWebSocket test successful!")


asyncio.run(test_websocket())
