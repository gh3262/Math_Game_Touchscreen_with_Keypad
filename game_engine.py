"""Incremental pure transition helpers for mode-selection flow.

This module intentionally avoids hardware/display dependencies.
"""


def _event_result(intent, state, data=None):
    return {"intent": intent, "state": state, "data": data}


def route_pressed_action(role, mode_select_active=False, game_started=False):
    if role == "quit":
        return "handle_quit"
    if role == "next":
        return "handle_next"
    if role == "name_entry":
        return "handle_name_entry"
    if role == "kb_entry" and game_started:
        return "handle_kb_entry"
    if role == "answer" and mode_select_active:
        return "handle_mode_select_answer"
    if role == "answer" and game_started:
        return "handle_game_answer"
    return "ignore"


def route_debounced_press(pressed_exists, matches_last_pressed, pending_press_count, debounce_press_count):
    return pressed_exists and (not matches_last_pressed) and pending_press_count >= debounce_press_count


def route_no_touch_state(touch_release_required, has_last_pressed, no_touch_count, touch_release_idle_count):
    next_no_touch_count = no_touch_count + 1
    clear_last_pressed = has_last_pressed and next_no_touch_count >= touch_release_idle_count
    return touch_release_required, next_no_touch_count, clear_last_pressed


def route_pending_press_state(has_pressed, is_same_as_pending, pending_press_count):
    if not has_pressed:
        return 0, True, False
    if is_same_as_pending:
        return pending_press_count + 1, False, False
    return 1, False, True


def route_touch_cycle_state(touch_exists, touch_release_required):
    if not touch_exists:
        return "handle_no_touch"
    return "wait_for_touch_release" if touch_release_required else "process_touch"


def choose_player_name_action(choice_text, selectable_player_names):
    if choice_text == "More":
        return "advance_page", ""
    if choice_text == "NEW":
        return "show_name_entry", ""
    if choice_text not in selectable_player_names:
        return "ignore", ""
    return "select_player", choice_text


def choose_problem_type_state(choice_text):
    if choice_text in ("Add", "Addition"):
        return {
            "question_bank": "addition",
            "operator_symbol": "+",
            "game_type": "Addition",
            "title": "Addition",
        }
    if choice_text in ("Subtract", "Subtraction"):
        return {
            "question_bank": "subtraction",
            "operator_symbol": "-",
            "game_type": "Subtraction",
            "title": "Subtraction",
        }
    if choice_text in ("Multiply", "Multiplication"):
        return {
            "question_bank": "multiplication",
            "operator_symbol": "*",
            "game_type": "Multiplication",
            "title": "Multiply",
        }
    if choice_text == "Mixed":
        return {
            "question_bank": "mixed",
            "operator_symbol": "+",
            "game_type": "Mixed",
            "title": "Mixed",
        }
    return None


def choose_problem_count_value(choice_text):
    if choice_text in ("10", "20", "35", "50"):
        return int(choice_text)
    return None


def initial_mode_select_state(
    selecting_score_name=False,
    selecting_problem_count=False,
    selecting_entry_type=False,
    current_game_type="Addition",
    current_operator_symbol="+",
    problem_count_target=10,
    current_player_name="",
):
    return {
        "selecting_score_name": selecting_score_name,
        "selecting_problem_count": selecting_problem_count,
        "selecting_entry_type": selecting_entry_type,
        "current_game_type": current_game_type,
        "current_operator_symbol": current_operator_symbol,
        "problem_count_target": problem_count_target,
        "current_player_name": current_player_name,
    }


def handle_mode_select_event(state, event_type, value=None, selectable_player_names=None):
    next_state = dict(state)

    if event_type == "answer_pressed_mode_select":
        if state.get("selecting_score_name", False):
            return _event_result("choose_player_name", next_state)
        if state.get("selecting_entry_type", False):
            return _event_result("choose_entry_type", next_state)
        if state.get("selecting_problem_count", False):
            return _event_result("choose_problem_count", next_state)
        return _event_result("choose_problem_type", next_state)

    if event_type == "next_pressed_mode_select":
        if state.get("selecting_score_name", False):
            return _event_result("show_title_screen", next_state)
        return _event_result("ignore", next_state)

    if event_type == "quit_pressed_mode_select":
        if state.get("selecting_score_name", False):
            return _event_result("prompt_choose_player", next_state)
        return _event_result("show_name_choices", next_state)

    if event_type == "player_name_choice":
        action, selected_name = choose_player_name_action(value, selectable_player_names or ())
        if action == "select_player":
            next_state["current_player_name"] = selected_name
            next_state["selecting_score_name"] = False
            next_state["selecting_entry_type"] = True
        return _event_result(action, next_state)

    if event_type == "entry_type_choice":
        if value not in ("Choice", "Keys", "TT"):
            return _event_result("ignore", next_state)

        next_state["selecting_entry_type"] = False
        if value == "TT":
            next_state["current_operator_symbol"] = "*"
            next_state["current_game_type"] = "Multiplication"
            next_state["selecting_problem_count"] = False
            next_state["selecting_score_name"] = False
            return _event_result("start_game", next_state, {"entry_type": value})
        return _event_result("show_problem_type_choices", next_state, {"entry_type": value})

    if event_type == "problem_type_choice":
        selection = choose_problem_type_state(value)
        if selection is None:
            return _event_result("ignore", next_state)

        next_state["current_operator_symbol"] = selection["operator_symbol"]
        next_state["current_game_type"] = selection["game_type"]
        next_state["selecting_problem_count"] = True
        next_state["selecting_score_name"] = False
        return _event_result("show_problem_count_choices", next_state, selection)

    if event_type == "problem_count_choice":
        selected_count = choose_problem_count_value(value)
        if selected_count is None:
            return _event_result("ignore", next_state)

        next_state["problem_count_target"] = selected_count
        next_state["selecting_problem_count"] = False
        return _event_result("start_game", next_state)

    return _event_result("ignore", next_state)


def initial_gameplay_state(
    game_started=False,
    current_problem_position=0,
    question_order_length=0,
    total_attempts=0,
    total_correct=0,
    total_skipped=0,
    current_correct_answer=None,
):
    return {
        "game_started": game_started,
        "current_problem_position": current_problem_position,
        "question_order_length": question_order_length,
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "total_skipped": total_skipped,
        "current_correct_answer": current_correct_answer,
    }


def handle_gameplay_event(state, event_type, payload=None):
    next_state = dict(state)

    if event_type == "quit_pressed_in_game":
        if not state.get("game_started", False):
            return _event_result("ignore", next_state)
        return _event_result("show_title_screen", next_state)

    if event_type == "next_pressed_in_game":
        if not state.get("game_started", False):
            return _event_result("ignore", next_state)

        next_state["total_skipped"] = state.get("total_skipped", 0) + 1
        next_state["current_problem_position"] = state.get("current_problem_position", 0) + 1
        if next_state["current_problem_position"] >= state.get("question_order_length", 0):
            return _event_result("finish_game", next_state)
        return _event_result("show_current_problem", next_state)

    if event_type == "answer_selected":
        if not state.get("game_started", False):
            return _event_result("ignore", next_state)

        if isinstance(payload, dict):
            chosen_value = payload.get("chosen_value")
        else:
            chosen_value = payload
        if chosen_value is None:
            return _event_result("ignore", next_state)

        next_state["total_attempts"] = state.get("total_attempts", 0) + 1
        is_correct = chosen_value == state.get("current_correct_answer")
        if not is_correct:
            return _event_result("wrong_answer", next_state)

        next_state["total_correct"] = state.get("total_correct", 0) + 1
        next_state["current_problem_position"] = state.get("current_problem_position", 0) + 1
        if next_state["current_problem_position"] >= state.get("question_order_length", 0):
            return _event_result("finish_game_correct", next_state)

        return _event_result("show_current_problem_correct", next_state)

    return _event_result("ignore", next_state)


def initial_post_score_state(post_score_status_active=False, post_score_page_index=0):
    return {
        "post_score_status_active": post_score_status_active,
        "post_score_page_index": post_score_page_index,
    }


def handle_post_score_event(state, event_type):
    next_state = dict(state)

    if event_type == "next_pressed_post_score":
        if not state.get("post_score_status_active", False):
            return _event_result("ignore", next_state)

        page_index = state.get("post_score_page_index", 0)
        if page_index == 1:
            next_state["post_score_page_index"] = 2
            return _event_result("show_ranking_page", next_state)
        if page_index == 2:
            next_state["post_score_page_index"] = 3
            return _event_result("show_top_scores_page", next_state)
        next_state["post_score_page_index"] = 0
        return _event_result("show_title_screen", next_state)

    if event_type == "quit_pressed_post_score":
        if not state.get("post_score_status_active", False):
            return _event_result("ignore", next_state)
        return _event_result("show_name_choices", next_state)

    return _event_result("ignore", next_state)


def initial_start_screen_scores_state(start_screen_top_scores_active=False, start_screen_top_score_index=0):
    return {
        "start_screen_top_scores_active": start_screen_top_scores_active,
        "start_screen_top_score_index": start_screen_top_score_index,
    }


def handle_start_screen_scores_event(state, event_type, payload=None):
    next_state = dict(state)

    if event_type == "next_pressed_start_screen_scores":
        if not state.get("start_screen_top_scores_active", False):
            return _event_result("ignore", next_state)

        if isinstance(payload, dict):
            score_type_count = payload.get("score_type_count", 0)
        else:
            score_type_count = payload if payload is not None else 0
        last_scores_page_index = score_type_count + 1
        current_index = state.get("start_screen_top_score_index", 0)

        if current_index >= last_scores_page_index:
            next_state["start_screen_top_score_index"] = 0
            return _event_result("show_title_screen", next_state)

        next_index = current_index + 1
        next_state["start_screen_top_score_index"] = next_index
        return _event_result("show_start_scores_page", next_state, next_index)

    if event_type == "quit_pressed_start_screen_scores":
        if not state.get("start_screen_top_scores_active", False):
            return _event_result("ignore", next_state)
        return _event_result("show_name_choices", next_state)

    return _event_result("ignore", next_state)
