import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def show(engine):
    st.header("⏰ Time Analysis")
    st.markdown("Analyze temporal patterns and shopping behaviors")
    
    # Heatmap: Hour x Day of Week
    st.subheader("🔥 Order Heatmap: Hour x Day of Week")
    
    try:
        df_heatmap = pd.read_sql("""
            SELECT 
                t.order_dow,
                t.dow_name,
                t.order_hour,
                COUNT(*) as orders
            FROM Fact_Orders fo
            JOIN Dim_Time t ON fo.time_id = t.time_id
            GROUP BY t.order_dow, t.dow_name, t.order_hour
            ORDER BY t.order_dow, t.order_hour
        """, engine)
        
        if not df_heatmap.empty:
            # Pivot for heatmap
            pivot = df_heatmap.pivot(
                index='order_hour', 
                columns='dow_name', 
                values='orders'
            )
            
            # Reorder columns to start from Sunday
            day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 
                        'Thursday', 'Friday', 'Saturday']
            pivot = pivot[[col for col in day_order if col in pivot.columns]]
            
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns,
                y=pivot.index,
                colorscale='YlOrRd',
                colorbar=dict(title="Orders"),
                hovertemplate='<b>%{x}</b><br>Hour: %{y}<br>Orders: %{z:,}<extra></extra>'
            ))
            
            fig.update_layout(
                xaxis_title="Day of Week",
                yaxis_title="Hour of Day",
                height=500,
                yaxis=dict(tickmode='linear', tick0=0, dtick=2)
            )
            st.plotly_chart(fig, width='stretch')
            
            # Find peak time
            peak_idx = df_heatmap['orders'].idxmax()
            peak_row = df_heatmap.loc[peak_idx]
            st.success(f"🔥 **Peak Time:** {peak_row['dow_name']} at {int(peak_row['order_hour'])}:00 with {int(peak_row['orders']):,} orders")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
    
    # Weekend vs Weekday
    st.markdown("---")
    st.subheader("📊 Weekend vs Weekday Comparison")
    
    try:
        df_comparison = pd.read_sql("""
            SELECT 
                CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END as day_type,
                COUNT(DISTINCT fo.order_id) as orders,
                AVG(fo.total_items) as avg_basket,
                AVG(fo.reorder_ratio) * 100 as avg_reorder
            FROM Fact_Orders fo
            JOIN Dim_Time t ON fo.time_id = t.time_id
            GROUP BY day_type
        """, engine)
        
        if not df_comparison.empty:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                fig = px.bar(
                    df_comparison, 
                    x='day_type', 
                    y='orders', 
                    color='day_type', 
                    color_discrete_sequence=['#636EFA', '#EF553B'],
                    labels={'orders': 'Total Orders', 'day_type': ''}
                )
                fig.update_layout(showlegend=False, title="Total Orders")
                st.plotly_chart(fig, width='stretch')
            
            with col2:
                fig = px.bar(
                    df_comparison, 
                    x='day_type', 
                    y='avg_basket',
                    color='day_type', 
                    color_discrete_sequence=['#636EFA', '#EF553B'],
                    labels={'avg_basket': 'Avg Items', 'day_type': ''}
                )
                fig.update_layout(showlegend=False, title="Avg Basket Size")
                st.plotly_chart(fig, width='stretch')
            
            with col3:
                fig = px.bar(
                    df_comparison, 
                    x='day_type', 
                    y='avg_reorder',
                    color='day_type', 
                    color_discrete_sequence=['#636EFA', '#EF553B'],
                    labels={'avg_reorder': 'Reorder Rate (%)', 'day_type': ''}
                )
                fig.update_layout(showlegend=False, title="Avg Reorder Rate %")
                st.plotly_chart(fig, width='stretch')
            
            # Comparison insights
            weekday_row = df_comparison[df_comparison['day_type'] == 'Weekday'].iloc[0]
            weekend_row = df_comparison[df_comparison['day_type'] == 'Weekend'].iloc[0]
            
            order_diff = ((weekend_row['orders'] - weekday_row['orders']) / weekday_row['orders']) * 100
            
            if order_diff > 0:
                st.info(f"📈 Weekend orders are **{order_diff:.1f}%** higher than weekday orders")
            else:
                st.info(f"📉 Weekday orders are **{abs(order_diff):.1f}%** higher than weekend orders")
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
    
    # Hourly distribution by weekday/weekend
    st.markdown("---")
    st.subheader("📈 Hourly Order Distribution: Weekday vs Weekend")
    
    try:
        df_hourly = pd.read_sql("""
            SELECT 
                t.order_hour,
                CASE WHEN t.is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END as day_type,
                COUNT(*) as orders
            FROM Fact_Orders fo
            JOIN Dim_Time t ON fo.time_id = t.time_id
            GROUP BY t.order_hour, day_type
            ORDER BY t.order_hour
        """, engine)
        
        if not df_hourly.empty:
            fig = px.line(
                df_hourly,
                x='order_hour',
                y='orders',
                color='day_type',
                markers=True,
                labels={
                    'order_hour': 'Hour of Day',
                    'orders': 'Number of Orders',
                    'day_type': 'Day Type'
                }
            )
            fig.update_layout(
                hovermode='x unified',
                xaxis=dict(tickmode='linear', tick0=0, dtick=2),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
