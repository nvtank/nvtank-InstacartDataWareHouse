"""
Recompute cluster profiles with complete features
Fixes missing basket_size and reorder_ratio in visualization
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from etl.config import get_engine
from sqlalchemy import text

sns.set_style("whitegrid")

def extract_full_features_with_clusters():
    """Extract user features and merge with cluster assignments"""
    print("\n📊 Extracting full user features with clusters...")
    engine = get_engine()
    
    # Load cluster assignments
    cluster_df = pd.read_csv('mining/results/cluster_labels.csv')
    print(f"   ✅ Loaded {len(cluster_df):,} user cluster assignments")
    
    # Extract features from database
    print("   Querying database for user features...")
    query = """
    SELECT 
        u.user_id,
        u.total_orders,
        COUNT(DISTINCT fo.order_id) as order_count,
        AVG(CAST(fo.total_items AS DECIMAL(10,2))) as avg_basket_size,
        AVG(CAST(fo.reorder_ratio AS DECIMAL(10,4))) as avg_reorder_ratio,
        AVG(CAST(fo.days_since_prior_order AS DECIMAL(10,2))) as avg_days_between_orders
    FROM Dim_User u
    JOIN Fact_Orders fo ON u.user_id = fo.user_id
    WHERE u.total_orders >= 3 
      AND fo.total_items > 0
    GROUP BY u.user_id, u.total_orders
    """
    
    features_df = pd.read_sql(query, engine)
    print(f"   ✅ Extracted {len(features_df):,} users with features")
    
    # Merge with clusters
    merged_df = features_df.merge(cluster_df, on='user_id', how='inner')
    print(f"   ✅ Merged: {len(merged_df):,} users with clusters and features")
    
    return merged_df

def compute_cluster_profiles(df):
    """Compute comprehensive cluster statistics"""
    print("\n📈 Computing cluster profiles...")
    
    # Define cluster names
    cluster_names = {
        0: 'Occasional Buyers',
        1: 'Occasional Buyers',
        2: 'VIP Customers',
        3: 'Frequent Shoppers'
    }
    
    profiles = []
    
    for cluster_id in sorted(df['cluster'].unique()):
        cluster_data = df[df['cluster'] == cluster_id]
        
        profile = {
            'cluster': cluster_id,
            'cluster_name': cluster_names.get(cluster_id, f'Cluster {cluster_id}'),
            'num_users': len(cluster_data),
            
            # Total orders stats
            'total_orders_mean': cluster_data['total_orders'].mean(),
            'total_orders_median': cluster_data['total_orders'].median(),
            'total_orders_min': cluster_data['total_orders'].min(),
            'total_orders_max': cluster_data['total_orders'].max(),
            
            # Basket size stats
            'avg_basket_size_mean': cluster_data['avg_basket_size'].mean(),
            'avg_basket_size_std': cluster_data['avg_basket_size'].std(),
            
            # Reorder ratio stats
            'avg_reorder_ratio_mean': cluster_data['avg_reorder_ratio'].mean(),
            'avg_reorder_ratio_std': cluster_data['avg_reorder_ratio'].std(),
            
            # Days between orders stats
            'avg_days_between_orders_mean': cluster_data['avg_days_between_orders'].mean(),
            'avg_days_between_orders_std': cluster_data['avg_days_between_orders'].std(),
        }
        
        profiles.append(profile)
        
        print(f"   Cluster {cluster_id} ({profile['cluster_name']}): "
              f"{profile['num_users']:,} users, "
              f"avg_basket={profile['avg_basket_size_mean']:.2f}, "
              f"reorder={profile['avg_reorder_ratio_mean']:.2%}")
    
    profiles_df = pd.DataFrame(profiles)
    return profiles_df

def visualize_cluster_profiles(profiles_df):
    """Create enhanced visualization with all metrics"""
    print("\n📊 Creating enhanced visualizations...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Customer Segmentation Analysis', fontsize=18, fontweight='bold', y=0.995)
    
    # 1. Number of users per cluster
    ax1 = axes[0, 0]
    colors = ['#87CEEB', '#FFB6C1', '#FF6B6B', '#4ECDC4']
    bars1 = ax1.bar(profiles_df['cluster_name'], profiles_df['num_users'], color=colors, alpha=0.8, edgecolor='black')
    ax1.set_title('Number of Users per Cluster', fontsize=14, fontweight='bold', pad=10)
    ax1.set_ylabel('Users', fontsize=12)
    ax1.tick_params(axis='x', rotation=15)
    
    # Add value labels
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height):,}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 2. Average orders per cluster
    ax2 = axes[0, 1]
    bars2 = ax2.bar(profiles_df['cluster_name'], profiles_df['total_orders_mean'], 
                    color=['#FFB6C1', '#87CEEB', '#FF6B6B', '#4ECDC4'], alpha=0.8, edgecolor='black')
    ax2.set_title('Average Orders per Cluster', fontsize=14, fontweight='bold', pad=10)
    ax2.set_ylabel('Avg Orders', fontsize=12)
    ax2.tick_params(axis='x', rotation=15)
    
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 3. Average basket size per cluster
    ax3 = axes[1, 0]
    bars3 = ax3.bar(profiles_df['cluster_name'], profiles_df['avg_basket_size_mean'],
                    color=['#4ECDC4', '#FFB6C1', '#FF6B6B', '#87CEEB'], alpha=0.8, edgecolor='black')
    ax3.set_title('Average Basket Size per Cluster', fontsize=14, fontweight='bold', pad=10)
    ax3.set_ylabel('Avg Items per Order', fontsize=12)
    ax3.tick_params(axis='x', rotation=15)
    
    for bar in bars3:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 4. Average reorder ratio per cluster
    ax4 = axes[1, 1]
    bars4 = ax4.bar(profiles_df['cluster_name'], profiles_df['avg_reorder_ratio_mean'],
                    color=['#FF6B6B', '#4ECDC4', '#FFB6C1', '#87CEEB'], alpha=0.8, edgecolor='black')
    ax4.set_title('Average Reorder Ratio per Cluster', fontsize=14, fontweight='bold', pad=10)
    ax4.set_ylabel('Reorder Ratio', fontsize=12)
    ax4.tick_params(axis='x', rotation=15)
    
    for bar in bars4:
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2%}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig('mining/results/cluster_profiles_chart_fixed.png', dpi=150, bbox_inches='tight')
    print("   ✅ Saved: mining/results/cluster_profiles_chart_fixed.png")
    
    plt.close()

def main():
    print("="*60)
    print("Recomputing Cluster Profiles with Full Features")
    print("="*60)
    
    # Extract features
    df = extract_full_features_with_clusters()
    
    # Compute profiles
    profiles_df = compute_cluster_profiles(df)
    
    # Save updated profiles
    profiles_df.to_csv('mining/results/cluster_profiles_fixed.csv', index=False)
    print("\n✅ Saved: mining/results/cluster_profiles_fixed.csv")
    
    # Visualize
    visualize_cluster_profiles(profiles_df)
    
    print("\n" + "="*60)
    print("✅ Cluster profiles recomputed successfully!")
    print("="*60)
    print("\nUpdated files:")
    print("  - mining/results/cluster_profiles_fixed.csv")
    print("  - mining/results/cluster_profiles_chart_fixed.png")

if __name__ == '__main__':
    main()
