import pytest
from story.postprocess import normalize_ai_text_to_story


def test_malformed_model_fields_do_not_break_story_or_memory(monkeypatch):
    from story import parser
    monkeypatch.setattr(parser, 'parse_ai_output', lambda _: {
        'narration': {'bad': 'type'}, 'clues': None,
        'choices': [None, 123, '10) Open the door', 'Open the door', 'Wait nearby'],
        'memory': {'npcs': [None, 123, ' Sarah ', 'Sarah', {}]}
    })
    result = normalize_ai_text_to_story('model response')
    assert result['narration']
    assert result['clues'] == ''
    assert result['choices'] == ['Open the door', 'Wait nearby']
    assert result['memory']['npcs'] == ['Sarah']


@pytest.mark.parametrize('options', [{'max_choices': 0}, {'max_choices': True}, {'max_narration_chars': -1}])
def test_invalid_output_limits_are_explicit(options):
    with pytest.raises(ValueError):
        normalize_ai_text_to_story('', **options)
