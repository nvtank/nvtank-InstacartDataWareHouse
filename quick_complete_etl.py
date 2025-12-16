#!/usr/bin/env python3
"""
Quick Complete ETL - Skip time_id update (not needed for dashboard)
Only update metrics and populate Dim_User
"""
import sys
import time
from sqlalchemy import text

sys.path.append('.')
from etl.config import get_engine

def update_metrics(engine):
    """Update total_items and reorder_ratio in Fact_Orders"""
    print("\n" + "="*60)
    print("Step 1: Updating Fact_Orders metrics...")
    print("="*60)
    
    # Update total_items
    print("\n[1/2] Updating total_items...")
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
        elapsed = time.time() - start
        print(f"  ✓ Updated in {elapsed:.2f}s ({elapsed/60:.1f} minutes)")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Update reorder_ratio
    print("\n[2/2] Updating reorder_ratio...")
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
        elapsed = time.time() - start
        print(f"  ✓ Updated in {elapsed:.2f}s ({elapsed/60:.1f} minutes)")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def populate_dim_user(engine):
    """Populate Dim_User from Fact_Orders"""
    print("\n" + "="*60)
    print("Step 2: Populating Dim_User...")
    print("="*60)
    
    start = time.time()
    try:
        with engine.connect() as conn:
            # Delete existing if any
            conn.execute(text("DELETE FROM Dim_User"))
            conn.commit()
            print("  ✓ Cleared existing Dim_User data")
            
            # Insert user aggregates
            print("  Inserting user aggregates...")
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
        
        print(f"  ✓ Populated {count:,} users in {elapsed:.2f}s ({elapsed/60:.1f} minutes)")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_data(engine):
    """Verify final data counts"""
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
        
        # Check sample metrics
        print("\n" + "="*60)
        print("Sample Metrics Check:")
        print("="*60)
        result = conn.execute(text("""
            SELECT 
                AVG(total_items) as avg_basket,
                AVG(reorder_ratio) as avg_reorder,
                COUNT(DISTINCT user_id) as unique_users
            FROM Fact_Orders
            LIMIT 1
        """))
        row = result.fetchone()
        print(f"  Average Basket Size: {row[0]:.2f} items")
        print(f"  Average Reorder Ratio: {row[1]:.2%}")
        print(f"  Unique Users: {row[2]:,}")

def main():
    print("="*60)
    print("QUICK COMPLETE ETL - Essential Steps Only")
    print("="*60)
    print("\nThis will:")
    print("  1. Update metrics in Fact_Orders (total_items, reorder_ratio)")
    print("  2. Populate Dim_User")
    print("\n⚠️  SKIPPING: time_id update in Fact_Order_Details")
    print("   (Not needed - Dashboard can JOIN with Fact_Orders)")
    print("\nEstimated time: 5-10 minutes")
    print("="*60)
    
    start_time = time.time()
    
    try:
        engine = get_engine()
        print("✓ Database connection established")
        
        # Execute steps
        success = True
        success &= update_metrics(engine)
        success &= populate_dim_user(engine)
        
        if success:
            verify_data(engine)
            
            elapsed = time.time() - start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            
            print("\n" + "="*60)
            print(f"✓ ETL COMPLETED in {minutes}m {seconds}s")
            print("="*60)
            print("\n✅ Dashboard is now ready!")
            print("\nNext steps:")
            print("  1. Run dashboard: cd dashboard && streamlit run app.py")
            print("  2. Run data mining: ./run_mining.sh all")
            return 0
        else:
            print("\n✗ Some steps failed")
            return 1
            
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())



