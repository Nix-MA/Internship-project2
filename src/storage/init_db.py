import os
from .db import init_db, DB_PATH
from src.utils.logger import get_logger

logger = get_logger("lumina.init_db")

def initialize_database():
    """Initializes the database safely avoiding race conditions."""
    if not os.path.exists(DB_PATH):
        logger.info(f"Database not found at {DB_PATH}. Initializing tables...")
        init_db()
        logger.info("Database initialized successfully.")
    else:
        logger.info("Database already exists. Skipping initialization.")

if __name__ == "__main__":
    initialize_database()
