"""FaithBloom's illustrated dashboard and shared, accessible navigation.

The reference images are kept intact. CSS frames reveal the supplied logo,
welcome artwork and sidebar illustration without modifying their pixels.
All navigation remains native Streamlit navigation.
"""
from __future__ import annotations

from base64 import b64encode
from functools import lru_cache
from html import escape
from pathlib import Path
import re

import streamlit as st

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=3)
def _asset(name: str) -> str:
    """Embed local artwork so it also works on Streamlit Cloud."""
    content = (ROOT / "assets" / name).read_bytes()
    return "data:image/jpeg;base64," + b64encode(content).decode("ascii")


CSS = """
<style>
:root {
  --fb-ink: #101e56; --fb-muted: #79829f; --fb-lilac: #8d39f4;
  --fb-pink: #f62c92; --fb-blue: #129be8; --fb-green: #00b77e;
  --fb-border: #ececf6; --fb-surface: #ffffff;
}
.stApp { background: linear-gradient(125deg,#fff 45%,#fdfbff 100%); color:var(--fb-ink); }
[data-testid="stMainBlockContainer"], .block-container {
  max-width:1600px; padding: .85rem 1.2rem 2.6rem;
}
[data-testid="stMain"] > div > div > [data-testid="stVerticalBlock"] { gap:.7rem; }
h1,h2,h3,h4,p { color:inherit; }
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown h4 { color:var(--fb-ink); }
[data-testid="stHeader"] { background:transparent; height:2.7rem; }
[data-testid="stDecoration"] { display:none; }
section[data-testid="stSidebar"] {
  width:220px !important; min-width:220px !important;
  background:linear-gradient(180deg,#ffffff 0%,#f8f9ff 100%);
  border-right:1px solid #ececf6;
}
[data-testid="stSidebarContent"] { padding:.3rem .7rem 1rem; }
[data-testid="stSidebarUserContent"] { padding:0; }
[data-testid="stSidebarHeader"] { padding:.3rem .3rem 0; height:1.6rem; }
[data-testid="stSidebarNav"] { display:none; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.18rem; }
[data-testid="stSidebar"] [data-testid="stPageLink"] { margin:0; }
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
  border:0 !important; box-shadow:none; background:transparent !important;
  min-height:34px; padding:6px 10px !important; gap:12px; border-radius:10px !important;
  color:var(--fb-ink); font-size:.79rem;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p { font-size:.79rem; font-weight:500; }
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
  transform:none; background:#f0e9ff !important;
}
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"],
[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-selected="true"] {
  color:#7d28e5; background:#eee4ff !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] {
  border:0 !important; background:transparent; border-radius:0 !important;
  box-shadow:none; border-top:1px solid #e9eaf4 !important; margin-top:.35rem;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary { padding:.6rem .35rem; }
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {
  font-size:.63rem; font-weight:700; color:#434e7c; letter-spacing:.02em;
}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] { padding:0; }
.st-key-fb_side_create [data-testid="stPageLink-NavLink"] span { color:#f62c92; }
.st-key-fb_side_continue [data-testid="stPageLink-NavLink"] span { color:#129be8; }
.st-key-fb_side_characters [data-testid="stPageLink-NavLink"] span { color:#00b77e; }
.st-key-fb_side_images [data-testid="stPageLink-NavLink"] span { color:#edaa00; }
.st-key-fb_side_text [data-testid="stPageLink-NavLink"] span { color:#8d39f4; }
.st-key-fb_side_publish [data-testid="stPageLink-NavLink"] span { color:#f62c92; }
.fb-brand-frame,.fb-promo-frame { position:relative; overflow:hidden; }
.fb-brand-frame { width:180px; max-width:100%; aspect-ratio:173 / 49; margin:0 auto .9rem; }
.fb-brand-frame img { position:absolute; width:739.885%; max-width:none; left:-9.827%; top:-20.408%; }
.fb-promo-frame { width:100%; aspect-ratio:196 / 128; border-radius:12px; margin-top:1.4rem; }
.fb-promo-frame img { position:absolute; width:653.061%; max-width:none; left:-6.633%; top:-449.219%; }
.fb-brand-frame.fb-brand-inline { width:170px; margin:0; }
.fb-banner { position:relative; margin:.2rem 0 .1rem; }
.fb-banner-frame { position:relative; width:100%; aspect-ratio:1280 / 575; overflow:hidden;
  border-radius:15px; isolation:isolate; container-type:inline-size; }
.fb-banner-frame > img { display:block; width:100%; height:100%; object-fit:contain; }
.fb-banner-desktop { aspect-ratio:1032 / 175; }
.fb-banner-desktop > img { position:absolute; width:124.031%; height:auto; max-width:none;
  left:-22.674%; top:-33.143%; object-fit:initial; }
.fb-banner-mobile { display:none; }
.fb-greeting { position:absolute; left:37%; top:12.65%; width:22%; height:11.25%; display:flex;
  align-items:center; background:linear-gradient(110deg,#c4e9ff,#d9ecfd 80%,#e9f0fc); border-radius:3px;
  color:#081848; font-weight:800; line-height:1; font-size:var(--greeting-size,5.4cqw); white-space:nowrap;
}
.fb-banner-motion { position:absolute; inset:0; pointer-events:none; overflow:hidden; z-index:2; }
.fb-banner-motion span,.fb-banner-motion svg { pointer-events:none; }
.fb-petal { position:absolute; left:var(--petal-left); top:-8%; width:.95%; height:2.5%;
  border-radius:90% 10% 85% 15%; background:linear-gradient(135deg,#ffd9ec,#f8a6c7 70%,#f794bb);
  box-shadow:inset 1px 1px 2px #fff9; opacity:0;
  animation:fb-petal-fall var(--petal-duration,20s) linear var(--petal-delay,0s) infinite;
}
.fb-petal-garden { animation-name:fb-petal-garden-fall; }
.fb-banner-star { position:absolute; color:#fff7c9; text-shadow:0 0 8px #ffe698;
  font-size:2.1cqw; line-height:1; opacity:.5; animation:fb-star-twinkle 3.8s ease-in-out infinite; }
.fb-banner-star-one { left:60.6%; top:8%; }
.fb-banner-star-two { left:62.7%; top:18.6%; font-size:1.35cqw; animation-delay:-1.8s; }
.fb-banner-star-three { left:22.2%; top:12.5%; font-size:1.2cqw; animation-delay:-2.6s; }
.fb-butterfly { position:absolute; width:3%; height:auto; opacity:.8;
  animation:fb-butterfly-float 8s ease-in-out infinite; }
.fb-butterfly > svg { display:block; width:100%; height:auto; overflow:visible; }
.fb-butterfly-one { left:15%; top:10%; }
.fb-butterfly-two { left:79%; top:7.5%; width:2.4%; animation-delay:-3.5s; }
.fb-butterfly-wings { transform-box:fill-box; transform-origin:center;
  animation:fb-butterfly-flutter .95s ease-in-out infinite alternate; }
.fb-heart-glow { position:absolute; left:78.6%; top:66.5%; width:5.4%; height:12.5%;
  border-radius:50%; background:radial-gradient(ellipse,#ff4adb44 0%,#ff72df33 35%,#ff78e100 75%);
  filter:blur(2px); animation:fb-heart-glow 4.2s ease-in-out infinite; }
.fb-banner-motion-paused * { animation-play-state:paused !important; }
.fb-banner-desktop .fb-greeting { left:40.3%; top:9.6%; width:17.1%; height:22.5%;
  background:linear-gradient(110deg,#e3f0ff,#ecf1ff 80%,#f4f2fc); }
.fb-banner-desktop .fb-petal { height:5.5%; }
.fb-banner-desktop .fb-banner-star-one { left:58%; top:8%; }
.fb-banner-desktop .fb-banner-star-two { left:59.3%; top:28%; }
.fb-banner-desktop .fb-banner-star-three { left:36.5%; top:10%; }
.fb-banner-desktop .fb-heart-glow { left:78.3%; top:75%; width:4.8%; height:28%; }
.st-key-fb_banner_controls { margin-top:-.15rem; margin-bottom:-.65rem; }
.st-key-fb_banner_controls [data-testid="stToggle"],
.st-key-fb_banner_controls [data-testid="stCheckbox"] { width:max-content; margin-left:auto; }
.st-key-fb_banner_controls [data-testid="stToggle"] p,
.st-key-fb_banner_controls [data-testid="stCheckbox"] p { font-size:.69rem; color:#6d7491; }
@keyframes fb-petal-fall {
  0% { top:-8%; transform:translateX(0) rotate(-20deg); opacity:0; }
  10% { opacity:.7; }
  90% { opacity:.65; }
  100% { top:108%; transform:translateX(10px) rotate(260deg); opacity:0; }
}
@keyframes fb-petal-garden-fall {
  0% { top:48%; transform:translateX(0) rotate(-35deg); opacity:0; }
  12% { opacity:.6; }
  88% { opacity:.6; }
  100% { top:108%; transform:translateX(-8px) rotate(220deg); opacity:0; }
}
@keyframes fb-star-twinkle { 0%,100% { opacity:.2; } 50% { opacity:.9; } }
@keyframes fb-butterfly-float {
  0%,100% { transform:translate(0,0) rotate(-7deg); }
  50% { transform:translate(6px,-5px) rotate(7deg); }
}
@keyframes fb-butterfly-flutter { from { transform:scaleX(1); } to { transform:scaleX(.65); } }
@keyframes fb-heart-glow { 0%,100% { opacity:.3; } 50% { opacity:.85; } }
.fb-sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
[class*="st-key-fb_action_"] {
  position:relative; border-radius:14px; padding:0 !important; overflow:visible;
  border:1px solid rgba(255,255,255,.75); min-height:90px;
  transition:transform .15s ease,box-shadow .15s ease;
}
[class*="st-key-fb_action_"]:hover { transform:translateY(-2px); box-shadow:0 7px 18px #2730680d; }
[class*="st-key-fb_action_"] [data-testid="stVerticalBlock"] { gap:0; }
[class*="st-key-fb_action_"] [data-testid="stElementContainer"]:has([data-testid="stPageLink"]) {
  position:absolute !important; inset:0; width:100%; height:100%; z-index:2;
}
[class*="st-key-fb_action_"] [data-testid="stPageLink"] { position:absolute; inset:0; z-index:2; }
[class*="st-key-fb_action_"] a[data-testid="stPageLink-NavLink"] {
  position:absolute; inset:0; width:100%; height:100%; border:0 !important;
  background:transparent !important; border-radius:14px !important; padding:0 !important;
}
[class*="st-key-fb_action_"] a[data-testid="stPageLink-NavLink"] p { opacity:0; }
[class*="st-key-fb_action_"] a[data-testid="stPageLink-NavLink"]:hover { transform:none; }
.fb-action { display:flex; align-items:center; gap:14px; padding:13px 12px; min-height:88px; border-radius:14px; }
.fb-action-icon { flex:0 0 56px; width:56px; height:58px; border-radius:13px;
  display:flex; align-items:center; justify-content:center; background:var(--action-icon-bg); color:var(--action-color); }
.fb-action-icon svg { width:39px; height:39px; }
.fb-action-copy { flex:1; min-width:0; }
.fb-action-copy h3 { font-size:1rem; font-weight:750; margin:0 0 2px; line-height:1.2; letter-spacing:-.025em; }
.fb-action-copy p { color:#283766; font-size:.8rem; line-height:1.35; margin:0; }
.fb-action-arrow { flex:0 0 27px; width:27px; height:27px; border-radius:50%; display:flex; align-items:center;
  justify-content:center; background:var(--action-icon-bg); color:var(--action-color); font-size:20px; }
[class*="st-key-fb_action_"]:has(.fb-action-pink) { background:#fff0f7; }
[class*="st-key-fb_action_"]:has(.fb-action-blue) { background:#eaf6ff; }
[class*="st-key-fb_action_"]:has(.fb-action-mint) { background:#e8fcf3; }
[class*="st-key-fb_action_"]:has(.fb-action-yellow) { background:#fff8e8; }
[class*="st-key-fb_action_"]:has(.fb-action-lilac) { background:#f2eaff; }
.fb-action-pink { --action-color:#f32a90; --action-icon-bg:#ffdbed; }
.fb-action-blue { --action-color:#0799ec; --action-icon-bg:#d5eeff; }
.fb-action-mint { --action-color:#00b77e; --action-icon-bg:#cef8e6; }
.fb-action-yellow { --action-color:#f0a400; --action-icon-bg:#ffedbc; }
.fb-action-lilac { --action-color:#8c34ed; --action-icon-bg:#e5d5ff; }
[data-testid="stButton"] > button,[data-testid="stDownloadButton"] > button { border-color:#e2ddef !important; color:var(--fb-ink); }
[data-testid="stButton"] > button[kind="primary"] {
  background:linear-gradient(105deg,#fb88b5,#bb55ed 60%,#8b68ff) !important;
  border:0 !important; color:white !important; box-shadow:none !important;
}
a:focus-visible,button:focus-visible,input:focus-visible,textarea:focus-visible,
[class*="st-key-fb_action_"] a[data-testid="stPageLink-NavLink"]:focus-visible {
  outline:3px solid #8033dc !important; outline-offset:3px; box-shadow:0 0 0 5px #f4eaff !important;
}
div[data-baseweb="input"] > div,div[data-baseweb="textarea"] > div,div[data-baseweb="select"] > div {
  background:#fff !important; border-color:#e5e6f0 !important; border-radius:10px !important;
}
.fb-panel-heading { display:flex; gap:10px; align-items:center; margin:0 0 8px; }
.fb-panel-heading h2 { font-size:1.05rem; margin:0; line-height:1.3; color:var(--fb-ink); }
.fb-panel-heading p { color:var(--fb-muted); font-size:.76rem; margin:1px 0 0; }
.fb-panel-icon { width:36px; height:36px; flex:0 0 36px; border-radius:50%; background:#f0e7ff;
  color:#923aef; display:flex; align-items:center; justify-content:center; font-size:21px; }
.fb-topbar-user { color:#3a4775; text-align:right; font-size:.85rem; line-height:2.6rem; white-space:nowrap; }
.fb-topbar-user strong { font-weight:650; }
.st-key-fb_topbar [data-testid="stTextInput"] input { font-size:.8rem; }
.st-key-fb_topbar [data-testid="stTextInput"] { max-width:360px; }
.st-key-fb_topbar [data-testid="stHorizontalBlock"] { align-items:center; }
.st-key-fb_topbar [data-testid="stPopoverButton"],
.st-key-fb_topbar [data-testid="stPopover"] > button {
  min-height:32px; height:32px; padding:4px 6px; border:0 !important;
  background:transparent !important; box-shadow:none !important; color:#61329d;
}
.st-key-fb_topbar [data-testid="stColumn"]:nth-child(3) [data-testid="stPopoverButton"],
.st-key-fb_topbar [data-testid="stColumn"]:nth-child(3) [data-testid="stPopover"] > button {
  background:#f2eaff !important; border-radius:10px !important;
}
.st-key-fb_topbar [data-testid="stColumn"]:nth-child(3) [data-testid="stPopoverButton"] p,
.st-key-fb_topbar [data-testid="stColumn"]:nth-child(3) [data-testid="stPopover"] > button p {
  font-size:.68rem; font-weight:650; white-space:nowrap;
}
.st-key-fb_topbar a[data-testid="stPageLink-NavLink"] {
  min-height:32px; border:0 !important; background:transparent !important; padding:4px 2px !important;
}
.st-key-fb_topbar a[data-testid="stPageLink-NavLink"] p { font-size:.8rem; }
.st-key-fb_jarvis,.st-key-fb_recent,.st-key-fb_production {
  background:#fff; border:1px solid #eeedf6; border-radius:14px; padding:12px !important;
  box-shadow:0 3px 12px #17255802;
}
.fb-empty-project { min-height:154px; border-radius:12px; padding:20px; background:linear-gradient(135deg,#fff8eb,#f7eeff); }
.fb-empty-project h3 { font-size:.98rem; margin:0 0 6px; }
.fb-empty-project p { font-size:.84rem; color:#717b99; margin:0; line-height:1.5; }
.fb-stage-list { list-style:none; margin:8px 0; padding:0; }
.fb-stage { display:flex; align-items:center; gap:9px; padding:8px 6px; border-bottom:1px solid #f1eff8; border-radius:8px; font-size:.75rem; }
.fb-stage-number { display:grid; place-items:center; width:20px; height:20px; flex:0 0 20px; border-radius:50%; background:#e8e8f2; color:#68738f; font-weight:700; }
.fb-stage-label { flex:1; font-weight:600; }
.fb-stage-status { font-size:.68rem; color:#8790a7; white-space:nowrap; }
.fb-stage-concluido .fb-stage-number { background:#05b982; color:white; }
.fb-stage-concluido .fb-stage-status { color:#138f6b; }
.fb-stage-em_andamento { background:#f2eaff; }
.fb-stage-em_andamento .fb-stage-number { background:#9148ed; color:white; }
.fb-stage-em_andamento .fb-stage-status { color:#8842d6; }
[class*="st-key-fb_project_"] { border:1px solid #eeedf6; border-radius:10px; padding:7px !important; }
[class*="st-key-fb_project_"] [data-testid="stVerticalBlock"] { gap:5px; }
[class*="st-key-fb_project_"] [data-testid="stImage"] img { border-radius:7px; aspect-ratio:1.35; object-fit:cover; }
[class*="st-key-fb_project_"] [data-testid="stButton"] button { min-height:30px; font-size:.72rem; padding:3px; }
[class*="st-key-fb_project_"] [data-testid="stCaptionContainer"] { font-size:.66rem; }
.fb-book-placeholder { aspect-ratio:1.35; display:flex; flex-direction:column; justify-content:space-around; align-items:center; gap:4px; padding:10px; background:linear-gradient(135deg,#ffe7ed,#e9eaff,#d6f5eb); border-radius:7px; text-align:center; color:#313f78; }
.fb-book-placeholder b { font-size:.85rem; line-height:1.3; }
.fb-project-title { margin:5px 0 0 !important; font-size:.8rem !important; line-height:1.35; }
.fb-project-badge { background:#eae1ff; color:#8742d6; border-radius:99px; font-size:.62rem; padding:3px 7px; display:inline-block; }
.st-key-fb_jarvis [data-testid="stFormSubmitButton"] button { background:linear-gradient(105deg,#fb88b5,#bb55ed 60%,#8b68ff) !important; color:white !important; border:0 !important; border-radius:10px; }
.st-key-fb_jarvis [data-testid="stTextInput"] input { font-size:.75rem; }
.st-key-fb_recent [data-testid="stButton"] button { font-size:.78rem; }
.st-key-fb_mobile_jarvis { display:none; }
@media (min-width: 1100px) {
  .st-key-fb_dashboard_actions [data-testid="stHorizontalBlock"] { gap:12px; }
  [class*="st-key-fb_action_"] { min-height:74px; }
  .fb-action { min-height:74px; padding:8px 12px; }
  .fb-action-icon { height:56px; }
  .fb-action-copy h3 { font-size:1rem; }
}
@media (max-width: 1100px) and (min-width: 769px) {
  .fb-action { gap:9px; padding:12px 9px; min-height:105px; }
  .fb-action-icon { width:42px; height:49px; flex-basis:42px; }
  .fb-action-icon svg { width:31px; height:31px; }
  .fb-action-copy h3 { font-size:.9rem; }
  .fb-action-copy p { font-size:.72rem; }
  .fb-action-arrow { flex-basis:22px; width:22px; height:22px; }
}
@media (max-width: 768px) {
  [data-testid="stMainBlockContainer"],.block-container { padding:2.8rem .8rem 2rem; }
  section[data-testid="stSidebar"] { width:240px !important; min-width:240px !important; }
  .fb-banner-frame { border-radius:14px; }
  .fb-banner-desktop { display:none; }
  .fb-banner-mobile { display:block; }
  .fb-action { min-height:87px; }
  .fb-action-copy h3 { font-size:.99rem; }
  .fb-action-copy p { font-size:.82rem; }
  .st-key-fb_mobile_jarvis { display:block; position:relative; border-radius:0 0 20px 20px;
    background:linear-gradient(125deg,#fff5d8,#e6f3fc 50%,#fdeafd); border:1px solid #ece3f0; overflow:hidden;
    margin-top:-.8rem; margin-bottom:.4rem; padding-bottom:13px !important; }
  .fb-mobile-jarvis-art { position:relative; overflow:hidden; aspect-ratio:682 / 582; }
  .fb-mobile-jarvis-art img { position:absolute; width:105.572%; max-width:none; left:-2.933%; top:-87.629%; }
  .st-key-fb_mobile_jarvis [data-testid="stButton"] { margin:0 auto; width:max-content; max-width:90%; }
  .st-key-fb_mobile_jarvis [data-testid="stButton"] button { border-radius:999px !important; background:#35586b !important;
    color:#fff !important; min-height:38px; padding:.4rem 1rem; }
  .st-key-fb_topbar [data-testid="stHorizontalBlock"] { flex-wrap:nowrap; gap:.5rem; }
  .st-key-fb_topbar [data-testid="stColumn"] { min-width:0; }
  .st-key-fb_topbar [data-testid="stColumn"]:nth-child(2),
  .st-key-fb_topbar [data-testid="stColumn"]:nth-child(3),
  .st-key-fb_topbar [data-testid="stColumn"]:nth-child(4) { display:none; }
  .st-key-fb_topbar [data-testid="stColumn"]:first-child { flex:5 1 0 !important; width:auto; }
  .st-key-fb_topbar [data-testid="stColumn"]:nth-child(5) { flex:1.25 1 0 !important; width:auto; }
  .st-key-fb_topbar [data-testid="stTextInput"] { max-width:none; }
  .fb-topbar-user { font-size:.75rem; }
  .st-key-fb_jarvis,.st-key-fb_recent,.st-key-fb_production { padding:12px !important; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior:auto !important; }
  *,*::before,*::after { transition:none !important; animation:none !important; }
  [class*="st-key-fb_action_"]:hover { transform:none; }
  .fb-banner-motion { display:none; }
}
</style>
"""


def aplicar_visual() -> None:
    """Call after the existing estilo.CSS so the shared palette is updated."""
    st.markdown(CSS, unsafe_allow_html=True)


def render_brand(sidebar: bool = True) -> None:
    classes = "fb-brand-frame" if sidebar else "fb-brand-frame fb-brand-inline"
    st.markdown(
        f'<div class="{classes}" role="img" aria-label="FaithBloom Book Studio">'
        f'<img src="{_asset("faithbloom-dashboard-reference.jpg")}" alt=""></div>',
        unsafe_allow_html=True,
    )


def render_banner(display_name: str = "Erica") -> None:
    """Reference dashboard artwork on desktop, complete garden on mobile."""
    name = str(display_name or "Erica").strip() or "Erica"
    # The supplied artwork includes Erica's greeting. Other profiles get a
    # text overlay in the same place instead of inheriting another name.
    personal = ""
    personal_desktop = ""
    if name.casefold() not in {"erica", "érica"}:
        greeting_size = 5.4 * 10 / max(10, len(name) + 5)
        personal = (
            f'<div class="fb-greeting" style="--greeting-size:{greeting_size:.2f}cqw" '
            f'aria-hidden="true">Oi, {escape(name)}!</div>'
        )
        desktop_size = 3.4 * 10 / max(10, len(name) + 5)
        personal_desktop = (
            f'<div class="fb-greeting" style="--greeting-size:{desktop_size:.2f}cqw" '
            f'aria-hidden="true">Oi, {escape(name)}!</div>'
        )
    with st.container(key="fb_banner_controls"):
        enabled = st.toggle(
            "Movimento",
            value=True,
            key="fb_banner_motion",
            help="Ativa ou pausa o movimento do banner. Respeita a preferência de reduzir movimento do seu dispositivo.",
        )
    motion = _banner_motion() if enabled else ""
    st.markdown(
        '<section class="fb-banner" aria-label="Boas-vindas">'
        f'<h1 class="fb-sr-only">Oi, {escape(name)}! O que você quer fazer hoje?</h1>'
        '<p class="fb-sr-only">O Jarvis entende seu objetivo, monta a equipe certa de especialistas '
        'e guia todo o processo, do começo ao fim. Você sonha. Nós orquestramos. Deus floresce. '
        'Oi! Eu sou o Jarvis! Vamos criar juntos?</p>'
        '<div class="fb-banner-frame fb-banner-desktop" aria-hidden="true">'
        f'<img src="{_asset("faithbloom-dashboard-reference.jpg")}" alt="">{personal_desktop}{motion}</div>'
        '<div class="fb-banner-frame fb-banner-mobile" aria-hidden="true">'
        f'<img src="{_asset("faithbloom-welcome.jpg")}" alt="">{personal}{motion}</div>'
        '</section>',
        unsafe_allow_html=True,
    )


def _banner_motion() -> str:
    """Decorations only: the original artwork never moves or changes."""
    butterfly = (
        '<svg viewBox="0 0 48 40" fill="none" aria-hidden="true">'
        '<g class="fb-butterfly-wings" stroke="#c77a22" stroke-width=".9">'
        '<path d="M24 20C14 0 1 2 4 17c1 8 12 10 20 3Z" fill="#ffd586"/>'
        '<path d="M24 21C10 16 4 27 10 33c6 6 12-2 14-12Z" fill="#ffb975"/>'
        '<path d="M24 20C34 0 47 2 44 17c-1 8-12 10-20 3Z" fill="#ffe19e"/>'
        '<path d="M24 21c14-5 20 6 14 12-6 6-12-2-14-12Z" fill="#ffc486"/>'
        '</g><path d="M24 15v16m0-14-4-5m4 5 4-5" stroke="#9a612c" stroke-width="1.6" stroke-linecap="round"/>'
        '</svg>'
    )
    petals = "".join(
        f'<span class="fb-petal{garden}" style="--petal-left:{left}%;'
        f'--petal-duration:{duration}s;--petal-delay:-{delay}s"></span>'
        for left, duration, delay, garden in [
            (1.5, 21, 4, ""), (4, 25, 16, ""), (7, 23, 10, ""),
            (98, 24, 8, ""), (95, 19, 12, " fb-petal-garden"),
            (91, 22, 5, " fb-petal-garden"),
        ]
    )
    return (
        '<div class="fb-banner-motion" aria-hidden="true">'
        f'{petals}<span class="fb-banner-star fb-banner-star-one">✦</span>'
        '<span class="fb-banner-star fb-banner-star-two">✧</span>'
        '<span class="fb-banner-star fb-banner-star-three">✦</span>'
        f'<span class="fb-butterfly fb-butterfly-one">{butterfly}</span>'
        f'<span class="fb-butterfly fb-butterfly-two">{butterfly}</span>'
        '<span class="fb-heart-glow"></span></div>'
    )


ICONS = {
    "book": '<path d="M3 5c5-2 9-2 13 1v22c-4-3-8-3-13-1V5Zm26 0c-5-2-9-2-13 1v22c4-3 8-3 13-1V5Z"/>',
    "refresh": '<path d="M26 11A11 11 0 0 0 6 8l-3 4M3 5v7h7M6 21a11 11 0 0 0 20 3l3-4M29 27v-7h-7"/>',
    "people": '<circle cx="16" cy="9" r="5" fill="currentColor" stroke="none"/><circle cx="5" cy="13" r="3" fill="currentColor" stroke="none"/><circle cx="27" cy="13" r="3" fill="currentColor" stroke="none"/><path d="M7 29v-4a9 9 0 0 1 18 0v4ZM1 28v-5a5 5 0 0 1 7-4M31 28v-5a5 5 0 0 0-7-4" fill="currentColor" stroke="none"/>',
    "image": '<rect x="3" y="3" width="26" height="26" rx="3"/><circle cx="10" cy="10" r="2"/><path d="m4 24 8-9 5 6 5-8 7 9"/>',
    "text": '<path d="M7 2h14l6 6v22H7V2Z" fill="currentColor" stroke="none"/><path d="M21 2v7h6" fill="none" stroke="#fff" opacity=".5"/><path d="M12 14h10M12 19h10M12 24h10" stroke="#fff" stroke-width="2"/>',
    "rocket": '<path d="M13 23C7 13 16 3 29 3c0 13-10 22-20 16M19 6a4 4 0 1 0 6 6M11 12H5l-3 9 7-1M21 22v5l-9 3 1-7M7 25l-4 4" fill="currentColor" stroke="currentColor"/>',
}


def _icon(name: str) -> str:
    aliases = {"📖": "book", "🔄": "refresh", "👥": "people", "🖼️": "image", "📝": "text", "🚀": "rocket"}
    key = aliases.get(name, name)
    if key not in ICONS:
        return escape(name)
    return f'<svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[key]}</svg>'


def render_action_card(title: str, description: str, route: str, color: str, icon: str, key: str) -> None:
    """A complete clickable card with a native, keyboard-accessible page link."""
    color = {"green": "mint", "purple": "lilac", "rose": "pink", "gold": "yellow"}.get(color, color)
    if color not in {"pink", "blue", "mint", "yellow", "lilac"}:
        color = "lilac"
    safe_key = re.sub(r"[^a-zA-Z0-9_]", "_", str(key))
    with st.container(key=f"fb_action_{safe_key}"):
        st.markdown(
            f'<div class="fb-action fb-action-{color}" aria-hidden="true">'
            f'<span class="fb-action-icon">{_icon(icon)}</span>'
            f'<div class="fb-action-copy"><h3>{escape(title)}</h3><p>{escape(description)}</p></div>'
            '<span class="fb-action-arrow">→</span></div>',
            unsafe_allow_html=True,
        )
        st.page_link(route, label=f"{title} — {description}", use_container_width=True)


def render_jarvis_mobile() -> bool:
    """Return True when the mobile conversation entry button is pressed."""
    with st.container(key="fb_mobile_jarvis"):
        st.markdown(
            '<div class="fb-mobile-jarvis-art" role="img" aria-label="Jarvis, o assistente do FaithBloom: vamos criar juntos!">'
            f'<img src="{_asset("faithbloom-mobile-reference.jpg")}" alt=""></div>',
            unsafe_allow_html=True,
        )
        return st.button("💗 Conversar com o Jarvis", key="fb_mobile_jarvis_start")


# IDs follow the existing pages folder, including legacy filenames. New pages
# are discovered and stay reachable under Ferramentas avançadas automatically.
PAGE_LABELS = {
    1: "Criar um livro", 2: "Continuar / Atualizar", 3: "Livros de colorir",
    4: "Ir direto para uma etapa", 5: "Analisar um livro", 6: "Galeria de personagens",
    7: "Lançamento", 8: "Galeria e armazenamento", 9: "Testes End-to-End",
    10: "Piloto visual", 11: "Custos e segurança", 12: "Fila de produção",
    13: "QA final e release", 14: "Personagens", 15: "Biblioteca editorial",
    16: "Texto e revisão", 17: "Emoção e cores", 18: "Style DNA Lab",
    19: "Restaurar ilustrações", 20: "Revisar livro de colorir", 21: "Traduzir e localizar",
    22: "Formatos de publicação", 23: "Livros de atividades", 24: "Audiobooks",
    25: "Revisão de qualidade", 26: "Publicar", 27: "Central de projetos",
    28: "Estabilidade da versão", 29: "Produção em nuvem", 30: "Validação para lançamento",
    31: "Imagens & ilustrações", 32: "Autores e colaboradores", 33: "Integração e UX",
    34: "Perfis e dashboard", 35: "Piloto real e correções", 36: "Revisão pré-lançamento",
    37: "Skills e análise editorial", 38: "Meus projetos",
}


def _routes() -> dict[int, str]:
    routes = {}
    for path in (ROOT / "pages").glob("*.py"):
        match = re.match(r"(\d+)_", path.name)
        if match:
            routes[int(match.group(1))] = f"pages/{path.name}"
    return routes


def render_sidebar() -> None:
    """Render all existing routes once per rerun, with the reference grouping."""
    routes = _routes()
    with st.sidebar:
        render_brand()
        with st.container(key="fb_side_home"):
            st.page_link("app.py", label="Início", icon=":material/home:", use_container_width=True)
        projects_page = 38 if 38 in routes else 34
        if projects_page in routes:
            st.page_link(routes[projects_page], label="Meus projetos", icon=":material/folder_open:", use_container_width=True)
        used = {projects_page}
        with st.expander("CRIAR & TRANSFORMAR", expanded=True):
            quick = [
                (1, "create", ":material/menu_book:"), (2, "continue", ":material/sync:"),
                (14, "characters", ":material/group:"), (31, "images", ":material/image:"),
                (16, "text", ":material/description:"), (26, "publish", ":material/rocket_launch:"),
            ]
            for number, name, icon in quick:
                if number in routes:
                    with st.container(key=f"fb_side_{name}"):
                        st.page_link(routes[number], label=PAGE_LABELS[number], icon=icon, use_container_width=True)
                    used.add(number)
        groups = [
            ("UNIVERSO & BIBLIOTECA", [6, 8, 15, 17, 18, 23, 24, 27, 32, 34], ":material/auto_stories:"),
            ("QUALIDADE & PUBLICAÇÃO", [3, 5, 7, 13, 19, 20, 21, 22, 25, 37], ":material/verified_user:"),
        ]
        for label, numbers, icon in groups:
            with st.expander(label, expanded=False):
                for number in numbers:
                    if number in routes:
                        st.page_link(routes[number], label=PAGE_LABELS[number], icon=icon, use_container_width=True)
                        used.add(number)
        with st.expander("FERRAMENTAS AVANÇADAS", expanded=False):
            for number in sorted(set(routes) - used):
                st.page_link(routes[number], label=PAGE_LABELS.get(number, Path(routes[number]).stem.replace("_", " ")),
                             icon=":material/settings:", use_container_width=True)
        st.markdown(
            '<div class="fb-promo-frame" role="img" aria-label="Mais histórias para um futuro ainda mais brilhante">'
            f'<img src="{_asset("faithbloom-dashboard-reference.jpg")}" alt=""></div>',
            unsafe_allow_html=True,
        )
