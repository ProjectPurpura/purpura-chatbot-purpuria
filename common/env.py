import dotenv
import os

dotenv.load_dotenv()

class ENV:
    REDIS_URL = os.getenv("REDIS_URL")
    POSTGRES_URL = os.getenv("POSTGRES_URL")
    MONGO_URL = os.getenv("MONGO_URL")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    @classmethod
    def check_missing(cls):
        missing = []
        for attr, value in cls.__dict__.items():
            # Ignore private attributes and methods
            if not attr.startswith("_") and not callable(value):
                if value is None:
                    missing.append(attr)
        if missing:
            print("❌ Variáveis de ambiente não definidas:")
            for name in missing:
                print(f"  - ⚠️ {name}")

            print("ℹ️ Por favor assegurar-se que tenha um arquivo .env na raíz do seu projeto com essas variáveis claramente definidas e com o exato mesmo nome.")
        else:
            print("✅ Todas as variáveis de ambiente carregadas.")

ENV.check_missing()