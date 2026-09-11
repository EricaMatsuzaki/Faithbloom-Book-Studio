import jarvis_heart_mic as heart


def test_heart_component_never_synthesizes_or_replays_reply_audio():
    js = heart.JS
    assert "speechSynthesis" not in js
    assert "SpeechSynthesisUtterance" not in js
    assert "new Audio" not in js
    assert "reply_audio" not in js
    assert "reply_text" not in js


def test_speaking_stage_returns_heart_to_ready_state():
    js = heart.JS
    assert "stage==='speaking'" in js
    assert "setVisual('idle','Toque no coração para falar')" in js
