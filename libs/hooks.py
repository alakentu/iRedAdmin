import web


def hook_set_language():
    # parameter `lang` in URI. e.g. https://xxx/?lang=es_ES
    _lang = web.input(lang=None, _method="GET").get("lang")

    # parameter `lang` in session.
    if not _lang:
        _lang = web.config.get("_session", {}).get("lang")

    web.ctx.lang = _lang or "es_ES"
