import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Cached data loading functions
@st.cache_data(ttl=86400, show_spinner="🏪 Loading department data...")
def get_department_overview(_engine):
    """Get department performance overview (cached for 30 minutes)"""
    return pd.read_sql("""
        SELECT 
            d.department_name,
            COUNT(DISTINCT fod.order_id) as orders,
            COUNT(*) as total_items,
            ROUND(AVG(fod.reordered) * 100, 1) as reorder_rate,
            COUNT(DISTINCT fod.product_id) as unique_products
        FROM Fact_Order_Details fod
        JOIN Dim_Product p ON fod.product_id = p.product_id
        JOIN Dim_Department d ON p.department_id = d.department_id
        GROUP BY d.department_id, d.department_name
        ORDER BY total_items DESC
    """, _engine)

@st.cache_data(ttl=86400, show_spinner="🔁 Loading reorder data...")
def get_department_reorder_rates(_engine):
    """Get reorder rates by department (cached for 30 minutes)"""
    return pd.read_sql("""
        SELECT 
            d.department_name,
            ROUND(AVG(fod.reordered) * 100, 1) as reorder_rate,
            COUNT(*) as items
        FROM Fact_Order_Details fod
        JOIN Dim_Product p ON fod.product_id = p.product_id
        JOIN Dim_Department d ON p.department_id = d.department_id
        GROUP BY d.department_id, d.department_name
        ORDER BY reorder_rate DESC
    """, _engine)

@st.cache_data(ttl=86400)
def get_department_list(_engine):
    """Get list of all departments (cached for 30 minutes)"""
    return pd.read_sql(
        "SELECT DISTINCT department_name FROM Dim_Department ORDER BY department_name",
        _engine
    )['department_name'].tolist()

@st.cache_data(ttl=86400)
def get_department_comparison(_engine, dept1, dept2):
    """Compare two departments (cached for 30 minutes)"""
    return pd.read_sql(f"""
        SELECT 
            d.department_name,
            COUNT(DISTINCT fod.order_id) as orders,
            COUNT(*) as items,
            ROUND(AVG(fod.reordered) * 100, 1) as reorder_rate,
            COUNT(DISTINCT fod.product_id) as products
        FROM Fact_Order_Details fod
        JOIN Dim_Product p ON fod.product_id = p.product_id
        JOIN Dim_Department d ON p.department_id = d.department_id
        WHERE d.department_name IN ('{dept1}', '{dept2}')
        GROUP BY d.department_name
    """, _engine)

def show(engine):
    st.header("🏪 Department Performance")
    st.markdown("Analyze department-level metrics and trends")
    
    # Department Overview
    st.subheader("📊 Department Performance Overview")
    
    try:
        # Use cached function
        df_dept = get_department_overview(engine)
        
        if not df_dept.empty:
            # Calculate market share
            df_dept['market_share'] = (df_dept['total_items'] / df_dept['total_items'].sum() * 100).round(2)
            
            # Top departments bar chart
            fig = px.bar(
                df_dept.head(10),
                x='department_name',
                y='total_items',
                color='reorder_rate',
                color_continuous_scale='RdYlGn',
                labels={
                    'department_name': 'Department',
                    'total_items': 'Total Items Sold',
                    'reorder_rate': 'Reorder Rate (%)'
                },
                title='Top 10 Departments by Sales Volume'
            )
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            
            # Department details table
            st.markdown("**📋 Department Details:**")
            st.dataframe(
                df_dept.style.format({
                    'orders': '{:,}',
                    'total_items': '{:,}',
                    'reorder_rate': '{:.1f}%',
                    'unique_products': '{:,}',
                    'market_share': '{:.2f}%'
                }),
                use_container_width=True,
                height=400
            )
            
            # Top performer highlight
            top_dept = df_dept.iloc[0]
            st.success(f"🏆 **Top Department:** {top_dept['department_name']} with {top_dept['market_share']:.1f}% market share")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
    
    # Reorder Rate by Department
    st.markdown("---")
    st.subheader("🔁 Reorder Rate Comparison")
    
    try:
        # Use cached function
        df_reorder = get_department_reorder_rates(engine)
        
        if not df_reorder.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Horizontal bar chart
                fig = px.bar(
                    df_reorder,
                    x='reorder_rate',
                    y='department_name',
                    orientation='h',
                    color='reorder_rate',
                    color_continuous_scale='RdYlGn',
                    labels={
                        'reorder_rate': 'Reorder Rate (%)',
                        'department_name': 'Department'
                    },
                    title='Reorder Rate by Department'
                )
                fig.update_layout(
                    yaxis={'categoryorder': 'total ascending'},
                    height=600
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Scatter plot: Items vs Reorder Rate
                fig = px.scatter(
                    df_reorder,
                    x='items',
                    y='reorder_rate',
                    size='items',
                    color='reorder_rate',
                    hover_name='department_name',
                    color_continuous_scale='Viridis',
                    labels={
                        'items': 'Total Items Sold',
                        'reorder_rate': 'Reorder Rate (%)'
                    },
                    title='Sales Volume vs Reorder Rate'
                )
                fig.update_layout(height=600)
                st.plotly_chart(fig, use_container_width=True)
            
            # Best and worst reorder rate
            best_reorder = df_reorder.iloc[0]
            worst_reorder = df_reorder.iloc[-1]
            
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"✅ **Highest Reorder Rate:** {best_reorder['department_name']} ({best_reorder['reorder_rate']:.1f}%)")
            with col2:
                st.warning(f"⚠️ **Lowest Reorder Rate:** {worst_reorder['department_name']} ({worst_reorder['reorder_rate']:.1f}%)")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
    
    # Department Comparison Tool
    st.markdown("---")
    st.subheader("🔍 Department Comparison")
    
    try:
        # Get department list for dropdown (cached)
        dept_list = get_department_list(engine)
        
        col1, col2 = st.columns(2)
        with col1:
            dept1 = st.selectbox("Select Department 1:", dept_list, key='dept1')
        with col2:
            dept2 = st.selectbox("Select Department 2:", dept_list, index=min(1, len(dept_list)-1), key='dept2')
        
        if dept1 and dept2:
            # Use cached comparison function
            df_compare = get_department_comparison(engine, dept1, dept2)
            
            if not df_compare.empty and len(df_compare) == 2:
                metrics = ['orders', 'items', 'reorder_rate', 'products']
                metric_names = ['Orders', 'Items Sold', 'Reorder Rate (%)', 'Product Variety']
                
                fig = go.Figure()
                
                for dept in [dept1, dept2]:
                    dept_data = df_compare[df_compare['department_name'] == dept]
                    values = [dept_data[m].values[0] for m in metrics]
                    
                    fig.add_trace(go.Scatterpolar(
                        r=values,
                        theta=metric_names,
                        fill='toself',
                        name=dept
                    ))
                
                fig.update_layout(
                    polar=dict(radialaxis=dict(visible=True)),
                    showlegend=True,
                    title=f'Department Comparison: {dept1} vs {dept2}'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Unable to compare departments. Please ensure data exists for both.")
    except Exception as e:
        st.error(f"Error loading comparison: {str(e)}")
