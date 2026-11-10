"""Importa PyQt5 (Krita 5) o PyQt6 (Krita 6) y unifica los enums."""

try:  # Krita 6
    from PyQt6 import QtCore, QtGui, QtWidgets
    from PyQt6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, pyqtSignal

    QT6 = True
except ImportError:  # Krita 5
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtCore import QEvent, QObject, QPointF, QRectF, Qt, pyqtSignal

    QT6 = False

QApplication = QtWidgets.QApplication


def event_type(name: str):
    """QEvent.Type.X con ocultación de la diferencia Qt5/Qt6."""
    t = getattr(QEvent, "Type", None)
    return getattr(t, name) if t is not None else getattr(QEvent, name)


def widget_attr(name: str):
    a = getattr(Qt, "WidgetAttribute", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def cursor_shape(name: str):
    a = getattr(Qt, "CursorShape", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def qaction_class():
    """QAction está en QtGui desde Qt6."""
    cls = getattr(QtGui, "QAction", None)
    return cls if cls is not None else QtWidgets.QAction


def shortcut_context(name: str):
    a = getattr(Qt, "ShortcutContext", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def key_code(name: str):
    a = getattr(Qt, "Key", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def keyboard_modifier(name: str):
    a = getattr(Qt, "KeyboardModifier", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def mouse_button(name: str):
    a = getattr(Qt, "MouseButton", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def image_format(name: str):
    f = getattr(QtGui.QImage, "Format", None)
    return getattr(f, name) if f is not None else getattr(QtGui.QImage, name)


def painter_hint(name: str):
    a = getattr(QtGui.QPainter, "RenderHint", None)
    return getattr(a, name) if a is not None else getattr(QtGui.QPainter, name)


def orientation(name: str):
    a = getattr(Qt, "Orientation", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def pen_style(name: str):
    a = getattr(Qt, "PenStyle", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def cap_style(name: str):
    a = getattr(Qt, "PenCapStyle", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)


def join_style(name: str):
    a = getattr(Qt, "PenJoinStyle", None)
    return getattr(a, name) if a is not None else getattr(Qt, name)
