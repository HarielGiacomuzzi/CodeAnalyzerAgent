from analyzer.models import CodeStats

# ponytail: prefix heuristic covers #, //, /* */ and -- comments; a real parser per language if accuracy matters
COMMENT_PREFIXES = ("#", "//", "/*", "*", "--")


def code_stats(code: str) -> CodeStats:
    """Deterministic size/shape metrics. Exposed to the LLM as the get_code_stats tool."""
    lines = [line.expandtabs(4) for line in code.splitlines()]
    non_blank = [line for line in lines if line.strip()]
    comments = sum(1 for line in non_blank if line.lstrip().startswith(COMMENT_PREFIXES))
    indents = [len(line) - len(line.lstrip()) for line in non_blank]
    return CodeStats(
        total_lines=len(lines),
        code_lines=len(non_blank) - comments,
        blank_lines=len(lines) - len(non_blank),
        comment_lines=comments,
        max_line_length=max((len(line) for line in lines), default=0),
        max_indent_depth=max(indents, default=0) // 4,
    )
