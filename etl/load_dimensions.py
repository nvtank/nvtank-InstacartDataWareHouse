"""
ETL Pipeline - Load Dimension Tables
Load aisles, departments, and products
"""
import pandas as pd
import sys
from sqlalchemy import text
from config import get_engine, CSV_FILES, BATCH_SIZE
import time

def load_dim_department(engine):
    """Load Dim_Department from departments.csv"""
    print("\n[1/3] Loading Dim_Department...")
    start_time = time.time()
    
    try:
        # Read CSV
        df = pd.read_csv(CSV_FILES['departments'])
        print(f"  ✓ Read {len(df)} departments from CSV")
        
        # Add dept_category (categorize departments)
        def categorize_department(dept_name):
            dept_lower = dept_name.lower()
            if any(word in dept_lower for word in ['produce', 'frozen', 'meat', 'seafood', 'deli']):
                return 'Food'
            elif any(word in dept_lower for word in ['dairy', 'beverages', 'alcohol']):
                return 'Beverage'
            elif any(word in dept_lower for word in ['personal', 'beauty', 'health']):
                return 'Personal Care'
            elif any(word in dept_lower for word in ['household', 'pets']):
                return 'Household'
            else:
                return 'General'
        
        df['dept_category'] = df['department'].apply(categorize_department)
        
        # Rename columns to match schema
        df = df.rename(columns={'department': 'department_name'})
        
        # Load to database
        df.to_sql('Dim_Department', engine, if_exists='append', index=False, method='multi', chunksize=BATCH_SIZE)
        
        elapsed = time.time() - start_time
        print(f"  ✓ Loaded {len(df)} records in {elapsed:.2f}s")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def load_dim_aisle(engine):
    """Load Dim_Aisle from aisles.csv"""
    print("\n[2/3] Loading Dim_Aisle...")
    start_time = time.time()
    
    try:
        # Read CSV
        df = pd.read_csv(CSV_FILES['aisles'])
        print(f"  ✓ Read {len(df)} aisles from CSV")
        
        # Add aisle_type (categorize aisles)
        def categorize_aisle(aisle_name):
            aisle_lower = aisle_name.lower()
            if any(word in aisle_lower for word in ['fresh', 'produce', 'fruit', 'vegetable']):
                return 'Fresh'
            elif any(word in aisle_lower for word in ['frozen', 'ice']):
                return 'Frozen'
            elif any(word in aisle_lower for word in ['beverage', 'drink', 'juice', 'soda', 'water']):
                return 'Beverage'
            elif any(word in aisle_lower for word in ['snack', 'candy', 'chocolate', 'cookies']):
                return 'Snacks'
            elif any(word in aisle_lower for word in ['dairy', 'milk', 'yogurt', 'cheese']):
                return 'Dairy'
            elif any(word in aisle_lower for word in ['packaged', 'canned', 'dry']):
                return 'Dry Goods'
            else:
                return 'General'
        
        df['aisle_type'] = df['aisle'].apply(categorize_aisle)
        
        # Rename columns
        df = df.rename(columns={'aisle': 'aisle_name'})
        
        # Load to database
        df.to_sql('Dim_Aisle', engine, if_exists='append', index=False, method='multi', chunksize=BATCH_SIZE)
        
        elapsed = time.time() - start_time
        print(f"  ✓ Loaded {len(df)} records in {elapsed:.2f}s")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def load_dim_product(engine):
    """Load Dim_Product from products.csv"""
    print("\n[3/3] Loading Dim_Product...")
    start_time = time.time()
    
    try:
        # Read CSV
        df = pd.read_csv(CSV_FILES['products'])
        print(f"  ✓ Read {len(df)} products from CSV")
        
        # Add product_category (same as department for now)
        df['product_category'] = 'General'  # Will be updated later if needed
        
        # Load to database in chunks (large table)
        total_rows = 0
        for chunk_start in range(0, len(df), BATCH_SIZE):
            chunk = df[chunk_start:chunk_start + BATCH_SIZE]
            chunk.to_sql('Dim_Product', engine, if_exists='append', index=False, method='multi')
            total_rows += len(chunk)
            print(f"  ... {total_rows}/{len(df)} products loaded", end='\r')
        
        elapsed = time.time() - start_time
        print(f"\n  ✓ Loaded {len(df)} records in {elapsed:.2f}s")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    """Main ETL process for dimension tables"""
    print("="*60)
    print("ETL: Loading Dimension Tables")
    print("="*60)
    
    try:
        engine = get_engine()
        print("✓ Database connection established")
        
        # Load dimensions
        success = True
        success &= load_dim_department(engine)
        success &= load_dim_aisle(engine)
        success &= load_dim_product(engine)
        
        if success:
            # Verify counts
            print("\n" + "="*60)
            print("Verification:")
            print("="*60)
            with engine.connect() as conn:
                for table in ['Dim_Department', 'Dim_Aisle', 'Dim_Product']:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.fetchone()[0]
                    print(f"  {table}: {count:,} records")
            
            print("\n✓ All dimension tables loaded successfully!")
            return 0
        else:
            print("\n✗ Some tables failed to load")
            return 1
            
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
