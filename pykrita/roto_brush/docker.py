"""Docker con los ajustes de la herramienta."""

from pathlib import Path

from krita import DockWidget

from . import log
from .controller import Controller, default_model_path
from .engine import BG, FG, REFINE, REFINE_ERASE
from .qt import QtWidgets, orientation


def lib_path() -> Path:
    return Path(__file__).resolve().parent / "lib" / "libroto_brush_core.so"


class RotoBrushDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Roto Brush")
        self.c = Controller(lib_path())
        self.c.ui = self
        self.c.status.connect(self._status)
        self.c.armed.connect(self._on_armed)
        self.c.params_reset.connect(self._sync_controls)
        self.c.failed.connect(lambda m: self._status(f"error: {m}"))
        self.setWidget(self._build())
        self._status("listo")

    def canvasChanged(self, canvas):  # noqa: N802
        log.info(f"canvasChanged: {canvas is not None}")

    # -- interfaz -------------------------------------------------------------

    def _build(self):
        box = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(8, 8, 8, 8)

        self.btn_paint = QtWidgets.QPushButton("Activar pincel")
        self.btn_paint.setCheckable(True)
        self.btn_paint.setChecked(False)
        self.btn_paint.toggled.connect(self._toggle_paint)
        lay.addWidget(self.btn_paint)

        row = QtWidgets.QHBoxLayout()
        self.modes = QtWidgets.QButtonGroup(box)
        for text, kind in (("Primer plano", FG), ("Fondo", BG), ("Refine", REFINE), ("Borrar refine", REFINE_ERASE)):
            b = QtWidgets.QPushButton(text)
            b.setCheckable(True)
            b.setChecked(kind == FG)
            self.modes.addButton(b, kind)
            row.addWidget(b)
        self.modes.idClicked.connect(self._set_mode)
        lay.addLayout(row)

        size = QtWidgets.QHBoxLayout()
        size.addWidget(QtWidgets.QLabel("Pincel (Refine)"))
        self.brush = QtWidgets.QSpinBox()
        self.brush.setRange(1, 300)
        self.brush.setValue(self.c.brush)
        self.brush.valueChanged.connect(self._set_brush)
        self.edit = QtWidgets.QCheckBox("Editar trazos (clic para seleccionar)")
        self.edit.toggled.connect(self._toggle_edit)
        lay.addWidget(self.edit)

        self.view_mask = QtWidgets.QCheckBox("Ver solo la máscara")
        self.view_mask.toggled.connect(self._toggle_mask_view)
        lay.addWidget(self.view_mask)
        size.addWidget(self.brush)
        lay.addLayout(size)

        self.feather = self._slider(lay, "Feather", 0, 40, 15)
        self.smooth = self._slider(lay, "Smooth", 0, 100, 10)
        self.contrast = self._slider(lay, "Contraste", -100, 100, 0)
        self.shift = self._slider(lay, "Desplazar borde", -100, 100, 0)
        self.model_weight = self._slider(lay, "Peso del modelo", 0, 20, 6)
        self.stroke_feather = self._slider(lay, "Feather del trazo", 0, 40, 0)
        self.edge = self._slider(lay, "Suavizar borde", 0, 16, 8)

        self.auto = QtWidgets.QCheckBox("Vista previa automática")
        self.auto.setChecked(True)
        self.auto.toggled.connect(lambda v: setattr(self.c, "auto_preview", v))
        lay.addWidget(self.auto)

        self.best = QtWidgets.QCheckBox("Mejor calidad")
        self.best.setChecked(True)
        self.best.toggled.connect(lambda v: self._opt("best", v))
        lay.addWidget(self.best)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("Radio de búsqueda"))
        self.search = QtWidgets.QSpinBox()
        self.search.setRange(1, 200)
        self.search.setValue(15)
        self.search.valueChanged.connect(lambda v: self._opt("search_radius", float(v)))
        row2.addWidget(self.search)
        lay.addLayout(row2)

        self.fill = QtWidgets.QCheckBox("Rellenar contornos (dibujos)")
        self.fill.setChecked(True)
        self.fill.toggled.connect(lambda v: self._opt("fill_holes", v))
        lay.addWidget(self.fill)

        self.clean = QtWidgets.QCheckBox("Limpiar islas")
        self.clean.setChecked(True)
        self.clean.toggled.connect(lambda v: setattr(self.c, "clean", v))
        lay.addWidget(self.clean)

        self.decon = QtWidgets.QCheckBox("Descontaminar borde")
        self.decon.setChecked(True)
        self.decon.toggled.connect(lambda v: self._opt("decontaminate", v))
        lay.addWidget(self.decon)

        actions = QtWidgets.QHBoxLayout()
        self.btn_do_apply = QtWidgets.QPushButton("Aplicar")
        self.btn_do_apply.clicked.connect(self.c.apply)
        self.btn_apply = QtWidgets.QPushButton("Recalcular")
        self.btn_apply.clicked.connect(self.c.compute)
        actions.addWidget(self.btn_do_apply)
        actions.addWidget(self.btn_apply)
        lay.addLayout(actions)

        actions2 = QtWidgets.QHBoxLayout()
        self.btn_restore = QtWidgets.QPushButton("Restaurar")
        self.btn_restore.clicked.connect(self.c.restore)
        self.btn_clear = QtWidgets.QPushButton("Borrar trazos")
        self.btn_clear.clicked.connect(self.c.clear)
        actions2.addWidget(self.btn_restore)
        actions2.addWidget(self.btn_clear)
        lay.addLayout(actions2)

        actions3 = QtWidgets.QHBoxLayout()
        self.btn_del = QtWidgets.QPushButton("Borrar seleccionado")
        self.btn_del.clicked.connect(self.c.delete_selected)
        actions3.addWidget(self.btn_del)
        lay.addLayout(actions3)

        self.btn_defaults = QtWidgets.QPushButton("Restablecer ajustes")
        self.btn_defaults.clicked.connect(self.c.reset_params)
        lay.addWidget(self.btn_defaults)
        lay.addLayout(actions2)

        model = default_model_path()
        self.info = QtWidgets.QLabel(f"modelo: {'ok' if model.exists() else 'falta'} — {model.name}")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addStretch(1)
        return box

    def _slider(self, lay, name, lo, hi, value):
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(name))
        s = QtWidgets.QSlider()
        s.setRange(lo, hi)
        s.setValue(value)
        s.setOrientation(orientation("Horizontal"))
        row.addWidget(s)
        lay.addLayout(row)
        if name == "Feather":
            s.valueChanged.connect(lambda v: self._opt("feather", v / 10.0))
        elif name == "Smooth":
            s.valueChanged.connect(lambda v: self._opt("smooth", max(0.1, v / 10.0)))
        elif name == "Contraste":
            s.valueChanged.connect(lambda v: self._opt("contrast", v / 100.0))
        elif name == "Desplazar borde":
            s.valueChanged.connect(lambda v: self._opt("shift", v / 100.0))
        elif name == "Peso del modelo":
            s.valueChanged.connect(lambda v: self._opt("sam_weight", float(v)))
        elif name == "Feather del trazo":
            s.valueChanged.connect(lambda v: self.c.set_selected_feather(v / 10.0))
        elif name == "Suavizar borde":
            s.valueChanged.connect(lambda v: self._opt("edge_smooth", int(v)))
        return s

    # -- acciones -------------------------------------------------------------

    def _toggle_paint(self, on: bool) -> None:
        if on and self.c.document is None:
            self.btn_paint.blockSignals(True)
            self.btn_paint.setChecked(False)
            self.btn_paint.blockSignals(False)
            self._status("abre una imagen antes de activar el pincel")
            return
        if on and not self.c.set_capture(True):
            self.btn_paint.setChecked(False)
            self._status("no encontré el lienzo")
            return
        if not on:
            self.c.set_capture(False)
        self._status("pincel activo" if on else "pincel desactivado")

    def _set_mode(self, kind: int) -> None:
        self.c.mode = kind

    def _set_brush(self, value: int) -> None:
        self.c.set_brush(float(value))
        self.c.changed()

    def _toggle_edit(self, on: bool) -> None:
        self.c.edit_mode = on
        self.c.overlay_update()
        self._status("clic sobre un trazo para seleccionarlo" if on else "edición desactivada")

    def _toggle_mask_view(self, on: bool) -> None:
        self.c.view_mask = on
        self.c.overlay_update()

    def _on_armed(self, on: bool) -> None:
        self.btn_paint.blockSignals(True)
        self.btn_paint.setChecked(on)
        self.btn_paint.blockSignals(False)

    def _sync_controls(self) -> None:
        c = self.c
        for w, v in (
            (self.brush, c.brush), (self.feather, int(c.feather * 10)),
            (self.smooth, int(c.smooth * 10)), (self.contrast, int(c.contrast * 100)),
            (self.shift, int(c.shift * 100)), (self.model_weight, int(c.sam_weight)),
            (self.search, int(c.search_radius)), (self.edge, int(c.edge_smooth)),
        ):
            w.blockSignals(True)
            w.setValue(int(round(v)))
            w.blockSignals(False)
        for w, v in (
            (self.best, c.best), (self.decon, c.decontaminate),
            (self.clean, c.clean), (self.fill, c.fill_holes),
            (self.auto, c.auto_preview), (self.edit, False), (self.view_mask, False),
        ):
            w.blockSignals(True)
            w.setChecked(bool(v))
            w.blockSignals(False)

    def _opt(self, name: str, value) -> None:
        setattr(self.c, name, value)
        self.c.changed()

    def _status(self, text: str) -> None:
        self.status.setText(text)
