"""Shared green visual system sampled from the user's screenshot (~#ADD47E)."""
import streamlit as st

CSS = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@500;600;700;800&display=swap');
html, body, [class*="css"], [data-testid="stAppViewContainer"] {font-family: 'DM Sans', sans-serif;}
[data-testid="stAppViewContainer"] {background: #f7faf4; color: #173728;}
[data-testid="stSidebar"] {background: #f0f6eb; border-right: 1px solid #dfebd6;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {color: #284833;}
.block-container {max-width: 1160px; padding-top: 1.7rem; padding-bottom: 3rem;}
h1,h2,h3 {font-family: 'Manrope',sans-serif; letter-spacing: -.035em; color:#173728;}
h1 {font-weight: 800;} .stCaption,small {color:#607466;}
.hero {background: linear-gradient(115deg,#add47e 0%,#d6edb9 62%,#eff8e5 100%); padding: 34px 38px;
       border: 1px solid #c7e3ab; border-radius: 26px; overflow: hidden; position: relative;
       box-shadow:0 12px 38px rgba(65,101,52,.08); margin-bottom: 22px;}
.hero:after {content:''; position:absolute; width:290px; height:290px; right:-70px; top:-145px;
       border:50px solid rgba(255,255,255,.22); border-radius:50%; pointer-events:none;}
.hero-label {text-transform:uppercase; font-size:11px; font-weight:800; letter-spacing:.16em; color:#385b37;}
.hero-title {font-size:clamp(28px,4vw,42px); font-family:Manrope,sans-serif; font-weight:800; letter-spacing:-.055em; color:#173728; line-height:1.18; margin:8px 0 8px;}
.hero-p {font-size:14px; max-width:570px; color:#36533c; line-height:1.65; margin:0;}
.brand {font-family:Manrope,sans-serif; font-size:27px; font-weight:800; letter-spacing:-.055em; color:#153820;}
.brand-dot {display:inline-block; background:#add47e; border-radius:7px; padding:0px 9px;}
.mini-label {font-size:11px; text-transform:uppercase; letter-spacing:.13em; font-weight:800; color:#6b7e70; margin-top:10px;}
.stat-card {border:1px solid #e0ebda; border-radius:20px; background:#fff; padding:22px 22px 16px;
      min-height:139px; box-shadow:0 7px 22px rgba(20,54,33,.035);}
.stat-icon {font-size:20px; margin-bottom:10px;}
.stat-label {font-size:12px; font-weight:700; color:#6a7d70; margin:0 0 4px;}
.stat-number {font-family:Manrope,sans-serif; font-weight:800; font-size:27px; letter-spacing:-.055em; color:#173728; margin:0;}
.stat-foot {color:#7a8b7b;font-size:11px;margin-top:9px;}
.section-title {font-family:Manrope,sans-serif; font-size:18px; font-weight:800; letter-spacing:-.035em; margin:25px 0 14px; color:#173728;}
.quick-card {border:1px solid #dfebd8; padding:22px; border-radius:20px; background:#fff; min-height:133px;}
.quick-head {font-size:23px; margin-bottom:10px;}
.quick-name {font-family:Manrope,sans-serif; font-size:16px; font-weight:800; color:#1d3c2a;}
.quick-sub {font-size:12px;color:#748678;margin-top:5px;}
.note {background:#eef7e7; border-left:4px solid #8fb968; border-radius:9px; padding:13px 16px; color:#36523a; font-size:13px; line-height:1.6; margin:14px 0;}
.eyebrow {font-size:12px; font-weight:750; color:#5d8550; text-transform:uppercase; letter-spacing:.1em;}
[data-testid="stForm"] {border:1px solid #e2ecdc; border-radius:20px; background:#fff; padding:1.2rem;}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {background:#315d37; border-color:#315d37; color:white; border-radius:12px; font-weight:750;}
.stButton > button[kind="primary"]:hover {background:#214c2e; border-color:#214c2e;}
.stButton > button {border-radius:12px;}
[data-testid="stFileUploader"], [data-testid="stCameraInput"] {background:white; border-radius:14px; padding:7px;}
[data-testid="stMetric"] {background:white; border:1px solid #dfead7; border-radius:16px; padding:16px;}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:#dfead7;}
@media (max-width:640px) {.hero {padding:26px 24px;} .block-container {padding-top:1rem;} .hero-title {font-size:31px;} }
</style>'''

def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)
