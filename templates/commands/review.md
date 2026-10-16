---
description: 'Revisão completa da branch atual pelo auditor, em cinco eixos, contra spec e Boundaries'
argument-hint: '[branch base, padrão main]'
---

Base: $ARGUMENTS (se vazio, use `main`; se não existir, `master`).

1. Calcule o diff da branch: `git diff $(git merge-base HEAD <base>)..HEAD`.
2. Chame @"auditor (agent)" sobre esse diff completo, pedindo, além da
   checklist dele, uma revisão nos cinco eixos da skill
   code-review-and-quality: correção, legibilidade, arquitetura,
   segurança e performance.
3. Mostre o parecer agrupado em crítico, importante e sugestão, com
   caminho:linha. Não corrija nada: só reporte.
