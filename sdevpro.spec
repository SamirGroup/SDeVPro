# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project_root = Path(SPECPATH)
engine_root = project_root / 'sdevpro' / 'engine'

tui_name = 'sdevpro-tui.exe' if sys.platform == 'win32' else 'sdevpro-tui'
tui_binary = project_root / 'build' / 'sidecar' / tui_name
if not tui_binary.is_file():
    raise FileNotFoundError(
        f'Missing Go TUI sidecar at {tui_binary}; run `make tui-build` first'
    )
binaries = [(str(tui_binary), 'sdevpro/engine/bin')]

datas = []

for md_file in engine_root.rglob('skills/**/*.md'):
    rel_path = md_file.relative_to(project_root)
    datas.append((str(md_file), str(rel_path.parent)))

for jinja_file in engine_root.rglob('agents/**/*.jinja'):
    rel_path = jinja_file.relative_to(project_root)
    datas.append((str(jinja_file), str(rel_path.parent)))

for xml_file in engine_root.rglob('*.xml'):
    rel_path = xml_file.relative_to(project_root)
    datas.append((str(xml_file), str(rel_path.parent)))

# Prebuilt local-viewer SPA (served by `sdevpro view`).
viewer_static = engine_root / 'interface' / 'viewer' / 'static'
for asset in viewer_static.rglob('*'):
    if asset.is_file():
        rel_path = asset.relative_to(project_root)
        datas.append((str(asset), str(rel_path.parent)))

datas += collect_data_files('tiktoken')
datas += collect_data_files('tiktoken_ext')

datas += collect_data_files('litellm')

datas += collect_data_files('agents', includes=['**/*.md', '**/*.jinja', '**/*.json'])

hiddenimports = [
    # Core dependencies
    'litellm',
    'litellm.llms',
    'litellm.llms.openai',
    'litellm.llms.anthropic',
    'litellm.llms.vertex_ai',
    'litellm.llms.bedrock',
    'litellm.utils',
    'litellm.caching',

    # Rich console
    'rich',
    'rich.console',
    'rich.panel',
    'rich.text',
    'rich.markup',
    'rich.style',
    'rich.align',
    'rich.live',

    # Pydantic
    'pydantic',
    'pydantic.fields',
    'pydantic_core',
    'email_validator',

    # Docker
    'docker',
    'docker.api',
    'docker.models',
    'docker.errors',

    # HTTP/Networking
    'httpx',
    'httpcore',
    'requests',
    'urllib3',
    'certifi',

    # Jinja2 templating
    'jinja2',
    'jinja2.ext',
    'markupsafe',

    # XML parsing
    'xmltodict',
    'defusedxml',
    'defusedxml.ElementTree',

    # Syntax highlighting
    'pygments',
    'pygments.lexers',
    'pygments.styles',
    'pygments.util',

    # Tiktoken (for token counting)
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',

    # Tenacity retry
    'tenacity',

    # CVSS scoring
    'cvss',

    # SDeVPro modules
    'sdevpro',
    'sdevpro.engine.interface',
    'sdevpro.engine.interface.main',
    'sdevpro.engine.interface.cli',
    'sdevpro.engine.interface.tui',
    'sdevpro.engine.interface.tui.runtime',
    'sdevpro.engine.interface.tui.history',
    'sdevpro.engine.interface.tui.live_view',
    'sdevpro.engine.interface.tui.backend',
    'sdevpro.engine.interface.tui.backend.controller',
    'sdevpro.engine.interface.tui.backend.messages',
    'sdevpro.engine.interface.tui.backend.protocol',
    'sdevpro.engine.interface.tui.backend.server',
    'sdevpro.engine.interface.utils',
    'sdevpro.engine.agents',
    'sdevpro.engine.agents.factory',
    'sdevpro.engine.agents.prompt',
    'sdevpro.engine.config.loader',
    'sdevpro.engine.config.settings',
    'sdevpro.engine.config.codex',
    'sdevpro.engine.core',
    'sdevpro.engine.core.agents',
    'sdevpro.engine.core.execution',
    'sdevpro.engine.core.inputs',
    'sdevpro.engine.core.paths',
    'sdevpro.engine.core.runner',
    'sdevpro.engine.core.sessions',
    'sdevpro.engine.report',
    'sdevpro.engine.report.dedupe',
    'sdevpro.engine.report.state',
    'sdevpro.engine.report.writer',
    'sdevpro.engine.interface.viewer',
    'sdevpro.engine.interface.viewer.auth',
    'sdevpro.engine.interface.viewer.cli',
    'sdevpro.engine.interface.viewer.report_pdf',
    'sdevpro.engine.interface.viewer.server',
    'sdevpro.engine.interface.viewer.transcript',

    # PDF report generation + encryption
    'reportlab',
    'reportlab.pdfgen',
    'reportlab.pdfbase',
    'reportlab.lib',
    'reportlab.platypus',
    'pypdf',
    'cryptography',
    'sdevpro.engine.runtime',
    'sdevpro.engine.runtime.backends',
    'sdevpro.engine.runtime.caido_bootstrap',
    'sdevpro.engine.runtime.docker_client',
    'sdevpro.engine.runtime.session_manager',
    'sdevpro.engine.telemetry',
    'sdevpro.engine.telemetry.logging',
    'sdevpro.engine.telemetry.posthog',
    'sdevpro.engine.tools',
    'sdevpro.engine.tools.agents_graph.tools',
    'sdevpro.engine.tools.finish.tool',
    'sdevpro.engine.tools.notes.tools',
    'sdevpro.engine.tools.proxy._calls',
    'sdevpro.engine.tools.proxy.tools',
    'sdevpro.engine.tools.python.tool',
    'sdevpro.engine.tools.reporting.tool',
    'sdevpro.engine.tools.thinking.tool',
    'sdevpro.engine.tools.todo.tools',
    'sdevpro.engine.tools.web_search.tool',
    'sdevpro.engine.skills',
]

hiddenimports += collect_submodules('litellm')
hiddenimports += collect_submodules('rich')
hiddenimports += collect_submodules('pydantic')
hiddenimports += collect_submodules('pygments')
# reportlab loads renderers/fonts dynamically, so pull its whole tree in.
hiddenimports += collect_submodules('reportlab')

# reportlab ships bundled fonts (.pfb/.afm) it needs at runtime.
datas += collect_data_files('reportlab')

# reportlab imports PIL (pillow) lazily for image handling, so it must be
# bundled explicitly and kept out of the excludes list below.
hiddenimports += collect_submodules('PIL')
datas += collect_data_files('PIL')

excludes = [
    # Sandbox-only packages
    'playwright',
    'playwright.sync_api',
    'playwright.async_api',
    'IPython',
    'ipython',
    'libtmux',
    'pyte',
    'openhands_aci',
    'openhands-aci',
    'numpydoc',

    # Google Cloud / Vertex AI
    'google.cloud',
    'google.cloud.aiplatform',
    'google.api_core',
    'google.auth',
    'google.oauth2',
    'google.protobuf',
    'grpc',
    'grpcio',
    'grpcio_status',

    # Test frameworks
    'pytest',
    'pytest_asyncio',
    'pytest_cov',
    'pytest_mock',

    # Development tools
    'mypy',
    'ruff',
    'black',
    'isort',
    'pylint',
    'pyright',
    'bandit',
    'pre_commit',

    # Unnecessary for runtime
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'cv2',
]

a = Analysis(
    ['sdevpro/engine/interface/main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='sdevpro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
