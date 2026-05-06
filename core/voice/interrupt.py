# modules/voice/interrupt.py
"""
Global interrupt flag used to cancel ongoing command processing
when wake word is detected during TTS or processing.
"""

_interrupt_requested = False

def set_interrupt():
    """Set interrupt flag (called from background wake word listener)."""
    global _interrupt_requested
    _interrupt_requested = True

def clear_interrupt():
    """Clear interrupt flag after handling."""
    global _interrupt_requested
    _interrupt_requested = False

def is_interrupted():
    """Check if interrupt has been requested."""
    return _interrupt_requested