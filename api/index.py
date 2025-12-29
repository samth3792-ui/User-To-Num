import asyncio
import re
import time
import os
import json
from pyrogram import Client
from pyrogram.errors import FloodWait, SessionPasswordNeeded

# Telegram credentials from environment variables
API_ID = int(os.environ.get("API_ID", "29969433"))
API_HASH = os.environ.get("API_HASH", "884f9ffa4e8ece099cccccade82effac")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER", "+919214045762")
TARGET_BOT = os.environ.get("TARGET_BOT", "@telebrecheddb_bot")

# Global client variable
app = None

# Initialize Telegram client
async def initialize_client():
    global app
    
    if app is None:
        print("Initializing Telegram client...")
        app = Client(
            "my_account",
            api_id=API_ID,
            api_hash=API_HASH,
            phone_number=PHONE_NUMBER,
            no_updates=True,
            in_memory=True
        )
        
        try:
            await app.start()
            print("Telegram client started successfully")
        except SessionPasswordNeeded:
            # If 2FA is enabled
            print("2FA password required")
            # For now, we'll skip 2FA in serverless
            raise Exception("Two-step verification is enabled. Please disable it temporarily.")
        except Exception as e:
            print(f"Failed to start client: {str(e)}")
            raise
    
    return app

# Parse bot response
def parse_response(text):
    if not text:
        return {"success": False, "error": "Empty response from bot"}
    
    result = {
        "success": True,
        "username": None,
        "id": None,
        "phone": None,
        "viewed_by": None,
        "name_history": []
    }
    
    try:
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
        history_pattern = r"(\d{2}\.\d{2}\.\d{4})\s*→\s*@([a-zA-Z0-9_]+)[,，]\s*([^→\n]+)"
        history_matches = re.findall(history_pattern, text)
        
        for date, username, info in history_matches:
            ids = re.findall(r"\d+", info)
            result["name_history"].append({
                "date": date,
                "username": username,
                "id": ids[0] if ids else None
            })
            
    except Exception as e:
        result["success"] = False
        result["error"] = f"Parsing error: {str(e)}"
    
    return result

# Main function to get user info
async def get_user_info(username):
    if not username:
        return {"success": False, "error": "Username is required"}
    
    # Clean username
    username = username.strip().lstrip('@')
    
    try:
        # Get client
        client = await initialize_client()
        
        # Send message to bot
        sent_message = await client.send_message(TARGET_BOT, f"t.me/{username}")
        
        # Wait for response
        response = None
        timeout = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            async for message in client.get_chat_history(TARGET_BOT, limit=10):
                if (message.id > sent_message.id and 
                    not message.outgoing and 
                    message.text and 
                    "t.me" in message.text):
                    response = message.text
                    break
            
            if response:
                break
            
            await asyncio.sleep(2)
        
        if not response:
            return {"success": False, "error": "Bot did not respond within timeout"}
        
        # Parse response
        return parse_response(response)
        
    except FloodWait as e:
        return {"success": False, "error": f"Flood wait: {e.value} seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Vercel serverless handler
async def main(request):
    from urllib.parse import parse_qs
    
    try:
        # Get query parameters
        query_string = request.get("query", {})
        username = query_string.get("username", [""])[0]
        
        if not username:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "success": False,
                    "error": "Please provide username parameter: ?username=@example"
                })
            }
        
        # Get user info
        result = await get_user_info(username)
        
        return {
            "statusCode": 200 if result["success"] else 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result, indent=2)
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": False,
                "error": f"Server error: {str(e)}"
            })
        }

# For Vercel
def handler(request, context):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(main(request))
    loop.close()
    return result

# For local testing
if __name__ == "__main__":
    # Simple test
    async def test():
        import sys
        username = sys.argv[1] if len(sys.argv) > 1 else "@telegram"
        print(f"Testing with username: {username}")
        result = await get_user_info(username)
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())
