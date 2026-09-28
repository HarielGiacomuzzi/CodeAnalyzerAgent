Lab 02: Code Analyzer Agent
Objective
Build a code analysis agent that uses LLM to analyze code files and provide structured feedback.

Time Allotted: 1 hour 15 minutes

Learning Goals
Create effective system prompts for code analysis
Implement structured output extraction
Build a simple agent with tool-use
Deploy to Railway/Vercel
What You'll Build
An API service that:

Accepts code via API
Analyzes it using an LLM
Returns structured JSON with issues and suggestions
┌─────────────────────────────────────────────────────────────┐
│ Code Analyzer Flow │
├─────────────────────────────────────────────────────────────┤
│ │
│ POST /analyze │
│ ├── Input: {"code": "...", "language": "python"} │
│ │ │
│ ├── [System Prompt + Code] → LLM │
│ │ │
│ └── Output: { │
│ "summary": "Brief overview", │
│ "issues": [ │
│ {"severity": "high", "line": 5, "issue": "..."} │
│ ], │
│ "suggestions": ["..."], │
│ "metrics": {"complexity": "medium", ...} │
│ } │
│ │
└─────────────────────────────────────────────────────────────┘
Requirements
Core Functionality
POST /analyze endpoint accepting {"code": "...", "language": "python"}
System prompt that instructs the LLM how to analyze code
Structured JSON output with:
Summary: 2-3 sentence overview
Issues: severity, line number, category (bug/security/performance/style/maintainability), description, suggestion
Suggestions: general improvements
Metrics: complexity, readability, test coverage estimate
Data validation using Pydantic (Python) or Zod (TypeScript)
LLM client abstraction (support at least one provider)
Health check endpoint
Frontend Requirements
Web interface where users can paste or upload code
Language selector dropdown
"Analyze" button with loading state
Results panel showing: summary, issues list (color-coded by severity), suggestions, metrics
Responsive design
Language Choice
Aspect Python TypeScript
Framework FastAPI Hono
Validation Pydantic Zod
Run uvicorn main:app --reload npm run dev
Deploy Railway Vercel / Railway
Deliverables
Working code analyzer API (Python OR TypeScript)
Custom system prompt for analysis
Structured JSON output
At least 2 analysis types (general + security OR performance)
Deployed to Railway/Vercel
Tested with sample code
Web frontend with code input and analysis results display
Application deployed to Vercel/Railway/Render (provide URL)
Extension Challenges
Multi-file Analysis: Accept multiple files and analyze relationships
Diff Analysis: Analyze code changes between two versions
Language Detection: Auto-detect programming language
Caching: Cache results for identical code
