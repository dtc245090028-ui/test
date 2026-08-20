import json
import os
from app.extensions import db
from app.models.ai_interaction_log import AIInteractionLog
from app.ai.prompts.inventory_prompts import SYSTEM_PROMPT_REORDER, USER_PROMPT_REORDER
from app.ai.inventory_report_service import _call_gemini_api

def generate_reorder_suggestion(reorder_data, user_id=None):
    user_prompt = USER_PROMPT_REORDER.format(reorder_data=json.dumps(reorder_data, ensure_ascii=False))
    
    try:
        response_text, model_used = _call_gemini_api(SYSTEM_PROMPT_REORDER, user_prompt)
        
        # Log to DB
        log = AIInteractionLog(
            feature_type="reorder_suggestion",
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
