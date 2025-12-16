# 🛒 Instacart Analytics Dashboard

Interactive Streamlit dashboard for analyzing Instacart Data Warehouse insights.

## Features

### 📊 Overview Dashboard
- **KPI Cards:** Total orders, users, products, average basket size
- **Day of Week Analysis:** Order distribution across weekdays
- **Department Market Share:** Interactive pie chart showing top 10 departments
- **Hourly Trends:** Peak shopping hours visualization

### 🏆 Product Analytics
- **Top 20 Products:** Best-selling items with reorder rates
- **Aisle Analysis:** Reorder patterns by product aisle
- **Product Search:** Find and analyze specific products
- **Color-coded Metrics:** Reorder rates shown with heatmap colors

### ⏰ Time Analysis
- **Order Heatmap:** Hour x Day of Week visualization
- **Weekend vs Weekday:** Comparative behavior analysis
- **Hourly Patterns:** Separate trends for weekday/weekend
- **Peak Time Detection:** Automatic highlighting of busiest times

### 👥 Customer Analytics
- **Segmentation:** VIP (50+ orders), Regular (10-49), New (1-9)
- **Basket Size Distribution:** Order size grouping and analysis
- **Order Frequency:** Days since prior order patterns
- **Customer Insights:** Loyalty metrics and retention indicators

### 🏪 Department Performance
- **Sales Volume:** Total items sold by department
- **Reorder Rate Comparison:** Department-level loyalty metrics
- **Market Share:** Percentage breakdown of sales
- **Department Comparison Tool:** Side-by-side radar chart analysis

## Installation

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Install dashboard dependencies
pip install -r requirements.txt
# or
pip install streamlit plotly

# 3. Ensure database is running
docker start instacart-mariadb

# 4. Run ETL if not already done
python etl/etl_pipeline.py
```

## Usage

### Quick Start
```bash
# Run dashboard with helper script
./run_dashboard.sh
```

### Manual Start
```bash
streamlit run dashboard/app.py
```

Dashboard will open at: **http://localhost:8501**

## Project Structure

```
dashboard/
├── app.py                      # Main Streamlit app with routing
├── pages/                      # Dashboard pages
│   ├── __init__.py
│   ├── overview.py            # KPI metrics & overall trends
│   ├── products.py            # Product analysis & search
│   ├── time_analysis.py       # Temporal patterns & heatmaps
│   ├── customers.py           # Segmentation & behavior
│   └── departments.py         # Department performance
└── README.md                  # This file
```

## Key Visualizations

### Chart Types Used
- **Bar Charts:** Product rankings, department performance
- **Line Charts:** Hourly trends, temporal patterns
- **Pie Charts:** Market share, customer segments
- **Heatmaps:** Hour x Day order density
- **Scatter Plots:** Volume vs reorder rate correlation
- **Radar Charts:** Multi-metric department comparison

### Interactive Features
- **Filters:** Search products, select time periods
- **Tooltips:** Hover for detailed metrics
- **Drill-down:** Click to explore specific segments
- **Comparison Tools:** Side-by-side department analysis

## Database Connection

Dashboard uses `etl/config.py` for database connection:

```python
# Connects to: mariadb://dwh_user@localhost:3307/instacart_dwh
# Credentials loaded from .env file
```

Ensure `.env` file exists with:
```
DB_HOST=localhost
DB_PORT=3307
DB_USER=dwh_user
DB_PASSWORD=your_password
DB_NAME=instacart_dwh
```

## Performance Notes

- **Data Caching:** Uses `@st.cache_resource` for connection pooling
- **Query Optimization:** Indexed queries with partition pruning
- **Lazy Loading:** Charts load only when page is active
- **Error Handling:** Graceful fallback if data not yet loaded

## Screenshots

### Overview Page
```
┌──────────────────────────────────────────────────┐
│  3.4M Orders │ 206K Users │ 49K Products │ 10.1  │
└──────────────────────────────────────────────────┘
📅 Bar Chart: Orders by Day of Week
🏪 Pie Chart: Department Market Share
⏰ Line Chart: Hourly Order Trends with Peak Highlight
```

### Time Analysis Heatmap
```
🔥 Heatmap showing peak: Sunday 10AM, Monday 2PM
📊 Comparison: Weekend orders 15% higher than weekday
```

### Customer Segmentation
```
🎯 VIP: 8.3% of users generate 42.1% of orders
🛒 Most common basket: 6-10 items (35.2% of orders)
💎 51.3% of repeat orders within 7 days
```

## Troubleshooting

### Dashboard won't start
```bash
# Check if port 8501 is available
lsof -i :8501

# Or specify different port
streamlit run dashboard/app.py --server.port 8502
```

### No data showing
```bash
# Verify database has data
docker exec instacart-mariadb mariadb -u dwh_user -p instacart_dwh \
  -e "SELECT COUNT(*) FROM Fact_Orders;"

# If empty, run ETL
python etl/etl_pipeline.py
```

### Import errors
```bash
# Reinstall dependencies
pip install --upgrade streamlit plotly pandas
```

## Next Steps

After exploring the dashboard:
1. **Chapter 7 - Data Mining:** Customer clustering & product recommendations
2. **Deploy to Cloud:** Streamlit Cloud (free hosting)
3. **Add Authentication:** Streamlit-authenticator for user login
4. **Schedule Updates:** Automate ETL with cron jobs

## Credits

Built with:
- [Streamlit](https://streamlit.io/) - Web framework
- [Plotly](https://plotly.com/) - Interactive charts
- [Pandas](https://pandas.pydata.org/) - Data manipulation
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
