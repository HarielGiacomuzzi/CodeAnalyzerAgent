def find_duplicates(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j] and items[i] not in duplicates:
                duplicates.append(items[i])
    return duplicates


def build_report(rows):
    report = ""
    for row in rows:
        report = report + ",".join(str(v) for v in row) + "\n"
    return report


def count_matches(path, words):
    counts = {}
    for word in words:
        with open(path) as f:
            counts[word] = f.read().count(word)
    return counts
