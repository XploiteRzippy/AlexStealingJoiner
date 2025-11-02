import asyncio
import aiohttp
import json
import os
from aiohttp import web

connected = set()
latest_job_data = None

async def handle_client(websocket):
    connected.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connected.remove(websocket)

async def send_to_clients(data):
    if not connected:
        return
    disconnected_clients = []
    for client in connected:
        try:
            await client.send(json.dumps(data))
        except (ConnectionResetError, Exception):
            disconnected_clients.append(client)
    for client in disconnected_clients:
        connected.discard(client)

# HTTP endpoint for Roblox to poll
async def http_latest(request):
    """Returns the latest job data"""
    if latest_job_data:
        return web.Response(
            text=json.dumps(latest_job_data),
            content_type='application/json',
            headers={'Access-Control-Allow-Origin': '*'}
        )
    return web.Response(
        text='{}',
        content_type='application/json',
        headers={'Access-Control-Allow-Origin': '*'}
    )

# Health check endpoint
async def http_health(request):
    """Health check endpoint"""
    return web.Response(text='Server is running!')

async def monitor_discord_channel(token, channel_id):
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    async with aiohttp.ClientSession() as session:
        url = f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=1"
        
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    messages = await response.json()
                    last_message_id = messages[0]['id'] if messages else None
                    print(f"✅ Connesso al canale Discord. Ultimo messaggio: {last_message_id}")
                else:
                    print(f"❌ Errore API Discord: {response.status}")
                    return
        except Exception as e:
            print(f"❌ Errore di connessione: {e}")
            return
        
        while True:
            try:
                url = f"https://discord.com/api/v9/channels/{channel_id}/messages?after={last_message_id}&limit=10"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        messages = await response.json()
                        
                        for message in reversed(messages):
                            await process_message(message)
                            last_message_id = message['id']
                    else:
                        print(f"⚠️ Errore API: {response.status}")
                        
            except Exception as e:
                print(f"❌ Errore durante il polling: {e}")
            
            await asyncio.sleep(0.1)

async def process_message(message):
    global latest_job_data
    
    target_channel_id = 1401775181025775738
    
    if str(message['channel_id']) != str(target_channel_id):
        return
        
    print(f"✅ Messaggio dal canale corretto: {message['channel_id']}")
    
    if 'embeds' in message and message['embeds']:
        for embed in message['embeds']:
            if 'fields' in embed and embed['fields']:
                jobId, moneyPerSec, petName = None, 0, 'Unknown'
                
                for field in embed['fields']:
                    fval = field.get('value', '')
                    
                    if 'Job ID' in field.get('name', ''):
                        jobId = fval.replace('`', '')
                    
                    if 'Name' in field.get('name', ''):
                        petName = fval
                    
                    if '$' in fval and 'M/s' in fval:
                        dollar = fval.split('$')[1].split('M/s')[0]
                        if dollar:
                            moneyPerSec = float(dollar) * 1000000
                    elif '$' in fval and 'K/s' in fval:
                        k = fval.split('$')[1].split('K/s')[0]
                        if k:
                            moneyPerSec = float(k) * 1000
                
                if jobId and moneyPerSec > 0 and petName:
                    data = {"jobid": jobId, "money": str(moneyPerSec), "name": petName}
                    latest_job_data = data  # Store for HTTP endpoint
                    print(f"📦 Invio dati: {data}")
                    await send_to_clients(data)

async def main():
    # Get token from environment variable or prompt
    discord_token = os.environ.get('DISCORD_TOKEN')
    
    if not discord_token:
        discord_token = input("Discord User Token: ")
    
    if not discord_token or len(discord_token.strip()) == 0:
        print("❌ Token vuoto! Inserisci un token valido.")
        return
    
    if not (discord_token.startswith('mfa.') or discord_token.startswith('MTk') or discord_token.startswith('OD')):
        print("⚠️ Attenzione: Il token potrebbe non essere nel formato corretto.")
    
    channel_id = 1401775181025775738
    
    # Create web app for HTTP endpoints
    app = web.Application()
    app.router.add_get('/latest', http_latest)
    app.router.add_get('/', http_health)
    
    # Start HTTP server
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Use PORT from environment (for Render) or default to 1488
    port = int(os.environ.get('PORT', 1488))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"🌐 HTTP Server running on port {port}")
    print(f"📡 Endpoint: http://0.0.0.0:{port}/latest")
    print(f"🔍 Health check: http://0.0.0.0:{port}/")
    print("🚀 Tentativo di connessione a Discord...")
    
    try:
        await monitor_discord_channel(discord_token, channel_id)
    except Exception as e:
        print(f"❌ Errore: {e}")

if __name__ == "__main__":
    asyncio.run(main())
