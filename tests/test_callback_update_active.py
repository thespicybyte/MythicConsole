from backend.callback.callback import Callback
from backend.callback.queries import CallbackQueries


async def test_update_active_issues_active_update_not_locked(fake_instance, monkeypatch):
    calls = []

    async def _update_active(_session, display_id, is_active):
        calls.append(("active", display_id, is_active))

    async def _update_locked(_session, display_id, is_locked):
        calls.append(("locked", display_id, is_locked))

    monkeypatch.setattr(CallbackQueries, "update_active", _update_active)
    monkeypatch.setattr(CallbackQueries, "update_locked", _update_locked)

    callback = Callback(fake_instance, callback_id=1)
    callback.display_id = 7

    await callback.update_active(True)

    assert calls == [("active", 7, True)]


async def test_update_locked_still_issues_locked_update(fake_instance, monkeypatch):
    calls = []

    async def _update_active(_session, display_id, is_active):
        calls.append(("active", display_id, is_active))

    async def _update_locked(_session, display_id, is_locked):
        calls.append(("locked", display_id, is_locked))

    monkeypatch.setattr(CallbackQueries, "update_active", _update_active)
    monkeypatch.setattr(CallbackQueries, "update_locked", _update_locked)

    callback = Callback(fake_instance, callback_id=1)
    callback.display_id = 7

    await callback.update_locked(True)

    assert calls == [("locked", 7, True)]


def test_apply_stream_update_sets_active_false(fake_instance):
    callback = Callback(fake_instance, callback_id=1)
    callback.active = True

    callback.apply_stream_update({"active": False})

    assert callback.active is False


def test_apply_stream_update_sets_active_true(fake_instance):
    callback = Callback(fake_instance, callback_id=1)
    callback.active = False

    callback.apply_stream_update({"active": True})

    assert callback.active is True
