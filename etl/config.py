"""
ETL Configuration Module
Database connection and path settings
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# Load environment variables
load_dotenv()

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rootpass123'),
    'database': os.getenv('DB_NAME', 'instacart_dwh'),
}

# Data Paths
DATA_PATH = os.getenv('DATA_PATH', '/home/nvtank/year3/ki1/kdl/ck/topic2')
CSV_FILES = {
    'aisles': os.path.join(DATA_PATH, 'aisles.csv'),
    'departments': os.path.join(DATA_PATH, 'departments.csv'),
    'products': os.path.join(DATA_PATH, 'products.csv'),
    'orders': os.path.join(DATA_PATH, 'orders.csv'),
    'order_products_prior': os.path.join(DATA_PATH, 'order_products__prior.csv'),
    'order_products_train': os.path.join(DATA_PATH, 'order_products__train.csv'),
}

# ETL Configuration
BATCH_SIZE = int(os.getenv('BATCH_SIZE', 10000))
CHUNK_SIZE = 50000  # For reading large CSV files

# SQLAlchemy Engine
def get_engine():
    """Create and return SQLAlchemy engine with connection pooling"""
    connection_string = (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        "?charset=utf8mb4"
    )
    
    engine = create_engine(
        connection_string,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verify connections before using
        echo=False  # Set True for SQL debugging
    )
    
    return engine

# Test connection
if __name__ == '__main__':
    print("Testing database connection...")
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION() as version"))
            version = result.fetchone()[0]
            print(f"✓ Connected to MariaDB {version}")
            
            result = conn.execute(text("SELECT DATABASE() as db"))
            db = result.fetchone()[0]
            print(f"✓ Using database: {db}")
            
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            print(f"✓ Found {len(tables)} tables: {', '.join(tables)}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
