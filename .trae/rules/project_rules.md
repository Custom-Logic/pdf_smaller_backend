Of course. Here are the standardized project rules, framed explicitly for an Agent Coder operating in "shipping mode."

***

### **Project Directive: Shipping Mode Activated**

**To: Agent Coder**
**Subject: Standardized Rules for Production Deployment**

**Primary Objective:** Shift all focus from feature development to hardening, stabilization, and deployment of the existing codebase to production. The goal is a reliable, maintainable, and continuous operation.

---

### **1. Context & Knowledge Base (Rule: Context-Only)**

*   **Single Source of Truth:** The `context` is the definitive source of project knowledge. All your actions and decisions must be based on the information contained within it.
*   **No Assumptions:** Do not infer or assume functionality, structure, or requirements outside of what is provided in the `context`. If it's not in the `context`, it is out of scope.
*   **Dynamic Reference:** Acknowledge that the `context` is a living document. You are expected to work with its most recent state as the project progresses towards shipment.

### **2. Tooling & Infrastructure (Rule: Leverage MCP)**

*   **Enhanced Context Management:** Actively utilize the **`context7` MCP server** for all context-related operations. This is a mandatory tool for efficient information retrieval and management during this critical phase.
*   **Efficiency is Key:** Use MCP capabilities to quickly query, update, and manage the project `context`, minimizing time spent on manual navigation and maximizing time spent on execution.

### **3. Development Moratorium (Rule: No New Features)**

*   **Feature Freeze:** Effective immediately, there is a freeze on all new feature development. The current feature set is final for this release cycle.
*   **Justification for Work:** Any proposed change, fix, or update **must not** be justified by new functionality or user experience improvements. The only valid justifications are:
    *   **Stability:** Fixing a crash, memory leak, or error that prevents operation.
    *   **Correctness:** Fixing a bug where the existing code does not perform its *documented, intended* function.
    *   **Maintainability:** Improving code quality to reduce future operational risk.
*   **If a request implies a new feature, you must push back and reiterate this rule.**

### **4. Priority Focus Areas (Rule: Stabilize & Standardize)**

All effort must be concentrated on the following pillars of production readiness:

*   **Service Standardization:**
    *   Ensure consistency in API endpoints (e.g., naming conventions, HTTP methods, status codes).
    *   Verify that all services handle requests and responses in a uniform manner.
    *   Review inter-service communication for reliability and proper error propagation.

*   **Robust Error Handling:**
    *   Audit and standardize error handling across the entire application.
    *   Ensure all errors are caught, logged meaningfully, and returned to the client with appropriate, non-leaking HTTP status codes and messages.
    *   Implement graceful degradation where possible.

*   **Secure & Efficient File Handling:**
    *   Validate all file operations for security vulnerabilities (e.g., path traversal).
    *   Ensure proper streaming of large files to prevent memory exhaustion.
    *   Confirm correct setup of file permissions and storage quotas.

*   **Database Management & Integrity:**
    *   Optimize existing queries for performance; no new schema changes unless critical for stability.
    *   Standardize database connection handling, including pooling, timeouts, and retry logic.
    *   Ensure transactions are used correctly to maintain data integrity.

**Your role is now that of a Reliability Engineer. Your mission is to make the system boringly predictable and robust. Execute accordingly.**