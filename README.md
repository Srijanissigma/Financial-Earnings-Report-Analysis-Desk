# Financial Earnings Report Analysis Desk (Group 9)

A multi-agent system that converts company earnings reports into a one-page analyst note covering revenue, risks and outlook. Every financial claim is checked against extracted or code-derived figures.

**Technology:** Python, Microsoft Semantic Kernel (`ChatCompletionAgent`), Groq API (`openai/gpt-oss-20b`).

### **Project Members**
Member 1
| Registration No. | 12315412
| Roll No. | 19
| Name | Srijan Suresh Kumar Suman
Member 2
| Registration No. | 12313827
| Roll No. | 49
| Name | Love Garg

## 1. Architecture: Fan-Out / Fan-In with Manager

```text
             Earnings Report (.txt)
                      |
              [Extraction Agent]
                      |
             Verified FactStore
                      |
          +-----------+-----------+
          |           |           |
      [Revenue]    [Risk]     [Outlook]
      [Analyst]   [Analyst]   [Analyst]
          |           |           |
          +-----------+-----------+
                      |
               [Editor Manager]
          Grounding & Disagreement Check
                      |
              Analyst Note (.md)
```

**Why this architecture fits:** The fan-out/fan-in approach divides financial analysis into three independent tasks that can execute concurrently using `asyncio.gather`. Each analyst focuses on a specific financial area while sharing the same verified facts. The Editor Manager combines their findings, detects disagreements and validates claims before producing the final report. This improves modularity, consistency and execution efficiency.

## 2. Agent Roster and Tools

Each agent is maintained in a separate Python module inside `desk/`.

| Agent / Module | Responsibility | Tools / Capabilities |
|---|---|---|
| Extraction (`extraction_agent.py`) | Extracts financial figures and source sentences. | LLM JSON extraction, regex fallback, source verification |
| Revenue (`revenue_analyst.py`) | Analyses revenue, growth, profit and margins. | FactStore retrieval, financial analysis |
| Risk (`risk_analyst.py`) | Identifies financial and operational risks. | FactStore retrieval, risk identification |
| Outlook (`outlook_analyst.py`) | Evaluates quarterly and annual guidance. | FactStore retrieval, guidance comparison |
| Editor Manager (`editor_manager.py`) | Coordinates agents and generates the final note. | Async orchestration, grounding validation, disagreement detection |

## 3. Shared Memory, Retrieval and Grounding

- **Shared memory:** `FactStore` (`models.py`) acts as a shared blackboard containing extracted financial facts, unique IDs (F1, F2...), numerical values and their original report sentences.
- **Derived figures:** `calc.py` calculates growth rates, basis-point changes and implied guidance growth. These receive D-series IDs (D1, D2...). Arithmetic is handled by code rather than the LLM.
- **Agent retrieval:** Revenue, Risk and Outlook agents access relevant facts from the shared FactStore instead of independently extracting figures.
- **Claim validation:** `grounding.py` checks whether claims cite valid fact IDs and whether their numerical values are supported by the cited facts. Unsupported claims are rejected and counted in the run log.
- **Final evidence:** The generated analyst note includes a source table containing fact IDs, figures, values and original report sentences.

The FactStore serves as working memory for the current report analysis rather than a persistent database of historical reports.

## 4. Fallback Mechanism and Honest Failure Handling

**Model fallback:** `PREFERRED_MODELS` attempts the configured `GROQ_MODEL` (default: `openai/gpt-oss-20b`), followed by `openai/gpt-oss-120b`, with retries for API failures and rate limits.

**Rule-based fallback:** When LLM requests fail or return invalid JSON, agents can switch to deterministic rule-based processing. The execution log records the processing mode used by each agent.

**Honest failure encountered:** During testing with the real Apple Q4 FY2026 report, repeated API timeouts and connection errors affected both configured models. The application triggered its retry and fallback mechanisms, switching affected agents to offline rule-based processing. It still generated an analyst note covering revenue, risk and outlook, with zero figures rejected during source verification. However, rule-based summaries had limitations in analytical depth and consistency compared with LLM-generated output.

## 5. Testing and Execution Results

**Northwind Technologies Q3 FY2026 (Sample Report)**

- Environment and API connectivity verified successfully.
- All three analytical agents executed using LLM processing.
- Extracted and verified 21 source references and 4 derived financial metrics.
- Generated revenue, risk and outlook assessments.
- Identified disagreements between analytical agents.
- Editor summary generation used rule-based fallback.

**Apple Q4 FY2026 (Real Report)**

- Encountered repeated API timeouts and connection failures.
- Triggered model retries and offline fallback processing.
- Generated the analyst note successfully.
- Completed source verification with zero figures rejected.

**Pending Improvements:** Improve API timeout configuration, optimize prompt size, investigate provider connectivity and improve consistency between LLM and rule-based summaries.

## 6. Development Notes

- Current model: `openai/gpt-oss-20b`.
- Earlier Llama models were replaced due to model availability changes on Groq.
- Proposed Comparison Agent is not implemented in the current version.

## 7. Execution

See `StepsToRun.txt` for complete setup instructions.

```bash
# Configure GROQ_API_KEY in .env

python setup_check.py
python main.py data/Apple_Q4_FY2026_Earnings_Report.txt
```

**Project Components:** Agent modules, shared FactStore, calculation and grounding utilities, demo notebook, architecture diagram, append-only execution log and automated tests.