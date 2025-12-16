#!/usr/bin/env python3
"""
Complete ETL Pipeline for Instacart Data Warehouse
Orchestrates the entire ETL process
"""
import sys
import time
from sqlalchemy import text

# Import ETL modules
from config import get_engine
import load_dimensions
import load_facts

def check_prerequisites():
    """Check if database schema exists"""
    print("Checking prerequisites...")
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            
            required_tables = [
                'Dim_Time', 'Dim_Department', 'Dim_Aisle', 'Dim_Product', 
                'Dim_User', 'Fact_Orders', 'Fact_Order_Details'
            ]
            
            missing = [t for t in required_tables if t not in tables]
            
            if missing:
                print(f"✗ Missing tables: {', '.join(missing)}")
                print("  Please run: ./sql/run_all_sql.sh")
                return False
            
            print(f"✓ All {len(required_tables)} tables exist")
            return True
            
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def check_data_already_loaded(engine):
    """Check if data is already loaded"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM Dim_Product"))
        count = result.fetchone()[0]
        return count > 0

def update_fact_metrics(engine):
    """Update aggregated metrics in Fact_Orders"""
    print("\n" + "="*60)
    print("Updating Fact Metrics...")
    print("="*60)
    
    # Update total_items in Fact_Orders
    print("\n[1/2] Updating total_items in Fact_Orders...")
    start = time.time()
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE Fact_Orders fo
                JOIN (
                    SELECT order_id, COUNT(*) as item_count
                    FROM Fact_Order_Details
                    GROUP BY order_id
                ) fod ON fo.order_id = fod.order_id
                SET fo.total_items = fod.item_count
            """))
            conn.commit()
        print(f"  ✓ Updated in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    # Update reorder_ratio in Fact_Orders
    print("\n[2/2] Updating reorder_ratio in Fact_Orders...")
    start = time.time()
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE Fact_Orders fo
                JOIN (
                    SELECT 
                        order_id,
                        SUM(reordered) / COUNT(*) as reorder_ratio
                    FROM Fact_Order_Details
                    GROUP BY order_id
                ) fod ON fo.order_id = fod.order_id
                SET fo.reorder_ratio = fod.reorder_ratio
            """))
            conn.commit()
        print(f"  ✓ Updated in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"  ✗ Error: {e}")

def populate_dim_user(engine):
    """Populate Dim_User from Fact_Orders aggregates"""
    print("\n" + "="*60)
    print("Populating Dim_User...")
    print("="*60)
    
    start = time.time()
    try:
        with engine.connect() as conn:
            # Insert user aggregates
            conn.execute(text("""
                INSERT INTO Dim_User (
                    user_id,
                    user_segment,
                    first_order_dow,
                    avg_basket_size,
                    total_orders,
                    avg_days_between_orders
                )
                SELECT 
                    user_id,
                    CASE 
                        WHEN COUNT(*) >= 100 THEN 'VIP'
                        WHEN COUNT(*) >= 10 THEN 'Regular'
                        ELSE 'New'
                    END as user_segment,
                    MIN(order_dow) as first_order_dow,
                    AVG(total_items) as avg_basket_size,
                    COUNT(*) as total_orders,
                    AVG(days_since_prior_order) as avg_days_between_orders
                FROM Fact_Orders
                GROUP BY user_id
            """))
            conn.commit()
            
        elapsed = time.time() - start
        
        # Get count
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM Dim_User"))
            count = result.fetchone()[0]
        
        print(f"  ✓ Populated {count:,} users in {elapsed:.2f}s")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")

def main():
    """Main ETL orchestration"""
    print("="*60)
    print("INSTACART DATA WAREHOUSE - COMPLETE ETL PIPELINE")
    print("="*60)
    
    start_time = time.time()
    
    # Step 0: Check prerequisites
    if not check_prerequisites():
        return 1
    
    engine = get_engine()
    
    # Check if already loaded
    if check_data_already_loaded(engine):
        print("\n⚠ WARNING: Data already exists in database!")
        response = input("Continue and append more data? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return 0
    
    # Step 1: Load Dimensions
    print("\n" + "="*60)
    print("PHASE 1: Loading Dimension Tables")
    print("="*60)
    if load_dimensions.main() != 0:
        print("✗ Dimension loading failed")
        return 1
    
    # Step 2: Load Facts
    print("\n" + "="*60)
    print("PHASE 2: Loading Fact Tables")
    print("="*60)
    print("⏱ This will take approximately 10-20 minutes...")
    if load_facts.main() != 0:
        print("✗ Fact loading failed")
        return 1
    
    # Step 3: Update metrics
    update_fact_metrics(engine)
    
    # Step 4: Populate Dim_User
    populate_dim_user(engine)
    
    # Final verification
    print("\n" + "="*60)
    print("FINAL VERIFICATION")
    print("="*60)
    
    with engine.connect() as conn:
        tables = [
            'Dim_Time', 'Dim_Department', 'Dim_Aisle', 'Dim_Product',
            'Dim_User', 'Fact_Orders', 'Fact_Order_Details'
        ]
        
        for table in tables:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.fetchone()[0]
            print(f"  {table:25s}: {count:>15,} records")
    
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    
    print("\n" + "="*60)
    print(f"✓ ETL PIPELINE COMPLETED in {minutes}m {seconds}s")
    print("="*60)
    print("\nNext steps:")
    print("  1. Check partitions: mysql < sql/10_check_partitions.sql")
    print("  2. Run maintenance: mysql < sql/11_maintenance.sql")
    print("  3. Create indexes: mysql < sql/09_additional_indexes.sql")
    print("  4. Start analysis: python analysis/queries.py")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
