"""
Quick script to update time_id in Fact_Order_Details
Run this if ETL was interrupted during time_id update
"""
import time
from sqlalchemy import text
from config import get_engine

def update_time_id_by_partition():
    """Update time_id using partition-aware batching"""
    print("="*60)
    print("Updating time_id in Fact_Order_Details")
    print("="*60)
    
    engine = get_engine()
    
    partitions = ['p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p_max']
    total_start = time.time()
    
    print(f"\nProcessing {len(partitions)} partitions...")
    
    for i, partition in enumerate(partitions, 1):
        partition_start = time.time()
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"""
                    UPDATE Fact_Order_Details PARTITION ({partition}) fod
                    JOIN Fact_Orders fo ON fod.order_id = fo.order_id
                    SET fod.time_id = fo.time_id
                    WHERE fod.time_id = 0
                """))
                rows_affected = result.rowcount
                conn.commit()
                
                partition_elapsed = time.time() - partition_start
                print(f"  [{i}/{len(partitions)}] Partition {partition}: {rows_affected:,} rows updated in {partition_elapsed:.1f}s")
                
        except Exception as e:
            print(f"  ✗ Error on partition {partition}: {e}")
            continue
    
    total_elapsed = time.time() - total_start
    print(f"\n✓ All partitions processed in {total_elapsed:.1f}s")
    
    # Verify
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM Fact_Order_Details WHERE time_id = 0"))
        remaining = result.fetchone()[0]
        
        if remaining > 0:
            print(f"⚠️  Warning: {remaining:,} rows still have time_id = 0")
        else:
            print("✓ All rows have valid time_id")

if __name__ == '__main__':
    update_time_id_by_partition()
