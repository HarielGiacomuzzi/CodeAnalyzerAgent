from analyzer.stats import code_stats


def test_counts_lines_blanks_and_comments():
    code = "# header\nimport os\n\n\ndef f():\n    # inner\n    return os.sep\n"
    s = code_stats(code)
    assert s.total_lines == 7
    assert s.blank_lines == 2
    assert s.comment_lines == 2
    assert s.code_lines == 3
    assert s.max_line_length == len("    return os.sep")
    assert s.max_indent_depth == 1


def test_handles_crlf_tabs_and_c_style_comments():
    code = "int main() {\r\n\t// hi\r\n\tif (x) {\r\n\t\treturn 1;\r\n\t}\r\n}"
    s = code_stats(code)
    assert s.total_lines == 6
    assert s.comment_lines == 1
    assert s.max_indent_depth == 2


def test_single_line_without_newline():
    s = code_stats("print(1)")
    assert s.total_lines == 1
    assert s.code_lines == 1
    assert s.blank_lines == 0
