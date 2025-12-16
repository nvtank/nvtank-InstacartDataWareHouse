#!/usr/bin/env python3
"""
Update metrics only - using temporary table to avoid locks
"""
import sys
import time
from sqlalchemy import text

sys.path.append('.')
from etl.config import get_engine

def update_metrics_safe(engine):
    """Update metrics using temporary table"""
    print("="*60)
    print("Updating Fact_Orders Metrics (Safe Method)")
    print("="*60)
    
    try:
        with engine.connect() as conn:
            # Step 1: Create temporary table with aggregated data
            print("\n[1/3] Creating temporary table with item counts...")
            start = time.time()
            conn.execute(text("""
                CREATE TEMPORARY TABLE temp_order_items AS
                SELECT 
                    order_id, 
                    COUNT(*) as item_count,
                    SUM(reordered) / COUNT(*) as reorder_ratio
                FROM Fact_Order_Details
                GROUP BY order_id
            """))
            conn.commit()
            elapsed = time.time() - start
            print(f"  ✓ Created temp table in {elapsed:.2f}s")
            
            # Step 2: Update total_items
            print("\n[2/3] Updating total_items...")
            start = time.time()
            conn.execute(text("""
                UPDATE Fact_Orders fo
                JOIN temp_order_items t ON fo.order_id = t.order_id
                SET fo.total_items = t.item_count
            """))
            conn.commit()
            elapsed = time.time() - start
            print(f"  ✓ Updated total_items in {elapsed:.2f}s")
            
            # Step 3: Update reorder_ratio
            print("\n[3/3] Updating reorder_ratio...")
            start = time.time()
            conn.execute(text("""
                UPDATE Fact_Orders fo
                JOIN temp_order_items t ON fo.order_id = t.order_id
                SET fo.reorder_ratio = t.reorder_ratio
            """))
            conn.commit()
            elapsed = time.time() - start
            print(f"  ✓ Updated reorder_ratio in {elapsed:.2f}s")
            
            # Verify
            result = conn.execute(text("""
                SELECT 
                    AVG(total_items) as avg_basket,
                    AVG(reorder_ratio) as avg_reorder
                FROM Fact_Orders
                LIMIT 1
            """))
            row = result.fetchone()
            print(f"\n  ✓ Average Basket Size: {row[0]:.2f} items")
            print(f"  ✓ Average Reorder Ratio: {row[1]:.2%}")
            
            return True
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    engine = get_engine()
    print("✓ Database connection established\n")
    
    if update_metrics_safe(engine):
        print("\n" + "="*60)
        print("✓ Metrics updated successfully!")
        print("="*60)
        print("\n✅ Dashboard is now ready!")
        print("   Run: cd dashboard && streamlit run app.py")
        sys.exit(0)
    else:
        print("\n✗ Failed to update metrics")
        sys.exit(1)



