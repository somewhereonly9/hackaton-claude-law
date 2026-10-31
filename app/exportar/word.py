"""Conversión de documentos TipTap (JSON) a .docx con python-docx."""

import io
import re

import docx

PROFUNDIDAD_MAXIMA = 50
_CARACTERES_INVALIDOS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")
_ESTILO_LISTA = {"bulletList": "List Bullet", "orderedList": "List Number"}
_EN_LINEA = {"text", "hardBreak"}


def _limpiar(texto) -> str:
    """Quita los caracteres que XML no admite (python-docx lanzaría ValueError)."""
    return _CARACTERES_INVALIDOS.sub("", texto) if isinstance(texto, str) else ""


def _hijos(nodo) -> list:
    contenido = nodo.get("content") if isinstance(nodo, dict) else None
    return contenido if isinstance(contenido, list) else []


def _tipo(nodo):
    return nodo.get("type") if isinstance(nodo, dict) else None


def _marcas(nodo) -> set:
    marcas = nodo.get("marks")
    if not isinstance(marcas, list):
        return set()
    return {m.get("type") for m in marcas if isinstance(m, dict)}


def _escribir_en_linea(parrafo, nodos: list, profundidad: int = 0) -> None:
    if profundidad > PROFUNDIDAD_MAXIMA:
        return
    for nodo in nodos:
        tipo = _tipo(nodo)
        if tipo == "text":
            run = parrafo.add_run(_limpiar(nodo.get("text")))
            marcas = _marcas(nodo)
            if "bold" in marcas:
                run.bold = True
            if "italic" in marcas:
                run.italic = True
        elif tipo == "hardBreak":
            parrafo.add_run().add_break()
        elif nodo is not None and _hijos(nodo):
            # Nodo en línea desconocido: se conserva su texto.
            _escribir_en_linea(parrafo, _hijos(nodo), profundidad + 1)


def _nivel(nodo) -> int:
    attrs = nodo.get("attrs")
    nivel = attrs.get("level") if isinstance(attrs, dict) else None
    if isinstance(nivel, int) and not isinstance(nivel, bool):
        return min(max(nivel, 1), 3)
    return 1


def _nueva_numeracion(documento, inicio: int) -> int:
    """Crea una instancia de numeración de 'List Number' que arranca en `inicio`."""
    numeracion = documento.part.numbering_part.element
    id_estilo = documento.styles["List Number"].element.pPr.numPr.numId.val
    abstracto = numeracion.num_having_numId(id_estilo).abstractNumId.val
    num = numeracion.add_num(abstracto)
    num.add_lvlOverride(ilvl=0).add_startOverride(inicio)
    return num.numId


def _inicio(nodo) -> int:
    attrs = nodo.get("attrs")
    inicio = attrs.get("start") if isinstance(attrs, dict) else None
    if isinstance(inicio, int) and not isinstance(inicio, bool) and 0 < inicio < 2**31:
        return inicio
    return 1


def _asignar_numeracion(parrafo, num_id) -> None:
    if num_id is not None:
        num_pr = parrafo._p.get_or_add_pPr().get_or_add_numPr()
        num_pr.get_or_add_ilvl().val = 0
        num_pr.get_or_add_numId().val = num_id


def _escribir_bloques(documento, nodos: list, profundidad: int = 0, estilo_lista=None, num_id=None) -> None:
    """Recorre nodos de bloque; agrupa los nodos en línea sueltos en un párrafo."""
    if profundidad > PROFUNDIDAD_MAXIMA:
        return
    suelto = []

    def vaciar():
        if suelto:
            p = documento.add_paragraph(style=estilo_lista)
            _asignar_numeracion(p, num_id)
            _escribir_en_linea(p, suelto)
            suelto.clear()

    for nodo in nodos:
        tipo = _tipo(nodo)
        if tipo in _EN_LINEA:
            suelto.append(nodo)
            continue
        vaciar()
        if not isinstance(nodo, dict):
            continue
        if tipo == "paragraph":
            p = documento.add_paragraph(style=estilo_lista)
            _asignar_numeracion(p, num_id)
            _escribir_en_linea(p, _hijos(nodo))
        elif tipo == "heading":
            p = documento.add_paragraph(style=f"Heading {_nivel(nodo)}")
            _escribir_en_linea(p, _hijos(nodo))
        elif tipo in _ESTILO_LISTA:
            # Cada lista ordenada reinicia su numeración; las anidadas se aplanan.
            num_lista = _nueva_numeracion(documento, _inicio(nodo)) if tipo == "orderedList" else None
            for item in _hijos(nodo):
                _escribir_bloques(documento, _hijos(item), profundidad + 1, _ESTILO_LISTA[tipo], num_lista)
        else:
            _escribir_bloques(documento, _hijos(nodo), profundidad + 1, estilo_lista, num_id)
    vaciar()


def tiptap_a_docx(contenido: dict, titulo: str) -> bytes:
    """Convierte el JSON de TipTap en un .docx; nunca lanza por contenido inesperado."""
    documento = docx.Document()
    documento.core_properties.title = _limpiar(titulo)
    try:
        _escribir_bloques(documento, _hijos(contenido))
    except RecursionError:  # red de seguridad si algo supera el límite de la pila
        pass
    salida = io.BytesIO()
    documento.save(salida)
    return salida.getvalue()
