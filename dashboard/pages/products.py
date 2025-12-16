import streamlit as st
import pandas as pd
import plotly.express as px

@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_top_products(_engine):
    return pd.read_sql("""
        SELECT 
            p.product_name,
            d.department_name,
            COUNT(DISTINCT fod.order_id) as orders,
            COUNT(*) as total_items,
            ROUND(AVG(fod.reordered) * 100, 1) as reorder_rate
        FROM Fact_Order_Details fod
        JOIN Dim_Product p ON fod.product_id = p.product_id
        JOIN Dim_Department d ON p.department_id = d.department_id
        GROUP BY p.product_id, p.product_name, d.department_name
        ORDER BY orders DESC
        LIMIT 20
    """, _engine)

@st.cache_data(ttl=600)
def get_aisle_reorder(_engine):
    return pd.read_sql("""
        SELECT 
            a.aisle_name,
            ROUND(AVG(fod.reordered) * 100, 2) as reorder_rate,
            COUNT(*) as items
        FROM Fact_Order_Details fod
        JOIN Dim_Product p ON fod.product_id = p.product_id
        JOIN Dim_Aisle a ON p.aisle_id = a.aisle_id
        GROUP BY a.aisle_id, a.aisle_name
        HAVING COUNT(*) >= 10000
        ORDER BY reorder_rate DESC
        LIMIT 15
    """, _engine)

def show(engine):
    st.header("🏆 Product Analytics")
    st.markdown("Analyze best-selling products and reorder patterns")
    
    # Top Products
    st.subheader("🥇 Top 20 Best-Selling Products")
    
    try:
        with st.spinner("Loading top products..."):
            df_top = get_top_products(engine)
        
        if not df_top.empty:
            fig = px.bar(
                df_top, 
                x='orders', 
                y='product_name',
                color='reorder_rate',
                orientation='h',
                color_continuous_scale='Viridis',
                hover_data=['department_name', 'total_items'],
                labels={
                    'orders': 'Number of Orders',
                    'product_name': 'Product Name',
                    'reorder_rate': 'Reorder Rate (%)'
                }
            )
            fig.update_layout(
                height=600,
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, width='stretch')
            
            # Show top 5 in table
            st.markdown("**📊 Top 5 Products Detail:**")
            st.dataframe(
                df_top.head(5).style.format({
                    'orders': '{:,}',
                    'total_items': '{:,}',
                    'reorder_rate': '{:.1f}%'
                }),
                width='stretch'
            )
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
    
    # Reorder Rate by Aisle
    st.markdown("---")
    st.subheader("🔁 Reorder Rate by Aisle (Top 15)")
    
    try:
        with st.spinner("Loading aisle data..."):
            df_aisle = get_aisle_reorder(engine)
        
        if not df_aisle.empty:
            fig = px.bar(
                df_aisle,
                x='reorder_rate',
                y='aisle_name',
                orientation='h',
                color='reorder_rate',
                color_continuous_scale='RdYlGn',
                labels={
                    'reorder_rate': 'Reorder Rate (%)',
                    'aisle_name': 'Aisle Name'
                }
            )
            fig.update_layout(
                height=500,
                yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig, width='stretch')
            
            # Highlight best aisle
            best_aisle = df_aisle.iloc[0]
            st.success(f"🌟 **Best Reorder Rate:** {best_aisle['aisle_name']} - {best_aisle['reorder_rate']:.1f}%")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
    
    # Product Search
    st.markdown("---")
    st.subheader("🔍 Product Search")
    
    search_term = st.text_input("Search product name:", placeholder="e.g., organic banana")
    
    if search_term:
        try:
            df_search = pd.read_sql(f"""
                SELECT 
                    p.product_name,
                    d.department_name,
                    a.aisle_name,
                    COUNT(DISTINCT fod.order_id) as orders,
                    COUNT(*) as total_items,
                    ROUND(AVG(fod.reordered) * 100, 1) as reorder_rate
                FROM Fact_Order_Details fod
                JOIN Dim_Product p ON fod.product_id = p.product_id
                JOIN Dim_Department d ON p.department_id = d.department_id
                JOIN Dim_Aisle a ON p.aisle_id = a.aisle_id
                WHERE LOWER(p.product_name) LIKE LOWER('%{search_term}%')
                GROUP BY p.product_id, p.product_name, d.department_name, a.aisle_name
                ORDER BY orders DESC
                LIMIT 50
            """, engine)
            
            if not df_search.empty:
                st.success(f"Found {len(df_search)} products matching '{search_term}'")
                st.dataframe(
                    df_search.style.format({
                        'orders': '{:,}',
                        'total_items': '{:,}',
                        'reorder_rate': '{:.1f}%'
                    }),
                    width='stretch',
                    height=400
                )
            else:
                st.warning(f"No products found matching '{search_term}'")
        except Exception as e:
            st.error(f"Error searching: {str(e)}")
