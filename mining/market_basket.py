"""
Market Basket Analysis using Apriori and FP-Growth
Discovers association rules between products
"""

import pandas as pd
import numpy as np
from mlxtend.frequent_patterns import apriori, fpgrowth, association_rules
from mlxtend.preprocessing import TransactionEncoder
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import os
import time
sys.path.append('..')
from etl.config import get_engine

# Set style
sns.set_style("whitegrid")

def extract_transactions(limit=None, min_items=2):
    """Extract transaction baskets from DWH"""
    print("\n📊 Extracting transactions from database...")
    engine = get_engine()
    
    query = """
    SELECT 
        fod.order_id,
        p.product_name,
        p.product_id
    FROM Fact_Order_Details fod
    JOIN Dim_Product p ON fod.product_id = p.product_id
    ORDER BY fod.order_id
    """
    
    if limit:
        query = f"""
        SELECT 
            fod.order_id,
            p.product_name,
            p.product_id
        FROM Fact_Order_Details fod
        JOIN Dim_Product p ON fod.product_id = p.product_id
        WHERE fod.order_id IN (
            SELECT DISTINCT order_id 
            FROM Fact_Order_Details 
            LIMIT {limit}
        )
        ORDER BY fod.order_id
        """
    
    df = pd.read_sql(query, engine)
    print(f"✅ Extracted {len(df):,} transaction items from {df['order_id'].nunique():,} orders")
    
    # Group by order to create baskets
    transactions = df.groupby('order_id')['product_name'].apply(list).tolist()
    
    # Filter baskets with minimum items
    transactions_filtered = [basket for basket in transactions if len(basket) >= min_items]
    
    print(f"✅ Created {len(transactions_filtered):,} transaction baskets (min {min_items} items)")
    print(f"   Avg basket size: {np.mean([len(b) for b in transactions_filtered]):.1f} items")
    
    return transactions_filtered

def create_basket_matrix(transactions):
    """Convert transaction list to one-hot encoded DataFrame"""
    print("\n🔄 Creating basket matrix...")
    
    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions)
    df_basket = pd.DataFrame(te_ary, columns=te.columns_)
    
    print(f"✅ Basket matrix shape: {df_basket.shape[0]:,} orders × {df_basket.shape[1]:,} products")
    
    # Calculate product frequencies
    product_freq = df_basket.sum().sort_values(ascending=False)
    print(f"   Most frequent products:")
    for product, freq in product_freq.head(10).items():
        pct = (freq / len(df_basket)) * 100
        print(f"     - {product}: {int(freq):,} orders ({pct:.2f}%)")
    
    return df_basket

def run_fpgrowth(df_basket, min_support=0.01):
    """Run FP-Growth algorithm (faster than Apriori)"""
    print(f"\n🚀 Running FP-Growth algorithm (min_support={min_support})...")
    
    start_time = time.time()
    
    frequent_itemsets = fpgrowth(
        df_basket, 
        min_support=min_support, 
        use_colnames=True,
        max_len=None  # No limit on itemset size
    )
    
    elapsed_time = time.time() - start_time
    
    print(f"✅ Found {len(frequent_itemsets):,} frequent itemsets in {elapsed_time:.2f} seconds")
    
    # Show itemset size distribution
    frequent_itemsets['length'] = frequent_itemsets['itemsets'].apply(len)
    size_dist = frequent_itemsets['length'].value_counts().sort_index()
    
    print(f"\n   Itemset size distribution:")
    for size, count in size_dist.items():
        print(f"     Size {size}: {count:,} itemsets")
    
    return frequent_itemsets

def run_apriori(df_basket, min_support=0.01):
    """Run Apriori algorithm (slower but classic)"""
    print(f"\n🔍 Running Apriori algorithm (min_support={min_support})...")
    
    start_time = time.time()
    
    frequent_itemsets = apriori(
        df_basket,
        min_support=min_support,
        use_colnames=True,
        max_len=None
    )
    
    elapsed_time = time.time() - start_time
    
    print(f"✅ Found {len(frequent_itemsets):,} frequent itemsets in {elapsed_time:.2f} seconds")
    
    return frequent_itemsets

def generate_rules(frequent_itemsets, metric="confidence", min_threshold=0.3):
    """Generate association rules from frequent itemsets"""
    print(f"\n📋 Generating association rules (min_{metric}={min_threshold})...")
    
    rules = association_rules(
        frequent_itemsets,
        metric=metric,
        min_threshold=min_threshold,
        support_only=False
    )
    
    if len(rules) == 0:
        print("⚠️ No rules found! Try lowering the threshold.")
        return rules
    
    # Sort by lift (descending)
    rules = rules.sort_values('lift', ascending=False)
    
    print(f"✅ Generated {len(rules):,} association rules")
    
    # Statistics
    print(f"\n   Rule statistics:")
    print(f"     Avg support: {rules['support'].mean():.4f}")
    print(f"     Avg confidence: {rules['confidence'].mean():.2%}")
    print(f"     Avg lift: {rules['lift'].mean():.2f}")
    print(f"     Max lift: {rules['lift'].max():.2f}")
    
    return rules

def display_top_rules(rules, n=20):
    """Display top N rules in readable format"""
    print(f"\n{'=' * 100}")
    print(f"TOP {n} ASSOCIATION RULES (sorted by Lift)")
    print('=' * 100)
    
    if len(rules) == 0:
        print("No rules to display.")
        return
    
    top_rules = rules.head(n)
    
    for i, (idx, row) in enumerate(top_rules.iterrows(), 1):
        antecedents = ', '.join(sorted(list(row['antecedents'])))
        consequents = ', '.join(sorted(list(row['consequents'])))
        
        # Truncate long names
        if len(antecedents) > 60:
            antecedents = antecedents[:57] + '...'
        if len(consequents) > 60:
            consequents = consequents[:57] + '...'
        
        print(f"\n{i}. {antecedents}")
        print(f"   → {consequents}")
        print(f"   Support: {row['support']:.4f} | Confidence: {row['confidence']:.2%} | Lift: {row['lift']:.2f}")

def visualize_rules(rules, top_n=50):
    """Create visualizations for association rules"""
    print(f"\n📊 Creating rule visualizations (top {top_n})...")
    
    if len(rules) == 0:
        print("⚠️ No rules to visualize")
        return
    
    top_rules = rules.head(top_n)
    
    # Plot 1: Support vs Confidence scatter
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # Scatter: Support vs Confidence (colored by Lift)
    scatter = axes[0, 0].scatter(
        top_rules['support'],
        top_rules['confidence'],
        c=top_rules['lift'],
        cmap='viridis',
        s=100,
        alpha=0.6,
        edgecolors='w',
        linewidth=0.5
    )
    axes[0, 0].set_xlabel('Support', fontsize=12)
    axes[0, 0].set_ylabel('Confidence', fontsize=12)
    axes[0, 0].set_title('Support vs Confidence (colored by Lift)', fontsize=13, fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=axes[0, 0], label='Lift')
    
    # Histogram: Lift distribution
    axes[0, 1].hist(top_rules['lift'], bins=30, color='skyblue', edgecolor='black', alpha=0.7)
    axes[0, 1].set_xlabel('Lift', fontsize=12)
    axes[0, 1].set_ylabel('Frequency', fontsize=12)
    axes[0, 1].set_title('Lift Distribution', fontsize=13, fontweight='bold')
    axes[0, 1].axvline(1, color='red', linestyle='--', label='Lift=1 (Independence)')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # Bar chart: Top 15 rules by lift
    top_15 = top_rules.head(15).copy()
    top_15['rule'] = top_15.apply(
        lambda x: f"{list(x['antecedents'])[0][:20]} → {list(x['consequents'])[0][:20]}", 
        axis=1
    )
    
    axes[1, 0].barh(range(len(top_15)), top_15['lift'], color='coral')
    axes[1, 0].set_yticks(range(len(top_15)))
    axes[1, 0].set_yticklabels(top_15['rule'], fontsize=9)
    axes[1, 0].set_xlabel('Lift', fontsize=12)
    axes[1, 0].set_title('Top 15 Rules by Lift', fontsize=13, fontweight='bold')
    axes[1, 0].invert_yaxis()
    axes[1, 0].grid(True, alpha=0.3, axis='x')
    
    # Scatter: Support vs Lift
    axes[1, 1].scatter(
        top_rules['support'],
        top_rules['lift'],
        c=top_rules['confidence'],
        cmap='plasma',
        s=100,
        alpha=0.6,
        edgecolors='w',
        linewidth=0.5
    )
    axes[1, 1].set_xlabel('Support', fontsize=12)
    axes[1, 1].set_ylabel('Lift', fontsize=12)
    axes[1, 1].set_title('Support vs Lift (colored by Confidence)', fontsize=13, fontweight='bold')
    axes[1, 1].axhline(1, color='red', linestyle='--', alpha=0.5)
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('mining/results/association_rules_viz.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved visualizations to mining/results/association_rules_viz.png")
    plt.close()

def save_rules(rules, filename='mining/results/association_rules.csv'):
    """Save association rules to CSV"""
    print(f"\n💾 Saving rules to CSV...")
    
    if len(rules) == 0:
        print("⚠️ No rules to save")
        return
    
    # Create export DataFrame
    rules_export = rules.copy()
    
    # Convert frozensets to readable strings
    rules_export['antecedents_str'] = rules_export['antecedents'].apply(
        lambda x: ', '.join(sorted(list(x)))
    )
    rules_export['consequents_str'] = rules_export['consequents'].apply(
        lambda x: ', '.join(sorted(list(x)))
    )
    
    # Select and reorder columns
    export_cols = [
        'antecedents_str', 'consequents_str', 
        'support', 'confidence', 'lift',
        'leverage', 'conviction'
    ]
    
    rules_export = rules_export[export_cols]
    rules_export.columns = [
        'Antecedents', 'Consequents',
        'Support', 'Confidence', 'Lift',
        'Leverage', 'Conviction'
    ]
    
    rules_export.to_csv(filename, index=False)
    print(f"✅ Saved {len(rules_export):,} rules to {filename}")

def main():
    """Main execution function"""
    print("=" * 80)
    print(" " * 20 + "MARKET BASKET ANALYSIS")
    print("=" * 80)
    
    # Create results directory
    os.makedirs('mining/results', exist_ok=True)
    
    try:
        # Step 1: Extract transactions (limit for demo - remove limit for full analysis)
        transactions = extract_transactions(limit=50000, min_items=2)  # 50K orders
        
        # Step 2: Create basket matrix
        df_basket = create_basket_matrix(transactions)
        
        # Step 3: Run FP-Growth (faster than Apriori)
        frequent_itemsets = run_fpgrowth(df_basket, min_support=0.01)
        
        # Alternative: Run Apriori (uncomment to compare)
        # frequent_itemsets = run_apriori(df_basket, min_support=0.01)
        
        # Step 4: Generate association rules
        rules = generate_rules(frequent_itemsets, metric="confidence", min_threshold=0.3)
        
        # Step 5: Display top rules
        display_top_rules(rules, n=20)
        
        # Step 6: Visualize rules
        visualize_rules(rules, top_n=50)
        
        # Step 7: Save results
        save_rules(rules)
        
        # Save frequent itemsets too
        if len(frequent_itemsets) > 0:
            itemsets_export = frequent_itemsets.copy()
            itemsets_export['itemsets_str'] = itemsets_export['itemsets'].apply(
                lambda x: ', '.join(sorted(list(x)))
            )
            itemsets_export[['itemsets_str', 'support']].to_csv(
                'mining/results/frequent_itemsets.csv',
                index=False
            )
            print(f"✅ Saved {len(itemsets_export):,} frequent itemsets to mining/results/frequent_itemsets.csv")
        
        print("\n" + "=" * 80)
        print("✅ MARKET BASKET ANALYSIS COMPLETE!")
        print("=" * 80)
        print("\n📁 Generated files:")
        print("   - mining/results/association_rules.csv")
        print("   - mining/results/association_rules_viz.png")
        print("   - mining/results/frequent_itemsets.csv")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
