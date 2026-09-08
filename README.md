# ai-onboard

Ambiente de estudo e prática para trabalhar com LLMs. Setup reproduzível via Nix + Python.

## Ambiente

```bash
nix develop        # entra no devshell (cria/ativa .venv automaticamente)
# ou, com direnv:
direnv allow
```

Python 3.12, `pip`, `virtualenv` e `uv` já disponíveis no shell.

---

## Glossário — 20 termos essenciais de LLMs

Terminologia usada no dia a dia de quem constrói, avalia e opera aplicações com LLMs.

### Avaliação e qualidade

1. **Golden Set** — Conjunto curado de exemplos (entrada → saída esperada) tratado como
   verdade de referência. Usado para medir regressões: toda mudança de prompt, modelo ou
   pipeline é validada contra o golden set antes de ir para produção.

2. **Ground Truth** — O rótulo/resposta correta de fato para um exemplo. É a base contra a
   qual as saídas do modelo são comparadas. O golden set é, na prática, um ground truth
   curado.

3. **Eval (Evaluation)** — Rotina automatizada que roda o modelo sobre um dataset e pontua
   as respostas (exatidão, similaridade, "LLM-as-judge", etc.). Fundamental para saber se
   uma mudança melhorou ou piorou o sistema.

4. **LLM-as-a-Judge** — Usar um LLM para avaliar as saídas de outro LLM segundo critérios
   definidos (correção, tom, aderência a formato). Substitui/complementa avaliação humana
   em escala.

5. **Hallucination (Alucinação)** — Quando o modelo gera conteúdo plausível porém falso ou
   inventado. Mitigado com RAG, grounding e verificação contra fontes.

### Deploy e operação

6. **Shadow (Shadow Mode / Shadow Deployment)** — Rodar um modelo/prompt novo em paralelo
   ao de produção, recebendo tráfego real mas **sem** afetar o usuário. Serve para comparar
   comportamento e coletar métricas antes de promover a mudança.

7. **Canary / Canary Release** — Liberar a mudança para uma fração pequena de usuários
   antes do rollout total, monitorando métricas para pegar problemas cedo.

8. **A/B Testing** — Comparar duas variantes (ex.: prompt A vs prompt B) dividindo tráfego
   e medindo qual performa melhor em uma métrica de negócio.

9. **Guardrails** — Camadas de proteção que filtram/validam entradas e saídas (bloqueio de
   conteúdo tóxico, PII, jailbreaks, validação de formato/JSON, limites de tópico).

10. **Observability / Tracing** — Instrumentação que registra cada passo de uma chamada
    (prompt, tokens, latência, custo, ferramentas invocadas) para debugar e otimizar.

### Prompting e contexto

11. **System Prompt** — Instrução de alto nível que define papel, regras e comportamento do
    modelo, aplicada antes das mensagens do usuário.

12. **Few-shot / Zero-shot** — Zero-shot: pedir a tarefa sem exemplos. Few-shot: incluir
    alguns exemplos no prompt para guiar o formato e o estilo da resposta.

13. **Chain-of-Thought (CoT)** — Induzir o modelo a raciocinar passo a passo antes de
    responder, melhorando desempenho em tarefas de raciocínio.

14. **Context Window** — Quantidade máxima de tokens que o modelo processa por vez (prompt
    + resposta). Excedê-la causa truncamento ou perda de informação.

15. **Temperature** — Parâmetro de amostragem que controla aleatoriedade da saída. Baixa =
    determinística/factual; alta = criativa/variada.

### RAG e ferramentas

16. **RAG (Retrieval-Augmented Generation)** — Recuperar trechos relevantes de uma base de
    conhecimento e injetá-los no prompt para o modelo responder com base em dados atuais e
    verificáveis, reduzindo alucinação.

17. **Embedding** — Representação vetorial de texto que captura significado semântico.
    Base da busca por similaridade em RAG e de vector databases.

18. **Function / Tool Calling** — Capacidade do modelo de invocar funções/ferramentas
    externas (APIs, cálculos, buscas) retornando argumentos estruturados que o app executa.

19. **Agent** — Sistema em que o LLM planeja e executa múltiplos passos de forma autônoma,
    usando ferramentas em loop (observar → decidir → agir) até cumprir um objetivo.

20. **Fine-tuning** — Treinar adicionalmente um modelo base em dados próprios para
    especializá-lo em um domínio/estilo, alternativa ou complemento ao prompting/RAG.

---

## Padrões de integração e extensibilidade

Termos centrais no ecossistema atual de agentes e ferramentas (ex.: OpenCode, Claude):

- **MCP (Model Context Protocol)** — Protocolo aberto que padroniza como LLMs/agentes se
  conectam a fontes de dados e ferramentas externas. Um **MCP server** expõe recursos,
  ferramentas e prompts; o cliente (agente) os consome de forma uniforme, evitando
  integrações ad-hoc para cada serviço.

- **Skill** — Unidade de conhecimento/instrução especializada que o agente carrega sob
  demanda quando a tarefa combina com sua descrição. Injeta workflows e recursos
  específicos no contexto sem inflar o prompt base, mantendo o agente enxuto e capaz de
  ativar expertise só quando necessário.

- **Command (Slash Command)** — Atalho reutilizável que dispara um prompt/ação
  pré-configurada (ex.: `/review`, `/test`). Encapsula tarefas recorrentes num único
  comando, padronizando e acelerando fluxos de trabalho.
