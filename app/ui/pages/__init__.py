from app.ui.pages import content, dashboard, experiments, login, providers, reports, settings


def register_pages() -> None:
    login.register()
    dashboard.register()
    providers.register()
    content.register()
    experiments.register()
    reports.register()
    settings.register()
