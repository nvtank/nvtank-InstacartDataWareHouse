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
        # First, check what data we actually have
        debug_query = """
            SELECT 
                fo.order_dow,
                fo.time_id,
                COUNT(*) as cnt,
                COUNT(DISTINCT fo.time_id) as distinct_time_ids
            FROM Fact_Orders fo
            GROUP BY fo.order_dow
            ORDER BY fo.order_dow
        """
        debug_df = pd.read_sql(debug_query, engine)
        
        # Try to get data directly from Fact_Orders first, then join for day names
        df_heatmap = pd.read_sql("""
            SELECT 
                fo.order_dow,
                COALESCE(t.dow_name, 
                    CASE fo.order_dow
                        WHEN 0 THEN 'Sunday'
                        WHEN 1 THEN 'Monday'
                        WHEN 2 THEN 'Tuesday'
                        WHEN 3 THEN 'Wednesday'
                        WHEN 4 THEN 'Thursday'
                        WHEN 5 THEN 'Friday'
                        WHEN 6 THEN 'Saturday'
                    END
                ) as dow_name,
                MOD(fo.time_id, 100) as order_hour,
                COUNT(*) as orders
            FROM Fact_Orders fo
            LEFT JOIN Dim_Time t ON fo.time_id = t.time_id
            GROUP BY fo.order_dow, dow_name, order_hour
            ORDER BY fo.order_dow, order_hour
        """, engine)
        
        if not df_heatmap.empty:
            # Show debug info
            with st.expander("🔍 Debug Information", expanded=False):
                st.markdown("**Data Distribution by Day of Week:**")
                st.dataframe(debug_df, use_container_width=True, hide_index=True)
                st.markdown(f"**Total unique combinations:** {len(df_heatmap)}")
                st.markdown(f"**Unique days:** {df_heatmap['order_dow'].nunique()}")
                st.markdown(f"**Unique hours:** {df_heatmap['order_hour'].nunique()}")
            
            # Show data statistics
            with st.expander("📊 Data Statistics & Raw Data", expanded=True):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Min Orders", f"{df_heatmap['orders'].min():,}")
                with col2:
                    st.metric("Max Orders", f"{df_heatmap['orders'].max():,}")
                with col3:
                    range_val = df_heatmap['orders'].max() - df_heatmap['orders'].min()
                    st.metric("Range", f"{range_val:,.0f}")
                with col4:
                    st.metric("Std Dev", f"{df_heatmap['orders'].std():,.2f}")
                
                # Show raw data table
                st.markdown("**Raw Data (First 20 rows):**")
                st.dataframe(
                    df_heatmap.head(20).style.background_gradient(subset=['orders'], cmap='YlOrRd'),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Show full pivot table
                st.markdown("**Full Data Matrix:**")
                pivot_display = df_heatmap.pivot(
                    index='order_hour', 
                    columns='dow_name', 
                    values='orders'
                )
                day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 
                            'Thursday', 'Friday', 'Saturday']
                pivot_display = pivot_display[[col for col in day_order if col in pivot_display.columns]]
                st.dataframe(
                    pivot_display.style.background_gradient(axis=None, cmap='YlOrRd'),
                    use_container_width=True
                )
            
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
            
            # Fill any NaN values with 0 (shouldn't happen, but just in case)
            pivot = pivot.fillna(0)
            
            # Calculate statistics for better color scale
            z_min = pivot.values.min()
            z_max = pivot.values.max()
            z_mean = pivot.values.mean()
            z_std = pivot.values.std()
            
            # Use percentile-based scaling if range is too small
            # This helps when all values are very close together
            if (z_max - z_min) < z_mean * 0.01:  # If range is less than 1% of mean
                # Use percentile-based bounds for better visualization
                z_p5 = pd.DataFrame(pivot.values).quantile(0.05).iloc[0]
                z_p95 = pd.DataFrame(pivot.values).quantile(0.95).iloc[0]
                z_min_display = max(z_min, z_p5 - (z_p95 - z_p5) * 0.1)
                z_max_display = min(z_max, z_p95 + (z_p95 - z_p5) * 0.1)
                st.warning(f"⚠️ Data has very small range ({z_max - z_min:.1f}). Using enhanced color scale for better visualization.")
            else:
                z_min_display = z_min
                z_max_display = z_max
            
            # Create heatmap with better color differentiation
            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns,
                y=pivot.index,
                colorscale=[
                    [0, 'rgb(68,1,84)'],      # Dark purple (lowest)
                    [0.1, 'rgb(59,82,139)'],   # Blue
                    [0.3, 'rgb(33,144,140)'],  # Teal
                    [0.5, 'rgb(92,200,99)'],   # Green
                    [0.7, 'rgb(253,231,37)'], # Yellow
                    [1, 'rgb(255,0,0)']        # Red (highest)
                ],
                zmin=z_min_display,
                zmax=z_max_display,
                colorbar=dict(
                    title="Orders",
                    tickformat=","
                ),
                hovertemplate='<b>%{x}</b><br>Hour: %{y}<br>Orders: %{z:,}<extra></extra>',
                text=pivot.values,  # Show values on heatmap
                texttemplate='%{text:,}',
                textfont={"size": 9, "color": "white"}
            ))
            
            fig.update_layout(
                xaxis_title="Day of Week",
                yaxis_title="Hour of Day",
                height=700,
                yaxis=dict(
                    tickmode='linear', 
                    tick0=0, 
                    dtick=1,
                    autorange='reversed'  # Reverse so hour 0 is at top
                ),
                xaxis=dict(side='bottom')
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Find peak and minimum times
            peak_idx = df_heatmap['orders'].idxmax()
            peak_row = df_heatmap.loc[peak_idx]
            
            min_idx = df_heatmap['orders'].idxmin()
            min_row = df_heatmap.loc[min_idx]
            
            col1, col2 = st.columns(2)
            with col1:
                st.success(f"🔥 **Peak Time:** {peak_row['dow_name']} at {int(peak_row['order_hour']):02d}:00 with {int(peak_row['orders']):,} orders")
            with col2:
                st.info(f"❄️ **Lowest Time:** {min_row['dow_name']} at {int(min_row['order_hour']):02d}:00 with {int(min_row['orders']):,} orders")
            
            # Show top 5 and bottom 5 times
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🔝 Top 5 Times:**")
                top5 = df_heatmap.nlargest(5, 'orders')[['dow_name', 'order_hour', 'orders']]
                top5['time'] = top5['dow_name'] + ' ' + top5['order_hour'].astype(str) + ':00'
                st.dataframe(
                    top5[['time', 'orders']].style.background_gradient(subset=['orders'], cmap='YlOrRd'),
                    use_container_width=True,
                    hide_index=True
                )
            with col2:
                st.markdown("**🔻 Bottom 5 Times:**")
                bottom5 = df_heatmap.nsmallest(5, 'orders')[['dow_name', 'order_hour', 'orders']]
                bottom5['time'] = bottom5['dow_name'] + ' ' + bottom5['order_hour'].astype(str) + ':00'
                st.dataframe(
                    bottom5[['time', 'orders']].style.background_gradient(subset=['orders'], cmap='YlOrRd'),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("No data available. Please run ETL pipeline first.")
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
    
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
            weekday_df = df_comparison[df_comparison['day_type'] == 'Weekday']
            weekend_df = df_comparison[df_comparison['day_type'] == 'Weekend']
            
            if not weekday_df.empty and not weekend_df.empty:
                weekday_row = weekday_df.iloc[0]
                weekend_row = weekend_df.iloc[0]
                
                order_diff = ((weekend_row['orders'] - weekday_row['orders']) / weekday_row['orders']) * 100
                
                if order_diff > 0:
                    st.info(f"📈 Weekend orders are **{order_diff:.1f}%** higher than weekday orders")
                else:
                    st.info(f"📉 Weekday orders are **{abs(order_diff):.1f}%** higher than weekend orders")
            else:
                st.warning("⚠️ Cannot compare: Missing weekday or weekend data")
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
