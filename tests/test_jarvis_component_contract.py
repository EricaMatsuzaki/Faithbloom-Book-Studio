import jarvis_push_to_talk as ptt


def test_jarvis_component_uses_state_only_for_persistent_payloads():
    # Each setStateValue already triggers a Streamlit rerun. Jarvis does not need
    # a second trigger event for the same submission, which could race/remount.
    assert "setStateValue('recording'" in ptt.JS
    assert "setStateValue('typed_request'" in ptt.JS
    assert "setStateValue('navigation'" in ptt.JS
    assert "setTriggerValue" not in ptt.JS


def test_jarvis_component_source_does_not_define_manual_trigger_defaults():
    import inspect

    source = inspect.getsource(ptt.push_to_talk)
    assert '"submitted"' not in source
    assert '"typed_submitted"' not in source
    assert '"navigation_submitted"' not in source
    assert 'default={"recording":None,"typed_request":None,"navigation":None}' in source.replace(" ", "")
