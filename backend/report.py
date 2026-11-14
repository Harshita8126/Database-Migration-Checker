"""
Analysis Report Generator & Graphviz Flowchart Definitions.


Generates:
1. Executive Markdown Summary Report.
2. JSON Report.
3. Graphviz DOT for Architecture Pipeline (Independent AST & Metadata branches).
4. Graphviz DOT for Rule-Based Decision Flowchart.
"""

from typing import Dict, Any, List
import json
from backend.risk_engine import AnalysisResult


def generate_pipeline_dot() -> str:
    """
    Generates Graphviz DOT code for the application workflow.
    Represents SQL Parsing (pglast) and DB Metadata Extraction (psycopg3)
    as independent parallel branches feeding into the Rule-Based Safety Engine.
    Matches the pre-deployment architecture pipeline.
    """
    return """digraph MigrationPipeline {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, margin="0.2,0.1"];
    edge [fontname="Helvetica", fontsize=10, color="#4B5563"];

    // Upload Node
    upload [label="SQL File Upload\\n(.sql migration)", fillcolor="#EFF6FF", color="#3B82F6", penwidth=2];

    // Parallel Branch 1: AST Parsing
    subgraph cluster_ast {
        label = "Static Analysis Branch (pglast)";
        style = dashed;
        color = "#60A5FA";
        fontcolor = "#1D4ED8";
        pglast_parse [label="SQL Parsing\\n(pglast AST)", fillcolor="#DBEAFE", color="#2563EB"];
        ast_extract [label="Extract Operations,\\nTables, Columns & Lines", fillcolor="#DBEAFE", color="#2563EB"];
    }

    // Parallel Branch 2: Database Metadata
    subgraph cluster_meta {
        label = "Database-Aware Branch (psycopg3)";
        style = dashed;
        color = "#34D399";
        fontcolor = "#047857";
        db_connect [label="PostgreSQL Connection\\n(psycopg3 read-only)", fillcolor="#D1FAE5", color="#059669"];
        meta_fetch [label="Fetch Catalogs\\n(pg_stat, pg_class, locks)", fillcolor="#D1FAE5", color="#059669"];
    }

    // Join Node
    combine [label="Combine AST &\\nTable Metadata", fillcolor="#FEF3C7", color="#D97706", penwidth=2];

    // Engine & Output
    risk_engine [label="Rule-Based Risk\\nAssessment Engine", fillcolor="#FEE2E2", color="#DC2626", penwidth=2];
    safe_sql [label="Safe SQL Generator\\n(CONCURRENTLY, NOT VALID)", fillcolor="#EDE9FE", color="#7C3AED"];
    final_report [label="Final Safety Report\\n(Metrics, Diff, Plotly)", fillcolor="#E0E7FF", color="#4338CA", penwidth=2];

    // Pipeline Connections
    upload -> pglast_parse;
    upload -> db_connect;

    pglast_parse -> ast_extract;
    db_connect -> meta_fetch;

    ast_extract -> combine [label="Parsed AST"];
    meta_fetch -> combine [label="Live Row Counts\\n& Table Size"];

    combine -> risk_engine;
    risk_engine -> safe_sql [label="Flagged Issues"];
    safe_sql -> final_report;
    risk_engine -> final_report [label="Risk Score"];
}"""


def generate_decision_tree_dot() -> str:
    """
    Generates Graphviz DOT code illustrating rule decision pathways
    for a statement (e.g. CREATE INDEX, ALTER TABLE, UPDATE).
    """
    return """digraph RuleDecisionTree {
    rankdir=TD;
    node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, margin="0.15,0.1"];
    edge [fontname="Helvetica", fontsize=10, color="#374151"];

    stmt [label="Incoming SQL Statement", fillcolor="#F3F4F6", color="#9CA3AF"];
    check_type [label="Operation Type?", shape=diamond, fillcolor="#FEF3C7", color="#D97706"];

    // CREATE INDEX path
    idx_check [label="CREATE INDEX\\ndetected", fillcolor="#DBEAFE", color="#2563EB"];
    is_conc [label="CONCURRENTLY\\npresent?", shape=diamond, fillcolor="#FEF3C7", color="#D97706"];
    idx_safe [label="Safe: Reads & writes\\nremain active", fillcolor="#D1FAE5", color="#059669"];
    check_size [label="Table size > 50MB\\nor rows > 100K?", shape=diamond, fillcolor="#FEE2E2", color="#DC2626"];
    idx_high [label="Severity: HIGH\\nWrite downtime outage risk", fillcolor="#FEE2E2", color="#DC2626"];
    idx_med [label="Severity: MEDIUM\\nBlocks writes on small table", fillcolor="#FFEDD5", color="#EA580C"];

    // ALTER TABLE path
    alt_check [label="ALTER TABLE\\ndetected", fillcolor="#DBEAFE", color="#2563EB"];
    alt_cmd [label="Command Subtype?", shape=diamond, fillcolor="#FEF3C7", color="#D97706"];
    alt_not_null [label="SET NOT NULL:\\nFlag Full Table Scan\\nSuggest CHECK NOT VALID", fillcolor="#FEE2E2", color="#DC2626"];
    alt_fk [label="ADD FOREIGN KEY:\\nCheck NOT VALID flag\\nSuggest 2-phase validation", fillcolor="#FFEDD5", color="#EA580C"];
    alt_type [label="ALTER COLUMN TYPE:\\nTable rewrite check\\nSuggest Expand-Contract", fillcolor="#FEE2E2", color="#DC2626"];

    // UPDATE path
    upd_check [label="UPDATE\\ndetected", fillcolor="#DBEAFE", color="#2563EB"];
    upd_where [label="WHERE clause\\npresent?", shape=diamond, fillcolor="#FEF3C7", color="#D97706"];
    upd_high [label="Severity: HIGH\\nUnbounded WAL & lock bloat\\nSuggest keyset batching", fillcolor="#FEE2E2", color="#DC2626"];
    upd_ok [label="Targeted UPDATE\\nPassed check", fillcolor="#D1FAE5", color="#059669"];

    // Tree connections
    stmt -> check_type;
    check_type -> idx_check [label="CREATE INDEX"];
    check_type -> alt_check [label="ALTER TABLE"];
    check_type -> upd_check [label="UPDATE"];

    idx_check -> is_conc;
    is_conc -> idx_safe [label="Yes"];
    is_conc -> check_size [label="No"];
    check_size -> idx_high [label="Yes (Prod scale)"];
    check_size -> idx_med [label="No (Dev scale)"];

    alt_check -> alt_cmd;
    alt_cmd -> alt_not_null [label="SET NOT NULL"];
    alt_cmd -> alt_fk [label="ADD FOREIGN KEY"];
    alt_cmd -> alt_type [label="ALTER COLUMN TYPE"];

    upd_check -> upd_where;
    upd_where -> upd_high [label="No (Unbounded)"];
    upd_where -> upd_ok [label="Yes (Bounded)"];
}"""


def build_markdown_report(result: AnalysisResult, db_version_str: str = "PostgreSQL 16.2") -> str:
    """Generates a comprehensive Markdown report of migration safety analysis."""
    summary = result.summary
    if not summary:
        return "# Migration Analysis Failed\n\nNo summary available."

    risk_badge = {
        "HIGH": "[HIGH RISK]",
        "MEDIUM": "[MEDIUM RISK]",
        "LOW": "[LOW RISK]",
    }.get(summary.overall_risk, summary.overall_risk)

    lines = [
        "# PostgreSQL Migration Safety Report",
        "Generated by PostgreSQL Migration Safety Checker\n",
        "### Executive Summary",
        f"- **Overall Risk Level**: {risk_badge}",
        f"- **Analysis Mode**: `{summary.analysis_mode.replace('_', ' ').title()}`",
        f"- **Total SQL Statements**: `{summary.total_statements}`",
        f"- **Total Issues Detected**: `{summary.total_issues}`",
        f"  - High Severity: `{summary.high_count}`",
        f"  - Medium Severity: `{summary.medium_count}`",
        f"  - Low Severity: `{summary.low_count}`",
        f"- **lock_timeout Configured**: `{'Configured' if summary.has_lock_timeout else 'Missing (Vulnerable to lock queues)'}`",
        f"- **PostgreSQL Target Engine**: `{db_version_str}`\n",
        "---",
        "### Database & Table Metadata",
    ]

    if result.metadata:
        lines.append("| Table Name | Schema | Estimated Rows | Total Table Size | Source |")
        lines.append("|---|---|---|---|---|")
        for tbl, m in result.metadata.items():
            lines.append(
                f"| `{tbl}` | `{m.get('schema_name', 'public')}` | {m.get('estimated_rows', 0):,} | {m.get('total_size_pretty', '0 kB')} | `{m.get('source', 'live_db')}` |"
            )
        lines.append("")
    else:
        lines.append("*Static analysis mode: No live database metadata was connected. Estimates are based on general PostgreSQL locking rules.*\n")

    lines.append("---")
    lines.append("### Detected Safety Issues")

    if not result.issues:
        lines.append("All SQL statements comply with zero-downtime PostgreSQL deployment rules. No hazards detected.")
    else:
        for idx, issue in enumerate(result.issues, start=1):
            sev = issue.get("severity", "INFO")
            lines.append(f"#### {idx}. [{sev}] {issue.get('rule_name')}")
            lines.append(f"- **Target Table**: `{issue.get('table') or 'Global / Session'}`")
            lines.append(f"- **Line Number**: `Line {issue.get('line_number', 1)}`")
            lines.append(f"- **Lock Type**: `{issue.get('lock_level', 'ACCESS EXCLUSIVE')}`")
            lines.append(f"- **Root Cause**: {issue.get('reason')}")
            lines.append(f"- **Production Impact**: {issue.get('impact')}")
            lines.append(f"- **Safe Fix**: {issue.get('suggestion')}")
            if issue.get("doc_url"):
                lines.append(f"- **Documentation**: [PostgreSQL Official Reference]({issue.get('doc_url')})")
            lines.append("\n**Original SQL:**")
            lines.append(f"```sql\n{issue.get('original_sql', '').strip()}\n```")
            lines.append("**Safer SQL Alternative:**")
            lines.append(f"```sql\n{issue.get('safe_sql', '').strip()}\n```\n")

        lines.append("---")
        lines.append("### Recommended Deployment Guidelines")
        lines.append("1. **Lock Timeouts**: Configure `SET lock_timeout = '3s';` before executing DDL.")
        lines.append("2. **Concurrently Build Indexes**: Use `CREATE INDEX CONCURRENTLY` to avoid blocking writes.")
        lines.append("3. **Two-Phase Constraints**: Enforce `NOT VALID` on creation, followed by `VALIDATE CONSTRAINT`.")
        lines.append("4. **Batch Data Backfills**: Update large tables in bounded chunks of 2,000–5,000 rows.")
        lines.append("5. **Expand-Contract Architecture**: Prefer multi-phase column migration over raw `ALTER COLUMN TYPE`.")

    return "\n".join(lines)


def build_json_report(result: AnalysisResult, db_version_str: str = "PostgreSQL 16.2") -> str:
    """Builds a formatted JSON string of the complete analysis report."""
    data = result.to_dict()
    data["db_version"] = db_version_str
    data["project"] = "PostgreSQL Database Migration Safety Checker"
    return json.dumps(data, indent=2)
