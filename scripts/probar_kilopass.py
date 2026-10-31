"""Prueba de humo manual de kilopass: chat, tool calling y embeddings.

Uso: uv run python scripts/probar_kilopass.py
Códigos de salida: 0 todo bien, 1 falla chat o herramientas, 2 sin credenciales.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI  # noqa: E402

from app.config import get_settings  # noqa: E402


def probar_chat(cliente: OpenAI, modelo: str) -> bool:
    try:
        r = cliente.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": "Responde solo: hola"}],
            max_tokens=20,
        )
        if not r.choices or not (r.choices[0].message.content or "").strip():
            raise ValueError("respuesta vacía")
        print("chat OK")
        return True
    except Exception as e:
        print(f"chat FALLA: {type(e).__name__}: {e}")
        return False


def probar_herramientas(cliente: OpenAI, modelo: str) -> bool:
    herramientas = [
        {
            "type": "function",
            "function": {
                "name": "sumar",
                "description": "Suma dos enteros.",
                "parameters": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
            },
        }
    ]
    try:
        r = cliente.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": "¿Cuánto es 2 + 3? Usa la herramienta."}],
            tools=herramientas,
        )
        llamadas = r.choices[0].message.tool_calls
        if not llamadas:
            raise ValueError("el modelo no pidió ninguna herramienta")
        if llamadas[0].function.name != "sumar":
            raise ValueError(f"herramienta inesperada: {llamadas[0].function.name}")
        argumentos = json.loads(llamadas[0].function.arguments)
        if argumentos != {"a": 2, "b": 3}:
            raise ValueError(f"argumentos inesperados: {argumentos}")
        print("tool calling OK")
        return True
    except Exception as e:
        print(f"tool calling FALLA: {type(e).__name__}: {e}")
        return False


def probar_embeddings(cliente: OpenAI, modelo: str) -> None:
    if not modelo:
        print("embeddings OMITIDO (sin modelo configurado)")
        return
    try:
        r = cliente.embeddings.create(model=modelo, input=["prueba"])
        print(f"embeddings OK (dimensión {len(r.data[0].embedding)})")
    except Exception as e:
        print(f"embeddings FALLA: {type(e).__name__}: {e}")


def main() -> int:
    s = get_settings()
    if not s.kilopass_api_key or not s.kilopass_base_url:
        print("SIN CREDENCIALES")
        return 2
    cliente = OpenAI(api_key=s.kilopass_api_key, base_url=s.kilopass_base_url)
    chat_ok = probar_chat(cliente, s.kilopass_model)
    tools_ok = probar_herramientas(cliente, s.kilopass_model)
    probar_embeddings(cliente, s.kilopass_embedding_model)
    return 0 if chat_ok and tools_ok else 1


if __name__ == "__main__":
    sys.exit(main())
