**Monitoring and Observability Requirements Meeting - Minutes**

Date: September 4, 2026
Subject: Monitoring and observability requirements for the AI applications platform (RBC Assist)
Attendees: Shivam, Emily, Ryan, Prateechi, John, Muntaser

**1. Purpose**

Define the monitoring and observability requirements for the AI applications, covering the technical architecture, the control framework (risks, controls, roles, frequency), and the operational process for review, exception handling, and escalation.

**2. Discussion**

Requirements raised by Ryan
- Controls are needed across the entire process, not at isolated points.
- The documentation must answer: where are logs stored, how are they reviewed, how are they extracted, and how can they be processed with an LLM.
- The platform must provide visibility and proof that guardrails and monitoring are in place and operating.
- Ryan shared a reference control description (section 4) as the level of specificity expected for each control.

Requirements raised by Emily
- Risks and controls must be documented alongside the architecture. Be clear about what the architecture is being built for; it should be framed in terms of the controls and roles it supports.
- Each control needs defined characteristics: frequency, owning role, exception handling, and mitigation strategy. A risk inventory should be maintained.
- Emily is escalating access with RBC through other channels.
- Emily and her team will help define the monitoring process. It should be defined by role, not by named individuals.

Risks identified (initial list)
- Prompt injection (used as the working example)
- PII exposure
- Tool use and alignment: agents must only be able to use tools in a manner consistent with compliance and security procedures
- Gaps in transparency and visibility
- Key risk identification and mitigation to be formalized in the risk inventory

Controls and monitoring capabilities discussed
- Hooks, guardrails, kill switches
- Real-time prompt injection detection
- Agentic log information and alerting
- Process monitoring
- Alert processing

Guiding principles agreed
- The first pass should be agnostic of RBC. Dependency on input from RBC should not be a blocker.
- Risk and mitigation are as important as the architecture itself.
- Sequence the work as low-hanging fruit first, larger projects later.

**3. Deliverables and action items**

1. Monitoring / observability architecture V1.
2. Key controls: design, documentation, and execution steps for each control.
3. Log management documentation: where logs will be stored, how they will be extracted and reviewed, and how that process will be automated.
4. Risk and control inventory, with the steps that can be taken to mitigate each risk.
5. Control characteristics for each control (frequency, owning role, exception handling, evidence).
6. Overall AI risk assessment: enumerate the risks seen (PII exposure, prompt injection, tool use governed by compliance and security procedures, and others).
7. Controls catalogue: hooks, guardrails, kill switches, real-time prompt injection detection, and others.
8. Monitoring / observability operating process, including accountability and ownership, defined by role. Owner: Emily and team to help define.
9. Project list for the current-to-target state transition, to decide next steps and the work required to enable monitoring and observability. Low-hanging fruit first, larger work later.
10. Options and timelines. Owner: tech team.
11. RBC access escalation through other channels. Owner: Emily.

Owners for items 1 to 7 and 9 were not assigned in the meeting.

**4. Reference: example control description (shared by Ryan)**

"On a monthly basis, designated Platform Owners or delegates review RBC Assist usage monitoring logs, including colleague prompts and system outputs, using predefined risk-based keywords and misuse indicators to identify inappropriate, non-compliant, or unauthorized prompting activity. Identified exceptions are documented in a maintained review record (e.g. Excel analysis and supporting documentation) and reviewed by a manager leveraging industry expertise to confirm escalations. Where applicable, significant issues are escalated to the appropriate governance body and remediated through corrective actions. This control ensures the accuracy, completeness, and timeliness of monitoring activities to support compliance with organizational policies and mitigate risks associated with misuse. Evidence of the control is stored in usage monitoring logs or reports, the keyword list/monitoring criteria, and documented reviews and exception tracking records maintained in the designated tracking system."

