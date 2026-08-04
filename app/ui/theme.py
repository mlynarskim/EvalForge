from nicegui import ui

APP_CSS = """
:root { --q-primary: #635bff; --q-secondary: #16a085; --q-accent: #8b5cf6; }
body { font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
.ef-page { max-width: 1480px; margin: 0 auto; padding: 24px 28px 48px; }
.ef-card { border: 1px solid rgba(145, 158, 171, .18); border-radius: 16px; box-shadow: 0 8px 28px rgba(16, 24, 40, .06); }
.ef-stat { min-height: 128px; }
.ef-muted { color: #667085; }
.ef-brand-mark { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; background: #635bff; color: white; font-weight: 800; }
.ef-nav .q-item { border-radius: 10px; margin: 3px 8px; }
.ef-nav .q-router-link--active { background: rgba(99,91,255,.10); color: #635bff; }
.ef-demo { border: 1px solid rgba(245,158,11,.35); background: rgba(245,158,11,.08); border-radius: 12px; }
.nicegui-content { padding: 0; }
@media (max-width: 900px) { .ef-page { padding: 18px 14px 36px; } }
"""


def apply_theme() -> None:
    ui.add_css(APP_CSS)
    ui.colors(primary="#635BFF", secondary="#16A085", accent="#8B5CF6")
