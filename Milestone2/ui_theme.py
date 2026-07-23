import streamlit as st

def inject_theme():
    """
    Injects custom CSS styling into Streamlit to strictly maintain the exact UI design system
    from Milestone 1 (fonts, colors, card styling, buttons, input fields, and layouts).
    """
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@300;400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');
        
        /* Global Styling - Pure White Background & Modern Corporate Feel */
        html, body, [data-testid="stApp"] {
            background-color: #FFFFFF !important;
            font-family: 'Inter', 'Segoe UI', sans-serif !important;
            color: #323130 !important;
        }
        
        /* Remove Streamlit header decoration line and footer */
        footer, div[data-testid="stDecoration"] {
            visibility: hidden !important;
            display: none !important;
        }
        header {
            background: transparent !important;
        }
        
        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #FFFFFF !important;
            border-right: 1px solid #E5E5E5 !important;
            box-shadow: 2px 0px 8px rgba(0, 0, 0, 0.01) !important;
        }
        
        /* Central Content Soft Gray Cards */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #F9FAFB !important;
            border: 1px solid #E5E7EB !important;
            border-radius: 16px !important;
            padding: 2.5rem !important;
            box-shadow: 0px 4px 18px rgba(0, 0, 0, 0.02) !important;
            margin-bottom: 1.5rem !important;
            transition: box-shadow 0.2s ease-in-out !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            box-shadow: 0px 6px 22px rgba(0, 0, 0, 0.03) !important;
        }
        
        /* Typography */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Segoe UI', sans-serif !important;
            font-weight: 700 !important;
            color: #111827 !important;
            margin-top: 0 !important;
        }
        
        /* Input Labels */
        label p {
            font-weight: 600 !important;
            color: #374151 !important;
            font-size: 14px !important;
            margin-bottom: 4px !important;
        }
        
        /* Inputs Form Styling */
        div[data-baseweb="base-input"], div[data-baseweb="select"] > div {
            background-color: transparent !important;
            border: none !important;
        }
        div[data-baseweb="input"], div[data-baseweb="select"] {
            background-color: #FFFFFF !important;
            border: 1px solid #D1D5DB !important;
            border-radius: 8px !important;
            transition: all 0.15s ease-in-out !important;
        }
        div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within {
            border-color: #0078D4 !important;
            box-shadow: 0 0 0 3px rgba(0, 120, 212, 0.12) !important;
        }
        input, div[data-baseweb="select"] span {
            color: #1F2937 !important;
            -webkit-text-fill-color: #1F2937 !important;
            font-size: 15px !important;
        }
        
        /* Rounded Buttons & Hover Effects */
        div[data-testid="stButton"] button {
            background: linear-gradient(135deg, #0078D4, #005A9E) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 20px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            height: 40px !important;
            min-height: 40px !important;
            width: 100% !important;
            box-shadow: 0px 4px 10px rgba(0, 120, 212, 0.15) !important;
            transition: all 0.2s ease !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }
        div[data-testid="stButton"] button:hover {
            background: linear-gradient(135deg, #005A9E, #004578) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0px 6px 14px rgba(0, 120, 212, 0.25) !important;
        }
        div[data-testid="stButton"] button:active {
            transform: translateY(1px) !important;
        }
        
        /* Custom Secondary Button Style Override */
        div[data-testid="stButton"] button[data-testid="baseButton-secondary"] {
            background: #F3F4F6 !important;
            color: #374151 !important;
            border: 1px solid #D1D5DB !important;
            box-shadow: none !important;
        }
        div[data-testid="stButton"] button[data-testid="baseButton-secondary"]:hover {
            background: #E5E7EB !important;
            color: #111827 !important;
        }
        
        /* Metrics visual cards inside dashboards */
        .dashboard-card {
            background-color: #F9FAFB;
            border: 1px solid #E5E7EB;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.01);
            text-align: center;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            margin-bottom: 12px;
        }
        .dashboard-card:hover {
            transform: translateY(-2px);
            box-shadow: 0px 6px 16px rgba(0, 0, 0, 0.03);
        }
        
        /* Live Password Strength Badge */
        .strength-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
            color: #FFFFFF;
            margin-top: 4px;
        }
    </style>
    """, unsafe_allow_html=True)

def render_auth_header(title_text: str):
    """Renders the standard portal brand header for guest authentication screens."""
    st.markdown(f"""
    <div style="text-align:center; padding:1.5rem 0 1rem;">
        <div style="font-size: 42px; margin-bottom: 10px; color: #0078D4;">📦</div>
        <h1 style="font-size: 2.1rem; font-weight: 700; color: #111827; margin: 0;">Infosys Springboard Portal</h1>
        <p style="color: #4B5563; font-size: 14px; margin: 4px 0 0; font-weight: 400;">
            Intelligent Freight Quote Generation System
        </p>
    </div>
    <div style="text-align:center; margin-bottom: 1.5rem;">
        <span style="font-size: 1.1rem; font-weight: 600; color: #0078D4;">{title_text}</span>
    </div>
    """, unsafe_allow_html=True)

def render_top_header(uname: str, is_admin: bool):
    """Renders the authenticated user banner across dashboard pages."""
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0078D4, #005A9E); border-radius: 16px; padding: 24px 32px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; color: #FFFFFF; box-shadow: 0px 4px 12px rgba(0, 120, 212, 0.15);">
        <div>
            <h1 style="color: #FFFFFF !important; margin: 0; font-size: 24px !important;">Infosys Springboard Portal</h1>
            <div style="color: rgba(255, 255, 255, 0.85); font-size: 13px; font-weight: 500; margin-top: 2px;">
                Intelligent Freight Quote Generation System — Milestone 2
            </div>
        </div>
        <div style="background: rgba(255, 255, 255, 0.2); padding: 8px 18px; border-radius: 30px; font-weight: 600; font-size: 13px; border: 1px solid rgba(255, 255, 255, 0.3);">
            {"🛡️ Administrator" if is_admin else "👤 Portal User"}: {uname}
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_password_strength_badge(score: int, rating: str, color: str, message: str):
    """Renders a live password strength indicator badge in Streamlit forms."""
    st.markdown(f"""
    <div style="margin-top: 4px; margin-bottom: 12px;">
        <span style="font-size: 12px; font-weight: 600; color: #4B5563;">Password Strength: </span>
        <span class="strength-badge" style="background-color: {color};">{rating} ({score}/12)</span>
        <div style="font-size: 11px; color: #6B7280; margin-top: 4px;">{message}</div>
    </div>
    """, unsafe_allow_html=True)

def render_dashboard_card(icon: str, value: str, title: str):
    """Renders a metric card matching Milestone 1 styling."""
    return f"""
    <div class="dashboard-card">
        <div style="font-size: 32px; margin-bottom: 8px;">{icon}</div>
        <div style="font-size: 24px; font-weight: 700; color: #111827;">{value}</div>
        <div style="color: #4B5563; font-size: 13px; font-weight: 600; margin-top: 4px;">{title}</div>
    </div>
    """
