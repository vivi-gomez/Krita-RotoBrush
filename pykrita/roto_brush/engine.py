"""Envoltorio ctypes del motor Rust."""

import ctypes
from array import array
from pathlib import Path

FG, BG, REFINE, REFINE_ERASE = 0, 1, 2, 3

CLASSIC, MODEL, SAM = 0, 1, 2


class Params(ctypes.Structure):
    _fields_ = [
        ("engine", ctypes.c_int),
        ("best", ctypes.c_int),
        ("feather", ctypes.c_float),
        ("smooth", ctypes.c_float),
        ("shift", ctypes.c_float),
        ("contrast", ctypes.c_float),
        ("decontaminate", ctypes.c_int),
        ("bgra", ctypes.c_int),
        ("sam_weight", ctypes.c_float),
        ("search_radius", ctypes.c_float),
        ("clean", ctypes.c_int),
        ("fill_holes", ctypes.c_int),
        ("prior", ctypes.c_char_p),
        ("prior_len", ctypes.c_size_t),
        ("prior_weight", ctypes.c_float),
        ("edge_smooth", ctypes.c_int),
    ]


class Engine:
    def __init__(self, lib_path: Path):
        self.lib = ctypes.CDLL(str(lib_path))
        self.lib.rb_model_load.restype = ctypes.c_void_p
        self.lib.rb_model_load.argtypes = [ctypes.c_char_p]
        self.lib.rb_model_free.argtypes = [ctypes.c_void_p]
        self.lib.rb_gray_mask.argtypes = [
            ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_char_p,
        ]
        self.lib.rb_dim_mask.argtypes = [
            ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_char_p,
            ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ubyte,
        ]
        self.lib.rb_render.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.POINTER(Params),
            ctypes.c_char_p,
            ctypes.c_size_t,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        self._model = None

    def load_model(self, path: Path) -> bool:
        if self._model:
            self.lib.rb_model_free(self._model)
            self._model = None
        self._model = self.lib.rb_model_load(str(path).encode("utf-8"))
        return bool(self._model)

    @property
    def has_model(self) -> bool:
        return bool(self._model)

    def dim_mask(self, alpha: bytes, w: int, h: int) -> bytes:
        """RGBA de atenuación para pintar la vista previa sobre el lienzo."""
        out = ctypes.create_string_buffer(w * h * 4)
        rc = self.lib.rb_dim_mask(alpha, w, h, out, 20, 20, 20, 150)
        if rc != 0:
            raise RuntimeError("no se pudo preparar la vista previa")
        return out.raw

    def gray_mask(self, alpha: bytes, w: int, h: int) -> bytes:
        """Máscara en escala de grises (blanco = objeto, negro = fondo)."""
        out = ctypes.create_string_buffer(w * h * 4)
        rc = self.lib.rb_gray_mask(alpha, w, h, out)
        if rc != 0:
            raise RuntimeError("no se pudo preparar la máscara")
        return out.raw

    def render(self, rgba: bytes, w: int, h: int, strokes, params: Params) -> bytes:
        """Devuelve el alfa (w*h bytes). Lanza RuntimeError con el mensaje del motor."""
        data = array("f")
        for kind, radius, points, feather in strokes:
            data.append(float(kind))
            data.append(float(radius))
            data.append(float(feather))
            data.append(float(len(points)))
            for x, y in points:
                data.append(float(x))
                data.append(float(y))
        buf = (ctypes.c_float * len(data))(*data) if data else (ctypes.c_float * 1)()
        out = ctypes.create_string_buffer(w * h)
        err = ctypes.create_string_buffer(512)
        rc = self.lib.rb_render(
            self._model,
            rgba,
            w,
            h,
            buf,
            len(data),
            ctypes.byref(params),
            out,
            w * h,
            err,
            512,
        )
        if rc != 0:
            raise RuntimeError(err.value.decode("utf-8", "replace") or "fallo del motor")
        return out.raw
