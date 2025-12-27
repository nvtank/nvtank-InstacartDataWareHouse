"""
ETL Pipeline - Load Fact Tables
Load orders and order_products (prior + train)
"""
import pandas as pd
import sys
from sqlalchemy import text
from config import get_engine, CSV_FILES, BATCH_SIZE, CHUNK_SIZE
import time

def load_fact_orders(engine):
    """Load Fact_Orders from orders.csv"""
    print("\n[1/2] Loading Fact_Orders...")
    start_time = time.time()
    
    try:
        # Read CSV in chunks (large file ~104MB)
        chunks = []
        chunk_count = 0
        
        for chunk in pd.read_csv(CSV_FILES['orders'], chunksize=CHUNK_SIZE):
            chunk_count += 1
            print(f"  Reading chunk {chunk_count}... ({len(chunk)} rows)", end='\r')
            chunks.append(chunk)
        
        df = pd.concat(chunks, ignore_index=True)
        print(f"\n  ✓ Read {len(df):,} orders from CSV")
        
        # Filter only 'prior' and 'train' orders (exclude 'test' which has no product data)
        df = df[df['eval_set'].isin(['prior', 'train'])].copy()
        print(f"  ✓ Filtered to {len(df):,} orders (prior + train)")
        
        # Validate and clean time data
        print(f"\n  🔍 Validating time data...")
        
        # Check for invalid hours (must be 0-23)
        invalid_hours = df[~df['order_hour_of_day'].between(0, 23)]
        if len(invalid_hours) > 0:
            print(f"  ⚠️  WARNING: Found {len(invalid_hours):,} orders with invalid hours!")
            print(f"     Hour range: {df['order_hour_of_day'].min():.0f} - {df['order_hour_of_day'].max():.0f}")
            print(f"     Unique invalid hours: {sorted(invalid_hours['order_hour_of_day'].unique())}")
            # Fix: Use MOD 24 to wrap invalid hours back to 0-23
            print(f"  🔧 Fixing invalid hours using MOD 24...")
            df['order_hour_of_day'] = df['order_hour_of_day'] % 24
            print(f"  ✓ Fixed! Hour range now: {df['order_hour_of_day'].min():.0f} - {df['order_hour_of_day'].max():.0f}")
        
        # Check for invalid days (must be 0-6)
        invalid_days = df[~df['order_dow'].between(0, 6)]
        if len(invalid_days) > 0:
            print(f"  ⚠️  WARNING: Found {len(invalid_days):,} orders with invalid days!")
            print(f"     Day range: {df['order_dow'].min():.0f} - {df['order_dow'].max():.0f}")
            # Fix: Use MOD 7 to wrap invalid days back to 0-6
            print(f"  🔧 Fixing invalid days using MOD 7...")
            df['order_dow'] = df['order_dow'] % 7
            print(f"  ✓ Fixed! Day range now: {df['order_dow'].min():.0f} - {df['order_dow'].max():.0f}")
        
        # Create time_id (dow * 100 + hour)
        df['time_id'] = df['order_dow'] * 100 + df['order_hour_of_day']
        
        # Verify time_id is valid (should match Dim_Time)
        unique_time_ids = df['time_id'].nunique()
        print(f"  ✓ Created {unique_time_ids} unique time_id values (expected: up to 168 for 7 days × 24 hours)")
        
        # Select and rename columns
        fact_df = df[[
            'order_id',
            'user_id',
            'time_id',
            'order_number',
            'days_since_prior_order',
            'order_dow'
        ]].copy()
        
        # Add placeholder columns (will be updated later)
        fact_df['total_items'] = 0
        fact_df['reorder_ratio'] = 0.0
        
        # Handle NaN in days_since_prior_order - use 0 instead of None
        fact_df['days_since_prior_order'] = fact_df['days_since_prior_order'].fillna(0).astype('Int64')
        
        # Load to database in batches (smaller batch to avoid parameter limit)
        total_loaded = 0
        small_batch = 1000  # 1000 rows × 8 cols = 8000 params (safe limit)
        for batch_start in range(0, len(fact_df), small_batch):
            batch = fact_df[batch_start:batch_start + small_batch]
            batch.to_sql('Fact_Orders', engine, if_exists='append', index=False)
            total_loaded += len(batch)
            print(f"  Loading... {total_loaded:,}/{len(fact_df):,} ({total_loaded*100//len(fact_df)}%)", end='\r')
        
        elapsed = time.time() - start_time
        print(f"\n  ✓ Loaded {len(fact_df):,} records in {elapsed:.2f}s ({len(fact_df)/elapsed:.0f} rows/sec)")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_fact_order_details(engine):
    """Load Fact_Order_Details from order_products__prior.csv and order_products__train.csv"""
    print("\n[2/2] Loading Fact_Order_Details...")
    start_time = time.time()
    
    total_loaded = 0
    
    for file_key in ['order_products_prior', 'order_products_train']:
        file_path = CSV_FILES[file_key]
        file_name = file_key.replace('_', ' ').title()
        
        print(f"\n  Processing {file_name}...")
        sub_start = time.time()
        
        try:
            # Read CSV in chunks
            chunk_num = 0
            file_total = 0
            
            for chunk in pd.read_csv(file_path, chunksize=CHUNK_SIZE):
                chunk_num += 1
                
                # Get time_id from Fact_Orders (JOIN)
                # For performance, we'll compute time_id later in a separate UPDATE query
                # For now, use a placeholder
                chunk['time_id'] = 0  # Will be updated via UPDATE JOIN query
                
                # Rename columns
                chunk = chunk.rename(columns={
                    'add_to_cart_order': 'add_to_cart_order'
                })
                
                # Add quantity column (always 1 in source data)
                chunk['quantity'] = 1
                
                # Validate add_to_cart_order range (SMALLINT max = 32767)
                max_cart = chunk['add_to_cart_order'].max()
                if max_cart > 32767:
                    print(f"\n    ⚠️  Warning: Max add_to_cart_order={max_cart}, clipping to 32767")
                    chunk['add_to_cart_order'] = chunk['add_to_cart_order'].clip(upper=32767)
                
                # Select columns for fact table
                fact_chunk = chunk[[
                    'order_id',
                    'product_id',
                    'time_id',
                    'add_to_cart_order',
                    'reordered',
                    'quantity'
                ]].copy()
                
                # Load to database in smaller batches (avoid parameter limit)
                small_batch = 1000  # 1000 rows × 6 cols = 6000 params (safe)
                for batch_start in range(0, len(fact_chunk), small_batch):
                    mini_batch = fact_chunk[batch_start:batch_start + small_batch]
                    mini_batch.to_sql('Fact_Order_Details', engine, if_exists='append', index=False)
                
                file_total += len(fact_chunk)
                total_loaded += len(fact_chunk)
                
                print(f"    Chunk {chunk_num}: {file_total:,} rows loaded from {file_name}", end='\r')
            
            sub_elapsed = time.time() - sub_start
            print(f"\n  ✓ {file_name}: {file_total:,} records in {sub_elapsed:.2f}s")
            
        except Exception as e:
            print(f"  ✗ Error loading {file_name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # Update time_id from Fact_Orders (using batch update for performance)
    print("\n  Updating time_id from Fact_Orders...")
    print("  ⚠️  This may take 5-10 minutes for 33M rows...")
    
    try:
        with engine.connect() as conn:
            # Use partition-aware batch update (much faster!)
            partitions = ['p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p_max']
            
            for i, partition in enumerate(partitions, 1):
                partition_start = time.time()
                result = conn.execute(text(f"""
                    UPDATE Fact_Order_Details PARTITION ({partition}) fod
                    JOIN Fact_Orders fo ON fod.order_id = fo.order_id
                    SET fod.time_id = fo.time_id
                    WHERE fod.time_id = 0
                """))
                conn.commit()
                
                partition_elapsed = time.time() - partition_start
                print(f"    Partition {i}/{len(partitions)} ({partition}): {partition_elapsed:.1f}s", end='\r')
            
        print(f"\n  ✓ time_id updated for all partitions")
    except Exception as e:
        print(f"  ⚠️  Warning: Could not update time_id (can be done later): {e}")
    
    elapsed = time.time() - start_time
    print(f"\n  ✓ Total loaded: {total_loaded:,} records in {elapsed:.2f}s ({total_loaded/elapsed:.0f} rows/sec)")
    return True

def main():
    """Main ETL process for fact tables"""
    print("="*60)
    print("ETL: Loading Fact Tables")
    print("="*60)
    print("WARNING: This will take 10-20 minutes for 33M+ records!")
    print("="*60)
    
    try:
        engine = get_engine()
        print("✓ Database connection established")
        
        # Load facts
        success = True
        success &= load_fact_orders(engine)
        success &= load_fact_order_details(engine)
        
        if success:
            # Verify counts
            print("\n" + "="*60)
            print("Verification:")
            print("="*60)
            with engine.connect() as conn:
                for table in ['Fact_Orders', 'Fact_Order_Details']:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.fetchone()[0]
                    print(f"  {table}: {count:,} records")
            
            print("\n✓ All fact tables loaded successfully!")
            print("\nNext step: Run update_fact_metrics.py to compute aggregates")
            return 0
        else:
            print("\n✗ Some tables failed to load")
            return 1
            
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
