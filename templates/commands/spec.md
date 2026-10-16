---
description: 'Especifica uma feature com a squad (discovery{{#researcher}} → researcher{{/researcher}} → tech-lead) e para para aprovação'
argument-hint: '<descrição da feature>'
---

Pedido do usuário: $ARGUMENTS

Se o pedido estiver vazio, pergunte o que deve ser especificado e pare.

Orquestre a squad, nesta ordem, chamando cada agente com @:

1. @"discovery (agent)": mapeie o projeto para o pedido acima. Passe só o
   pedido do usuário.
{{#researcher}}
2. Se o discovery listou itens "a confirmar na documentação", chame
   @"researcher (agent)" só com essas perguntas, em termos genéricos (sem
   nomes internos nem código). Se não listou, pule.
{{/researcher}}
3. @"tech-lead (agent)": escreva a spec da feature em {{SPECS_DIR}}/. Passe
   o pedido e os resumos do discovery{{#researcher}} e do researcher{{/researcher}}.
4. Mostre ao usuário: caminho da spec, resumo em até 10 linhas, a seção
   "Impacto em integrações" e as Open Questions.
5. Peça aprovação e PARE. Não planeje nem implemente neste turno.

Nunca escreva em {{BASE_SPEC}}. Open Questions precisam de resposta antes
da aprovação.
{{#ponytail}}
O Ponytail não deve encurtar a spec: clareza vale mais que concisão aqui.
{{/ponytail}}
