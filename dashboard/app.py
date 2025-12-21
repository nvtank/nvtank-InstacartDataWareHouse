import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text
import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from etl.config import get_engine

# Page config
st.set_page_config(
    page_title="Instacart Analytics Dashboard",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize database connection
@st.cache_resource
def init_connection():
    return get_engine()

engine = init_connection()

# Sidebar navigation
st.sidebar.title("🛒 Instacart DWH")
st.sidebar.markdown("**Data Warehouse & Analytics**")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "📑 Navigation",
    ["📊 Overview", "🏆 Products", "⏰ Time Analysis", 
     "👥 Customers", "🏪 Departments", "🗄️ Tables"]
)

st.sidebar.markdown("---")
st.sidebar.info("""
**Dashboard Features:**
- Real-time KPI tracking
- Interactive visualizations
- Customer segmentation
- Product recommendations
""")

# Main title
st.markdown('<p class="main-header">🛒 Instacart Analytics Dashboard</p>', 
            unsafe_allow_html=True)

# Page routing
if page == "📊 Overview":
    from pages import overview
    overview.show(engine)
elif page == "🏆 Products":
    from pages import products
    products.show(engine)
elif page == "⏰ Time Analysis":
    from pages import time_analysis
    time_analysis.show(engine)
elif page == "👥 Customers":
    from pages import customers
    customers.show(engine)
elif page == "🏪 Departments":
    from pages import departments
    departments.show(engine)
elif page == "🗄️ Tables":
    from pages import tables
    tables.show(engine)
