"""
Dark Theme Stylesheet

발표용 통제 시스템 느낌. 다크 배경 + 청록 액센트.
"""

DARK_THEME = """
QMainWindow {
    background-color: #0d1117;
}

QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 11pt;
}

QGroupBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
    color: #58a6ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background-color: #0d1117;
    color: #58a6ff;
}

QLabel {
    color: #c9d1d9;
    background: transparent;
}

QLabel#title {
    color: #58a6ff;
    font-size: 14pt;
    font-weight: bold;
}

QLabel#status_value {
    color: #7ee787;
    font-size: 12pt;
    font-weight: bold;
}

QLabel#status_value_warning {
    color: #f0883e;
}

QLabel#status_value_danger {
    color: #f85149;
}

QLabel#help_key {
    color: #58a6ff;
    font-weight: bold;
}

QLabel#help_desc {
    color: #8b949e;
}

QLabel#video_label {
    background-color: #000000;
    border: 1px solid #30363d;
}

QStatusBar {
    background-color: #161b22;
    color: #8b949e;
    border-top: 1px solid #30363d;
}
"""


# 색상 팔레트 (커스텀 페인팅용)
COLORS = {
    'bg_main': '#0d1117',
    'bg_panel': '#161b22',
    'border': '#30363d',
    'text_primary': '#c9d1d9',
    'text_dim': '#8b949e',
    'accent': '#58a6ff',
    'success': '#7ee787',
    'warning': '#f0883e',
    'danger': '#f85149',
    'robot': '#58a6ff',
    'sensor_safe': '#7ee787',
    'sensor_warn': '#f0883e',
    'sensor_danger': '#f85149',
}
