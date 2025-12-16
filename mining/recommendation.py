"""
Product Recommendation System
Combines clustering and association rules for personalized recommendations
"""

import pandas as pd
import numpy as np
import sys
sys.path.append('..')
from etl.config import get_engine

def load_association_rules():
    """Load pre-computed association rules"""
    try:
        rules = pd.read_csv('mining/results/association_rules.csv')
        print(f"✅ Loaded {len(rules):,} association rules")
        return rules
    except FileNotFoundError:
        print("❌ Association rules not found. Please run market_basket.py first.")
        return None

def load_cluster_labels():
    """Load user cluster assignments"""
    try:
        clusters = pd.read_csv('mining/results/cluster_labels.csv')
        print(f"✅ Loaded {len(clusters):,} user cluster labels")
        return clusters
    except FileNotFoundError:
        print("❌ Cluster labels not found. Please run customer_clustering.py first.")
        return None

def recommend_by_rules(cart_items, rules, n=5):
    """
    Recommend products based on association rules
    
    Args:
        cart_items: List of product names in current cart
        rules: DataFrame of association rules
        n: Number of recommendations
    
    Returns:
        List of recommended product names
    """
    if rules is None or len(rules) == 0:
        return []
    
    recommendations = {}
    
    for item in cart_items:
        # Find rules where item appears in antecedents
        relevant_rules = rules[
            rules['Antecedents'].str.contains(item, case=False, na=False)
        ].copy()
        
        # Score by lift
        for _, rule in relevant_rules.iterrows():
            consequents = rule['Consequents'].split(', ')
            
            for product in consequents:
                if product not in cart_items:
                    if product not in recommendations:
                        recommendations[product] = 0
                    recommendations[product] += rule['Lift']
    
    # Sort by score and return top N
    sorted_recs = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)
    return [product for product, score in sorted_recs[:n]]

def recommend_by_cluster(user_id, clusters, n=5):
    """
    Recommend products popular in user's cluster
    
    Args:
        user_id: User ID
        clusters: DataFrame with user_id and cluster columns
        n: Number of recommendations
    
    Returns:
        List of recommended product names
    """
    engine = get_engine()
    
    # Get user's cluster
    user_cluster = clusters[clusters['user_id'] == user_id]['cluster'].values
    
    if len(user_cluster) == 0:
        print(f"⚠️ User {user_id} not found in clusters")
        return []
    
    user_cluster = user_cluster[0]
    
    # Get top products in this cluster
    query = f"""
    SELECT 
        p.product_name,
        COUNT(DISTINCT fod.order_id) as order_count,
        ROUND(AVG(fod.reordered) * 100, 1) as reorder_rate
    FROM Fact_Order_Details fod
    JOIN Dim_Product p ON fod.product_id = p.product_id
    JOIN Dim_User u ON fod.user_id = u.user_id
    WHERE u.user_id IN (
        SELECT user_id 
        FROM (SELECT * FROM cluster_temp) AS ct
        WHERE cluster = {user_cluster}
    )
    GROUP BY p.product_id, p.product_name
    ORDER BY order_count DESC
    LIMIT {n}
    """
    
    # Create temp table for clusters (workaround for CSV data)
    try:
        clusters.to_sql('cluster_temp', engine, if_exists='replace', index=False)
        recommendations = pd.read_sql(query, engine)
        return recommendations['product_name'].tolist()
    except Exception as e:
        print(f"❌ Error getting cluster recommendations: {e}")
        return []

def hybrid_recommend(user_id, cart_items, rules, clusters, n=10):
    """
    Hybrid recommendation combining rules and clustering
    
    Args:
        user_id: User ID
        cart_items: List of products in cart
        rules: Association rules DataFrame
        clusters: User cluster labels DataFrame
        n: Number of recommendations
    
    Returns:
        List of recommended products with scores
    """
    recommendations = {}
    
    # Strategy 1: Association rules (weight: 0.6)
    if rules is not None and len(cart_items) > 0:
        rule_recs = recommend_by_rules(cart_items, rules, n=n*2)
        for i, product in enumerate(rule_recs):
            score = (len(rule_recs) - i) * 0.6  # Decreasing weight
            recommendations[product] = recommendations.get(product, 0) + score
    
    # Strategy 2: Cluster popularity (weight: 0.4)
    if clusters is not None:
        cluster_recs = recommend_by_cluster(user_id, clusters, n=n*2)
        for i, product in enumerate(cluster_recs):
            score = (len(cluster_recs) - i) * 0.4  # Decreasing weight
            if product not in cart_items:
                recommendations[product] = recommendations.get(product, 0) + score
    
    # Sort by combined score
    sorted_recs = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)
    
    return [(product, score) for product, score in sorted_recs[:n]]

def demo_recommendations():
    """Demo recommendation system with examples"""
    print("\n" + "=" * 80)
    print(" " * 25 + "RECOMMENDATION DEMO")
    print("=" * 80)
    
    # Load data
    rules = load_association_rules()
    clusters = load_cluster_labels()
    
    if rules is None:
        print("\n⚠️ Please run 'python mining/market_basket.py' first")
        return
    
    # Example 1: Rule-based recommendations
    print("\n📦 Example 1: Cart-based Recommendations")
    print("-" * 80)
    
    cart = ['Banana', 'Organic Avocado', 'Strawberries']
    print(f"Cart items: {cart}")
    
    recs = recommend_by_rules(cart, rules, n=5)
    print(f"\nRecommended products:")
    for i, product in enumerate(recs, 1):
        print(f"  {i}. {product}")
    
    # Example 2: Cluster-based recommendations
    if clusters is not None:
        print("\n\n👥 Example 2: Cluster-based Recommendations")
        print("-" * 80)
        
        sample_user = clusters['user_id'].iloc[100]
        user_cluster = clusters[clusters['user_id'] == sample_user]['cluster'].iloc[0]
        
        print(f"User ID: {sample_user} (Cluster {user_cluster})")
        
        cluster_recs = recommend_by_cluster(sample_user, clusters, n=5)
        print(f"\nPopular in your segment:")
        for i, product in enumerate(cluster_recs, 1):
            print(f"  {i}. {product}")
    
    # Example 3: Hybrid recommendations
    print("\n\n🎯 Example 3: Hybrid Recommendations")
    print("-" * 80)
    
    cart = ['Organic Whole Milk', 'Organic Strawberries']
    print(f"Cart: {cart}")
    
    if clusters is not None:
        sample_user = clusters['user_id'].iloc[200]
        hybrid_recs = hybrid_recommend(sample_user, cart, rules, clusters, n=8)
        
        print(f"\nPersonalized recommendations for User {sample_user}:")
        for i, (product, score) in enumerate(hybrid_recs, 1):
            print(f"  {i}. {product} (score: {score:.2f})")
    
    print("\n" + "=" * 80)

def evaluate_recommendations():
    """Evaluate recommendation quality (basic metrics)"""
    print("\n📊 Recommendation System Evaluation")
    print("=" * 80)
    
    rules = load_association_rules()
    
    if rules is None:
        return
    
    # Metrics
    total_rules = len(rules)
    avg_lift = rules['Lift'].mean()
    high_confidence = len(rules[rules['Confidence'] >= 0.5])
    
    print(f"\n📈 Association Rules Quality:")
    print(f"   Total rules: {total_rules:,}")
    print(f"   Average lift: {avg_lift:.2f}")
    print(f"   High confidence rules (≥50%): {high_confidence:,} ({high_confidence/total_rules*100:.1f}%)")
    
    # Coverage
    unique_antecedents = set()
    unique_consequents = set()
    
    for _, row in rules.iterrows():
        unique_antecedents.update(row['Antecedents'].split(', '))
        unique_consequents.update(row['Consequents'].split(', '))
    
    print(f"\n📦 Product Coverage:")
    print(f"   Products in antecedents: {len(unique_antecedents):,}")
    print(f"   Products in consequents: {len(unique_consequents):,}")
    print(f"   Total unique products: {len(unique_antecedents | unique_consequents):,}")
    
    print("\n" + "=" * 80)

def main():
    """Main execution"""
    demo_recommendations()
    evaluate_recommendations()

if __name__ == "__main__":
    main()
