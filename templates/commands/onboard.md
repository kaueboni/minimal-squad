---
description: 'Situa um dev novo no projeto — o que é, estado atual, como rodar e próximos passos'
---

1. Rode `git log --oneline -20` e guarde o resultado.
2. Chame @"discovery (agent)" em modo onboarding, passando o git log, e
   peça: o que o app faz ({{INSTRUCTIONS_FILE}}, {{BASE_SPEC}}); estado e histórico
   (PROGRESS.md, últimas specs em {{SPECS_DIR}}/, tasks/todo.md); mapa do
   código e das integrações externas lidas e escritas.
3. Mostre ao usuário:
   - resumo do projeto em 5 linhas;
   - feature em andamento e próxima tarefa pendente;
   - checklist de setup da seção "Setup para um novo dev" do PROGRESS.md,
     marcando o que já parece configurado nesta máquina
     (`git config core.hooksPath`{{#rtk}}, `rtk --version`{{/rtk}});
{{#cortex}}
   - se docs/MEMORIA.md existir, as decisões vigentes mais importantes;
{{/cortex}}
   - como trabalhar aqui: /spec → /build auto NNN → /review.
Não edite nada.
