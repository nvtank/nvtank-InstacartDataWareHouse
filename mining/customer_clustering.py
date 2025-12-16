"""
Customer Clustering using K-Means
Segments customers based on shopping behavior
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import os
sys.path.append('..')
from etl.config import get_engine

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)

def extract_features():
    """Extract customer features from DWH"""
    print("\n📊 Extracting customer features from database...")
    engine = get_engine()
    
    query = """
    SELECT 
        u.user_id,
        u.total_orders,
        AVG(fo.total_items) as avg_basket_size,
        AVG(fo.reorder_ratio) as avg_reorder_ratio,
        MIN(fo.days_since_prior) as min_days_between_orders,
        AVG(fo.days_since_prior) as avg_days_between_orders,
        MAX(fo.days_since_prior) as max_days_between_orders
    FROM Dim_User u
    JOIN Fact_Orders fo ON u.user_id = fo.user_id
    WHERE u.total_orders >= 3  -- Filter active users only
    GROUP BY u.user_id, u.total_orders
    """
    
    df = pd.read_sql(query, engine)
    print(f"✅ Extracted {len(df):,} users with behavioral features")
    print(f"   Features: {list(df.columns)[1:]}")
    
    return df

def find_optimal_k(X_scaled, max_k=10):
    """Use Elbow Method to find optimal number of clusters"""
    print(f"\n🔍 Running Elbow Method (K=2 to {max_k})...")
    
    inertias = []
    silhouette_scores = []
    K_range = range(2, max_k + 1)
    
    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        kmeans.fit(X_scaled)
        inertias.append(kmeans.inertia_)
        
        # Calculate silhouette score
        labels = kmeans.labels_
        score = silhouette_score(X_scaled, labels)
        silhouette_scores.append(score)
        
        print(f"   K={k}: Inertia={kmeans.inertia_:.2f}, Silhouette={score:.3f}")
    
    # Plot elbow curve
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
    
    # Inertia plot
    ax1.plot(K_range, inertias, 'bo-', linewidth=2, markersize=8)
    ax1.set_xlabel('Number of Clusters (K)', fontsize=12)
    ax1.set_ylabel('Inertia (Within-cluster sum of squares)', fontsize=12)
    ax1.set_title('Elbow Method: Inertia vs K', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # Silhouette plot
    ax2.plot(K_range, silhouette_scores, 'ro-', linewidth=2, markersize=8)
    ax2.set_xlabel('Number of Clusters (K)', fontsize=12)
    ax2.set_ylabel('Silhouette Score', fontsize=12)
    ax2.set_title('Silhouette Score vs K', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('mining/results/elbow_curve.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved elbow curve to mining/results/elbow_curve.png")
    plt.close()
    
    # Recommend optimal K
    optimal_k = K_range[np.argmax(silhouette_scores)]
    print(f"\n💡 Recommended K={optimal_k} (highest silhouette score)")
    
    return inertias, silhouette_scores, optimal_k

def train_kmeans(df, n_clusters=4):
    """Train K-Means clustering model"""
    print(f"\n🤖 Training K-Means with K={n_clusters}...")
    
    # Select features
    features = ['total_orders', 'avg_basket_size', 'avg_reorder_ratio', 
                'avg_days_between_orders']
    X = df[features].fillna(0)
    
    # Standardization (important for K-Means)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train K-Means
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10, max_iter=300)
    df['cluster'] = kmeans.fit_predict(X_scaled)
    
    # Evaluate clustering
    silhouette_avg = silhouette_score(X_scaled, df['cluster'])
    davies_bouldin = davies_bouldin_score(X_scaled, df['cluster'])
    
    print(f"✅ Clustering complete!")
    print(f"   Silhouette Score: {silhouette_avg:.3f} (higher is better, range: -1 to 1)")
    print(f"   Davies-Bouldin Index: {davies_bouldin:.3f} (lower is better)")
    print(f"   Inertia: {kmeans.inertia_:.2f}")
    
    print(f"\n📊 Cluster distribution:")
    cluster_counts = df['cluster'].value_counts().sort_index()
    for cluster_id, count in cluster_counts.items():
        pct = (count / len(df)) * 100
        print(f"   Cluster {cluster_id}: {count:,} users ({pct:.1f}%)")
    
    return df, kmeans, scaler, X_scaled

def visualize_clusters(df, X_scaled):
    """Visualize clusters using PCA dimensionality reduction"""
    print("\n📊 Creating cluster visualizations...")
    
    # PCA to 2D
    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X_scaled)
    
    # Explained variance
    var_explained = pca.explained_variance_ratio_
    print(f"   PCA explained variance: PC1={var_explained[0]:.1%}, PC2={var_explained[1]:.1%}")
    print(f"   Total: {var_explained.sum():.1%}")
    
    # Create scatter plot
    plt.figure(figsize=(14, 10))
    
    # Plot each cluster with different color
    clusters = df['cluster'].unique()
    colors = plt.cm.viridis(np.linspace(0, 1, len(clusters)))
    
    for cluster_id, color in zip(sorted(clusters), colors):
        mask = df['cluster'] == cluster_id
        cluster_points = X_pca[mask]
        
        plt.scatter(
            cluster_points[:, 0], 
            cluster_points[:, 1],
            c=[color],
            label=f'Cluster {cluster_id}',
            alpha=0.6,
            s=50,
            edgecolors='w',
            linewidth=0.5
        )
    
    plt.xlabel(f'Principal Component 1 ({var_explained[0]:.1%} variance)', fontsize=12)
    plt.ylabel(f'Principal Component 2 ({var_explained[1]:.1%} variance)', fontsize=12)
    plt.title('Customer Clusters Visualization (PCA Projection)', fontsize=14, fontweight='bold')
    plt.legend(loc='best', framealpha=0.9)
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('mining/results/clusters_pca.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved PCA visualization to mining/results/clusters_pca.png")
    plt.close()
    
    # Create 3D visualization if possible
    try:
        from mpl_toolkits.mplot3d import Axes3D
        
        pca_3d = PCA(n_components=3, random_state=42)
        X_pca_3d = pca_3d.fit_transform(X_scaled)
        
        fig = plt.figure(figsize=(14, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        for cluster_id, color in zip(sorted(clusters), colors):
            mask = df['cluster'] == cluster_id
            cluster_points = X_pca_3d[mask]
            
            ax.scatter(
                cluster_points[:, 0],
                cluster_points[:, 1],
                cluster_points[:, 2],
                c=[color],
                label=f'Cluster {cluster_id}',
                alpha=0.6,
                s=30
            )
        
        ax.set_xlabel('PC1', fontsize=10)
        ax.set_ylabel('PC2', fontsize=10)
        ax.set_zlabel('PC3', fontsize=10)
        ax.set_title('3D Cluster Visualization', fontsize=14, fontweight='bold')
        ax.legend()
        
        plt.savefig('mining/results/clusters_3d.png', dpi=300, bbox_inches='tight')
        print(f"✅ Saved 3D visualization to mining/results/clusters_3d.png")
        plt.close()
    except ImportError:
        print("   ⚠️ 3D visualization skipped (matplotlib 3D not available)")

def profile_clusters(df):
    """Generate detailed cluster profiles"""
    print("\n📋 Generating cluster profiles...")
    
    profiles = df.groupby('cluster').agg({
        'user_id': 'count',
        'total_orders': ['mean', 'median', 'min', 'max'],
        'avg_basket_size': ['mean', 'std'],
        'avg_reorder_ratio': ['mean', 'std'],
        'avg_days_between_orders': ['mean', 'std']
    }).round(2)
    
    profiles.columns = ['_'.join(col).strip('_') for col in profiles.columns]
    profiles = profiles.reset_index()
    profiles.rename(columns={'user_id_count': 'num_users'}, inplace=True)
    
    # Assign cluster names based on characteristics
    cluster_names = []
    for idx, row in profiles.iterrows():
        if row['total_orders_mean'] >= 50:
            cluster_names.append('VIP Customers')
        elif row['total_orders_mean'] >= 20:
            cluster_names.append('Frequent Shoppers')
        elif row['total_orders_mean'] >= 10:
            cluster_names.append('Regular Customers')
        else:
            cluster_names.append('Occasional Buyers')
    
    profiles['cluster_name'] = cluster_names
    
    # Reorder columns
    cols = ['cluster', 'cluster_name', 'num_users'] + [col for col in profiles.columns if col not in ['cluster', 'cluster_name', 'num_users']]
    profiles = profiles[cols]
    
    print("\n" + "=" * 120)
    print("CLUSTER PROFILES")
    print("=" * 120)
    print(profiles.to_string(index=False))
    print("=" * 120)
    
    # Save to CSV
    profiles.to_csv('mining/results/cluster_profiles.csv', index=False)
    print(f"\n✅ Saved cluster profiles to mining/results/cluster_profiles.csv")
    
    # Create bar chart
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Plot 1: Users per cluster
    axes[0, 0].bar(profiles['cluster_name'], profiles['num_users'], color='skyblue')
    axes[0, 0].set_title('Number of Users per Cluster', fontweight='bold')
    axes[0, 0].set_ylabel('Users')
    axes[0, 0].tick_params(axis='x', rotation=45)
    
    # Plot 2: Avg orders
    axes[0, 1].bar(profiles['cluster_name'], profiles['total_orders_mean'], color='salmon')
    axes[0, 1].set_title('Average Orders per Cluster', fontweight='bold')
    axes[0, 1].set_ylabel('Avg Orders')
    axes[0, 1].tick_params(axis='x', rotation=45)
    
    # Plot 3: Avg basket size
    axes[1, 0].bar(profiles['cluster_name'], profiles['avg_basket_size_mean'], color='lightgreen')
    axes[1, 0].set_title('Average Basket Size per Cluster', fontweight='bold')
    axes[1, 0].set_ylabel('Avg Items per Order')
    axes[1, 0].tick_params(axis='x', rotation=45)
    
    # Plot 4: Avg reorder ratio
    axes[1, 1].bar(profiles['cluster_name'], profiles['avg_reorder_ratio_mean'], color='gold')
    axes[1, 1].set_title('Average Reorder Ratio per Cluster', fontweight='bold')
    axes[1, 1].set_ylabel('Reorder Ratio')
    axes[1, 1].tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig('mining/results/cluster_profiles_chart.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved profile charts to mining/results/cluster_profiles_chart.png")
    plt.close()
    
    return profiles

def save_cluster_labels(df):
    """Save user-cluster assignments to database"""
    print("\n💾 Saving cluster labels...")
    
    # Save to CSV
    df[['user_id', 'cluster']].to_csv(
        'mining/results/cluster_labels.csv', 
        index=False
    )
    print(f"✅ Saved {len(df):,} cluster labels to mining/results/cluster_labels.csv")

def main():
    """Main execution function"""
    print("=" * 80)
    print(" " * 20 + "CUSTOMER CLUSTERING - K-MEANS")
    print("=" * 80)
    
    # Create results directory if not exists
    os.makedirs('mining/results', exist_ok=True)
    
    try:
        # Step 1: Extract features
        df = extract_features()
        
        # Step 2: Prepare data for clustering
        features = ['total_orders', 'avg_basket_size', 'avg_reorder_ratio', 
                    'avg_days_between_orders']
        X = df[features].fillna(0)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Step 3: Find optimal K
        inertias, silhouette_scores, optimal_k = find_optimal_k(X_scaled, max_k=10)
        
        # Step 4: Train with optimal K (or use K=4 as default)
        use_k = 4  # Can change to optimal_k if preferred
        df, kmeans, scaler, X_scaled = train_kmeans(df, n_clusters=use_k)
        
        # Step 5: Visualize clusters
        visualize_clusters(df, X_scaled)
        
        # Step 6: Profile clusters
        profiles = profile_clusters(df)
        
        # Step 7: Save results
        save_cluster_labels(df)
        
        print("\n" + "=" * 80)
        print("✅ CUSTOMER CLUSTERING COMPLETE!")
        print("=" * 80)
        print("\n📁 Generated files:")
        print("   - mining/results/elbow_curve.png")
        print("   - mining/results/clusters_pca.png")
        print("   - mining/results/cluster_profiles.csv")
        print("   - mining/results/cluster_profiles_chart.png")
        print("   - mining/results/cluster_labels.csv")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
