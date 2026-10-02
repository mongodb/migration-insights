# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Migration Insights.
Produces a one-directory bundle that includes the Python interpreter,
all dependencies, templates, images, and JSON configuration files.

Usage (from the migration_insights directory):
    pyinstaller migration_insights.spec
"""
import os
import importlib

block_cipher = None

# Resolve certifi CA bundle so TLS connections work in the frozen build
certifi_path = os.path.join(os.path.dirname(importlib.import_module('certifi').__file__), 'cacert.pem')

a = Analysis(
    ['migration_insights.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Flask HTML templates
        ('templates', 'templates'),
        # Static images served by Flask
        ('images', 'images'),
        # Shared JS (served via /static/js/ route)
        ('static', 'static'),
        # certifi CA bundle for pymongo TLS
        (certifi_path, 'certifi'),
    ],
    hiddenimports=[
        'blueprints',
        'blueprints.live',
        'lib.session_support',
        'lib.migration_verifier',
        'lib.utils',
        'lib.app_config',
        'lib.connection_validator',
        'engineio.async_drivers.threading',
        'dns.resolver',
        'dns.rdatatype',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='migration-insights',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='migration-insights',
)
