# Dashboard Optimization Notes

## Vấn đề đã sửa:

### 1. ✅ Sửa Warnings về `use_container_width`
- Thay thế tất cả `use_container_width=True` → `width='stretch'`
- Thay thế tất cả `use_container_width=False` → `width='content'`
- Sửa trong tất cả 5 pages

### 2. ✅ Thêm Caching cho Queries
- Thêm `@st.cache_data(ttl=300-600)` cho các queries chậm
- Cache 5-10 phút để giảm load time
- Đã cache trong `overview.py` và `products.py`

### 3. ⚠️ Cần tối ưu thêm:

#### Queries chậm nhất:
1. **Top Products** - JOIN 33M rows → Đã cache
2. **Market Share by Department** - JOIN 33M rows → Đã cache  
3. **Customer Segmentation** - GROUP BY 206K users → Cần cache
4. **Time Heatmap** - GROUP BY 3.3M orders → Cần cache
5. **Department Performance** - JOIN 33M rows → Cần cache

#### Giải pháp:
- Thêm caching cho tất cả queries
- Thêm loading spinners
- Tối ưu queries với LIMIT và indexes
- Có thể tạo materialized views nếu cần

### 4. 🔧 Nếu vẫn chậm:

1. **Tăng cache TTL**: Từ 300s → 1800s (30 phút)
2. **Tạo indexes**:
   ```sql
   CREATE INDEX idx_fod_product ON Fact_Order_Details(product_id);
   CREATE INDEX idx_fod_order ON Fact_Order_Details(order_id);
   ```
3. **Tối ưu queries**: Thêm WHERE clauses để filter sớm
4. **Materialized Views**: Tạo pre-aggregated tables

### 5. 📊 Performance Monitoring:

Kiểm tra query time:
```sql
EXPLAIN SELECT ... -- Xem execution plan
SHOW PROCESSLIST; -- Xem queries đang chạy
```

---

**Status**: Đã sửa warnings và thêm caching cho overview + products pages.
**Next**: Cần thêm caching cho customers, time_analysis, departments pages.



