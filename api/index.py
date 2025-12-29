import asyncio
import os
import json
import time
import re
from pyrogram import Client
from pyrogram.errors import FloodWait

# Environment variables
API_ID = int(os.environ.get("API_ID", "29969433"))
API_HASH = os.environ.get("API_HASH", "884f9ffa4e8ece099cccccade82effac")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "+919214045762")
TARGET_BOT = os.environ.get("TARGET_BOT", "@telebrecheddb_bot")

# Telegram client
tg_client = None

async def get_telegram_client():
    """Initialize Telegram client"""
    global tg_client
    
    if tg_client is None:
        print("Creating new Telegram client...")
        tg_client = Client(
            "vercel_session",
            api_id=API_ID,
            api_hash=API_HASH,
            phone_number=PHONE_NUMBER,
            no_updates=True,
            in_memory=True
        )
        
        try:
            await tg_client.start()
            print("Telegram client started successfully")
            
            # Send test message to verify connection
            me = await tg_client.get_me()
            print(f"Logged in as: {me.first_name} (@{me.username})")
            
        except Exception as e:
            print(f"Failed to start client: {e}")
            tg_client = None
            raise
    
    return tg_client

def parse_bot_response(text):
    """Parse bot response"""
    if not text:
        return {"success": False, "error": "Empty response"}
    
    # Replace Russian text
    text = text.replace("Телефон", "Phone") \
               .replace("История изменения имени", "Name change history") \
               .replace("Интересовались этим", "Viewed by")
    
    result = {
        "success": True,
        "username": None,
        "id": None,
        "phone": None,
        "viewed_by": None,
        "name_history": []
    }
    
    # Extract username
    username_match = re.search(r"t\.me/([a-zA-Z0-9_]+)", text)
    if username_match:
        result["username"] = username_match.group(1)
    
    # Extract ID
    id_match = re.search(r"ID[:：]\s*(\d+)", text)
    if id_match:
        result["id"] = id_match.group(1)
    
    # Extract phone
    phone_match = re.search(r"Phone[:：]\s*(\d+)", text)
    if phone_match:
        result["phone"] = phone_match.group(1)
    
    # Extract viewed by
    viewed_match = re.search(r"Viewed by[:：]\s*(\d+)", text)
    if viewed_match:
        result["viewed_by"] = viewed_match.group(1)
    
    # Extract history
    history_matches = re.findall(r"(\d{2}\.\d{2}\.\d{4})\s*→\s*@([a-zA-Z0-9_]+)[,，]\s*([^→\n]+)", text)
    for date, username, info in history_matches:
        ids = re.findall(r"\d+", info)
        result["name_history"].append({
            "date": date,
            "username": username,
            "id": ids[0] if ids else None
        })
    
    return result

async def get_user_info_from_bot(username):
    """Get user info from Telegram bot"""
    try:
        # Clean username
        username = username.strip().lstrip('@')
        
        # Get client
        client = await get_telegram_client()
        
        # Send message to bot
        message = f"t.me/{username}"
        sent = await client.send_message(TARGET_BOT, message)
        
        # Wait for response (max 30 seconds)
        response = None
        for _ in range(15):  # 15 * 2 = 30 seconds
            async for msg in client.get_chat_history(TARGET_BOT, limit=5):
                if msg.id > sent.id and not msg.outgoing and msg.text:
                    if "t.me" in msg.text or "ID" in msg.text:
                        response = msg.text
                        break
            
            if response:
                break
            await asyncio.sleep(2)
        
        if not response:
            return {"success": False, "error": "No response from bot"}
        
        # Parse response
        return parse_bot_response(response)
        
    except FloodWait as e:
        return {"success": False, "error": f"Please wait {e.value} seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# VERCEL SERVERLESS FUNCTION
def handler(event, context):
    """Main handler for Vercel"""
    
    # Parse request
    try:
        # Get query parameters
        query = event.get('queryStringParameters', {}) or {}
        username = query.get('username', '')
        
        # Get path
        path = event.get('path', '/')
        
        # Handle different routes
        if path == '/' or path == '':
            # Home page
            if username:
                # Get user info
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(get_user_info_from_bot(username))
                loop.close()
            else:
                # Show instructions
                result = {
                    "success": True,
                    "message": "Telegram User Info API",
                    "usage": "Add ?username=@example to URL",
                    "example": "https://user-to-5trud8t4y-samth3792-uis-projects.vercel.app/?username=@telegram",
                    "endpoints": {
                        "check_user": "/?username=@username",
                        "health": "/health"
                    }
                }
        
        elif path == '/health':
            # Health check
            result = {
                "success": True,
                "status": "online",
                "timestamp": time.time()
            }
        
        else:
            # 404
            result = {
                "success": False,
                "error": "Endpoint not found",
                "available_endpoints": ["/", "/health"]
            }
        
        # Return response
        return {
            'statusCode': 200 if result.get('success', False) else 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result, indent=2)
        }
        
    except Exception as e:
        # Error response
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                "success": False,
                "error": str(e),
                "note": "Check Vercel environment variables"
            }, indent=2)
        }

# Local testing
if __name__ == "__main__":
    # Test the handler
    test_event = {
        'path': '/',
        'queryStringParameters': {'username': '@telegram'}
    }
    
    print("Testing API...")
    result = handler(test_event, None)
    print("Status Code:", result['statusCode'])
    print("Response:", result['body'])
