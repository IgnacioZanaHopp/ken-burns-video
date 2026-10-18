"""Errores de dominio que la CLI presenta sin traceback."""


class VideoError(Exception):
    """Error de configuración, medios o herramientas externas."""


class ConfigurationError(VideoError):
    """Parámetros de render inválidos."""


class MediaError(VideoError):
    """No se puede inspeccionar el audio."""


class RenderError(VideoError):
    """El render no se pudo completar."""
