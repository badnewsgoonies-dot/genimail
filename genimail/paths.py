import os


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT_DIR, "email_config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
TOKEN_CACHE_FILE = os.path.join(CONFIG_DIR, "token_cache.json")
CACHE_DB_FILE = os.path.join(CONFIG_DIR, "email_cache.db")
PDF_DIR = os.path.join(ROOT_DIR, "pdf")
QUOTE_DIR = os.path.join(ROOT_DIR, "quotes")
DEFAULT_QUOTE_TEMPLATE_FILE = os.path.join(CONFIG_DIR, "quote_template.doc")

