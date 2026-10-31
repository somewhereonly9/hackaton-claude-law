# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado del proyecto

El repositorio está vacío: todavía no hay código, dependencias ni comandos de build/test. El nombre del proyecto (`hackatonclaudelaw`) sugiere un hackatón con temática legal, pero la idea concreta aún no está definida.

## Dirección técnica tentativa (sin confirmar)

- **Lenguaje:** probablemente Python.
- **IA:** posible uso de RAG (Retrieval-Augmented Generation) sobre modelos de lenguaje; si se usan modelos de Claude, preferir la familia más reciente.
- **Base de datos:** probablemente MySQL.

Nada de lo anterior está decidido. Confirma con el usuario antes de fijar frameworks, estructura de carpetas o proveedores.

## Mantenimiento de este archivo

Cuando exista código, actualiza este archivo con:
- Comandos reales para instalar dependencias, ejecutar la app, lint y tests (incluido cómo correr un solo test).
- La arquitectura de alto nivel (p. ej. flujo de ingesta → embeddings → recuperación → generación, y cómo se integra MySQL).
