import io

import docx

from app.exportar.word import tiptap_a_docx


def leer(b):
    return docx.Document(io.BytesIO(b))


def texto(t):
    return {"type": "text", "text": t}


def parrafo(*hijos):
    return {"type": "paragraph", "content": list(hijos)}


def test_encabezados_parrafos_y_marcas():
    c = {"type": "doc", "content": [
        {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "CONTRATO"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "Las partes "}, {"type": "text", "text": "acuerdan", "marks": [{"type": "bold"}]}]}]}
    d = leer(tiptap_a_docx(c, "Contrato"))
    assert d.paragraphs[0].style.name == "Heading 1" and d.paragraphs[0].text == "CONTRATO"
    assert d.paragraphs[1].text == "Las partes acuerdan" and d.paragraphs[1].runs[1].bold


def test_listas():
    c = {"type": "doc", "content": [{"type": "orderedList", "content": [
        {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Primera"}]}]}]}]}
    p = leer(tiptap_a_docx(c, "x")).paragraphs[0]
    assert p.text == "Primera" and p.style.name == "List Number"


def test_documento_vacio():
    for c in ({"type": "doc", "content": []}, {"type": "doc"}):
        assert leer(tiptap_a_docx(c, "Vacío")) is not None


def test_nodos_desconocidos_se_exportan_como_texto():
    c = {"type": "doc", "content": [{"type": "blockquote", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Cita"}]}]}, {"type": "table"}]}
    assert "Cita" in [p.text for p in leer(tiptap_a_docx(c, "x")).paragraphs]


def test_titulo_en_propiedades():
    d = leer(tiptap_a_docx({"type": "doc"}, "Mi contrato"))
    assert d.core_properties.title == "Mi contrato"


def test_lista_con_viñetas_cursiva_y_salto():
    c = {"type": "doc", "content": [{"type": "bulletList", "content": [
        {"type": "listItem", "content": [parrafo(
            texto("a"), {"type": "hardBreak"},
            {"type": "text", "text": "b", "marks": [{"type": "italic"}]})]}]}]}
    p = leer(tiptap_a_docx(c, "x")).paragraphs[0]
    assert p.style.name == "List Bullet"
    assert p.text == "a\nb"
    assert p.runs[-1].italic


def test_lista_anidada_no_falla_y_conserva_texto():
    c = {"type": "doc", "content": [{"type": "bulletList", "content": [
        {"type": "listItem", "content": [
            parrafo(texto("padre")),
            {"type": "orderedList", "content": [
                {"type": "listItem", "content": [parrafo(texto("hijo"))]}]}]}]}]}
    ps = leer(tiptap_a_docx(c, "x")).paragraphs
    assert [p.text for p in ps] == ["padre", "hijo"]


def test_nivel_de_encabezado_fuera_de_rango_o_invalido():
    for nivel in (0, 7, "x", None):
        c = {"type": "doc", "content": [
            {"type": "heading", "attrs": {"level": nivel}, "content": [texto("T")]}]}
        p = leer(tiptap_a_docx(c, "x")).paragraphs[0]
        assert p.text == "T" and p.style.name.startswith("Heading")


def test_entradas_malformadas_nunca_lanzan():
    basura = [
        {}, {"type": "doc", "content": None}, {"type": "doc", "content": "hola"},
        {"type": "doc", "content": [None, 3, "x", {"type": None}, {"content": []}]},
        {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text"}]}]},
        {"type": "doc", "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "a\x00b\x0c", "marks": ["bold", {"type": "bold"}, None]}]}]},
        {"type": "doc", "content": [{"type": "bulletList", "content": [{"type": "paragraph"}]}]},
        {"type": "doc", "content": [{"type": "horizontalRule"}, {"type": "codeBlock", "content": [texto("x = 1")]}]},
    ]
    for c in basura:
        assert leer(tiptap_a_docx(c, "T\x00")) is not None


def test_anidamiento_profundo_no_lanza():
    nodo = parrafo(texto("fondo"))
    for _ in range(3000):
        nodo = {"type": "blockquote", "content": [nodo]}
    assert leer(tiptap_a_docx({"type": "doc", "content": [nodo]}, "x")) is not None
