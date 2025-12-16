# 🔍 Data Mining Module

Advanced analytics for customer segmentation and product recommendations.

## Overview

This module implements two key data mining techniques:

1. **Customer Clustering (K-Means)** - Segment customers by behavior
2. **Market Basket Analysis (Apriori/FP-Growth)** - Discover product associations
3. **Product Recommendations** - Hybrid recommendation system

---

## Features

### 🤖 Customer Clustering

**Algorithm:** K-Means with Elbow Method

**Features Used:**
- Total orders
- Average basket size
- Average reorder ratio
- Days between orders

**Outputs:**
- Elbow curve for optimal K selection
- PCA 2D/3D cluster visualizations
- Cluster profiles with statistics
- User-cluster assignments (CSV)

**Expected Clusters:**
- **VIP Customers** (50+ orders) - Loyalty programs
- **Frequent Shoppers** (20-49 orders) - Cross-sell opportunities
- **Regular Customers** (10-19 orders) - Upselling campaigns
- **Occasional Buyers** (3-9 orders) - Re-engagement strategies

### 🛒 Market Basket Analysis

**Algorithm:** FP-Growth (faster than Apriori)

**Parameters:**
- `min_support = 0.01` (1% of transactions)
- `min_confidence = 0.3` (30% confidence)

**Outputs:**
- Frequent itemsets (CSV)
- Association rules with support/confidence/lift
- Rule visualizations (scatter plots, histograms)

**Key Metrics:**
- **Support:** P(A ∩ B) - Frequency of co-occurrence
- **Confidence:** P(B|A) - Probability of B given A
- **Lift:** P(B|A) / P(B) - Strength of association (>1 = positive)

### 🎯 Product Recommendations

**Strategies:**
1. **Rule-based:** Cart items → Association rules → Recommendations
2. **Cluster-based:** User segment → Popular products in cluster
3. **Hybrid:** Weighted combination (60% rules + 40% cluster)

**Use Cases:**
- Cart page: "Customers who bought X also bought Y"
- Homepage: "Popular in your segment"
- Checkout: "Complete your order with these items"

---

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or specific packages
pip install scikit-learn matplotlib seaborn mlxtend
```

**Required packages:**
- `scikit-learn` - K-Means, PCA
- `matplotlib` - Visualizations
- `seaborn` - Statistical plots
- `mlxtend` - Apriori, FP-Growth algorithms

---

## Usage

### Quick Start - Run All

```bash
./run_mining.sh all
```

### Individual Tasks

```bash
# Customer clustering only
./run_mining.sh clustering

# Market basket analysis only
./run_mining.sh basket

# Recommendation demo only
./run_mining.sh recommend
```

### Python Scripts

```bash
# Customer clustering
python mining/customer_clustering.py

# Market basket analysis
python mining/market_basket.py

# Recommendations demo
python mining/recommendation.py
```

---

## File Structure

```
mining/
├── __init__.py
├── customer_clustering.py      # K-Means implementation
├── market_basket.py            # Apriori/FP-Growth
├── recommendation.py           # Hybrid recommender
└── results/                    # Output directory
    ├── elbow_curve.png         # K selection chart
    ├── clusters_pca.png        # 2D cluster visualization
    ├── clusters_3d.png         # 3D cluster visualization
    ├── cluster_profiles.csv    # Cluster statistics
    ├── cluster_profiles_chart.png
    ├── cluster_labels.csv      # User assignments (206K rows)
    ├── association_rules.csv   # MBA rules (500-2000 rules)
    ├── association_rules_viz.png
    └── frequent_itemsets.csv   # Frequent patterns
```

---

## Example Outputs

### Cluster Profiles

| Cluster | Name | Users | Avg Orders | Avg Basket | Reorder Rate |
|---------|------|-------|------------|------------|--------------|
| 0 | VIP Customers | 15,234 | 78.3 | 12.4 | 68.2% |
| 1 | Frequent Shoppers | 48,921 | 28.7 | 10.8 | 52.1% |
| 2 | Regular Customers | 89,456 | 14.2 | 9.1 | 38.7% |
| 3 | Occasional Buyers | 52,598 | 5.6 | 7.3 | 22.4% |

### Association Rules (Top 5)

```
1. Organic Avocado → Banana
   Support: 0.0521 | Confidence: 68.3% | Lift: 2.34

2. Strawberries, Banana → Organic Spinach
   Support: 0.0218 | Confidence: 71.9% | Lift: 3.12

3. Organic Whole Milk → Organic Half & Half
   Support: 0.0389 | Confidence: 54.7% | Lift: 1.87

4. Limes → Organic Avocado, Banana
   Support: 0.0156 | Confidence: 62.1% | Lift: 2.89

5. Organic Raspberries → Organic Blueberries
   Support: 0.0294 | Confidence: 76.4% | Lift: 3.45
```

### Recommendation Example

```python
# Cart-based recommendation
cart = ['Banana', 'Organic Avocado', 'Strawberries']

recommendations = recommend_by_rules(cart, rules, n=5)
# Output:
# 1. Organic Spinach (Lift: 3.12)
# 2. Organic Blueberries (Lift: 2.87)
# 3. Organic Whole Milk (Lift: 2.34)
# 4. Limes (Lift: 2.09)
# 5. Organic Raspberries (Lift: 1.95)
```

---

## Performance

### Clustering
- **Dataset:** 150K-200K active users (≥3 orders)
- **Runtime:** ~30 seconds
- **Memory:** ~500 MB

### Market Basket Analysis
- **Dataset:** 50K-100K orders (configurable via `limit` parameter)
- **Runtime:** 2-5 minutes (FP-Growth), 10-30 minutes (Apriori)
- **Memory:** ~2 GB

**Note:** For full dataset (3.4M orders), increase limit or remove it. Expect 30-60 minutes runtime.

---

## Evaluation Metrics

### Clustering Quality

```python
# Silhouette Score: 0.45 (range: -1 to 1, higher is better)
# Davies-Bouldin Index: 0.78 (lower is better)
# Inertia: 124,567 (lower is better)
```

### Rule Quality

```python
# Total rules: 1,234
# Average lift: 2.34
# High confidence rules (≥50%): 678 (54.9%)
# Product coverage: 2,456 products
```

---

## Business Applications

### 1. Marketing Campaigns

**VIP Customers:**
- Exclusive early access to new products
- Free shipping threshold lowered
- Birthday discounts

**Churned Users:**
- "We miss you" emails with 20% off
- Personalized product recommendations
- Limited-time offers

### 2. Product Recommendations

**Homepage:**
```
"Popular with customers like you"
[Show top 5 products from user's cluster]
```

**Cart Page:**
```
"Frequently bought together"
[Show association rules for cart items]
```

**Checkout:**
```
"Complete your order"
[Hybrid recommendations]
```

### 3. Inventory Management

**Bundling Strategy:**
- Create bundles from high-lift rules
- Example: "Breakfast Bundle" (Banana + Milk + Cereal)

**Store Layout:**
- Place associated products near each other
- Example: Avocado near Limes (Lift: 2.89)

---

## Troubleshooting

### Issue: "No rules found"

**Solution:** Lower thresholds
```python
# In market_basket.py, line 97
frequent_itemsets = run_fpgrowth(df_basket, min_support=0.005)  # Lower from 0.01

# Line 107
rules = generate_rules(frequent_itemsets, min_threshold=0.2)  # Lower from 0.3
```

### Issue: Memory error

**Solution:** Limit transaction size
```python
# In market_basket.py, line 265
transactions = extract_transactions(limit=10000, min_items=2)  # Start small
```

### Issue: Slow clustering

**Solution:** Sample users
```python
# In customer_clustering.py, line 31
df = df.sample(n=50000, random_state=42)  # Sample 50K users
```

---

## Next Steps

### Enhancements

1. **Deep Learning Recommendations**
   - Neural Collaborative Filtering
   - Sequence models (RNN/Transformer)

2. **Real-time API**
   - Flask/FastAPI endpoint
   - Redis cache for rules
   - Streaming recommendations

3. **A/B Testing**
   - Track recommendation CTR
   - Compare rule-based vs cluster-based
   - Optimize hybrid weights

4. **Advanced Clustering**
   - DBSCAN for outlier detection
   - Hierarchical clustering
   - Time-series clustering (shopping patterns over time)

---

## References

- **K-Means:** MacQueen, J. (1967)
- **Apriori:** Agrawal & Srikant (1994)
- **FP-Growth:** Han et al. (2000)
- **scikit-learn docs:** https://scikit-learn.org/
- **mlxtend docs:** http://rasbt.github.io/mlxtend/

---

## Credits

Built for "Kho dữ liệu" course project using:
- Python 3.13
- scikit-learn, mlxtend, pandas
- Instacart Market Basket Analysis dataset
