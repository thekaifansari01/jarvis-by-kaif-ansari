import sys
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QSize
from PyQt5.QtWidgets import QLabel, QWidget, QGraphicsDropShadowEffect, QVBoxLayout, QSizePolicy, QApplication
from PyQt5.QtGui import QFont, QColor
from markdown2 import markdown

class TypingPopup(QWidget):
    # CHANGE: speed=60 kar diya hai (Jitna bada number, utni slow typing)
    # duration=10000 (10 seconds hold time)
    def __init__(self, full_text, speed=60, duration=10000, max_width=600):
        super().__init__()
        self.full_text = full_text
        self.displayed_text = ""
        self.index = 0
        self.speed = speed
        self.duration = duration
        self.max_width = max_width
        self.markdown_enabled = True 

        self.init_ui()
        self.start_slide_in()
        self.show_typing()
        self.show()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.label = QLabel("", self)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        font = QFont("Segoe UI Semibold", 12, QFont.Bold)
        self.label.setFont(font)
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(30, 30, 30, 220);
                padding: 15px 25px;
                border-radius: 15px;
                border: 2px solid white;
            }
        """)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.label.setGraphicsEffect(shadow)

        layout.addWidget(self.label)
        layout.setAlignment(Qt.AlignCenter)

        self.setMaximumWidth(self.max_width)
        self.resize(self.max_width, 100)
        self.adjustSize()
        self.move_to_top_center()

        self.setWindowOpacity(0)

    def move_to_top_center(self):
        screen = self.screen().availableGeometry()
        size = self.size()
        self.move(
            int((screen.width() - size.width()) / 2 + screen.left()),
            screen.top() + 50
        )

    def start_slide_in(self):
        screen = self.screen().availableGeometry()
        start_pos = QPoint(self.x(), screen.top() - self.height())
        end_pos = QPoint(self.x(), screen.top() + 50)

        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(600)
        self.anim.setStartValue(start_pos)
        self.anim.setEndValue(end_pos)
        self.anim.start()

        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(600)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        self.fade_anim.start()

    def show_typing(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_text)
        self.timer.start(self.speed)

    def update_text(self):
        if self.index < len(self.full_text):
            self.displayed_text += self.full_text[self.index]
            if self.markdown_enabled:
                try:
                    html_text = markdown(self.displayed_text, extras=["fenced-code-blocks"])
                    self.label.setText(html_text)
                except Exception as e:
                    self.label.setText(self.displayed_text)
            else:
                self.label.setText(self.displayed_text)
            
            self.adjustSize()
            self.move_to_top_center()
            self.index += 1
        else:
            self.timer.stop()
            # Typing khatam hone ke baad 10 seconds wait karega
            QTimer.singleShot(self.duration, self.fade_out)

    def fade_out(self):
        self.fade_anim_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim_out.setDuration(800)
        self.fade_anim_out.setStartValue(1)
        self.fade_anim_out.setEndValue(0)
        self.fade_anim_out.finished.connect(self.close)
        self.fade_anim_out.start()

    def sizeHint(self):
        size = self.label.sizeHint()
        return size + QSize(50, 50)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    text_to_show = sys.argv[1] if len(sys.argv) > 1 else "Hello Jarvis!"
    # Default speed ab class definition se 60 hi uthayega
    popup = TypingPopup(text_to_show)
    sys.exit(app.exec_())