import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_total_orders(_engine):
    return pd.read_sql("SELECT COUNT(*) as cnt FROM Fact_Orders", _engine).iloc[0, 0]

@st.cache_data(ttl=300)
def get_total_users(_engine):
    return pd.read_sql("SELECT COUNT(*) as cnt FROM Dim_User", _engine).iloc[0, 0]

@st.cache_data(ttl=300)
def get_total_products(_engine):
    return pd.read_sql("SELECT COUNT(*) as cnt FROM Dim_Product", _engine).iloc[0, 0]

@st.cache_data(ttl=300)
def get_avg_basket(_engine):
    result = pd.read_sql("""
        SELECT AVG(total_items) as avg 
        FROM Fact_Orders 
        WHERE total_items > 0
    """, _engine)
    return result.iloc[0, 0] if not result.empty and result.iloc[0, 0] else None

@st.cache_data(ttl=300)
def get_orders_by_dow(_engine):
    return pd.read_sql("""
        SELECT 
            t.dow_name,
            t.order_dow,
            COUNT(*) as orders
        FROM Fact_Orders fo
        JOIN Dim_Time t ON fo.time_id = t.time_id
        GROUP BY t.order_dow, t.dow_name
        ORDER BY t.order_dow
    """, _engine)

@st.cache_data(ttl=300)
def get_market_share(_engine):
    return pd.read_sql("""
        SELECT 
            d.department_name,
            COUNT(*) as items
        FROM Fact_Order_Details fod
        JOIN Dim_Product p ON fod.product_id = p.product_id
        JOIN Dim_Department d ON p.department_id = d.department_id
        GROUP BY d.department_name
        ORDER BY items DESC
        LIMIT 10
    """, _engine)

@st.cache_data(ttl=300)
def get_orders_by_hour(_engine):
    return pd.read_sql("""
        SELECT 
            t.order_hour,
            COUNT(*) as orders,
            AVG(fo.total_items) as avg_basket
        FROM Fact_Orders fo
        JOIN Dim_Time t ON fo.time_id = t.time_id
        GROUP BY t.order_hour
        ORDER BY t.order_hour
    """, _engine)

def show(engine):
    st.header("📊 Overview Dashboard")
    st.markdown("Real-time business metrics and key performance indicators")
    
    # KPI Metrics
    st.subheader("📈 Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        try:
            total_orders = get_total_orders(engine)
            st.metric("Total Orders", f"{total_orders:,}")
        except Exception as e:
            st.metric("Total Orders", "N/A")
            st.caption(f"Error: {str(e)[:50]}")
    
    with col2:
        try:
            total_users = get_total_users(engine)
            st.metric("Total Users", f"{total_users:,}")
        except Exception as e:
            st.metric("Total Users", "N/A")
            st.caption(f"Error: {str(e)[:50]}")
    
    with col3:
        try:
            total_products = get_total_products(engine)
            st.metric("Total Products", f"{total_products:,}")
        except Exception as e:
            st.metric("Total Products", "N/A")
            st.caption(f"Error: {str(e)[:50]}")
    
    with col4:
        try:
            avg_basket = get_avg_basket(engine)
            st.metric("Avg Basket Size", f"{avg_basket:.1f}" if avg_basket else "N/A")
        except Exception as e:
            st.metric("Avg Basket Size", "N/A")
            st.caption(f"Error: {str(e)[:50]}")
    
    st.markdown("---")
    
    # Row 2: Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📅 Orders by Day of Week")
        try:
            df_dow = get_orders_by_dow(engine)
            
            if not df_dow.empty:
                fig = px.bar(
                    df_dow, 
                    x='dow_name', 
                    y='orders',
                    color='orders',
                    color_continuous_scale='Blues',
                    labels={'dow_name': 'Day of Week', 'orders': 'Number of Orders'}
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No data available. Please run ETL pipeline first.")
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
    
    with col2:
        st.subheader("🏪 Market Share by Department")
        try:
            df_dept = get_market_share(engine)
            
            if not df_dept.empty:
                fig = px.pie(
                    df_dept, 
                    values='items', 
                    names='department_name',
                    hole=0.4,
                    color_discrete_sequence=px.colors.sequential.RdBu
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No data available. Please run ETL pipeline first.")
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
    
    # Row 3: Hourly trend
    st.markdown("---")
    st.subheader("⏰ Orders by Hour of Day")
    try:
        df_hour = get_orders_by_hour(engine)
        
        if not df_hour.empty:
            fig = px.line(
                df_hour, 
                x='order_hour', 
                y='orders',
                markers=True,
                labels={'order_hour': 'Hour of Day', 'orders': 'Number of Orders'}
            )
            fig.update_traces(line_color='#1f77b4', line_width=3)
            fig.update_layout(
                hovermode='x unified',
                xaxis=dict(tickmode='linear', tick0=0, dtick=2)
            )
            st.plotly_chart(fig, width='stretch')
            
            # Peak hour highlight
            peak_hour = df_hour.loc[df_hour['orders'].idxmax()]
            st.success(f"🔥 **Peak Hour:** {int(peak_hour['order_hour'])}:00 with {int(peak_hour['orders']):,} orders")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
