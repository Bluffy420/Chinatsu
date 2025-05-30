import os
from dotenv import load_dotenv
import logging
from bot import run_bot

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        logging.error(f"Bot crashed: {e}", exc_info=True) 