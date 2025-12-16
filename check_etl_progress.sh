echo "📊 Kiểm tra tiến độ ETL Pipeline"
echo "=================================="
echo ""

# Kiểm tra process ETL có đang chạy không
if pgrep -f "etl_pipeline.py" > /dev/null; then
    echo "✅ ETL đang chạy (PID: $(pgrep -f etl_pipeline.py))"
else
    echo "❌ ETL không chạy"
fi

echo ""
echo "📈 Số lượng records hiện tại:"
echo "=================================="

docker exec instacart-mariadb mariadb -u dwh_user -pdwh_pass123 instacart_dwh -e "
SELECT 
    'Dim_Product' as table_name, 
    COUNT(*) as current_rows,
    '49,688' as expected_rows
FROM Dim_Product
UNION ALL
SELECT 
    'Fact_Orders', 
    COUNT(*),
    '3,346,083'
FROM Fact_Orders
UNION ALL
SELECT 
    'Fact_Order_Details', 
    COUNT(*),
    '33,819,106'
FROM Fact_Order_Details
UNION ALL
SELECT 
    'Dim_User',
    COUNT(*),
    '206,209'
FROM Dim_User;
"

echo ""
echo "📝 Log ETL (10 dòng cuối):"
echo "=================================="
tail -10 etl_output.log 2>/dev/null || echo "Chưa có log file"

echo ""
echo "💡 Chạy lại script này để xem tiến độ: ./check_etl_progress.sh"

