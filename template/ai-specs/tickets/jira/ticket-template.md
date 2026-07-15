# Template de ticket de Jira (para usar con `/implement`)

Copiá este esqueleto en la descripción del ticket de Jira. Está pensado como el "negativo"
de lo que pide el flujo OpenSpec: cada sección alimenta directamente un artefacto que genera
`/implement` (ver `.claude/commands/implement.md`), así los `proposal.md` / `design.md` /
`specs/` salen con menos idas y vueltas.

Cuanto más completas las secciones, mejores los artefactos. Las que no apliquen, dejalas
con "N/A" en vez de borrarlas (sirve para dejar explícito que se evaluaron).

---

## Contexto / Problema
<!-- 1-3 frases: qué problema resuelve y por qué ahora. Alimenta el "Why" del proposal. -->

## Qué se quiere (alcance)
<!-- Cambios concretos en bullets: nuevos endpoints, modificaciones, remociones.
     Marcar con **BREAKING** lo que rompa compatibilidad. Alimenta "What Changes". -->
-

## Criterios de aceptación
<!-- Condiciones verificables. Cada una se vuelve un Scenario WHEN/THEN en el spec.
     Redactá en términos de comportamiento observable, no de implementación. -->
- [ ]
- [ ]

## Fuera de alcance (Non-goals)
<!-- Lo que explícitamente NO entra en este ticket. Evita scope creep en los artefactos. -->
-

## Notas técnicas / integraciones
<!-- Endpoints y payloads de ejemplo, plataformas/módulos afectados, conexiones de DB,
     y datos de prueba concretos (ej. "usar orden 1215"). Alimenta el design. -->
-

## Dependencias / riesgos
<!-- Tickets relacionados, servicios externos, flags de config, y riesgos conocidos. -->
-

---

### Sugerencias de redacción
- Un ticket = un objetivo. Si hay varios objetivos independientes, conviene partirlo.
- Los criterios de aceptación son lo más valioso para `/implement`: se traducen casi 1:1 a
  los scenarios del `spec.md`.
- Si el ticket toca convenciones del repo (rutas, colas, jobs programados, conexiones de DB),
  mencionalo en "Notas técnicas" — el comando ancla los artefactos a `CLAUDE.md`.
