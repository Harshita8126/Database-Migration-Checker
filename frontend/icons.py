"""
SVG Icon Library for PG Migration Guard.
Crisp, Lucide-style outline icons, 20px, stroke 1.75, matching the reference image.
"""

def get_icon_svg(name: str, color: str = "#0B6B4F", size: int = 20) -> str:
    """Returns Lucide-style inline SVG string for the requested icon."""
    stroke_w = "1.75"
    icons = {
        # 3 stacked discs for brand logo
        "db_stack": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
        </svg>""",
        # Bolt icon (Prevent Downtime)
        "bolt": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>""",
        # Brain icon (ML Risk Prediction)
        "brain": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04z"></path>
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04z"></path>
        </svg>""",
        # Code brackets (Safe SQL Rewrites)
        "code": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="16 18 22 12 16 6"></polyline>
            <polyline points="8 6 2 12 8 18"></polyline>
        </svg>""",
        # Bar chart (Live Lock & Latency)
        "chart": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <line x1="12" y1="20" x2="12" y2="10"></line>
            <line x1="18" y1="20" x2="18" y2="4"></line>
            <line x1="6" y1="20" x2="6" y2="16"></line>
        </svg>""",
        # Document (Upload SQL)
        "document": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
        </svg>""",
        # Magnifier (Analyze)
        "search": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>""",
        # Shield Check (Get Safe SQL)
        "shield_check": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            <polyline points="9 12 11 14 15 10"></polyline>
        </svg>""",
        # Gear (Auto Rewrite)
        "gear": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>""",
        # Database (DB Metadata)
        "database": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
        </svg>""",
        # Sun icon (Theme toggle)
        "sun": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>""",
        # Warning Triangle (Risk banner)
        "alert_triangle": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>""",
        # Arrow right
        "arrow_right": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"></line>
            <polyline points="12 5 19 12 12 19"></polyline>
        </svg>""",
        # Play icon
        "play": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>""",
        # Copy
        "copy": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>""",
        # Download
        "download": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>""",
        # Home
        "home": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
            <polyline points="9 22 9 12 15 12 15 22"></polyline>
        </svg>""",
        # Trend / Line
        "trend": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
            <polyline points="17 6 23 6 23 12"></polyline>
        </svg>""",
        # Clock
        "clock": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
        </svg>""",
        # Book
        "book": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
        </svg>""",
        # Layers
        "layers": f"""<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
            <polyline points="2 17 12 22 22 17"></polyline>
            <polyline points="2 12 12 17 22 12"></polyline>
        </svg>""",
    }
    return icons.get(name, "")


def render_hero_illustration_svg() -> str:
    """
    Renders the exact illustration from the reference image:
    - Soft green blob behind everything
    - Teal 3D database cylinder with PostgreSQL elephant emblem
    - Overlapped by a window card with 3 dots (pink, green), monospace 'ALTER TABLE ...', red '◆ High Risk' pill
    - Below it, a light green pill 'Safe Alternative ✓'
    """
    # Clean, compact HTML without multiline indentation so Streamlit's markdown parser never treats it as code block
    return (
        '<div style="position:relative;width:100%;height:380px;display:flex;align-items:center;justify-content:center;">'
        '<svg style="position:absolute;width:100%;height:100%;overflow:visible;" viewBox="0 0 450 360" fill="none">'
        '<path d="M380 90C430 150 410 260 330 300C250 340 120 330 70 260C20 190 50 80 130 40C210 0 330 30 380 90Z" fill="rgba(18, 183, 106, 0.12)" />'
        '</svg>'
        '<svg width="220" height="260" viewBox="0 0 220 260" style="position:absolute;left:30px;top:50px;">'
        '<defs>'
        '<linearGradient id="dbCylGrad" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#0F766E"/>'
        '<stop offset="50%" stop-color="#14B8A6"/>'
        '<stop offset="100%" stop-color="#0D5F58"/>'
        '</linearGradient>'
        '<linearGradient id="dbCapGrad" x1="0%" y1="0%" x2="0%" y2="100%">'
        '<stop offset="0%" stop-color="#2DD4BF"/>'
        '<stop offset="100%" stop-color="#14B8A6"/>'
        '</linearGradient>'
        '</defs>'
        '<path d="M20 140 C20 170 200 170 200 140 L200 180 C200 210 20 210 20 180 Z" fill="url(#dbCylGrad)" opacity="0.9"/>'
        '<path d="M20 90 C20 120 200 120 200 90 L200 140 C200 170 20 170 20 140 Z" fill="url(#dbCylGrad)"/>'
        '<path d="M20 40 C20 70 200 70 200 40 L200 90 C200 120 20 120 20 90 Z" fill="url(#dbCylGrad)"/>'
        '<ellipse cx="110" cy="40" rx="90" ry="24" fill="url(#dbCapGrad)"/>'
        '<path d="M98 90 C92 78 128 78 122 90 C120 94 125 106 116 112 C110 116 110 128 106 128 C102 128 102 118 98 114 C90 106 96 96 98 90 Z" fill="#FFFFFF" opacity="0.85"/>'
        '<circle cx="104" cy="88" r="2.5" fill="#0F766E"/>'
        '</svg>'
        '<div style="position:absolute;right:20px;top:40px;width:250px;background:#FFFFFF;border:1px solid #E3EBE7;border-radius:12px;box-shadow:0 10px 30px rgba(16,24,40,0.1);overflow:hidden;">'
        '<div style="background:#F4F7F5;padding:8px 12px;display:flex;align-items:center;gap:6px;border-bottom:1px solid #E3EBE7;">'
        '<div style="width:8px;height:8px;border-radius:50%;background:#F43F5E;"></div>'
        '<div style="width:8px;height:8px;border-radius:50%;background:#F59E0B;"></div>'
        '<div style="width:8px;height:8px;border-radius:50%;background:#10B981;"></div>'
        '</div>'
        '<div style="padding:12px;">'
        '<div style="font-family:\'JetBrains Mono\',monospace;font-size:0.72rem;color:#0F1F1A;line-height:1.5;margin-bottom:10px;">'
        '<span style="color:#2563EB;font-weight:700;">ALTER TABLE</span> orders<br>'
        '<span style="color:#2563EB;font-weight:700;">ADD COLUMN</span> status;'
        '</div>'
        '<div style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;background:#FEF3F2;border:1px solid #FECDCA;border-radius:16px;font-size:0.72rem;font-weight:700;color:#D92D20;">'
        '<span>◆</span> High Risk'
        '</div>'
        '</div>'
        '</div>'
        '<div style="position:absolute;right:45px;bottom:45px;background:#ECFDF3;border:1px solid #A6F4C5;border-radius:20px;padding:8px 16px;display:flex;align-items:center;gap:8px;box-shadow:0 6px 18px rgba(18,183,106,0.15);">'
        '<div style="width:8px;height:8px;border-radius:50%;background:#12B76A;"></div>'
        '<span style="font-size:0.82rem;font-weight:700;color:#0B6B4F;">Safe Alternative ✓</span>'
        '</div>'
        '</div>'
    )
