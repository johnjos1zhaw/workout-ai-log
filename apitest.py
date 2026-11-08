import os
from dotenv import load_dotenv

load_dotenv()
print("API key loaded:", bool(os.getenv("OPENAI_API_KEY")))