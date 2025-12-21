"""
Update aggregated metrics in Fact_Orders
- total_items: Count products per order
- reorder_ratio: Average reorder rate per order
"""
import time
from sqlalchemy import text
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from etl.config import get_engine

def update_fact_orders_metrics(engine):
    """Update total_items and reorder_ratio in Fact_Orders"""
    
    print("\n[1/2] Updating total_items...")
    print("   This will count products for each of 3.3M orders...")
    start = time.time()
    
    with engine.connect() as conn:
        # Update total_items (count products per order)
        result = conn.execute(text("""
            UPDATE Fact_Orders fo
            SET total_items = (
                SELECT COUNT(*)
                FROM Fact_Order_Details fod
                WHERE fod.order_id = fo.order_id
            )
        """))
        rows_affected = result.rowcount
        conn.commit()
    
    elapsed = time.time() - start
    print(f"   ✅ Updated {rows_affected:,} orders in {elapsed:.1f}s ({rows_affected/elapsed:.0f} rows/sec)")
    
    print("\n[2/2] Updating reorder_ratio...")
    print("   This will calculate average reorder rate per order...")
    start = time.time()
    
    with engine.connect() as conn:
        # Update reorder_ratio (average reorder rate per order)
        result = conn.execute(text("""
            UPDATE Fact_Orders fo
            SET reorder_ratio = (
                SELECT AVG(reordered)
                FROM Fact_Order_Details fod
                WHERE fod.order_id = fo.order_id
            )
        """))
        rows_affected = result.rowcount
        conn.commit()
    
    elapsed = time.time() - start
    print(f"   ✅ Updated {rows_affected:,} orders in {elapsed:.1f}s ({rows_affected/elapsed:.0f} rows/sec)")

def main():
    print("="*60)
    print("Updating Fact_Orders Metrics")
    print("="*60)
    print("⚠️  This will take 5-10 minutes for 3.3M orders")
    print("="*60)
    
    engine = get_engine()
    print("✅ Database connection established")
    
    total_start = time.time()
    update_fact_orders_metrics(engine)
    total_elapsed = time.time() - total_start
    
    print("\n" + "="*60)
    print("✅ All metrics updated!")
    print(f"Total time: {total_elapsed:.1f}s")
    print("="*60)
    
    # Verify
    print("\nVerifying sample data:")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                order_id, 
                total_items, 
                ROUND(reorder_ratio, 2) as reorder_ratio
            FROM Fact_Orders
            WHERE total_items > 0
            LIMIT 5
        """))
        
        print("\n  order_id | total_items | reorder_ratio")
        print("  " + "-"*42)
        for row in result:
            print(f"  {row[0]:8d} | {row[1]:11d} | {row[2]:13.2f}")
    
    print("\n✅ Metrics updated successfully!")
    print("\nNext: Re-run mining/recompute_cluster_profiles.py")

if __name__ == '__main__':
    main()
