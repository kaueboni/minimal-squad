---
description: 'Implementa tarefas com a squad (contract-tester → developer → auditor). Use "auto" para executar o plano inteiro com uma única aprovação.'
argument-hint: '[auto] [número ou nome da spec]'
---

Argumentos: $ARGUMENTS

## Modos
- `/build` — implementa a PRÓXIMA tarefa pendente e para.
- `/build auto [NNN|nome]` — gera o plano se preciso, pede UMA aprovação e
  implementa TODAS as tarefas sem parar entre elas.
O modo autônomo não pula verificação: cada tarefa continua com teste,
auditoria e commit próprio.

## Preparação (os dois modos)
1. **Spec.** Use a spec da feature em {{SPECS_DIR}}/NNN-SPEC-<nome>.md. Se os
   argumentos indicarem número ou nome, use essa. Se não indicarem e houver
   mais de uma com tarefas pendentes, pergunte qual. Se não houver nenhuma,
   pare e diga para rodar /spec primeiro. Leia sempre o {{BASE_SPEC}}: os
   Boundaries dele valem para todas as tarefas. Nunca escreva no {{BASE_SPEC}}.
2. **Base limpa.** Rode `git status --porcelain`. Se houver mudanças fora de
   {{SPECS_DIR}}/, tasks/plan.md e tasks/todo.md, pare e peça para o usuário
   commitar, guardar ou dizer o que fazer.

## Ciclo de uma tarefa
a. Se a tarefa N tem "Integração: sim" em tasks/todo.md:
   - @"contract-tester (agent)": escreva os testes de contrato da tarefa N.
   - Confirme que eles FALHAM. Se algum passar sem implementação, peça ao
     contract-tester para corrigir.
   - Guarde `git hash-object` de cada arquivo criado em tests/contract/ e
     tests/fixtures/.
   Se "Integração: não", vá para b.
b. @"developer (agent)": implemente a tarefa N.
c. @"auditor (agent)": audite a tarefa N, passando os hashes de a (se houver).
d. REPROVADO → mande ao developer só os itens crítico/importante e repita c.
   No máximo 2 rodadas; na terceira reprovação, PARE e mostre o último
   parecer. Se o developer disser que um teste de contrato está errado,
   PARE e mostre o argumento: só o usuário decide alterar o teste.
e. APROVADO → marque a tarefa como concluída em tasks/todo.md, faça
   `git add` só dos arquivos da tarefa (código, testes do developer, testes
   de contrato e fixtures da tarefa) e de tasks/todo.md, e commit
   "feat(NNN): tarefa N — <resumo>". Nunca `git add -A`. Testes de contrato
   entram no MESMO commit da implementação (sozinhos, falhando, o
   pre-commit os bloquearia).
{{#ponytail}}
   Antes do commit, se o Ponytail estiver ativo, revise só o diff desta
   tarefa; nunca corte código fora dela.
{{/ponytail}}

## /build (uma tarefa)
Execute o ciclo para a próxima tarefa pendente e pare.

## /build auto
3. **Plano.** Se não existir tasks/plan.md para esta spec, chame
   @"tech-lead (agent)" para gerar tasks/plan.md e tasks/todo.md. Se
   existirem com tarefas abertas de OUTRA spec, pare e pergunte.
4. **Única aprovação.** Mostre o plano e espere um "sim" inequívoco ("go",
   "aprovado"). Respostas vagas ("parece bom") não contam. Aprovado, faça
   um commit só de tasks/.
5. Execute o ciclo a–e para cada tarefa pendente, na ordem de dependência.
6. **Pare e pergunte** quando: a spec for ambígua; a tarefa exigir algo do
   "Ask first" do {{BASE_SPEC}} (mudança de schema ou contrato, permissão ou
   credencial nova, dependência nova, configuração de infraestrutura,
   remover código fora do escopo); ou houver algo que `git revert` não
   desfaça (escritas em sistemas externos, deploy, dados).
   Resolvido o bloqueio, o usuário roda `/build auto` de novo e você
   continua da próxima tarefa pendente.
7. **Ao final:**
   - @"auditor (agent)" sobre o conjunto
     (`git diff <commit do plano>..HEAD`);
   - atualize PROGRESS.md (Estado atual e Histórico de features);
{{#cortex}}
   - exporte a memória para revisão do time:
     `{{PYTHON}} .claude/minimal-squad/bin/export_memory.py docs/MEMORIA.md`
     (se não funcionar, avise o usuário e siga);
{{/cortex}}
   - liste os testes de integração criados e lembre o usuário de rodar
     `{{TEST_INTEGRATION_CMD}}` contra o ambiente de desenvolvimento antes
     do deploy;
{{#agentmeter}}
   - sugira `/agentmeter:tokens --sessao` para ver o custo por subagente;
{{/agentmeter}}
   - resuma: tarefas, testes, commits, pendências.
   Nunca rode testes de integração, push ou deploy.

Se algum passo falhar sem causa óbvia, siga a skill debugging-and-error-recovery.
