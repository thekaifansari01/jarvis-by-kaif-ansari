import sys
import json
import os
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QFileSystemWatcher, QPoint, QParallelAnimationGroup
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QFrame, QSizePolicy
from PyQt5.QtGui import QFont, QColor, QFontDatabase

class AgentPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.status_file = "Data/agent_status.json"
        self.last_status = None
        self.current_step = -1
        
        # --- SAFE FONT LOADING ---
        self.font_id = QFontDatabase.addApplicationFont("Data/fonts/plain-text.ttf")
        families = QFontDatabase.applicationFontFamilies(self.font_id)
        self.custom_font = families[0] if (self.font_id != -1 and families) else "Segoe UI"

        self.initUI()
        
        # --- DEBOUNCED SMART WATCHER ---
        os.makedirs(os.path.dirname(self.status_file), exist_ok=True)
        if not os.path.exists(self.status_file):
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump({"step": 0, "thought": "", "action": "", "action_detail": "", "observation": ""}, f)
        
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.process_status_update)

        self.watcher = QFileSystemWatcher(self)
        self.watcher.addPath(self.status_file)
        self.watcher.fileChanged.connect(lambda: self.update_timer.start(100))
        
        self.process_status_update()

    def initUI(self):
        # Ghost Mode + Tool Window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        
        self.setMinimumWidth(350)
        self.setMaximumWidth(700)

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(40, 40, 40, 40)

        # --- DYNAMIC ISLAND (ULTRA PREMIUM) ---
        self.container = QFrame(self)
        self.container.setObjectName("Island")
        self.container.setAttribute(Qt.WA_StyledBackground, True)
        self.container.setMinimumHeight(85) 
        self.container.setStyleSheet("""
            #Island {
                background-color: #000000;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 26px;
            }
        """)

        # Deeper, softer Apple-like shadow
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(40)
        self.shadow.setColor(QColor(0, 0, 0, 160))
        self.shadow.setOffset(0, 15)
        self.container.setGraphicsEffect(self.shadow)

        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(26, 20, 26, 24)
        self.layout.setSpacing(14) 

        # --- HEADER ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        # Indicator Dot (Like STT Popup)
        self.pulse_dot = QFrame()
        self.pulse_dot.setFixedSize(12, 12)
        self.pulse_dot.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.pulse_dot.setStyleSheet("background-color: #BF5AF2; border-radius: 6px;") # Apple AI Purple
        self.pulse_opacity = QGraphicsOpacityEffect(self.pulse_dot)
        self.pulse_dot.setGraphicsEffect(self.pulse_opacity)
        self.start_pulse_animation()
        
        self.status_tag = QLabel("AGENT ACTIVE")
        self.status_tag.setFont(QFont(self.custom_font, 9, QFont.Bold))
        self.status_tag.setStyleSheet("color: rgba(255, 255, 255, 0.7); letter-spacing: 1.5px; border: none; background: transparent;")

        header_layout.addWidget(self.pulse_dot)
        header_layout.addWidget(self.status_tag)
        header_layout.addStretch()
        
        self.phase_label = QLabel("STEP: 00")
        self.phase_label.setFont(QFont(self.custom_font, 9, QFont.Bold))
        self.phase_label.setStyleSheet("color: rgba(255, 255, 255, 0.3); letter-spacing: 1px; border: none; background: transparent;")
        self.phase_opacity = QGraphicsOpacityEffect(self.phase_label)
        self.phase_label.setGraphicsEffect(self.phase_opacity)
        
        header_layout.addWidget(self.phase_label)
        self.layout.addLayout(header_layout)
        
        # --- TEXT AREA (THOUGHT) ---
        self.thought_label = QLabel("")
        self.thought_label.setWordWrap(True)
        self.thought_label.setAlignment(Qt.AlignCenter)
        self.thought_label.setFont(QFont(self.custom_font, 11)) 
        self.thought_label.setStyleSheet("color: rgba(255, 255, 255, 0.95); line-height: 1.4; border: none; background: transparent;")
        
        self.text_opacity = QGraphicsOpacityEffect(self.thought_label)
        self.thought_label.setGraphicsEffect(self.text_opacity)
        self.layout.addWidget(self.thought_label)

        # --- OBSERVATION AREA (RESULT) ---
        self.obs_label = QLabel("")
        self.obs_label.setWordWrap(True)
        self.obs_label.setAlignment(Qt.AlignCenter)
        self.obs_label.setFont(QFont(self.custom_font, 9)) 
        # Apple Siri Blue for observation results
        self.obs_label.setStyleSheet("color: #0A84FF; line-height: 1.2; border: none; background: transparent; padding-top: 2px;")
        self.layout.addWidget(self.obs_label)
        self.obs_label.hide()

        self.outer_layout.addWidget(self.container)

        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_panel)
        
        self.setWindowOpacity(0.0)
        self.hide()

    # ==========================================
    # CORE ANIMATION LOGIC (Glitch-Free)
    # ==========================================
    
    def calculate_geometry(self):
        # Removed QApplication.processEvents() to strictly prevent flickering
        self.adjustSize()
        
        screen = QApplication.primaryScreen().availableGeometry()
        w = self.width()
        h = self.height()
        x = (screen.width() - w) // 2
        y = screen.top() + 10 # 10px spacing from top
        return x, y, w, h

    def recenter(self):
        x, y, w, h = self.calculate_geometry()
        self.setGeometry(x, y, w, h)

    def start_pulse_animation(self):
        self.p_anim = QPropertyAnimation(self.pulse_opacity, b"opacity")
        self.p_anim.setDuration(1000)
        self.p_anim.setStartValue(0.2)
        self.p_anim.setEndValue(1.0)
        self.p_anim.setLoopCount(-1)
        self.p_anim.setEasingCurve(QEasingCurve.InOutSine) 
        self.p_anim.start()

    # --- TEXT TRANSITION ---
    def update_text_smoothly(self, new_text):
        if self.thought_label.text() == new_text:
            return
            
        self.pending_text = new_text
        
        self.text_fade_out = QPropertyAnimation(self.text_opacity, b"opacity")
        self.text_fade_out.setDuration(150)
        self.text_fade_out.setStartValue(self.text_opacity.opacity())
        self.text_fade_out.setEndValue(0.0)
        self.text_fade_out.finished.connect(self._apply_text_and_fade_in)
        self.text_fade_out.start()

    def _apply_text_and_fade_in(self):
        if hasattr(self, 'pending_text'):
            self.thought_label.setText(self.pending_text)
            self.recenter() 
            del self.pending_text
            
        self.text_fade_in = QPropertyAnimation(self.text_opacity, b"opacity")
        self.text_fade_in.setDuration(250) 
        self.text_fade_in.setStartValue(0.0)
        self.text_fade_in.setEndValue(1.0)
        self.text_fade_in.setEasingCurve(QEasingCurve.InOutQuad) 
        self.text_fade_in.start()

    # --- STEP TRANSITION ---
    def update_step_smoothly(self, new_step):
        self.pending_step = new_step
        
        self.step_fade_out = QPropertyAnimation(self.phase_opacity, b"opacity")
        self.step_fade_out.setDuration(150)
        self.step_fade_out.setStartValue(self.phase_opacity.opacity())
        self.step_fade_out.setEndValue(0.0)
        self.step_fade_out.finished.connect(self._apply_step_and_fade_in)
        self.step_fade_out.start()

    def _apply_step_and_fade_in(self):
        if hasattr(self, 'pending_step'):
            self.phase_label.setText(f"STEP: {self.pending_step:02}")
            del self.pending_step
            
        self.step_fade_in = QPropertyAnimation(self.phase_opacity, b"opacity")
        self.step_fade_in.setDuration(250)
        self.step_fade_in.setStartValue(0.0)
        self.step_fade_in.setEndValue(1.0)
        self.step_fade_in.setEasingCurve(QEasingCurve.InOutQuad)
        self.step_fade_in.start()

    # --- WINDOW TRANSITIONS ---
    def show_panel(self):
        # Explicitly stop hide timer to prevent race conditions
        self.hide_timer.stop()

        x, y, w, h = self.calculate_geometry()
        
        if hasattr(self, 'hide_anim_group') and self.hide_anim_group.state() == QPropertyAnimation.Running:
            self.hide_anim_group.stop()
            self.hide_anim_group.finished.disconnect()
                
        if not self.isVisible() or self.windowOpacity() == 0.0:
            start_y = y - 30 # Start slightly above
            self.setGeometry(x, start_y, w, h)
            self.show()
            self.raise_()

            self.show_anim_group = QParallelAnimationGroup(self)
            
            fade_in = QPropertyAnimation(self, b"windowOpacity")
            fade_in.setDuration(300)
            fade_in.setStartValue(self.windowOpacity())
            fade_in.setEndValue(1.0)
            
            slide_down = QPropertyAnimation(self, b"pos")
            slide_down.setDuration(400)
            slide_down.setStartValue(QPoint(x, start_y))
            slide_down.setEndValue(QPoint(x, y))
            slide_down.setEasingCurve(QEasingCurve.OutBack) # Premium bounce

            self.show_anim_group.addAnimation(fade_in)
            self.show_anim_group.addAnimation(slide_down)
            self.show_anim_group.start()
        else:
            self.setGeometry(x, y, w, h)
        
        self.hide_timer.start(6000)

    def hide_panel(self):
        if not self.isVisible(): return
        
        if hasattr(self, 'show_anim_group') and self.show_anim_group.state() == QPropertyAnimation.Running:
            self.show_anim_group.stop()

        self.hide_anim_group = QParallelAnimationGroup(self)
        
        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(250)
        fade_out.setStartValue(self.windowOpacity())
        fade_out.setEndValue(0.0)
        
        slide_up = QPropertyAnimation(self, b"pos")
        slide_up.setDuration(300)
        slide_up.setStartValue(self.pos())
        slide_up.setEndValue(QPoint(self.x(), self.y() - 20))
        slide_up.setEasingCurve(QEasingCurve.InBack)

        self.hide_anim_group.addAnimation(fade_out)
        self.hide_anim_group.addAnimation(slide_up)
        self.hide_anim_group.finished.connect(self.hide)
        self.hide_anim_group.start()

    # ==========================================
    # DATA PROCESSING
    # ==========================================
    
    def process_status_update(self):
        if not os.path.exists(self.status_file): return
        
        try:
            with open(self.status_file, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip(): return
                status = json.loads(content)
        except (json.JSONDecodeError, IOError):
            return 

        if status == self.last_status:
            if self.isVisible() and self.last_status.get("step", 0) > 0:
                self.hide_timer.start(6000)
            return
        
        self.last_status = status
        step = status.get("step", 0)
        thought = status.get("thought", "")
        action = status.get("action", "")
        action_detail = status.get("action_detail", "")
        observation = status.get("observation", "")

        if step == 0:
            self.current_step = -1 
            self.hide_timer.start(1500) 
            return

        self.show_panel()

        # Update Action Header with DYNAMIC DETAIL
        action_map = {
            "THINKING": "THINKING",
            "search_actions": "SEARCHING WEB",
            "deep_research": "DEEP RESEARCH",
            "workspace_action": "WORKSPACE",
            "email_action": "SENDING EMAIL",
            "whatsapp_action": "WHATSAPP",
            "apps_to_open": "OPENING APP",
            "urls_to_open": "OPENING URL",
            "image_command": "GENERATING IMAGE"
        }
        
        base_text = action_map.get(action, "EXECUTING")
        if action_detail and action != "THINKING":
            detail_clean = str(action_detail).upper()
            if len(detail_clean) > 30:
                detail_clean = detail_clean[:27] + "..."
            self.status_tag.setText(f"{base_text} -> {detail_clean}")
            self.pulse_dot.setStyleSheet("background-color: #0A84FF; border-radius: 6px;") # Action Blue
        else:
            if action == "THINKING":
                self.status_tag.setText("THINKING...")
                self.pulse_dot.setStyleSheet("background-color: #BF5AF2; border-radius: 6px;") # Think Purple
            else:
                self.status_tag.setText(f"{base_text}...")
                self.pulse_dot.setStyleSheet("background-color: #0A84FF; border-radius: 6px;")

        # Update Step (Smoothly)
        if self.current_step != step:
            self.update_step_smoothly(step)
            self.current_step = step
        
        # Update Text (Smoothly)
        if thought:
            clean_thought = thought.upper()
            if len(clean_thought) > 150:
                clean_thought = clean_thought[:147] + "..."
            self.update_text_smoothly(clean_thought)
        else:
            self.update_text_smoothly("")

        # Display Observation/Result (🚀 BUG FIXED: Jitter removed, 120 char limit)
        if observation and "Observation:" in observation:
            clean_obs = observation.replace("Observation:", "").strip()
            if len(clean_obs) > 120:
                clean_obs = clean_obs[:117] + "..."
            
            # Only update text and layout if it actually changed
            if self.obs_label.text() != clean_obs:
                self.obs_label.setText(f"{clean_obs}")
                if not self.obs_label.isVisible():
                    self.obs_label.show()
                # 🚀 The Magic Key: Unconditionally recenter whenever text updates 
                # to prevent layout expansion from breaking alignment.
                self.recenter()
        else:
            if self.obs_label.isVisible():
                self.obs_label.setText("")
                self.obs_label.hide()
                self.recenter()

def run_panel():
    app = QApplication(sys.argv)
    panel = AgentPanel()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run_panel()