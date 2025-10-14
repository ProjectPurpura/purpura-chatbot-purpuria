import dotenv
import os

dotenv.load_dotenv()

class ENV:
    REDIS_URL = os.getenv("REDIS_URL")
    POSTGRES_URL = os.getenv("POSTGRES_URL")
    MONGO_URL = os.getenv("MONGO_URL")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
