import streamlit as st
import pandas as pd
from sqlalchemy import text, inspect

@st.cache_data(ttl=300)
def get_table_schema(_engine, table_name):
    """Get column information for a table"""
    inspector = inspect(_engine)
    columns = inspector.get_columns(table_name)
    return pd.DataFrame([
        {
            'Column': col['name'],
            'Type': str(col['type']),
            'Nullable': 'Yes' if col['nullable'] else 'No',
            'Default': str(col['default']) if col['default'] is not None else '',
            'Comment': col.get('comment', '')
        }
        for col in columns
    ])

@st.cache_data(ttl=300)
def get_table_indexes(_engine, table_name):
    """Get index information for a table"""
    inspector = inspect(_engine)
    indexes = inspector.get_indexes(table_name)
    if not indexes:
        return pd.DataFrame()
    
    return pd.DataFrame([
        {
            'Index Name': idx['name'],
            'Columns': ', '.join(idx['column_names']),
            'Unique': 'Yes' if idx['unique'] else 'No'
        }
        for idx in indexes
    ])

@st.cache_data(ttl=300)
def get_table_row_count(_engine, table_name):
    """Get row count for a table"""
    try:
        result = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {table_name}", _engine)
        return result.iloc[0, 0]
    except Exception as e:
        return None

@st.cache_data(ttl=300)
def get_table_sample(_engine, table_name, limit=10):
    """Get sample data from a table"""
    try:
        return pd.read_sql(f"SELECT * FROM {table_name} LIMIT {limit}", _engine)
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_table_partitions(_engine, table_name):
    """Get partition information for a table"""
    try:
        query = f"""
        SELECT 
            PARTITION_NAME as 'Partition',
            TABLE_ROWS as 'Rows',
            DATA_LENGTH / 1024 / 1024 as 'Size (MB)',
            PARTITION_COMMENT as 'Comment'
        FROM information_schema.PARTITIONS
        WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = '{table_name}'
            AND PARTITION_NAME IS NOT NULL
        ORDER BY PARTITION_ORDINAL_POSITION
        """
        result = pd.read_sql(query, _engine)
        return result if not result.empty else None
    except Exception as e:
        return None

def show_table_details(engine, table_name, table_type):
    """Display detailed information about a table"""
    st.subheader(f"📋 {table_name}")
    st.caption(f"Type: {table_type}")
    
    # Get row count
    row_count = get_table_row_count(engine, table_name)
    if row_count is not None:
        st.metric("Total Rows", f"{row_count:,}")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Schema", "📝 Sample Data", "🔍 Indexes", "🗂️ Partitions"])
    
    with tab1:
        st.markdown("**Table Schema**")
        try:
            schema_df = get_table_schema(engine, table_name)
            if not schema_df.empty:
                st.dataframe(schema_df, use_container_width=True, hide_index=True)
            else:
                st.info("No schema information available")
        except Exception as e:
            st.error(f"Error loading schema: {str(e)}")
    
    with tab2:
        st.markdown("**Sample Data (First 10 rows)**")
        try:
            sample_df = get_table_sample(engine, table_name, limit=10)
            if not sample_df.empty:
                st.dataframe(sample_df, use_container_width=True, hide_index=True)
            else:
                st.info("No data available in this table")
        except Exception as e:
            st.error(f"Error loading sample data: {str(e)}")
    
    with tab3:
        st.markdown("**Indexes**")
        try:
            indexes_df = get_table_indexes(engine, table_name)
            if not indexes_df.empty:
                st.dataframe(indexes_df, use_container_width=True, hide_index=True)
            else:
                st.info("No indexes defined for this table")
        except Exception as e:
            st.error(f"Error loading indexes: {str(e)}")
    
    with tab4:
        st.markdown("**Partitions**")
        try:
            partitions_df = get_table_partitions(engine, table_name)
            if partitions_df is not None and not partitions_df.empty:
                st.dataframe(partitions_df, use_container_width=True, hide_index=True)
                
                # Show partition summary
                total_rows = partitions_df['Rows'].sum()
                total_size = partitions_df['Size (MB)'].sum()
                st.metric("Total Partitioned Rows", f"{int(total_rows):,}")
                st.metric("Total Size", f"{total_size:.2f} MB")
            else:
                st.info("This table is not partitioned")
        except Exception as e:
            st.error(f"Error loading partitions: {str(e)}")

def show(engine):
    st.header("🗄️ Database Schema & Tables")
    st.markdown("View detailed information about all dimension and fact tables in the data warehouse")
    
    # Table categories
    dim_tables = {
        "Dim_Time": "Time dimension for order analysis",
        "Dim_Department": "Department dimension",
        "Dim_Aisle": "Aisle dimension",
        "Dim_Product": "Product dimension",
        "Dim_User": "User/Customer dimension"
    }
    
    fact_tables = {
        "Fact_Orders": "Order summary fact table",
        "Fact_Order_Details": "Order line items fact table"
    }
    
    # Sidebar for quick navigation
    st.sidebar.markdown("### Quick Navigation")
    
    # Dimension tables section
    st.markdown("## 📐 Dimension Tables")
    st.markdown("Dimension tables store descriptive attributes for analysis")
    
    for i, (table_name, description) in enumerate(dim_tables.items()):
        with st.expander(f"🔷 {table_name} - {description}", expanded=(i == 0)):
            show_table_details(engine, table_name, "Dimension")
        st.markdown("---")
    
    # Fact tables section
    st.markdown("## 📊 Fact Tables")
    st.markdown("Fact tables store measurable business events and metrics")
    
    for i, (table_name, description) in enumerate(fact_tables.items()):
        with st.expander(f"🔶 {table_name} - {description}", expanded=(i == 0)):
            show_table_details(engine, table_name, "Fact")
        st.markdown("---")
    
    # Summary section
    st.markdown("## 📈 Database Summary")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Dimension Tables")
        dim_summary = []
        for table_name in dim_tables.keys():
            count = get_table_row_count(engine, table_name)
            if count is not None:
                dim_summary.append({"Table": table_name, "Rows": f"{count:,}"})
        if dim_summary:
            st.dataframe(pd.DataFrame(dim_summary), use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("### Fact Tables")
        fact_summary = []
        for table_name in fact_tables.keys():
            count = get_table_row_count(engine, table_name)
            if count is not None:
                fact_summary.append({"Table": table_name, "Rows": f"{count:,}"})
        if fact_summary:
            st.dataframe(pd.DataFrame(fact_summary), use_container_width=True, hide_index=True)
