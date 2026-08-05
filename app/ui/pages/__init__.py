from app.ui.pages import (
    content,
    dashboard,
    experiments,
    login,
    providers,
    public,
    reports,
    settings,
)


def register_pages() -> None:
    public.register()
    login.register()
    dashboard.register()
    providers.register()
    content.register()
    experiments.register()
    reports.register()
    settings.register()
