import os
import json
import google.generativeai as genai
from google.api_core import retry

class QueryGenerator:
    def __init__(self, prompt_path= os.path.join('PROMPT', 'SYSTEM_PROMPT.txt')):
        # 1. Load Environment Variables
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_id = os.getenv("GEMINI_KEYS_GENERATOR_MODEL_ID", "gemini-2.0-flash")

        if not self.api_key:
            raise ValueError("Environment variable 'GEMINI_API_KEY' is not set.")

        # 2. Configure Gemini
        genai.configure(api_key=self.api_key)

        # 3. Load System Prompt from file
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt file not found at: {prompt_path}")
            
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.system_instruction = f.read()

        # 4. Initialize Model
        self.model = genai.GenerativeModel(
            model_name=self.model_id,
            system_instruction=self.system_instruction,
            generation_config={"response_mime_type": "application/json"}
        )

    @retry.Retry(predicate=retry.if_transient_error)
    def generate(self, user_input):
        """
        Nhận input string, trả về Dict (JSON parsed).
        """
        try:
            response = self.model.generate_content(user_input)
            return json.loads(response.text)
        except json.JSONDecodeError:
            print("Error: Model did not return valid JSON.")
            return None
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return None