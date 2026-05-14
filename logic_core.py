import random


# Inclusive operand bounds for generated math problems.
PROBLEM_OPERAND_MIN = 0
PROBLEM_OPERAND_MAX = 12


def build_problem(a, b, operator):
    if operator == "+":
        answer = a + b
    elif operator == "-":
        answer = a - b
    else:
        answer = a * b

    if operator == "*":
        offsets = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    else:
        offsets = [1, 2, 3, 4]

    candidates = []
    for offset in offsets:
        candidates.append(answer + offset)
        candidates.append(answer - offset)
    for i in range(len(candidates) - 1, 0, -1):
        j = random.randrange(i + 1)
        candidates[i], candidates[j] = candidates[j], candidates[i]

    choices = [answer]
    for candidate in candidates:
        if candidate not in choices:
            choices.append(candidate)
            if len(choices) == 4:
                break

    return (a, b, choices[0], choices[1], choices[2], choices[3])


def _operand_range(min_operand=None, max_operand=None):
    if min_operand is None:
        min_operand = PROBLEM_OPERAND_MIN
    if max_operand is None:
        max_operand = PROBLEM_OPERAND_MAX
    if min_operand > max_operand:
        min_operand, max_operand = max_operand, min_operand
    return min_operand, max_operand


def problem_pool_size(operator, min_operand=None, max_operand=None):
    min_operand, max_operand = _operand_range(min_operand, max_operand)
    span = (max_operand - min_operand) + 1
    if operator == "-":
        return (span * (span + 1)) // 2
    return span * span


def build_problem_set(operator, count=None, min_operand=None, max_operand=None):
    min_operand, max_operand = _operand_range(min_operand, max_operand)
    pairs = []
    if operator == "-":
        for left in range(min_operand, max_operand + 1):
            for right in range(min_operand, left + 1):
                pairs.append((left, right))
    else:
        for left in range(min_operand, max_operand + 1):
            for right in range(min_operand, max_operand + 1):
                pairs.append((left, right))

    if count is None or count > len(pairs):
        count = len(pairs)

    problems = []
    for pair in pairs[:count]:
        problems.append(build_problem(pair[0], pair[1], operator))
    return problems


def tag_problem_set(problem_set, operator_symbol):
    tagged_problems = []
    for problem in problem_set:
        tagged_problems.append(problem + (operator_symbol,))
    return tagged_problems


def parse_score_line(line):
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 6:
        return None
    try:
        pct_text = parts[5].replace("%", "")
        timestamp_text = ""
        entry_mode = "mc"  # Default for legacy lines
        if len(parts) >= 7:
            timestamp_text = parts[6]
        if len(parts) >= 8:
            entry_mode = parts[7].lower()
        return {
            "player": parts[0],
            "type": parts[1],
            "nbr_q": int(parts[2]),
            "nbr_skipped": int(parts[3]),
            "avg_time": float(parts[4]),
            "pct_correct": float(pct_text),
            "timestamp": timestamp_text,
            "entry_mode": entry_mode,
        }
    except (ValueError, IndexError):
        return None


def category_time_bounds(score_entries, game_type, min_avg_time, max_avg_time):
    category_entries = []
    for entry in score_entries:
        if entry["type"] == game_type:
            category_entries.append(entry)

    if len(category_entries) == 0:
        return min_avg_time, max_avg_time

    if len(category_entries) == 1:
        return min_avg_time, category_entries[0]["avg_time"]

    min_time = category_entries[0]["avg_time"]
    max_time = min_time
    for entry in category_entries[1:]:
        value = entry["avg_time"]
        if value < min_time:
            min_time = value
        if value > max_time:
            max_time = value
    return min_time, max_time


def normalized_time_score(avg_time_value, min_time, max_time):
    low = min(min_time, max_time)
    high = max(min_time, max_time)
    if high <= low:
        return 1.0
    normalized = (high - avg_time_value) / (high - low)
    if normalized < 0.0:
        return 0.0
    if normalized > 1.0:
        return 1.0
    return normalized


def composite_score(percent_correct, avg_time_value, min_time, max_time, accuracy_weighting, time_weighting):
    accuracy_score = percent_correct / 100.0
    time_score = normalized_time_score(avg_time_value, min_time, max_time)
    weighted_score = (accuracy_score * accuracy_weighting) + (time_score * time_weighting)
    if weighted_score < 0.0:
        return 0.0
    if weighted_score > 1.0:
        return 1.0
    return weighted_score


def format_score_timestamp(dt):
    return "{:04d}{:02d}{:02d}_{:02d}{:02d}".format(
        dt[0],
        dt[1],
        dt[2],
        dt[3],
        dt[4],
    )
