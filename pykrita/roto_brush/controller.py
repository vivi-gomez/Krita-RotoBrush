"""Estado de la herramienta, cálculo en hilo aparte y escritura en la capa."""

import os
import threading
import time
from pathlib import Path

from krita import Krita

from . import canvas, log
from .recorder import Recorder
from .engine import FG, REFINE, REFINE_ERASE, Engine
from .overlay import Overlay
from .compute import ComputeOps
from .diagnostics import Diagnostics
from .edits import StrokeEdits
from .qt import QObject, QtCore, QtGui, QtWidgets, pyqtSignal, qaction_class, shortcut_context

PREVIEW_DELAY_MS = 700





def default_model_path() -> Path:
    env = os.environ.get("ROTO_BRUSH_MODEL")
    if env:
        return Path(env)
    return Path.home() / ".config" / "effectcraft" / "models" / "mobile_sam.pt"


class Controller(StrokeEdits, ComputeOps, Diagnostics, QObject):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    status = pyqtSignal(str)
    armed = pyqtSignal(bool)
    params_reset = pyqtSignal()

    def __init__(self, lib_path: Path):
        super().__init__()
        self.engine = Engine(lib_path)
        self.model_path = default_model_path()
        self.strokes = []
        self.mode = FG
        self.brush = 18
        self.best = True
        self.decontaminate = True
        self.feather = 1.5
        self.smooth = 1.0
        self.edge_smooth = 8
        self.contrast = 0.0
        self.shift = 0.0
        self.search_radius = 15.0
        self.sam_weight = 6.0
        self.clean = True
        self.fill_holes = True
        self.edit_mode = False
        self.selected = None
        self.view_mask = False
        self.capture = canvas.Capture(self)
        self.recorder = Recorder()
        self.overlay = None
        self.source = None  # (node_id, rect, rgba original)
        self._doc_key = None
        self._source_node = None
        self.mask = None
        self.applied = False
        self.computed_strokes = 0
        self.busy = False
        self.pending = False
        self.auto_preview = True
        self._doc = None
        self._saved_tool = None
        self._connect_notifier()
        self._bad_points = 0
        self._undo_qaction = None
        self._undo_krita = None
        self._undo_shortcuts = None
        self._undo_ctx = None
        self.undo_stack = []
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(PREVIEW_DELAY_MS)
        self._timer.timeout.connect(self.compute)
        self._watch = QtCore.QTimer(self)
        self._watch.setInterval(1500)
        self._watch.timeout.connect(self._watch_document)
        self._watch.start()
        self.done.connect(self._preview)
        self.failed.connect(self._fail)
        if os.environ.get("ROTO_BRUSH_DUMP"):
            QtCore.QTimer.singleShot(5000, self.dump_ui)
        if os.environ.get("ROTO_BRUSH_SELFTEST"):
            QtCore.QTimer.singleShot(8000, self.selftest)
        if os.environ.get("ROTO_BRUSH_SAMTEST"):
            QtCore.QTimer.singleShot(9000, self.samtest)
        if os.environ.get("ROTO_BRUSH_APPLYTEST"):
            QtCore.QTimer.singleShot(9000, self.applytest)
        if os.environ.get("ROTO_BRUSH_EVENTTEST"):
            QtCore.QTimer.singleShot(9000, self.event_test)

    @property
    def window(self):
        return Krita.instance().activeWindow()

    @property
    def view(self):
        w = self.window
        return w.activeView() if w is not None else None

    @property
    def document(self):
        return Krita.instance().activeDocument()

    # -- captura --------------------------------------------------------------

    def set_capture(self, on: bool) -> bool:
        if not on:
            self._timer.stop()
            self.recorder.note("captura desactivada")
            self.capture.stop()
            self._drop_overlay()
            self._restore_tool()
            self._remove_undo_shortcut()
            self.armed.emit(False)
            return True
        self._sync_document()
        if not self.capture.start():
            return False
        self.recorder.begin(self)
        self._neutral_tool()
        self._make_overlay()
        self._install_undo_shortcut()
        return True

    def _neutral_tool(self) -> None:
        """Cambia a Move para que el pincel normal no pinte ni ensucie el undo."""
        try:
            qwin = self.window.qwindow()
            actions = list(qwin.actions())
        except Exception:  # noqa: BLE001
            return
        for a in actions:
            try:
                if a.objectName() == "tool_move":
                    self._saved_tool = a
                    a.trigger()
                    log.info("herramienta neutral: tool_move")
                    return
            except Exception:  # noqa: BLE001
                continue
        log.info("herramienta neutral: no encontrada")

    def _install_undo_shortcut(self) -> None:
        """Mientras la herramienta está activa, Ctrl+Z es nuestro."""
        if self._undo_qaction is not None:
            return
        try:
            win = self.window
            qwin = win.qwindow() if win is not None else None
            if qwin is None:
                return
            kact = Krita.instance().action("edit_undo")
            if kact is not None:
                self._undo_krita = kact
                self._undo_shortcuts = list(kact.shortcuts())
                kact.setShortcuts([])
            act = qaction_class()(qwin)
            act.setShortcut(QtGui.QKeySequence("Ctrl+Z"))
            act.setShortcutContext(shortcut_context("WindowShortcut"))
            act.triggered.connect(self.undo)
            qwin.addAction(act)
            self._undo_qaction = act
            log.info("atajo Ctrl+Z propio instalado")
        except Exception as e:  # noqa: BLE001
            log.error(f"atajo undo: {e!r}")

    def _remove_undo_shortcut(self) -> None:
        try:
            if self._undo_qaction is not None:
                qwin = self.window.qwindow() if self.window is not None else None
                if qwin is not None:
                    qwin.removeAction(self._undo_qaction)
                self._undo_qaction.deleteLater()
                self._undo_qaction = None
            if self._undo_krita is not None and self._undo_shortcuts:
                self._undo_krita.setShortcuts(self._undo_shortcuts)
            self._undo_krita = None
            self._undo_shortcuts = None
        except Exception as e:  # noqa: BLE001
            log.error(f"quitar atajo undo: {e!r}")

    def tool_is_neutral(self) -> bool:
        """Solo se captura si la herramienta activa es Move (así zoom/mano funcionan)."""
        try:
            qwin = self.window.qwindow()
            for a in qwin.actions():
                name = a.objectName()
                if name.startswith("tool_") and a.isCheckable() and a.isChecked():
                    return name == "tool_move"
        except Exception:  # noqa: BLE001
            pass
        action = self._saved_tool
        try:
            return action is None or action.isChecked()
        except Exception:  # noqa: BLE001
            return True

    def _restore_tool(self) -> None:
        if self._saved_tool is not None:
            try:
                self._saved_tool.trigger()
            except Exception:  # noqa: BLE001
                pass
            self._saved_tool = None
        self._connect_notifier()
        self._bad_points = 0
        self._undo_qaction = None
        self._undo_krita = None
        self._undo_shortcuts = None
        self._undo_ctx = None
        self.undo_stack = []

    def _make_overlay(self):
        self._drop_overlay()
        if self.capture.target is not None:
            self.overlay = Overlay(self.capture.target, self)

    def _drop_overlay(self):
        ov = self.overlay
        self.overlay = None
        if ov is not None:
            try:
                ov.deleteLater()
            except Exception:  # noqa: BLE001
                pass

    def set_hover(self, pos) -> None:
        ov = self.overlay
        if ov is None:
            return
        try:
            ov.set_hover(pos)
        except RuntimeError:
            self.overlay = None

    def _refresh(self) -> None:
        """Repintado barato: sin recolocar el widget en cada punto."""
        ov = self.overlay
        if ov is None:
            return
        try:
            ov.update()
        except RuntimeError:
            self.overlay = None

    def overlay_update(self) -> None:
        """Refresca el overlay; si Krita lo borró (imagen cerrada), lo olvida."""
        ov = self.overlay
        if ov is None:
            return
        try:
            ov.sync()
            ov.update()
        except RuntimeError:
            self.overlay = None

    def _fail(self, msg: str) -> None:
        self.busy = False
        log.error(msg)
        self.status.emit(f"error: {msg}")

