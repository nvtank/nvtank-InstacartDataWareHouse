#!/bin/bash

# ============================================
# Run All SQL Analysis Queries
# ============================================
# Chạy tất cả 11 analytical queries và lưu kết quả
# ============================================

cd "$(dirname "$0")"
cd analysis

echo "=========================================="
echo "Running SQL Analysis Queries"
echo "=========================================="
echo ""

# Tạo thư mục results
mkdir -p ../sql_results

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Chạy từng query
queries=(
    "01_top_products:SELECT p.product_id, p.product_name, COUNT(*) as total_quantity, SUM(fod.reordered) as times_reordered, ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate_pct FROM Fact_Order_Details fod JOIN Dim_Product p ON fod.product_id = p.product_id GROUP BY p.product_id, p.product_name ORDER BY total_quantity DESC LIMIT 20"
    
    "02_peak_hours:SELECT t.order_hour, t.hour_range, CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END as day_type, COUNT(DISTINCT fo.order_id) as total_orders, COUNT(DISTINCT fo.user_id) as unique_users, ROUND(AVG(fo.total_items), 2) as avg_basket_size, ROUND(AVG(fo.reorder_ratio) * 100, 2) as avg_reorder_pct FROM Fact_Orders fo JOIN Dim_Time t ON fo.time_id = t.time_id GROUP BY t.order_hour, t.hour_range, day_type ORDER BY total_orders DESC"
    
    "03_day_of_week:SELECT t.order_dow, t.dow_name, t.is_weekend, COUNT(DISTINCT fo.order_id) as total_orders, COUNT(DISTINCT fo.user_id) as unique_users, ROUND(AVG(fo.total_items), 2) as avg_basket_size, ROUND(AVG(fo.days_since_prior_order), 2) as avg_days_between_orders, ROUND(AVG(fo.reorder_ratio) * 100, 2) as avg_reorder_pct FROM Fact_Orders fo JOIN Dim_Time t ON fo.time_id = t.time_id GROUP BY t.order_dow, t.dow_name, t.is_weekend ORDER BY t.order_dow"
    
    "04_department_performance:SELECT d.department_id, d.department_name, d.dept_category, COUNT(*) as total_items_sold, SUM(fod.reordered) as reordered_items, ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate_pct FROM Fact_Order_Details fod JOIN Dim_Product p ON fod.product_id = p.product_id JOIN Dim_Department d ON p.department_id = d.department_id GROUP BY d.department_id, d.department_name, d.dept_category ORDER BY total_items_sold DESC"
    
    "05_customer_segmentation:SELECT CASE WHEN u.total_orders >= 50 THEN 'VIP' WHEN u.total_orders >= 10 THEN 'Regular' ELSE 'New' END as user_segment, COUNT(DISTINCT u.user_id) as total_users, ROUND(COUNT(DISTINCT u.user_id) * 100.0 / (SELECT COUNT(*) FROM Dim_User), 2) as pct_users, ROUND(AVG(u.total_orders), 2) as avg_orders_per_user, ROUND(AVG(u.avg_basket_size), 2) as avg_basket_size, ROUND(AVG(u.avg_days_between_orders), 2) as avg_frequency_days, SUM(u.total_orders) as total_orders_by_segment, ROUND(SUM(u.total_orders) * 100.0 / (SELECT SUM(total_orders) FROM Dim_User), 2) as order_contribution_pct FROM Dim_User u GROUP BY user_segment ORDER BY CASE user_segment WHEN 'VIP' THEN 1 WHEN 'Regular' THEN 2 ELSE 3 END"
    
    "06_aisle_reorder_analysis:SELECT a.aisle_id, a.aisle_name, a.aisle_type, COUNT(*) as total_items, SUM(fod.reordered) as reordered_items, ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate_pct FROM Fact_Order_Details fod JOIN Dim_Product p ON fod.product_id = p.product_id JOIN Dim_Aisle a ON p.aisle_id = a.aisle_id GROUP BY a.aisle_id, a.aisle_name, a.aisle_type HAVING COUNT(*) >= 10000 ORDER BY reorder_rate_pct DESC LIMIT 20"
    
    "07_basket_size_distribution:SELECT CASE WHEN fo.total_items BETWEEN 1 AND 5 THEN '1-5 items' WHEN fo.total_items BETWEEN 6 AND 10 THEN '6-10 items' WHEN fo.total_items BETWEEN 11 AND 20 THEN '11-20 items' WHEN fo.total_items BETWEEN 21 AND 30 THEN '21-30 items' ELSE '30+ items' END as basket_size, COUNT(*) as orders, ROUND(AVG(fo.reorder_ratio) * 100, 1) as avg_reorder_rate FROM Fact_Orders fo GROUP BY basket_size ORDER BY MIN(fo.total_items)"
    
    "08_weekend_vs_weekday:SELECT CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END as day_type, COUNT(DISTINCT fo.order_id) as orders, AVG(fo.total_items) as avg_basket, AVG(fo.reorder_ratio) * 100 as avg_reorder FROM Fact_Orders fo JOIN Dim_Time t ON fo.time_id = t.time_id GROUP BY day_type"
    
    "09_product_reorder_patterns:SELECT p.product_id, p.product_name, COUNT(*) as total_purchases, SUM(CASE WHEN fod.reordered = 0 THEN 1 ELSE 0 END) as first_time_purchases, SUM(CASE WHEN fod.reordered = 1 THEN 1 ELSE 0 END) as reorder_purchases, ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate_pct FROM Fact_Order_Details fod JOIN Dim_Product p ON fod.product_id = p.product_id GROUP BY p.product_id, p.product_name HAVING COUNT(*) >= 5000 ORDER BY reorder_rate_pct DESC LIMIT 30"
)

# Chạy từng query
for query_info in "${queries[@]}"; do
    IFS=':' read -r query_name query_sql <<< "$query_info"
    
    echo -e "${YELLOW}Running: ${query_name}.sql...${NC}"
    start_time=$(date +%s)
    
    # Chạy query
    docker exec instacart-mariadb mariadb -u dwh_user -pdwh_pass123 instacart_dwh -e "$query_sql" > "../sql_results/${query_name}.txt" 2>&1
    
    end_time=$(date +%s)
    elapsed=$((end_time - start_time))
    
    if [ -s "../sql_results/${query_name}.txt" ]; then
        lines=$(wc -l < "../sql_results/${query_name}.txt")
        echo -e "${GREEN}  ✓ Done in ${elapsed}s: $lines lines${NC}"
        head -3 "../sql_results/${query_name}.txt" | sed 's/^/    /'
    else
        echo -e "${RED}  ⚠ Empty or error after ${elapsed}s${NC}"
        head -5 "../sql_results/${query_name}.txt" | sed 's/^/    /'
    fi
    echo ""
done

# Chạy query 10 và 11 từ file (phức tạp hơn)
echo -e "${YELLOW}Running: 10_partition_performance_test.sql...${NC}"
start_time=$(date +%s)
grep -v "^USE" "10_partition_performance_test.sql" | grep -v "^--" | \
docker exec -i instacart-mariadb mariadb -u dwh_user -pdwh_pass123 instacart_dwh \
> "../sql_results/10_partition_performance_test.txt" 2>&1
end_time=$(date +%s)
elapsed=$((end_time - start_time))
if [ -s "../sql_results/10_partition_performance_test.txt" ]; then
    lines=$(wc -l < "../sql_results/10_partition_performance_test.txt")
    echo -e "${GREEN}  ✓ Done in ${elapsed}s: $lines lines${NC}"
else
    echo -e "${RED}  ⚠ Empty or error${NC}"
fi
echo ""

echo -e "${YELLOW}Running: 11_summary_statistics.sql...${NC}"
start_time=$(date +%s)
grep -v "^USE" "11_summary_statistics.sql" | grep -v "^--" | \
docker exec -i instacart-mariadb mariadb -u dwh_user -pdwh_pass123 instacart_dwh \
> "../sql_results/11_summary_statistics.txt" 2>&1
end_time=$(date +%s)
elapsed=$((end_time - start_time))
if [ -s "../sql_results/11_summary_statistics.txt" ]; then
    lines=$(wc -l < "../sql_results/11_summary_statistics.txt")
    echo -e "${GREEN}  ✓ Done in ${elapsed}s: $lines lines${NC}"
else
    echo -e "${RED}  ⚠ Empty or error${NC}"
fi
echo ""

# Tổng kết
echo "=========================================="
echo -e "${GREEN}SQL Analysis Complete!${NC}"
echo "=========================================="
echo ""
echo "Results saved in: sql_results/"
echo ""
echo "Summary:"
for file in ../sql_results/*.txt; do
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file" 2>/dev/null || echo 0)
        size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo 0)
        echo "  $(basename $file): $lines lines, ${size} bytes"
    fi
done

