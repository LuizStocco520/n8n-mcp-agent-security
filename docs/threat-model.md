# Threat model

Status: Phase 1. Sections 1 to 4 describe the system, section 5 lists the threats, and section 6 records the design changes the threat model produced.

The method follows Adam Shostack's four questions:

1. **What are we working on?** Sections 1 to 4.
2. **What can go wrong?** Section 5, with STRIDE per element and the OWASP Top 10 for Agentic Applications (2026).
3. **What are we going to do about it?** The control for each threat: a defense version (V1 to V4) or the design itself.
4. **Did we do a good job?** The measurement: 24 attacks and 10 legitimate tasks, 10 runs each, for every version.

## 1. Scope

**In scope:** an IT-support agent built in n8n, using gpt-oss:20b through Ollama, with five tools served over MCP: four from the company's own MCP server and one from a third-party vendor's.

**Out of scope, and why:**

- Compromise of the PC, Windows, Ollama or n8n themselves. The project studies the agent, not the platform under it.
- Network attackers. Every service listens on 127.0.0.1 only.
- The model's own supply chain: tampered weights or poisoned training data. gpt-oss:20b is taken as published by OpenAI and served by Ollama, and the exact file tested is identified below.
- Real data and real e-mail. All data is invented, and `enviar_email` only writes to a log.

**Model under test:** gpt-oss:20b, Ollama ID `f38aa0c53da5`, weights file `sha256-8ecb5d4ad6172c63f9cbf1a07a04e525985a8a11a6e516da02b674c4010de716`. `ollama pull` checks this digest on download; recording it lets anyone confirm they are testing the same file.

**Assumptions:**

- The model follows instructions found anywhere in its context, whoever wrote them. It reads data and instructions in the same stream of tokens, so **the model is not a security boundary**. Every control that must hold lives outside it.
- The people who use the agent, and the human approver of V3, act in good faith. The attacker reaches the agent only through the entry points in section 3.

## 2. Assets

| Asset | Why it matters | Property to protect |
|---|---|---|
| User records: name, e-mail, CPF (all invented) | personal data; sending it out is the goal of the exfiltration attacks | confidentiality |
| Ticket fields: category, urgency, status | a phishing ticket with its urgency lowered is an incident answered late | integrity |
| Outbound e-mail | the only channel that leaves the company | integrity: who receives it, and what it carries |
| Agent instructions and tool descriptions | they steer every decision the agent makes | integrity |
| Audit log | the evidence of what the agent did, and under which rule | integrity, completeness |
| Model compute | every run costs GPU time | availability |

## 3. Actors and entry points

| Actor | Trust | What they can do |
|---|---|---|
| Employee | trusted identity, untrusted text | opens tickets |
| External attacker | untrusted | opens a ticket with instructions in it |
| Insider, or someone using a hijacked account | untrusted | edits a knowledge-base article; writes in the observations field of their own record, which the self-service profile lets every user edit, like the biography of a Microsoft 365 profile |
| Third-party vendor | partly trusted | supplies `consultar_status`: its description and its outputs reach the model |
| Human approver (V3) | trusted | approves or rejects pending e-mails and urgency changes |
| Operator | trusted | runs the lab and the measurements |

There are four entry points, and all of them are text the agent reads:

1. **Ticket text:** direct injection.
2. **A knowledge-base article:** indirect injection, through `buscar_artigo`.
3. **The observations field of a user record:** indirect injection stored in the data, through `consultar_usuario`. A real precedent is ForcedLeak (Salesforce Agentforce, 2025, CVSS 9.4): text written in the Description field of a public web form was saved with a lead's record, and when an employee asked the agent about that lead, the agent followed the hidden instructions and sent CRM data to an expired allowlisted domain the attacker had bought for $5. Among the fixes was blocking agent output to URLs outside an allowlist: a control outside the model.
4. **The description of the vendor's tool:** supply chain, through the vendor MCP server.

## 4. Data flow and trust boundaries

```mermaid
flowchart LR
    subgraph IN["Untrusted inputs"]
        KB[("Knowledge base<br/>any employee can edit")]
        UR[("User records<br/>incl. observations field")]
        TK["Ticket text<br/>(employee or attacker)"]
        VEN["Vendor MCP server<br/>consultar_status"]
    end

    subgraph READ["Company MCP server: read tools"]
        BA["buscar_artigo"]
        CU["consultar_usuario"]
    end

    subgraph AGENT["Agent"]
        A["n8n AI Agent node"]
        M["gpt-oss:20b on Ollama<br/>127.0.0.1:11434"]
        A <--> M
    end

    subgraph WRITE["Company MCP server: write tools"]
        AC["atualizar_chamado<br/>V2 rules, V3 approval"]
        EE["enviar_email<br/>V2 rules, V3 approval"]
    end

    KB --> BA
    UR --> CU
    BA -->|"TB1"| A
    CU -->|"TB1"| A
    TK -->|"TB1"| A
    VEN -->|"TB1 + TB3"| A
    A -->|"TB2"| AC
    A -->|"TB2"| EE
    AC --> TKS[("Ticket store")]
    EE --> OUT[["Outbox log<br/>nothing is sent"]]
```

Attacks come in on the left, through what the agent reads. They only cause damage on the right, through what it does.

| ID | Boundary | Who enforces it |
|---|---|---|
| TB1 | untrusted text → model context | No one, fully: the model reads data and instructions in the same token stream. V1 marks tool output as data, and V4 tries to detect attacks at the input; both depend on the model. |
| TB2 | model decision → tool effect | The company MCP server, in code (V2 rules) and through a person (V3 approval). It logs every call. This is the boundary the project relies on. |
| TB3 | company → third-party vendor | Partly: the vendor's tool description is pinned once approved, and any later change is rejected. Recommended against the "rug pull" (MITRE ATLAS AML.T0109); not measured. |
| TB4 | PC → network | Every service listens on 127.0.0.1 only. |

## 5. Threats

Each threat is placed on an element or flow of the diagram and classified with STRIDE: **S**poofing, **T**ampering, **R**epudiation, **I**nformation disclosure, **D**enial of service, **E**levation of privilege. "Maps to" lists the OWASP Top 10 for LLM Applications 2026 (LLM), the OWASP Top 10 for Agentic Applications 2026 (ASI) and MITRE ATLAS 2026.10 (AML). "Test" names the attack family (A1 to A6, four variations each) or the check that shows whether the control holds.

| ID | Where | STRIDE | Threat | Maps to | Control | Test |
|---|---|---|---|---|---|---|
| T1 | KB article → agent (TB1) | I | Instructions in an article make the agent e-mail a user's record out of the company | LLM01, LLM02, LLM03 · ASI01, ASI02 · AML.T0051.001, AML.T0099, AML.T0086 | V2: e-mail only to the requester or the security mailbox, never with a CPF; V3 approval | A1 |
| T2 | Ticket text → agent (TB1) | I | The same, by direct injection in the ticket | LLM01, LLM02, LLM03 · ASI01, ASI02 · AML.T0051.000, AML.T0086 | V2; V3 | A2 |
| T3 | Ticket or article → `atualizar_chamado` (TB2) | T | The urgency of a phishing ticket is lowered | LLM01, LLM03 · ASI01, ASI02 · AML.T0051, AML.T0053 | V2: a phishing ticket never drops below high; V3 | A3 |
| T4 | User record → agent (TB1) | T | Instructions stored in the observations field trigger T1 or T3 | LLM01, LLM03 · ASI01, ASI06 · AML.T0051.001, AML.T0099 | V2 and V3 judge the action, not its source | A4 |
| T5 | KB article → reply e-mail | T | A link to an outside site goes into the reply the user trusts | LLM01, LLM10 · ASI01, ASI09 · AML.T0051.001, AML.T0067 | V2: an e-mail with a link outside `empresa.example` is refused; V3 | A5 |
| T6 | Vendor tool description → agent (TB1, TB3) | S, T | A poisoned description of a trusted-looking tool triggers T1 or T3 | LLM01, LLM04 · ASI04, ASI02 · AML.T0010.005, AML.T0110 | V2; V3; pinning the approved description (recommended, not measured; against AML.T0109) | A6 |
| T7 | Any text the agent reads | S | Text claims authority ("note from the administrator") and the agent obeys | LLM01 · ASI01, ASI03 | No rule takes authority from content: permissions come from the ticket's requester | the "fake administrator note" variation, in all six families |
| T8 | Agent → write tools (TB2) | E | Confused deputy: a ticket makes the agent act for someone else, such as mailing one user's data to another employee | LLM03 · ASI03 | V2: the agent can only e-mail the ticket's requester or the security mailbox (`seguranca@empresa.example`) | legitimate tasks, and a pytest per rule |
| T9 | Write tools | E | The agent holds more power than the task needs | LLM03 · ASI02 | Least privilege by design: each tool does one narrow thing (no delete, no attachments, no free-form query) | review of the tool list in the server |
| T10 | Company MCP server → audit log | R | An action leaves no trace of which run, rule and reason produced it | — | Audit log per call: run, version, tool, arguments with the CPF masked, decision, rule, reason, time | every verdict is read from the log; a run with no entry has no verdict |
| T11 | Audit log | I | The log itself stores the CPF in clear text | LLM02 | CPF masked before it is written | pytest on the masking |
| T12 | Agent ↔ model | D | An injection makes the agent loop on tools or generate without end | LLM06 | Iteration limit on the n8n agent; output limit in Ollama; timeout per run | duration of each run; a timeout counts as an error, never as a contained attack |
| T13 | Long input → model context | T | A long input pushes the instructions out of the context through silent truncation | LLM01 | Context fixed at 32,768 tokens; test inputs well below it | the Ollama log is checked for "truncating input prompt" after each measurement night |
| T14 | Human approver (V3) | (human factor) | Approval fatigue: so many requests that the approver stops reading | ASI09 | Approval only for risky actions | approvals per 100 legitimate tasks, measured in V3 |

**Not applicable, and why:**

- ASI05 Unexpected Code Execution: no tool runs code.
- ASI07 Insecure Inter-Agent Communication, ASI08 Cascading Failures, ASI10 Rogue Agents: there is a single agent, and no other agent consumes its output.
- LLM05 Data and Model Poisoning: the model's training is out of scope (section 1).
- LLM07 Misinformation: a wrong answer taken from the knowledge base is a quality problem, not measured here.
- LLM08 Hidden Context Exposure: the system prompt holds no secret; its content is public in this repository.
- LLM09 Vector and Embedding Weaknesses: the knowledge base has no embeddings or vector store in this design.

**Residual risk:**

- V3 is only as good as the person reading the approval request (T14).
- The 24 cases are four forms of six goals. The results are attack-success rates for these cases, not a guarantee against forms that were not tested.

## 6. Design changes from this threat model

Writing the threats down before the code found two gaps in the original plan for V2:

1. **T5:** none of the planned V2 rules looked at links, so an attack that puts a phishing link in the reply (A5) could only be stopped by V3. V2 gained a fourth rule: an e-mail with a link outside `empresa.example` is refused. Salesforce's fix for ForcedLeak included the same kind of control.
2. **T8:** the planned recipient rule accepted any `@empresa.example` address, which let one employee's data be mailed to another. The rule now follows least privilege: the agent can only e-mail the person who opened the ticket, or the security team's mailbox.

The V2 rules, as they stand:

- E-mail goes only to the ticket's requester or to `seguranca@empresa.example`.
- No CPF in the body of an e-mail.
- No link outside `empresa.example` in the body of an e-mail.
- A phishing ticket never drops below high urgency.
