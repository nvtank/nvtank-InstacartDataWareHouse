#!/usr/bin/env python3
"""
Clear Streamlit Cache
Run this if you want to force refresh all cached data
"""
import streamlit as st
import sys
import os

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def clear_all_caches():
    """Clear all Streamlit caches"""
    print("🧹 Clearing Streamlit caches...")
    
    try:
        # Clear data cache
        st.cache_data.clear()
        print("  ✓ Cleared @st.cache_data")
    except Exception as e:
        print(f"  ✗ Error clearing cache_data: {e}")
    
    try:
        # Clear resource cache
        st.cache_resource.clear()
        print("  ✓ Cleared @st.cache_resource")
    except Exception as e:
        print(f"  ✗ Error clearing cache_resource: {e}")
    
    print("\n✅ Cache cleared! Restart dashboard to see fresh data.")
    print("   Run: ./run_dashboard.sh")

if __name__ == "__main__":
    clear_all_caches()
