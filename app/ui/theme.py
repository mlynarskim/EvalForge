from nicegui import ui

APP_CSS = """
:root { --q-primary: #635bff; --q-secondary: #16a085; --q-accent: #8b5cf6; }
body { font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
.ef-page { max-width: 1480px; margin: 0 auto; padding: 24px 28px 48px; container-type: inline-size; }
.ef-card { border: 1px solid rgba(145, 158, 171, .18); border-radius: 16px; box-shadow: 0 8px 28px rgba(16, 24, 40, .06); }
.ef-stat { min-height: 128px; min-width: 0; }
.ef-stat-value { overflow-wrap: anywhere; line-height: 1.15; }
.ef-muted { color: #667085; }
.ef-header { background: #ffffff !important; color: #0f172a !important; border-bottom-color: #e2e8f0 !important; }
body.body--dark .ef-header { background: #111827 !important; color: #ffffff !important; border-bottom-color: #1e293b !important; }
.ef-brand-mark { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; background: #635bff; color: white; font-weight: 800; }
.ef-nav .q-item { border-radius: 10px; margin: 3px 8px; }
.ef-nav .q-router-link--active { background: rgba(99,91,255,.10); color: #635bff; }
.ef-demo { border: 1px solid rgba(245,158,11,.35); background: rgba(245,158,11,.08); border-radius: 12px; }
.ef-stats-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 16px; width: 100%; }
.ef-charts-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; width: 100%; }
.ef-card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; width: 100%; }
.ef-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; width: 100%; }
.ef-onboarding-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; width: 100%; }
.ef-step { border: 1px solid rgba(145, 158, 171, .22); border-radius: 14px; padding: 16px; min-width: 0; }
.ef-step-number { width: 30px; height: 30px; border-radius: 999px; display: grid; place-items: center; background: rgba(99,91,255,.12); color: #635bff; font-weight: 700; flex: 0 0 auto; }
.ef-public-header { background: rgba(255,255,255,.94) !important; color: #0f172a !important; border-bottom: 1px solid #e2e8f0; backdrop-filter: blur(12px); }
body.body--dark .ef-public-header { background: rgba(17,24,39,.94) !important; color: #ffffff !important; border-bottom-color: #334155; }
.ef-public-sign-in { color: inherit !important; }
.ef-landing { overflow: hidden; }
.ef-hero { width: min(1180px, calc(100% - 40px)); min-height: 680px; margin: 0 auto; padding: 88px 0 72px; display: grid; grid-template-columns: 1.08fr .92fr; align-items: center; gap: 64px; }
.ef-hero-copy { align-items: flex-start; gap: 18px; }
.ef-eyebrow { color: #635bff; font-weight: 800; text-transform: uppercase; letter-spacing: .12em; font-size: .78rem; }
.ef-hero-title { font-size: clamp(2.55rem, 5vw, 4.7rem); line-height: 1.02; letter-spacing: -.045em; font-weight: 850; max-width: 760px; }
.ef-hero-body { color: #667085; font-size: clamp(1.05rem, 2vw, 1.32rem); line-height: 1.65; max-width: 680px; }
.ef-product-preview { width: 100%; padding: 28px; transform: rotate(1deg); background: linear-gradient(145deg, #ffffff, #f7f7ff); }
body.body--dark .ef-product-preview { background: linear-gradient(145deg, #1f2937, #111827); }
.ef-preview-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 24px 0; }
.ef-preview-stat { min-width: 0; border: 1px solid rgba(99,91,255,.18); border-radius: 13px; padding: 16px 12px; background: rgba(99,91,255,.05); }
.ef-preview-result { display: flex; align-items: center; gap: 12px; border-radius: 14px; padding: 16px; background: rgba(34,197,94,.09); }
.ef-public-section { width: min(1180px, calc(100% - 40px)); margin: 0 auto; padding: 84px 0; }
.ef-section-title { font-size: clamp(2rem, 4vw, 3.25rem); line-height: 1.1; letter-spacing: -.03em; font-weight: 800; max-width: 850px; }
.ef-section-lead { color: #667085; font-size: 1.15rem; line-height: 1.7; max-width: 760px; margin-top: 14px; }
.ef-feature-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; margin-top: 42px; }
.ef-feature-card { padding: 26px; min-width: 0; gap: 14px; }
.ef-how { border-top: 1px solid rgba(145,158,171,.18); }
.ef-steps-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; margin-top: 38px; }
.ef-public-step { display: grid; grid-template-columns: auto 1fr; align-items: start; gap: 10px 14px; padding: 6px; }
.ef-public-step .ef-muted { grid-column: 2; line-height: 1.6; }
.ef-public-footer { width: min(1180px, calc(100% - 40px)); margin: 0 auto; padding: 28px 0 42px; border-top: 1px solid rgba(145,158,171,.18); display: flex; align-items: center; justify-content: space-between; gap: 18px; flex-wrap: wrap; }
.ef-public-footer a { color: #635bff; text-decoration: none; }
.ef-legal { width: min(820px, calc(100% - 40px)); margin: 0 auto; padding: 70px 0 90px; gap: 28px; }
.ef-legal-title { font-size: clamp(2.5rem, 5vw, 4rem); line-height: 1.05; letter-spacing: -.04em; font-weight: 850; }
.ef-legal-section { display: flex; flex-direction: column; gap: 9px; }
.ef-legal-paragraph { color: #667085; line-height: 1.75; font-size: 1.02rem; white-space: normal; }
.ef-model-result { min-width: 0; }
.ef-model-recommended { border: 2px solid rgba(34,197,94,.55); background: rgba(34,197,94,.04); }
.ef-recommendation-card { background: linear-gradient(135deg, rgba(34,197,94,.10), rgba(99,91,255,.06)); }
.ef-result-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, .7fr); gap: 16px; width: 100%; }
.nicegui-content { padding: 0; }
@media (max-width: 900px) { .ef-page { padding: 18px 14px 36px; } }
@media (max-width: 860px) { .ef-hero { grid-template-columns: 1fr; min-height: auto; padding: 64px 0; gap: 44px; } .ef-product-preview { max-width: 620px; transform: none; } .ef-feature-grid, .ef-steps-grid { grid-template-columns: 1fr; } .ef-public-section { padding: 64px 0; } }
@media (max-width: 560px) { .ef-hero, .ef-public-section, .ef-public-footer, .ef-legal { width: min(100% - 28px, 1180px); } .ef-hero { padding: 46px 0 54px; } .ef-hero-title { font-size: 2.55rem; } .ef-product-preview { padding: 18px; } .ef-preview-grid { grid-template-columns: 1fr; } .ef-public-header { padding-left: 14px !important; padding-right: 8px !important; } .ef-public-header .ef-brand-mark { width: 30px; height: 30px; } .ef-public-header .text-xl { display: none; } .ef-feature-card { padding: 20px; } .ef-public-footer { align-items: flex-start; flex-direction: column; } }
@container (max-width: 1200px) { .ef-stats-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@container (max-width: 900px) { .ef-card-grid, .ef-onboarding-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .ef-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@container (max-width: 720px) { .ef-charts-grid { grid-template-columns: minmax(0, 1fr); } }
@container (max-width: 720px) { .ef-result-grid { grid-template-columns: minmax(0, 1fr); } }
@container (max-width: 560px) { .ef-stats-grid, .ef-card-grid, .ef-summary-grid, .ef-onboarding-grid { grid-template-columns: minmax(0, 1fr); } }
"""


def apply_theme() -> None:
    ui.add_css(APP_CSS)
    ui.colors(primary="#635BFF", secondary="#16A085", accent="#8B5CF6")
