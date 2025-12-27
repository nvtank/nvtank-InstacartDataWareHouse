# 🛒 Instacart Data Warehouse Project

**Building a Data Warehouse for Instacart: Shopping Behavior Analysis and Product Recommendations**

---

## 📚 Project Overview

- **Course:** Data Warehouse
- **Dataset:** Instacart Market Basket Analysis
  - 3.4M orders (3,124,301 records)
  - 33M order items (31,843,317 records)
  - 206K users (205,700 records)
  - 49K products (49,596 records)
  - 21 departments, 134 aisles
- **Tech Stack:** MariaDB 12.1, Python 3.13, Streamlit, scikit-learn, mlxtend
- **Architecture:** Constellation Schema with LIST + RANGE Partitioning
- **Total Size:** ~1.8 GB (with indexes)

---

## 📁 Project Structure

```
Instacart/
├── data/                       # CSV dataset files (681 MB)
├── sql/                        # SQL scripts (11 files)
│   ├── 01_create_database.sql
│   ├── 02-06_dim_*.sql         # Dimension tables
│   ├── 07-08_fact_*.sql        # Fact tables (partitioned)
│   └── 09-11_*.sql             # Indexes, checks, maintenance
├── etl/                        # Python ETL Pipeline
│   ├── config.py               # Database connection
│   ├── load_dimensions.py      # Load dimension tables
│   ├── load_facts.py           # Load fact tables
│   └── etl_pipeline.py         # Main orchestrator
├── analysis/                   # SQL Analytical Queries (11 files)
├── sql_results/                # Query results
├── dashboard/                  # Streamlit Dashboard
│   ├── app.py                  # Main app
│   └── pages/                  # 5 dashboard pages
├── mining/                     # Data Mining Module
│   ├── customer_clustering.py  # K-Means clustering
│   ├── market_basket.py        # FP-Growth association rules
│   └── recommendation.py       # Hybrid recommender
└── requirements.txt
```

---

## 🗄️ Database Schema

### Constellation Schema

**Dimension Tables:**
- `Dim_Time` (168 rows): Time dimension (7 days × 24 hours)
- `Dim_User` (206K rows): Customer profiles with metrics
- `Dim_Product` (49K rows): Product catalog
- `Dim_Aisle` (134 rows): Product aisles
- `Dim_Department` (21 rows): Department hierarchy

**Fact Tables:**
- `Fact_Orders` (3.1M rows, 7 partitions): Orders with LIST partitioning by day of week
- `Fact_Order_Details` (31.8M rows, 8 partitions): Order items with RANGE partitioning by order_id

**Total:** 15 partitions, 36.6M rows, ~1.8 GB

---

## ⚙️ Configuration

```bash
# MariaDB Docker Container
Host: localhost:3307
Database: instacart_dwh
User: dwh_user
Password: dwh_pass123
```

**Start Docker Container:**
```bash
docker run -d \
  --name instacart-mariadb \
  -p 3307:3306 \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=instacart_dwh \
  -e MYSQL_USER=dwh_user \
  -e MYSQL_PASSWORD=dwh_pass123 \
  mariadb:latest
```

**Environment Variables (`.env`):**
```
DB_HOST=localhost
DB_PORT=3307
DB_USER=dwh_user
DB_PASSWORD=dwh_pass123
DB_NAME=instacart_dwh
DATA_PATH=./data
```

---

## 🔄 ETL Pipeline

### ETL Process
1. **Load Dimensions** → 5 dimension tables
2. **Load Facts** → 2 fact tables (chunked loading)
3. **Update References** → Link time_id to Dim_Time
4. **Compute Metrics** → Order metrics and user aggregations

### Performance
- **Total Records:** 36.6M rows
- **Total Time:** 30-45 minutes
- **Throughput:** ~1,380 rows/second
- **Chunk Size:** 50,000 rows per batch

### Run ETL
```bash
python etl/etl_pipeline.py
```

---

## 📊 SQL Analysis

### 11 Analytical Queries
1. **Top Products** - Best-selling products
2. **Peak Hours** - Busiest order times
3. **Day of Week** - Weekly trends
4. **Department Performance** - Sales by department
5. **Customer Segmentation** - User segments
6. **Aisle Reorder Analysis** - Reorder rates by aisle
7. **Basket Size Distribution** - Cart size patterns
8. **Weekend vs Weekday** - Period comparison
9. **Product Reorder Patterns** - Repurchase behavior
10. **Partition Performance** - Query optimization test
11. **Summary Statistics** - Overall metrics

### Key Insights
- 🥇 **Top Product:** Banana (488K items, 84.48% reorder rate)
- 🏆 **Top Department:** Produce (9.8M items, 65.04% reorder rate)
- 💎 **VIP Customers:** 867 users (0.42%) with 50+ orders
- 🥛 **Highest Reorder:** Milk aisle (78.18%)

### Run Analysis
```bash
./run_sql_analysis.sh
```

---

## 📈 Interactive Dashboard

### 5 Dashboard Pages
1. **Overview** - KPIs, trends, department breakdown
2. **Products** - Top products, aisle analysis
3. **Time Analysis** - Order heatmap, peak times
4. **Customers** - Segmentation, basket distribution
5. **Departments** - Sales volume, reorder comparison

### Features
- ✅ Real-time data from MariaDB
- ✅ Interactive Plotly charts
- ✅ Data caching for performance
- ✅ Responsive design

### Launch Dashboard
```bash
./run_dashboard.sh
# Access: http://localhost:8501
```

---

## 🔍 Data Mining

### 3 Mining Modules

**1. Customer Clustering (K-Means)**
- 4 segments: VIP, Frequent, Regular, Occasional
- Features: Orders, basket size, reorder rate, days between orders
- Visualizations: PCA 2D/3D, elbow curve

**2. Market Basket Analysis (FP-Growth)**
- Association rules with min_support=0.01, min_confidence=0.3
- 500-2000 rules generated
- Metrics: Support, confidence, lift

**3. Product Recommendations (Hybrid)**
- Rule-based: Cart items → Association rules
- Cluster-based: User segment → Popular products
- Weighted combination: 60% rules + 40% cluster

### Run Data Mining
```bash
./run_mining.sh all
```

---

## 🚀 Quick Start

### 1. Start Database
```bash
docker start instacart-mariadb
```

### 2. Setup Python Environment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create Database Schema
```bash
cd sql
./run_all_sql.sh
```

### 4. Run ETL Pipeline
```bash
python etl/etl_pipeline.py
```

### 5. Launch Dashboard
```bash
./run_dashboard.sh
```

### 6. Run SQL Analysis
```bash
./run_sql_analysis.sh
```

### 7. Run Data Mining
```bash
./run_mining.sh all
```

---

## 📈 Results

### Performance
- ✅ **Partition Pruning:** 7x speedup for date-filtered queries
- ✅ **Query Time:** <1 second for most analytical queries
- ✅ **ETL Success Rate:** 100% (all records loaded)
- ✅ **Dashboard Load Time:** <2 seconds

### Deliverables
- ✅ Database Schema (7 tables, 15 partitions)
- ✅ ETL Pipeline (36.6M rows loaded)
- ✅ SQL Analysis (11 queries executed)
- ✅ Interactive Dashboard (5 pages)
- ✅ Data Mining (Clustering + Association Rules)

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | MariaDB 12.1 | Data warehouse with partitioning |
| ETL | Python 3.13, Pandas, SQLAlchemy | Data pipeline |
| Analytics | SQL | Business intelligence queries |
| Dashboard | Streamlit, Plotly | Interactive visualization |
| Machine Learning | scikit-learn | K-Means clustering |
| Association Mining | mlxtend | FP-Growth algorithm |
| Container | Docker | MariaDB deployment |

---

## 🔧 Troubleshooting

**Database Connection Issues:**
```bash
docker restart instacart-mariadb
docker logs instacart-mariadb
```

**ETL Errors:**
```bash
cat .env  # Check configuration
python -c "from etl.config import get_engine; print(get_engine())"
```

**Dashboard No Data:**
```bash
# Check if data is loaded
docker exec instacart-mariadb mariadb -u dwh_user -pdwh_pass123 instacart_dwh \
  -e "SELECT COUNT(*) FROM Fact_Orders;"
```

---

## 🎯 Key Features

✅ **Advanced Partitioning:** LIST + RANGE for performance optimization  
✅ **Code-First Approach:** Python/SQL scripts (no GUI tools)  
✅ **Interactive Dashboard:** 5 pages with Plotly visualizations  
✅ **Advanced Analytics:** K-Means clustering + FP-Growth rules  
✅ **Production-Ready:** Docker deployment, error handling  
✅ **Comprehensive Analysis:** 11 SQL queries + Mining + Dashboard  

---

## 📊 Project Stats

- **Code Lines:** ~5,000+ (Python + SQL)
- **Database Tables:** 7 tables (2 facts + 5 dimensions)
- **Partitions:** 15 partitions
- **SQL Queries:** 11 analytical queries
- **Dashboard Pages:** 5 interactive pages
- **Mining Algorithms:** 2 (K-Means + FP-Growth)
- **Total Data:** 36.6M rows, ~1.8 GB

---

## 📝 License

Educational project for Data Warehouse course.  
Dataset: [Instacart Market Basket Analysis](https://www.kaggle.com/c/instacart-market-basket-analysis) (Kaggle)

---

**Status:** ✅ **Project Complete**

```
Instacart/
├── data/                       # Dataset CSV files (681 MB)
│   ├── orders.csv
│   ├── order_products__prior.csv
│   ├── products.csv
│   ├── departments.csv
│   ├── aisles.csv
│   └── users.csv
│
├── sql/                        # SQL scripts (11 files)
│   ├── 01_create_database.sql
│   ├── 02_dim_time.sql
│   ├── 03_dim_department.sql
│   ├── 04_dim_aisle.sql
│   ├── 05_dim_product.sql
│   ├── 06_dim_user.sql
│   ├── 07_fact_orders.sql      # LIST partitioning (7 partitions)
│   ├── 08_fact_order_details.sql  # RANGE partitioning (8 partitions)
│   ├── 09_additional_indexes.sql
│   ├── 10_check_partitions.sql
│   ├── 11_maintenance.sql
│   └── run_all_sql.sh
│
├── etl/                        # Python ETL Pipeline (4 scripts)
│   ├── config.py               # Database connection config
│   ├── load_dimensions.py      # Load 5 dimension tables
│   ├── load_facts.py           # Load 2 fact tables
│   ├── update_time_id.py       # Update time_id references
│   └── etl_pipeline.py         # Main orchestrator
│
├── analysis/                   # SQL Analytical Queries (11 files)
│   ├── 01_top_products.sql
│   ├── 02_peak_hours.sql
│   ├── 03_day_of_week.sql
│   ├── 04_department_performance.sql
│   ├── 05_customer_segmentation.sql
│   ├── 06_aisle_reorder_analysis.sql
│   ├── 07_basket_size_distribution.sql
│   ├── 08_weekend_vs_weekday.sql
│   ├── 09_product_reorder_patterns.sql
│   ├── 10_partition_performance_test.sql
│   ├── 11_summary_statistics.sql
│   └── run_sql_analysis.sh      # Run all queries
│
├── sql_results/                # SQL Analysis Results (11 files)
│   ├── 01_top_products.txt
│   ├── 02_peak_hours.txt
│   └── ... (9 more files)
│
├── dashboard/                  # Streamlit Interactive Dashboard
│   ├── app.py                  # Main app with routing
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── overview.py         # KPI cards & overall trends
│   │   ├── products.py          # Product analytics
│   │   ├── time_analysis.py     # Temporal patterns
│   │   ├── customers.py         # Customer segmentation
│   │   └── departments.py       # Department performance
│   └── README.md
│
├── mining/                     # Data Mining Module
│   ├── customer_clustering.py  # K-Means clustering
│   ├── market_basket.py        # FP-Growth association rules
│   ├── recommendation.py       # Hybrid recommender system
│   ├── results/                # Output files
│   │   ├── cluster_profiles.csv
│   │   ├── association_rules.csv
│   │   └── *.png (visualizations)
│   └── README.md
│
├── requirements.txt            # Python dependencies
├── run_complete.sh             # Master script (setup → dashboard)
├── run_dashboard.sh            # Launch dashboard
├── run_mining.sh               # Run data mining
├── run_sql_analysis.sh         # Run SQL analysis
└── README.md                   # This file

**Status:** ✅ **Project Complete**
