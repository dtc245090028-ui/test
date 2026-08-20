import json
import os
import requests
from flask import current_app
from app.extensions import db
from app.models.ai_interaction_log import AIInteractionLog
from app.ai.prompts.inventory_prompts import SYSTEM_PROMPT_INVENTORY, USER_PROMPT_INVENTORY
from datetime import datetime, timezone

def _call_gemini_api(system_prompt, user_prompt):
    api_key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("AI_MODEL", "gemini-1.5-flash")
    if not api_key:
        raise Exception("GEMINI_API_KEY is not configured.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text, model
        else:
            raise Exception("No content in AI response")
    except Exception as e:
        raise Exception(f"AI Service error: {str(e)}")

def generate_inventory_report(inventory_data, user_id=None):
    user_prompt = USER_PROMPT_INVENTORY.format(inventory_report=json.dumps(inventory_data, ensure_ascii=False))
    
    try:
        response_text, model_used = _call_gemini_api(SYSTEM_PROMPT_INVENTORY, user_prompt)
        
        # Log to DB
        log = AIInteractionLog(
            feature_type="inventory_report",
            user_id=user_id,
            prompt_input=user_prompt[:500] + "..." if len(user_prompt) > 500 else user_prompt,
            ai_response=response_text,
            model_used=model_used
        )
        db.session.add(log)
        db.session.commit()
        
        return json.loads(response_text)
    except Exception as e:
        return {"error": str(e)}
