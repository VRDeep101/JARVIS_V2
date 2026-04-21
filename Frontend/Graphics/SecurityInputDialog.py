# =============================================================
#  Frontend/Graphics/SecurityInputDialog.py
#  Security Mode Input Overlay
#
#  Kya karta:
#    - URL check, Password strength/breach check, Email breach
#      ke liye keyboard input lene ka GUI overlay
#    - PasswordScreen jaisa full-screen HUD card design
#    - 3 modes: "url" | "password" | "email"
#    - Password mode mein echo off (masked input)
#    - Result area inline hi dikhata hai - separate screen nahi
#    - Signals: input_submitted(value, mode), cancelled()
#
#  Usage:
#    dialog = SecurityInputDialog(theme=security_theme)
#    dialog.show_for("url")
#    dialog.input_submitted.connect(handler)
# =============================================================

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QLineEdit, QSizePolicy, QScrollArea,
)

from Frontend.Themes.base_theme import Theme

try:
    from Frontend.Themes.security_theme import security_theme as _default_sec_theme
except Exception:
    _default_sec_theme = None


# =============================================================
#  Mode metadata
# =============================================================
_MODE_META = {
    "url": {
        "title":       "URL THREAT CHECK",
        "subtitle":    "Paste or type the URL to analyse",
        "placeholder": "https://example.com or just domain.com",
        "btn_label":   "SCAN",
        "masked":      False,
        "icon":        "🔗",
    },
    "password": {
        "title":       "PASSWORD ANALYSER",
        "subtitle":    "Type the password — it stays local, never sent",
        "placeholder": "Enter password...",
        "btn_label":   "ANALYSE",
        "masked":      True,
        "icon":        "🔐",
    },
    "email": {
        "title":       "EMAIL BREACH CHECK",
        "subtitle":    "Enter the email address to check HaveIBeenPwned",
        "placeholder": "user@example.com",
        "btn_label":   "CHECK",
        "masked":      False,
        "icon":        "📧",
    },
}

# Fallback meta for unknown modes
_DEFAULT_META = {
    "title": "SECURITY INPUT",
    "subtitle": "Enter the value to check",
    "placeholder": "Type here...",
    "btn_label": "SUBMIT",
    "masked": False,
    "icon": "🛡",
}


# =============================================================
#  SecurityInputDialog
# =============================================================
class SecurityInputDialog(QWidget):
    """Full-screen HUD overlay for Security Mode keyboard input."""

    input_submitted = pyqtSignal(str, str)   # (value, mode)
    cancelled       = pyqtSignal()

    def __init__(self, theme: Theme = None, parent=None):
        super().__init__(parent)
        self.theme       = theme or _default_sec_theme
        self._mode       = "url"
        self._meta       = _MODE_META["url"]
        self._showing_result = False

        self._build_ui()

    # =========================================================
    #  Build
    # =========================================================
    def _build_ui(self):
        th = self.theme

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {th.bg_main};
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        card_row = QHBoxLayout()
        card_row.addStretch()

        # ---- Card ----
        card = QFrame()
        card.setObjectName("sec_input_card")
        card.setFixedWidth(500)
        card.setStyleSheet(f"""
            QFrame#sec_input_card {{
                background-color: {th.bg_panel};
                border: 2px solid {th.primary};
                border-radius: 18px;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(16)

        # Icon + Title row
        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        self.icon_label = QLabel("🛡")
        self.icon_label.setStyleSheet("font-size: 22pt; background: transparent; border: none;")
        title_row.addWidget(self.icon_label)

        self.title_label = QLabel("SECURITY INPUT")
        self.title_label.setStyleSheet(f"""
            color: {th.primary};
            font-family: "{th.font_display}";
            font-size: 15pt;
            font-weight: bold;
            letter-spacing: 5px;
            background: transparent;
            border: none;
        """)
        title_row.addWidget(self.title_label)
        title_row.addStretch()
        card_layout.addLayout(title_row)

        # Subtitle
        self.subtitle_label = QLabel("")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet(f"""
            color: {th.text_muted};
            font-size: 10pt;
            background: transparent;
            border: none;
            padding-bottom: 4px;
        """)
        card_layout.addWidget(self.subtitle_label)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background: {th.border}; max-height: 1px; border: none;")
        card_layout.addWidget(divider)

        # Input field
        self.input_field = QLineEdit()
        self.input_field.setFixedHeight(46)
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {th.bg_input if hasattr(th, 'bg_input') else th.bg_main};
                color: {th.text_primary};
                border: 1px solid {th.border};
                border-radius: 8px;
                font-size: 11pt;
                font-family: "{th.font_mono}";
                padding: 6px 12px;
                letter-spacing: 1px;
            }}
            QLineEdit:focus {{
                border: 1px solid {th.primary};
            }}
        """)
        self.input_field.returnPressed.connect(self._submit)
        card_layout.addWidget(self.input_field)

        # Show/Hide toggle row (only for password mode)
        self.toggle_row = QHBoxLayout()
        self.toggle_row.setContentsMargins(0, 0, 0, 0)
        self._show_pw_visible = False
        self.toggle_btn = QPushButton("Show")
        self.toggle_btn.setFixedSize(70, 26)
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {th.text_muted};
                border: 1px solid {th.border};
                border-radius: 5px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                color: {th.primary};
                border: 1px solid {th.primary};
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_password_visibility)
        self.toggle_row.addStretch()
        self.toggle_row.addWidget(self.toggle_btn)
        card_layout.addLayout(self.toggle_row)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {th.text_muted};
                border: 1px solid {th.border};
                border-radius: 8px;
                font-size: 10pt;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                color: {th.text_primary};
                border: 1px solid {th.text_muted};
            }}
        """)
        self.cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self.cancel_btn, stretch=1)

        self.submit_btn = QPushButton("SCAN")
        self.submit_btn.setFixedHeight(40)
        self.submit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {th.hex_with_alpha(th.primary, 0.15)};
                color: {th.primary};
                border: 1px solid {th.hex_with_alpha(th.primary, 0.7)};
                border-radius: 8px;
                font-size: 10pt;
                font-weight: bold;
                letter-spacing: 2px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background: {th.hex_with_alpha(th.primary, 0.28)};
                border: 1px solid {th.primary};
            }}
            QPushButton:pressed {{
                background: {th.hex_with_alpha(th.primary, 0.4)};
            }}
        """)
        self.submit_btn.clicked.connect(self._submit)
        btn_row.addWidget(self.submit_btn, stretch=2)

        card_layout.addLayout(btn_row)

        # Status / error line
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(20)
        self.status_label.setStyleSheet(f"""
            color: {th.error if hasattr(th, 'error') else '#ff4444'};
            font-size: 9pt;
            background: transparent;
            border: none;
        """)
        card_layout.addWidget(self.status_label)

        # ---- Result area (hidden initially) ----
        self.result_frame = QFrame()
        self.result_frame.setObjectName("result_frame")
        self.result_frame.setStyleSheet(f"""
            QFrame#result_frame {{
                background: {th.hex_with_alpha(th.primary, 0.07)};
                border: 1px solid {th.border};
                border-radius: 10px;
            }}
        """)
        result_inner = QVBoxLayout(self.result_frame)
        result_inner.setContentsMargins(14, 12, 14, 12)
        result_inner.setSpacing(8)

        result_hdr = QLabel("ANALYSIS RESULT")
        result_hdr.setStyleSheet(f"""
            color: {th.primary};
            font-family: "{th.font_display}";
            font-size: 9pt;
            font-weight: bold;
            letter-spacing: 3px;
            background: transparent;
        """)
        result_inner.addWidget(result_hdr)

        self.result_score_label = QLabel("")
        self.result_score_label.setStyleSheet(f"""
            color: {th.text_primary};
            font-size: 13pt;
            font-weight: bold;
            background: transparent;
        """)
        result_inner.addWidget(self.result_score_label)

        self.result_verdict_label = QLabel("")
        self.result_verdict_label.setWordWrap(True)
        self.result_verdict_label.setStyleSheet(f"""
            color: {th.text_primary};
            font-size: 10pt;
            background: transparent;
        """)
        result_inner.addWidget(self.result_verdict_label)

        self.result_reasons_label = QLabel("")
        self.result_reasons_label.setWordWrap(True)
        self.result_reasons_label.setStyleSheet(f"""
            color: {th.text_muted};
            font-size: 9pt;
            background: transparent;
        """)
        result_inner.addWidget(self.result_reasons_label)

        self.result_close_btn = QPushButton("Close")
        self.result_close_btn.setFixedHeight(34)
        self.result_close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {th.text_muted};
                border: 1px solid {th.border};
                border-radius: 6px;
                font-size: 9pt;
                margin-top: 4px;
            }}
            QPushButton:hover {{
                color: {th.text_primary};
                border: 1px solid {th.text_muted};
            }}
        """)
        self.result_close_btn.clicked.connect(self._close_result)
        result_inner.addWidget(self.result_close_btn)

        self.result_frame.hide()
        card_layout.addWidget(self.result_frame)

        # ---- End card ----
        card_row.addWidget(card)
        card_row.addStretch()

        outer.addLayout(card_row)
        outer.addStretch()

    # =========================================================
    #  Public API
    # =========================================================
    def show_for(self, mode: str):
        """
        Configure the dialog for a given mode and reset state.
        Call this before making the widget visible.
        mode: "url" | "password" | "email"
        """
        self._mode = mode
        self._meta = _MODE_META.get(mode, _DEFAULT_META)
        self._showing_result = False

        meta = self._meta
        self.icon_label.setText(meta["icon"])
        self.title_label.setText(meta["title"])
        self.subtitle_label.setText(meta["subtitle"])
        self.input_field.setPlaceholderText(meta["placeholder"])
        self.submit_btn.setText(meta["btn_label"])
        self.input_field.clear()
        self.status_label.setText("")
        self.result_frame.hide()

        # Toggle button only makes sense in password mode
        if meta["masked"]:
            self.input_field.setEchoMode(QLineEdit.Password)
            self._show_pw_visible = False
            self.toggle_btn.setText("Show")
            self.toggle_row.setEnabled(True)
            # Show the toggle row by making it visible via the spacer layout
            self.toggle_btn.show()
        else:
            self.input_field.setEchoMode(QLineEdit.Normal)
            self.toggle_btn.hide()

        # Re-enable input + buttons after result
        self.input_field.setEnabled(True)
        self.submit_btn.setEnabled(True)
        self.input_field.setFocus()

    def show_result(self, result: dict):
        """
        Display the analysis result inside the card.
        result dict keys: safe (bool), risk_score (int), verdict (str),
                          reasons (list[str]), message (str), strength (str),
                          score (int), breached (bool), count (int)
        """
        th = self.theme
        self._showing_result = True

        # Determine score / colour
        risk  = result.get("risk_score", result.get("score", 0))
        safe  = result.get("safe", result.get("breached") is False)
        strength = result.get("strength", "")

        if strength:
            # Password mode
            score_text = f"Strength: {strength.upper()}  ({risk}/100)"
            colour = (
                th.error   if risk < 40 else
                th.warn    if risk < 70 else
                th.success
            )
        else:
            # URL / email mode
            score_text = f"Risk Score: {risk} / 100"
            colour = th.success if safe else (
                th.warn if risk < 60 else th.error
            )

        self.result_score_label.setText(score_text)
        self.result_score_label.setStyleSheet(f"""
            color: {colour};
            font-size: 13pt;
            font-weight: bold;
            background: transparent;
        """)

        verdict = result.get("verdict", result.get("message", ""))
        self.result_verdict_label.setText(verdict)

        reasons = result.get("reasons", result.get("issues", []))
        if reasons and isinstance(reasons, list):
            reasons_text = "Issues: " + "  ·  ".join(reasons[:4])
        else:
            reasons_text = ""
        self.result_reasons_label.setText(reasons_text)

        self.result_frame.show()

        # Disable further input while result is showing
        self.input_field.setEnabled(False)
        self.submit_btn.setEnabled(False)

    def show_error(self, msg: str):
        """Show an error message below the input field."""
        self.status_label.setText(msg)
        # Flash input border red
        orig = self.input_field.styleSheet()
        th = self.theme
        err_style = orig.replace(th.border, th.error if hasattr(th, 'error') else '#ff4444')
        self.input_field.setStyleSheet(err_style)
        QTimer.singleShot(600, lambda: self.input_field.setStyleSheet(orig))

    def reset(self):
        """Full reset — called before making widget visible."""
        self.show_for(self._mode)

    def set_theme(self, theme: Theme):
        """Hot-swap theme."""
        self.theme = theme

    # =========================================================
    #  Handlers
    # =========================================================
    def _submit(self):
        value = self.input_field.text().strip()
        if not value:
            self.show_error("Please enter a value first.")
            return
        self.status_label.setText("")
        self.input_submitted.emit(value, self._mode)

    def _cancel(self):
        self.input_field.clear()
        self.status_label.setText("")
        self.result_frame.hide()
        self._showing_result = False
        self.cancelled.emit()

    def _close_result(self):
        """Hide result area and re-enable input for another check."""
        self.result_frame.hide()
        self._showing_result = False
        self.input_field.setEnabled(True)
        self.submit_btn.setEnabled(True)
        self.input_field.clear()
        self.status_label.setText("")
        self.input_field.setFocus()

    def _toggle_password_visibility(self):
        """Toggle show/hide for password mode."""
        self._show_pw_visible = not self._show_pw_visible
        if self._show_pw_visible:
            self.input_field.setEchoMode(QLineEdit.Normal)
            self.toggle_btn.setText("Hide")
        else:
            self.input_field.setEchoMode(QLineEdit.Password)
            self.toggle_btn.setText("Show")


# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setStyleSheet("background-color: #080E18;")
    win.resize(900, 700)

    try:
        from Frontend.Themes.security_theme import security_theme as th
    except Exception:
        from Frontend.Themes.base_theme import Theme
        th = Theme()

    dialog = SecurityInputDialog(theme=th)

    def on_submit(value, mode):
        print(f"[TEST] mode={mode}  value={value}")
        # Fake result
        fake = {
            "url":      {"safe": False, "risk_score": 75, "verdict": "HIGH RISK - suspicious domain.", "reasons": ["No HTTPS", "Phishing pattern"]},
            "password": {"strength": "fair", "score": 45, "verdict": "Add uppercase and symbols.", "issues": ["No uppercase", "No special chars"]},
            "email":    {"ok": True, "breached": True, "count": 1234, "message": "Found in 1,234 breaches — change it!"},
        }
        dialog.show_result(fake.get(mode, {}))

    def on_cancel():
        print("[TEST] Cancelled")

    dialog.input_submitted.connect(on_submit)
    dialog.cancelled.connect(on_cancel)
    dialog.show_for("url")

    win.setCentralWidget(dialog)
    win.show()
    sys.exit(app.exec_())