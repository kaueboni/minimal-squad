---
description: 'Roda a suíte da squad ou aplica TDD a um bug (padrão Prove-It)'
argument-hint: '[descrição do bug, ou vazio para só rodar a suíte]'
---

Argumentos: $ARGUMENTS

Se vazio: rode `{{TEST_SUITE_CMD}}`{{#lint}} e `{{LINT_CMD}}`{{/lint}} e resuma
falhas com caminho:linha. Não rode `{{TEST_INTEGRATION_CMD}}`: testes de
integração só são rodados por humanos.

Se houver descrição de bug, use a skill test-driven-development no padrão
Prove-It:
1. Escreva um teste que reproduz o bug e confirme que ele FALHA.
2. Corrija com a menor mudança possível.
3. Confirme que o teste passa e rode a suíte inteira.
4. Não faça commit; mostre o diff e pare.
