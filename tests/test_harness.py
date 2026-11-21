from mqbench.engine import Level
from mqbench.harness import CAP, board_text, prompt, run_level
from mqbench.solver import solve

LEVEL = 'G....\nG....\n..#..\n.....\n..AB.'  # original level 1, minimum 8


def scripted(*replies):
    """A fake model that gives these replies in turn."""
    replies = iter(replies)
    return lambda messages: (next(replies), {key: 1 for key in ['input_tokens', 'output_tokens', 'reasoning_tokens', 'cost', 'seconds']})


def test_one_shot_solution_is_scored():
    solution = solve(Level(LEVEL))
    record = run_level(scripted(f'Thinking...\n**MOVES:** {" ".join(solution)}'), 'fake', 'one-shot', 'dev-1', LEVEL, 8)
    assert (record['solved'], record['moves'], record['calls'], record['output_tokens']) == (True, 8, 1, 1)


def test_one_shot_without_an_answer_fails():
    record = run_level(scripted('I am not sure.'), 'fake', 'one-shot', 'dev-1', LEVEL, 8)
    assert (record['solved'], record['submitted']) == (False, '')


def test_interactive_plays_one_action_per_turn():
    replies = ['ACTION: R', 'ACTION: R', 'no action here', 'ACTION: UNDO'] + [f'ACTION: {m}' for m in solve(Level(LEVEL))]
    record = run_level(scripted(*replies), 'fake', 'interactive', 'dev-1', LEVEL, 8)
    assert (record['solved'], record['moves'], record['total_actions']) == (True, 8, 12)
    assert record['messages'][4]['content'].startswith('Nothing moved.')
    assert record['messages'][-1]['role'] == 'assistant'


def test_interactive_stops_at_the_action_cap():
    record = run_level(scripted(*['ACTION: RESET'] * 100), 'fake', 'interactive', 'dev-1', LEVEL, 8)
    assert (record['solved'], record['total_actions']) == (False, CAP * 8)


def test_prompt_shows_the_board_and_hidden_squares():
    level = Level(LEVEL)
    assert board_text(level, (((0, 0), (4, 3)), frozenset())) == 'A....\nG....\n..#..\n.....\n...B.\nA is on a goal.'
    text = prompt('one-shot', level)
    assert level.render(level.start) in text and '{' not in text and 'MOVES:' in text
