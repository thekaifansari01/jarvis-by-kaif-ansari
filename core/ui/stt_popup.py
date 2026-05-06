import sys
import json
import os
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QFileSystemWatcher, QPoint, QParallelAnimationGroup, QRect
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QFrame, QSizePolicy
from PyQt5.QtGui import QFont, QColor, QFontDatabase

class STTPopup(QWidget):
    def __init__(self):
        super().__init__()
        self.status_file = "Data/stt_status.json"
        
        self.font_id = QFontDatabase.addApplicationFont("Data/fonts/plain-text.ttf")
        families = QFontDatabase.applicationFontFamilies(self.font_id)
        # 🚀 BUG FIXED HERE: Removed the comma so it remains a pure String
        self.custom_font = families[0] if (self.font_id != -1 and families) else "Segoe UI"

        self.initUI()
        
        os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
        if not os.path.exists(self.status_file):
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump({"status": "idle", "text": ""}, f)
        
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.process_status_update)

        self.transcribed_timer = QTimer()
        self.transcribed_timer.setSingleShot(True)
        self.transcribed_timer.timeout.connect(self.allow_hide)
        self.can_hide = True 

        self.watcher = QFileSystemWatcher(self)
        self.watcher.addPath(self.status_file)
        self.watcher.fileChanged.connect(lambda: self.update_timer.start(20))
        
        self.process_status_update()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;") 

        self.setMinimumWidth(220)
        self.setMaximumWidth(600)

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(40, 40, 40, 40)

        # --- DYNAMIC ISLAND (ULTRA PREMIUM) ---
        self.container = QFrame(self)
        self.container.setObjectName("Island")
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.container.setStyleSheet("""
            #Island {
                background-color: #000000;
                border: 1px solid rgba(255, 255, 255, 0.08); /* Extremely subtle premium border */
                border-radius: 26px;
            }
        """)

        # Deeper, softer Apple-like shadow
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(40)
        self.shadow.setColor(QColor(0, 0, 0, 160))
        self.shadow.setOffset(0, 15)
        self.container.setGraphicsEffect(self.shadow)

        self.layout = QHBoxLayout(self.container)
        self.layout.setContentsMargins(22, 14, 22, 14) # Slightly wider side margins
        self.layout.setSpacing(16)
        
        # --- INDICATOR DOT ---
        self.indicator_dot = QFrame()
        self.indicator_dot.setObjectName("Dot")
        self.indicator_dot.setFixedSize(12, 12) # Slightly smaller for elegance
        self.indicator_dot.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) 
        self.indicator_dot.setStyleSheet("""
            #Dot {
                background-color: #0A84FF;
                border-radius: 6px;
            }
        """)
        
        self.dot_opacity = QGraphicsOpacityEffect(self.indicator_dot)
        self.indicator_dot.setGraphicsEffect(self.dot_opacity)
        self.pulse_anim = QPropertyAnimation(self.dot_opacity, b"opacity")
        self.pulse_anim.setLoopCount(-1)
        self.pulse_anim.setEasingCurve(QEasingCurve.InOutSine)
        
        # --- TEXT LABEL ---
        self.text_label = QLabel("Initializing...")
        self.text_label.setWordWrap(True)
        self.text_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.text_label.setMinimumHeight(24) 
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setFont(QFont(self.custom_font, 11))
        self.text_label.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        
        self.layout.addWidget(self.indicator_dot, 0, Qt.AlignVCenter | Qt.AlignLeft)
        self.layout.addWidget(self.text_label, 1, Qt.AlignVCenter | Qt.AlignLeft)
        
        self.outer_layout.addWidget(self.container)
        self.setWindowOpacity(0.0)
        self.hide()

    def start_pulse(self, duration, color_hex):
        self.dot_opacity.setEnabled(True) 
        self.indicator_dot.setStyleSheet(f"#Dot {{ background-color: {color_hex}; border-radius: 6px; }}")
        if self.pulse_anim.state() == QPropertyAnimation.Running:
            if self.pulse_anim.duration() == duration:
                return 
            self.pulse_anim.stop()
            
        self.pulse_anim.setDuration(duration)
        self.pulse_anim.setStartValue(0.2)
        self.pulse_anim.setEndValue(1.0)
        self.pulse_anim.start()

    def stop_pulse(self, color_hex):
        if self.pulse_anim.state() == QPropertyAnimation.Running:
            self.pulse_anim.stop()
        self.dot_opacity.setEnabled(False) 
        self.indicator_dot.setStyleSheet(f"#Dot {{ background-color: {color_hex}; border-radius: 6px; }}")

    def calculate_geometry(self):
        self.text_label.adjustSize()
        self.container.adjustSize()
        self.adjustSize()
        QApplication.processEvents() 
        
        screen = QApplication.primaryScreen().availableGeometry()
        w = self.width()
        h = self.height()
        x = (screen.width() - w) // 2
        y = screen.bottom() - h - 50 
        return x, y, w, h

    def show_panel(self):
        x, y, w, h = self.calculate_geometry()
        
        if not self.isVisible() or self.windowOpacity() == 0.0:
            start_y = y + 40 
            self.setGeometry(x, start_y, w, h)
            self.show()
            self.raise_()

            self.show_anim_group = QParallelAnimationGroup(self)
            
            fade_in = QPropertyAnimation(self, b"windowOpacity")
            fade_in.setDuration(250)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            
            slide_up = QPropertyAnimation(self, b"pos")
            slide_up.setDuration(400) # Slightly slower for a more luxurious feel
            slide_up.setStartValue(QPoint(x, start_y))
            slide_up.setEndValue(QPoint(x, y))
            slide_up.setEasingCurve(QEasingCurve.OutBack)

            self.show_anim_group.addAnimation(fade_in)
            self.show_anim_group.addAnimation(slide_up)
            self.show_anim_group.start()
        else:
            self.setGeometry(x, y, w, h)

    def hide_panel(self):
        if not self.isVisible(): return
        
        self.hide_anim_group = QParallelAnimationGroup(self)
        
        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(250)
        fade_out.setStartValue(self.windowOpacity())
        fade_out.setEndValue(0.0)
        
        slide_down = QPropertyAnimation(self, b"pos")
        slide_down.setDuration(300)
        slide_down.setStartValue(self.pos())
        slide_down.setEndValue(QPoint(self.x(), self.y() + 20))
        slide_down.setEasingCurve(QEasingCurve.InBack)

        self.hide_anim_group.addAnimation(fade_out)
        self.hide_anim_group.addAnimation(slide_down)
        self.hide_anim_group.finished.connect(self.hide)
        self.hide_anim_group.start()

    def allow_hide(self):
        self.can_hide = True
        self.process_status_update()

    def process_status_update(self):
        if not os.path.exists(self.status_file): return
        
        try:
            with open(self.status_file, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip(): return
                data = json.loads(content)
        except (json.JSONDecodeError, IOError):
            return 

        status = data.get("status", "idle")
        text = data.get("text", "")

        if status == "exit":
            QApplication.quit()
            return

        if status == "idle":
            if not self.can_hide:
                return 
            self.hide_panel()
            return
            
        if status == "listening":
            self.start_pulse(700, "#0A84FF") # Elegant Siri Blue
            self.text_label.setText("Listening...")
            self.text_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-style: italic; letter-spacing: 0.5px;")
            
        elif status == "understanding":
            self.start_pulse(350, "#BF5AF2") # Apple AI Purple (Premium & Futuristic)
            self.text_label.setText("Processing...")
            self.text_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-style: italic; letter-spacing: 0.5px;")
            
        elif status == "transcribed":
            self.can_hide = False
            self.transcribed_timer.start(2500) # Give slightly more time to read
            
            # Pure White dot, completely static. Looks incredibly clean.
            self.stop_pulse("#FFFFFF") 
            
            display_text = text.capitalize()
            if len(display_text) > 100:
                display_text = display_text[:97] + "..."
                
            self.text_label.setText(f'"{display_text}"')
            # Soft White Text (90% opacity), normal weight, elegant spacing
            self.text_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-weight: normal; letter-spacing: 0.2px;")

        self.show_panel()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = STTPopup()
    sys.exit(app.exec_())