import sys
import json
import os
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QFrame
from PyQt5.QtGui import QFont, QColor, QFontDatabase

class AgentPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.status_file = "Data/agent_status.json"
        self.last_status = None
        self.hide_timer = None
        
        # --- CUSTOM FONT ---
        self.font_id = QFontDatabase.addApplicationFont("Data/fonts/plain-text.ttf")
        if self.font_id != -1:
            self.custom_font = QFontDatabase.applicationFontFamilies(self.font_id)[0]
        else:
            self.custom_font = "Segoe UI"

        self.initUI()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_status)
        self.timer.start(500)

    def initUI(self):
        # Window constraints
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # FIX: Explicit Min/Max width instead of FixedWidth to avoid Windows geometry clash
        self.setMinimumWidth(650)
        self.setMaximumWidth(650)

        # Outer layout
        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(15, 15, 15, 25)

        # --- Main Container ---
        self.container = QFrame(self)
        self.container.setMinimumHeight(90) 
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            #MainContainer {
                background-color: rgba(15, 15, 15, 230);
                border: 2px solid white;
                border-radius: 20px;
            }
        """)

        # Drop Shadow
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(25)
        self.shadow.setColor(QColor(0, 0, 0, 180))
        self.shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(self.shadow)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(25, 15, 25, 20)

        # --- Top Header: Status & Step ---
        header_layout = QHBoxLayout()
        
        self.status_tag = QLabel("AGENT ACTIVE")
        self.status_tag.setFont(QFont(self.custom_font, 9, QFont.Bold))
        self.status_tag.setStyleSheet("color: white; letter-spacing: 2px;")
        
        self.pulse_dot = QLabel("●")
        self.pulse_dot.setStyleSheet("color: #00ffcc; font-size: 8px; margin-left: 5px;")
        self.pulse_opacity = QGraphicsOpacityEffect(self.pulse_dot)
        self.pulse_dot.setGraphicsEffect(self.pulse_opacity)
        self.start_pulse_animation()

        header_layout.addWidget(self.status_tag)
        header_layout.addWidget(self.pulse_dot)
        header_layout.addStretch()
        
        self.phase_label = QLabel("STEP: 00")
        self.phase_label.setFont(QFont(self.custom_font, 9))
        self.phase_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); letter-spacing: 1px;")
        header_layout.addWidget(self.phase_label)
        
        self.layout.addLayout(header_layout)

        # --- Central Hero: The Thought ---
        self.layout.addSpacing(5) 
        
        self.thought_label = QLabel("")
        self.thought_label.setWordWrap(True)
        self.thought_label.setAlignment(Qt.AlignCenter)
        self.thought_label.setFont(QFont(self.custom_font, 10)) 
        self.thought_label.setStyleSheet("color: white; line-height: 1.4;")
        
        self.text_opacity = QGraphicsOpacityEffect(self.thought_label)
        self.thought_label.setGraphicsEffect(self.text_opacity)
        self.layout.addWidget(self.thought_label)

        self.outer_layout.addWidget(self.container)

        # Setup Hide Timer
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out_and_hide)
        
        self.hide()
        
        # UI load hone ka halka sa delay pehli baar center hone se pehle
        QTimer.singleShot(100, self.recenter)

    def recenter(self):
        """Window ko dynamically screen ke top-center mein set karega bina warning ke"""
        QApplication.processEvents() # UI ko content ke hisab se refresh hone ka waqt do
        ideal_height = self.outer_layout.sizeHint().height()
        self.resize(650, ideal_height)
        
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - 650) // 2
        y = screen.top() + 40
        self.move(x, y)

    def start_pulse_animation(self):
        self.p_anim = QPropertyAnimation(self.pulse_opacity, b"opacity")
        self.p_anim.setDuration(800)
        self.p_anim.setStartValue(0.2)
        self.p_anim.setEndValue(1.0)
        self.p_anim.setLoopCount(-1)
        self.p_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.p_anim.start()

    # 🚀 BULLET-PROOF ANIMATION QUEUE
    def fade_in_text(self, new_text):
        new_text_upper = new_text.upper()
        
        if self.thought_label.text() == new_text_upper and not hasattr(self, 'pending_text'):
            return
            
        self.pending_text = new_text_upper
        
        # Agar pehle se text fade_out ho raha hai, toh usi queue ko chalne do
        if hasattr(self, 'fade_out') and self.fade_out.state() == QPropertyAnimation.Running:
            return
            
        # Agar fade-in ho raha tha, toh usko wahin rok do aur naya text lao
        if hasattr(self, 'fade_in') and self.fade_in.state() == QPropertyAnimation.Running:
            self.fade_in.stop()

        self.fade_out = QPropertyAnimation(self.text_opacity, b"opacity")
        self.fade_out.setDuration(150)
        self.fade_out.setStartValue(self.text_opacity.opacity())
        self.fade_out.setEndValue(0.0)
        self.fade_out.finished.connect(self._apply_pending_text)
        self.fade_out.start()

    def _apply_pending_text(self):
        if hasattr(self, 'pending_text'):
            self.thought_label.setText(self.pending_text)
            self.recenter()
            del self.pending_text
        
        self.fade_in = QPropertyAnimation(self.text_opacity, b"opacity")
        self.fade_in.setDuration(250)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.start()

    def fade_out_and_hide(self):
        if not self.isVisible(): return
        self.fade_panel = QPropertyAnimation(self, b"windowOpacity")
        self.fade_panel.setDuration(300)
        self.fade_panel.setStartValue(1.0)
        self.fade_panel.setEndValue(0.0)
        self.fade_panel.finished.connect(self.hide)
        self.fade_panel.start()

    def show_panel(self):
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self.hide_timer.start(5000)

    def update_agent_view(self, step, thought):
        self.phase_label.setText(f"STEP: {step:02}")
        if thought:
            self.fade_in_text(thought)
        else:
            self.fade_in_text("")

    def check_status(self):
        if not os.path.exists(self.status_file): return
        try:
            with open(self.status_file, "r") as f:
                status = json.load(f)
        except (json.JSONDecodeError, IOError): return

        if status == self.last_status:
            if self.last_status and self.last_status.get("step", 0) > 0:
                self.hide_timer.start(5000)
            return
        
        self.last_status = status
        step = status.get("step", 0)
        thought = status.get("thought", "")

        if step == 0:
            self.hide_timer.start(1000)
        else:
            self.show_panel()
            self.update_agent_view(step, thought)

def run_panel():
    app = QApplication(sys.argv)
    panel = AgentPanel()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run_panel()