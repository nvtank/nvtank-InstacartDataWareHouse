import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def show(engine):
    st.header("👥 Customer Analytics")
    st.markdown("Understand customer segments and shopping behaviors")
    
    # User Segmentation
    st.subheader("🎯 Customer Segmentation")
    
    try:
        df_segment = pd.read_sql("""
            SELECT 
                CASE 
                    WHEN u.total_orders >= 50 THEN 'VIP'
                    WHEN u.total_orders >= 10 THEN 'Regular'
                    ELSE 'New'
                END as segment,
                COUNT(DISTINCT u.user_id) as users,
                AVG(u.total_orders) as avg_orders,
                SUM(u.total_orders) as total_orders
            FROM Dim_User u
            GROUP BY segment
            ORDER BY 
                CASE segment 
                    WHEN 'VIP' THEN 1 
                    WHEN 'Regular' THEN 2 
                    ELSE 3 
                END
        """, engine)
        
        if not df_segment.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Pie chart for user distribution
                fig = px.pie(
                    df_segment,
                    values='users',
                    names='segment',
                    title='Customer Distribution',
                    color='segment',
                    color_discrete_map={
                        'VIP': '#FFD700',
                        'Regular': '#4169E1',
                        'New': '#90EE90'
                    },
                    hole=0.4
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, width='stretch')
            
            with col2:
                # Bar chart for orders by segment
                fig = px.bar(
                    df_segment,
                    x='segment',
                    y='total_orders',
                    color='segment',
                    title='Total Orders by Segment',
                    color_discrete_map={
                        'VIP': '#FFD700',
                        'Regular': '#4169E1',
                        'New': '#90EE90'
                    },
                    labels={'total_orders': 'Total Orders', 'segment': 'Segment'}
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width='stretch')
            
            # Segment details table
            st.markdown("**📊 Segment Details:**")
            df_display = df_segment.copy()
            df_display['avg_orders'] = df_display['avg_orders'].round(1)
            st.dataframe(
                df_display.style.format({
                    'users': '{:,}',
                    'avg_orders': '{:.1f}',
                    'total_orders': '{:,}'
                }),
                width='stretch'
            )
            
            # VIP insights
            vip_row = df_segment[df_segment['segment'] == 'VIP'].iloc[0]
            vip_percentage = (vip_row['users'] / df_segment['users'].sum()) * 100
            vip_order_percentage = (vip_row['total_orders'] / df_segment['total_orders'].sum()) * 100
            
            st.success(f"🌟 **VIP Customers:** {vip_percentage:.1f}% of users generate {vip_order_percentage:.1f}% of orders")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
    
    # Basket Size Distribution
    st.markdown("---")
    st.subheader("🛒 Basket Size Distribution")
    
    try:
        df_basket = pd.read_sql("""
            SELECT 
                CASE 
                    WHEN fo.total_items BETWEEN 1 AND 5 THEN '1-5 items'
                    WHEN fo.total_items BETWEEN 6 AND 10 THEN '6-10 items'
                    WHEN fo.total_items BETWEEN 11 AND 20 THEN '11-20 items'
                    WHEN fo.total_items BETWEEN 21 AND 30 THEN '21-30 items'
                    ELSE '30+ items'
                END as basket_size,
                COUNT(*) as orders,
                ROUND(AVG(fo.reorder_ratio) * 100, 1) as avg_reorder_rate
            FROM Fact_Orders fo
            GROUP BY basket_size
            ORDER BY MIN(fo.total_items)
        """, engine)
        
        if not df_basket.empty:
            fig = px.bar(
                df_basket,
                x='basket_size',
                y='orders',
                color='avg_reorder_rate',
                color_continuous_scale='Viridis',
                labels={
                    'basket_size': 'Basket Size',
                    'orders': 'Number of Orders',
                    'avg_reorder_rate': 'Avg Reorder Rate (%)'
                },
                title='Order Distribution by Basket Size'
            )
            st.plotly_chart(fig, width='stretch')
            
            # Most common basket size
            most_common = df_basket.loc[df_basket['orders'].idxmax()]
            st.info(f"🛒 **Most Common Basket Size:** {most_common['basket_size']} with {int(most_common['orders']):,} orders")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
    
    # Days Since Prior Order
    st.markdown("---")
    st.subheader("📅 Order Frequency Analysis")
    
    try:
        df_frequency = pd.read_sql("""
            SELECT 
                CASE 
                    WHEN fo.days_since_prior = 0 THEN 'Same Day'
                    WHEN fo.days_since_prior BETWEEN 1 AND 7 THEN '1-7 days'
                    WHEN fo.days_since_prior BETWEEN 8 AND 14 THEN '8-14 days'
                    WHEN fo.days_since_prior BETWEEN 15 AND 30 THEN '15-30 days'
                    ELSE '30+ days'
                END as frequency_group,
                COUNT(*) as orders,
                AVG(fo.total_items) as avg_basket
            FROM Fact_Orders fo
            WHERE fo.days_since_prior IS NOT NULL
            GROUP BY frequency_group
            ORDER BY MIN(fo.days_since_prior)
        """, engine)
        
        if not df_frequency.empty:
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=df_frequency['frequency_group'],
                y=df_frequency['orders'],
                name='Orders',
                marker_color='lightblue',
                yaxis='y'
            ))
            
            fig.add_trace(go.Scatter(
                x=df_frequency['frequency_group'],
                y=df_frequency['avg_basket'],
                name='Avg Basket Size',
                marker_color='red',
                mode='lines+markers',
                yaxis='y2'
            ))
            
            fig.update_layout(
                title='Order Frequency vs Basket Size',
                xaxis=dict(title='Days Since Prior Order'),
                yaxis=dict(title='Number of Orders', side='left'),
                yaxis2=dict(title='Avg Basket Size', overlaying='y', side='right'),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, width='stretch')
            
            # Loyal customer insight
            loyal_orders = df_frequency[df_frequency['frequency_group'] == '1-7 days']['orders'].sum()
            total_orders = df_frequency['orders'].sum()
            loyal_percentage = (loyal_orders / total_orders) * 100
            
            st.success(f"💎 **Loyal Customers:** {loyal_percentage:.1f}% of repeat orders happen within 7 days")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
