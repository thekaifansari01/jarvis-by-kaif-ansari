import sys
import re
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QParallelAnimationGroup, QEasingCurve, qInstallMessageHandler
from PyQt5.QtWidgets import (QLabel, QWidget, QGraphicsDropShadowEffect, QVBoxLayout, 
                             QSizePolicy, QApplication, QFrame, QPushButton, QHBoxLayout, 
                             QScrollArea)
from PyQt5.QtGui import QFont, QColor, QFontDatabase, QTextDocument, QPalette
from markdown2 import markdown

# --- Warning Suppressor ---
def suppress_qt_warnings(mode, context, message):
    if "OpenType support missing" in message:
        pass
    else:
        print(message)

class TypingPopup(QWidget):
    def __init__(self, full_text, speed=80, duration=8000, max_width=750):
        super().__init__()
        self.full_text = full_text
        self.displayed_text = ""
        
        self.words = re.findall(r'\S+\s*|\s+', self.full_text)
        self.index = 0
        
        self.speed = speed
        self.duration = duration
        self.max_width = max_width
        self.markdown_enabled = True 

        # Fonts load
        self.eng_font_id = QFontDatabase.addApplicationFont("Data/fonts/english.ttf")
        eng_families = QFontDatabase.applicationFontFamilies(self.eng_font_id)
        self.eng_font = eng_families[0] if (self.eng_font_id != -1 and eng_families) else "Segoe UI"

        self.hin_font_id = QFontDatabase.addApplicationFont("Data/fonts/devangri.ttf")
        hin_families = QFontDatabase.applicationFontFamilies(self.hin_font_id)
        self.hin_font = hin_families[0] if (self.hin_font_id != -1 and hin_families) else "Nirmala UI"

        self.init_ui()
        self.pre_calculate_size()
        self.start_animations()
        QTimer.singleShot(250, self.show_typing)
        self.show()

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(50, 50, 50, 50) 

        self.container = QFrame(self)
        self.container.setObjectName("Island")
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.container.setStyleSheet("""
            #Island {
                background-color: rgba(26, 27, 32, 0.96); 
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 15)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.container.setGraphicsEffect(shadow)

        self.container_layout = QVBoxLayout(self.container)
        # Margins ekdum balance kar diye kyunki ab scrollbar ki jagah nahi chahiye
        self.container_layout.setContentsMargins(24, 16, 24, 14) 
        self.container_layout.setSpacing(6)

        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 0) 
        self.header_layout.addStretch() 
        
        self.close_btn = QPushButton("✕", self.container)
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                color: rgba(255, 255, 255, 0.3);
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: bold;
                border-radius: 13px;
            }
            QPushButton:hover {
                color: rgba(255, 255, 255, 0.9);
                background: rgba(255, 59, 48, 0.8); 
            }
            QPushButton:pressed {
                background: rgba(255, 59, 48, 1.0);
            }
        """)
        self.close_btn.clicked.connect(self.fade_out)
        self.header_layout.addWidget(self.close_btn)

        # 🚀 SCROLL AREA (SCROLLBAR COMPLETELY HIDDEN) 🚀
        self.scroll_area = QScrollArea(self.container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # <-- NO MORE SCROLLBAR!
        
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)

        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label.setCursor(Qt.IBeamCursor) 
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label.setFont(QFont(self.eng_font, 11))

        # Premium selection highlight
        palette = self.label.palette()
        palette.setColor(QPalette.Highlight, QColor(255, 255, 255, 45))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255, 255))
        self.label.setPalette(palette)

        self.label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                margin: 0px;
                padding: 0px; 
            }
        """)

        self.scroll_area.setWidget(self.label)
        self.container_layout.addLayout(self.header_layout)
        self.container_layout.addWidget(self.scroll_area)
        
        self.outer_layout.addWidget(self.container)
        self.outer_layout.setAlignment(Qt.AlignCenter)

        self.setWindowOpacity(0.0)
        self.oldPos = None

    def pre_calculate_size(self):
        html_content = self.full_text
        if self.markdown_enabled:
            try:
                html_content = markdown(self.full_text, extras=["fenced-code-blocks"])
            except Exception:
                pass
                
        doc = QTextDocument()
        doc.setDefaultFont(QFont(self.eng_font, 11))
        doc.setDocumentMargin(0) 
        doc.setHtml(self.get_styled_html(html_content))
        
        padding_w = 150 
        padding_h = 160 
        
        max_content_width = self.max_width - padding_w
        
        doc.setTextWidth(-1) 
        ideal_width = doc.idealWidth()
        
        if ideal_width < max_content_width:
            content_w = ideal_width + 8 
            doc.setTextWidth(content_w)
            content_h = doc.size().height()
        else:
            content_w = max_content_width
            doc.setTextWidth(content_w)
            content_h = doc.size().height()
            
        final_w = int(content_w) + padding_w
        final_h = int(content_h) + padding_h
        
        screen = QApplication.primaryScreen().availableGeometry()
        max_allowed_height = int(screen.height() * 0.75) 
        
        if final_h > max_allowed_height:
            final_h = max_allowed_height
            # Scrollbar nahi aayega toh extra width dene ki zaroorat nahi hai
            
        final_w = max(final_w, 300)
        final_h = max(final_h, 100) 
        
        self.setFixedSize(final_w, final_h)

    def get_centered_x(self):
        screen = QApplication.primaryScreen().availableGeometry()
        w = self.width()
        return (screen.width() - w) // 2

    def get_styled_html(self, content):
        return f"""
        <style>
            body, p, div {{
                margin: 0px;
                padding: 0px;
            }}
            .content {{
                color: rgba(255, 255, 255, 0.9);
                line-height: 1.5; 
                letter-spacing: 0.4px;
                font-family: '{self.eng_font}', '{self.hin_font}', 'Segoe UI', sans-serif;
            }}
            code {{
                background-color: rgba(255, 255, 255, 0.12);
                color: #A3BE8C;
                padding: 3px 6px;
                border-radius: 5px;
                font-family: Consolas, monospace;
                font-size: 0.95em;
            }}
            pre {{
                background-color: rgba(0, 0, 0, 0.4); 
                padding: 14px;
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                margin-top: 10px;
                margin-bottom: 10px;
            }}
            a {{
                color: #81A1C1;
                text-decoration: none;
                border-bottom: 1px dashed rgba(129, 161, 193, 0.5); 
            }}
        </style>
        <div class="content">{content}</div>
        """

    def start_animations(self):
        screen = QApplication.primaryScreen().availableGeometry()
        start_y = screen.top() - 30
        end_y = screen.top() + 30 
        x = self.get_centered_x()

        self.setGeometry(x, start_y, self.width(), self.height())

        self.anim_group = QParallelAnimationGroup(self)

        fade_in = QPropertyAnimation(self, b"windowOpacity")
        fade_in.setDuration(400)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        
        slide_down = QPropertyAnimation(self, b"pos")
        slide_down.setDuration(600)
        slide_down.setStartValue(QPoint(x, start_y))
        slide_down.setEndValue(QPoint(x, end_y))
        slide_down.setEasingCurve(QEasingCurve.OutExpo)

        self.anim_group.addAnimation(fade_in)
        self.anim_group.addAnimation(slide_down)
        self.anim_group.start()

    def show_typing(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_text)
        self.timer.start(self.speed)

    def update_text(self):
        if self.index < len(self.words):
            self.displayed_text += self.words[self.index]
            
            html_content = self.displayed_text
            if self.markdown_enabled:
                try:
                    html_content = markdown(self.displayed_text, extras=["fenced-code-blocks"])
                except Exception:
                    pass
            
            self.label.setText(self.get_styled_html(html_content))
            QTimer.singleShot(10, self.auto_scroll_down)
            
            self.index += 1
        else:
            self.timer.stop()

    def auto_scroll_down(self):
        # Even without visible scrollbar, this will keep auto-scrolling to the bottom!
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def fade_out(self):
        if not self.isVisible(): return
        
        self.out_anim_group = QParallelAnimationGroup(self)

        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(300)
        fade_out.setStartValue(self.windowOpacity())
        fade_out.setEndValue(0.0)

        slide_up = QPropertyAnimation(self, b"pos")
        slide_up.setDuration(400)
        slide_up.setStartValue(self.pos())
        slide_up.setEndValue(QPoint(self.x(), self.y() - 30))
        slide_up.setEasingCurve(QEasingCurve.InExpo)

        self.out_anim_group.addAnimation(fade_out)
        self.out_anim_group.addAnimation(slide_up)
        self.out_anim_group.finished.connect(self.close)
        self.out_anim_group.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.oldPos is not None:
            delta = QPoint(event.globalPos() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.oldPos = None

if __name__ == "__main__":
    qInstallMessageHandler(suppress_qt_warnings)
    app = QApplication(sys.argv)
    
    test_text = """नमस्ते! 🙏 
This is a **Premium UI** component. 

Scrollbar ka poora kissa khatam kar diya hai! 
Ab sirf text hai aur mouse wheel se smoothly scroll hoga.
Line 1
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8
Line 9
Line 10
Makkhan jaisi scrolling bina kisi purane dabbo ke! ✨
"""

    text_to_show = sys.argv[1] if len(sys.argv) > 1 else test_text
    popup = TypingPopup(text_to_show)
    sys.exit(app.exec_())