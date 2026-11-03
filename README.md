# pgIndexEval

Avaliador de estratégias de indexação em PostgreSQL. Dado um banco, uma carga
de consultas (*workload*) e um conjunto de cenários de índice, a ferramenta
executa os testes de forma controlada, mede o tempo de execução com
`EXPLAIN ANALYZE`, aplica tratamento estatístico (desvio amostral, *n−1*) e
**recomenda a melhor estratégia** para aquele workload.

É o Produto Técnico-Tecnológico (PTT) derivado da dissertação sobre indexação
em PostgreSQL, do Mestrado Profissional em Governança, Tecnologia e Inovação
(MGTI/UCB).

- **Tipo CAPES:** T7 — Software/Aplicativo · **Grupo 4** · **Nível 3 (inovador)**
- **Linha de pesquisa:** Linha 2 — Tecnologia da Informação e Suporte à Decisão

## Instalação

Requer Python 3.10+ e um servidor PostgreSQL acessível.

```bash
pip install -r requirements.txt
```

## Uso

1. Copie `exemplo_config.json` e ajuste a conexão, o *workload* e os cenários.
2. Valide a configuração sem tocar no banco:

```bash
python -m pgindexeval --config exemplo_config.json --dry-run
```

3. Execute o experimento:

```bash
python -m pgindexeval --config exemplo_config.json
```

A senha pode ser informada pela variável de ambiente `PGPASSWORD`, evitando
deixá-la em texto no arquivo de configuração.

## Aplicativo web (para gestores)

Além da CLI, há uma interface web (sem instalação de frameworks) para uso por gestores:

```bash
python -m pgindexeval.webapp
```

Abre em `http://127.0.0.1:8765`. O gestor: (1) informa a conexão e lista os bancos (com a versão do servidor), (2) escolhe o banco, a tabela e a coluna de texto, (3) digita um termo de exemplo e marca as estratégias. A aplicação executa o ciclo **criar índice → medir → relatório → excluir e limpar**, exibe as três métricas e **destaca em verde o índice recomendado** (deixando claro que é uma *sugestão*). O relatório pode ser exportado em **PDF nativo** (gerado pelo servidor com reportlab). Uma segunda aba, **Simulação de carga**, projeta o comportamento com mais dados (tabela temporária escalada por um multiplicador). O botão **Encerrar aplicação** desliga o servidor local.

### Como executar (Windows)

- **Mais simples:** execute `criar_atalho.bat` uma vez. Ele cria um atalho **pgIndexEval** na área de trabalho (resolve inclusive a área de trabalho do OneDrive). Depois, dê **duplo clique no atalho**: abre o navegador na aplicação e deixa uma janela de console (o servidor) aberta.
- **Ou:** duplo clique em `run_web.bat` (mesmo efeito), ou, no terminal, `python -m pgindexeval.webapp`.
- **Para encerrar:** use o botão **Encerrar aplicação** na interface, ou feche a janela do console, ou `Ctrl+C` nela.

> A interface cria e remove índices no banco indicado. Use sempre uma cópia de testes (ex.: `bd_mestrado_ptt`); há uma confirmação obrigatória antes de executar.

## As três métricas

Para cada cenário, a ferramenta mede, como no protocolo da dissertação:

1. **Tempo de construção** — o índice é removido e recriado `repeticoes_build` vezes (padrão 3), cronometrando cada construção.
2. **Tamanho em disco** — `pg_relation_size` sobre o índice criado.
3. **Tempo de consulta** — a consulta é aquecida e executada `repeticoes_consulta` vezes (padrão 10) com `EXPLAIN (ANALYZE, BUFFERS)`, tomando o `Execution Time` do servidor; o plano de execução é capturado.

Não há cenário *baseline* sem índice: as estratégias são comparadas **entre si**. Com `enable_seqscan=false`, a ferramenta executa `SET enable_seqscan = off` para forçar o uso do índice pretendido. Um cenário cujo índice não possa ser construído (ex.: trigrama GiST sobre textos longos) é registrado como **inviável**, sem interromper os demais.

## O arquivo de configuração

| Campo | Descrição |
|---|---|
| `conexao` | parâmetros do `psycopg.connect` (host, port, dbname, user, password) |
| `repeticoes_consulta` | execuções medidas por consulta (padrão 10) |
| `repeticoes_build` | construções medidas por índice (padrão 3) |
| `descartar_aquecimento` | execuções iniciais descartadas por cache frio (padrão 1) |
| `enable_seqscan` | `false` ⇒ `SET enable_seqscan = off` antes das consultas |
| `cenarios` | lista `{id, nome, busca, indices[], preparacao[], consulta}` |
| `cenarios[].indices` | `{nome, ddl}` — `nome` é usado para medir tamanho e remover |
| `cenarios[].preparacao` | SETs antes da consulta (ex.: `SET ivfflat.probes = 10`) |
| `saida` | diretório dos artefatos de saída |

## Saídas (documentos comprobatórios do PTT)

No diretório de saída:

- `consolidado.csv` — build médio, desvio (*n−1*), disco, consulta média/desvio e plano, por cenário (estilo Tabela 5 da dissertação);
- `resultados_brutos.csv` — todas as medições individuais (reprodutibilidade);
- `grafico_consulta.svg` e `grafico_build.svg` — tempos em escala logarítmica (PNG também, se houver matplotlib);
- `relatorio.md` — síntese textual com a recomendação.

## Como funciona (resumo)

Para cada cenário: remove os índices concorrentes (para isolar o efeito), constrói
o índice do cenário medindo tempo e tamanho, mede o tempo de consulta com o cache
aquecido e `enable_seqscan=off`, captura o plano e, ao final, **remove os índices
que criou**. Depois compara as estratégias entre si.

## Segurança

A ferramenta **remove e recria índices** no banco indicado. Aponte-a sempre para
uma **cópia de testes** (ex.: `bd_mestrado_ptt`), nunca para o banco original.

## Licença

Uso acadêmico e livre no contexto do MGTI/UCB.
