"""macOS bundle assembly. Never modifies the supplied official application."""
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

SHELL_ID = 'local.personal.pi-desktop.shell'
APP_ID = 'local.personal.pi-desktop'


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def validate_runtime(root):
    root = Path(root).resolve()
    entry = root / 'bin/pi'
    if not entry.is_file() or not os.access(entry, os.X_OK):
        raise ValueError('Pi runtime must contain executable bin/pi')
    for file in root.rglob('*'):
        if file.is_symlink() and not file.resolve(strict=True).is_relative_to(root):
            raise ValueError(f'Pi runtime links outside its bundle: {file}')


def configure_shell(info):
    result = dict(info)
    result.update(CFBundleIdentifier=SHELL_ID, CFBundleName='Pi Desktop',
                  CFBundleDisplayName='Pi Desktop')
    # Avoid registering official login callbacks and file associations twice.
    for key in ('CFBundleURLTypes', 'CFBundleDocumentTypes', 'SUFeedURL',
                'SUEnableAutomaticChecks', 'SUAutomaticallyUpdate',
                'SUAllowsAutomaticUpdates'):
        result.pop(key, None)
    result['SUEnableAutomaticChecks'] = False
    result['SUAllowsAutomaticUpdates'] = False
    return result


def adhoc_entitlements(original):
    # Ad-hoc signatures cannot claim a vendor's provisioning identity or
    # restricted services; shared groups would also defeat profile isolation.
    return {key: value for key, value in original.items()
            if key.startswith('com.apple.security.')
            and key != 'com.apple.security.application-groups'}


def validate_inspection(document):
    if document.get('desktopError') or not document.get('desktop'):
        raise ValueError(f"Bundled Desktop discovery failed: {document.get('desktopError')}")


def assemble(codex, pi, payload, output):
    if sys.platform != 'darwin':
        raise RuntimeError('Packaging requires macOS')
    codex, pi, payload, output = map(lambda p: Path(p).resolve(), (codex, pi, payload, output))
    validate_runtime(pi)
    required = ('bin/codexhost', 'libexec/codexhost-shim', 'runtime/node',
                'app/host-runtime.mjs', 'app/desktop-controller.mjs',
                'app/renderer-extension.js')
    for relative in required:
        if not (payload / relative).is_file():
            raise ValueError(f'Missing patched Host payload file: {relative}')
    app = output / 'Pi Desktop.app'
    dmg = output / 'Pi Desktop.dmg'
    if app.exists() or dmg.exists():
        raise FileExistsError('Refusing to replace existing application or DMG')
    contents = app / 'Contents'
    resources = contents / 'Resources'
    (contents / 'MacOS').mkdir(parents=True)
    resources.mkdir()
    run('/usr/bin/ditto', codex, resources / 'Pi Shell.app')
    run('/usr/bin/ditto', pi, resources / 'pi-runtime')
    # RPC mode defers permission setup until a computer tool is requested.
    cu_extension = resources / 'pi-runtime/node_modules/@injaneity/pi-computer-use/extensions/computer-use.ts'
    cu_extension.write_text(cu_extension.read_text().replace('if (!ctx.hasUI) return;', 'if (!ctx.hasUI || process.env.PI_DESKTOP_LOCAL_PI) return;'))
    cu_helper = resources / 'pi-runtime/node_modules/@injaneity/pi-computer-use/src/platform/macos/helper.ts'
    cu_helper.write_text(cu_helper.read_text().replace('const usingExternalHelperSocket = HELPER_SOCKET_PATH !== DEFAULT_HELPER_SOCKET_PATH;', 'const usingExternalHelperSocket = HELPER_SOCKET_PATH !== DEFAULT_HELPER_SOCKET_PATH && !process.env.PI_DESKTOP_LOCAL_PI;'))
    extension_source = Path(__file__).resolve().parent / 'extensions'
    run('/usr/bin/ditto', extension_source, resources / 'pi-extensions')
    tools_bin = resources / 'pi-tools' / 'bin'
    tools_bin.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve().parent / 'pi-tools.sh', tools_bin / 'pi')
    (tools_bin / 'pi').chmod(0o755)
    helper_env = {**os.environ, 'PI_COMPUTER_USE_HELPER_APP_PATH': str(resources / 'Pi Computer Use.app')}
    run(payload / 'runtime/node', resources / 'pi-runtime/node_modules/@injaneity/pi-computer-use/scripts/setup-helper.mjs', env=helper_env)

    run('/usr/bin/ditto', payload, resources / 'host')
    info_path = resources / 'Pi Shell.app/Contents/Info.plist'
    with info_path.open('rb') as file:
        info = configure_shell(plistlib.load(file))
    with info_path.open('wb') as file:
        plistlib.dump(info, file)
    wrapper = {
        'CFBundleIdentifier': APP_ID, 'CFBundleName': 'Pi Desktop',
        'CFBundleDisplayName': 'Pi Desktop', 'CFBundleExecutable': 'pi-desktop',
        'CFBundlePackageType': 'APPL', 'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0', 'LSUIElement': True,
        'LSMinimumSystemVersion': info.get('LSMinimumSystemVersion', '12.0'),
    }
    icon_file = Path(__file__).resolve().parent / 'assets/pi-desktop.icns'
    if not icon_file.is_file():
        raise FileNotFoundError('Pi icon asset is required')
    shutil.copy2(icon_file, resources / 'pi-desktop.icns')
    shutil.copy2(icon_file, resources / 'Pi Shell.app/Contents/Resources/pi-desktop.icns')
    original_icon = info.get('CFBundleIconFile')
    if original_icon:
        old_icon = resources / 'Pi Shell.app/Contents/Resources' / original_icon
        if not old_icon.suffix:
            old_icon = old_icon.with_suffix('.icns')
        shutil.copy2(icon_file, old_icon)
    info['CFBundleIconFile'] = 'pi-desktop.icns'
    info.pop('CFBundleIconName', None)
    with info_path.open('wb') as file:
        plistlib.dump(info, file)
    wrapper['CFBundleIconFile'] = 'pi-desktop.icns'
    with (contents / 'Info.plist').open('wb') as file:
        plistlib.dump(wrapper, file)
    launcher = contents / 'MacOS/pi-desktop'
    launcher.write_bytes(Path(__file__).with_name('launch.sh').read_bytes())
    launcher.chmod(0o755)
    # Remove the packaged Host updater: accidental stock Host upgrades would
    # replace the isolation modifications. UI update requests may report an error.
    updater = resources / 'host/libexec/codexhost-updater'
    updater.unlink(missing_ok=True)
    # Preserve Electron entitlements when resigning the copied outer shell.
    # Its embedded helpers are left untouched; app.asar is also untouched.
    with tempfile.TemporaryDirectory(prefix='pi-sign-') as temp:
        entitlements = Path(temp) / 'entitlements.plist'
        result = run('/usr/bin/codesign', '-d', '--entitlements', ':-', codex,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sign_args = ['/usr/bin/codesign', '--force', '--sign', '-']
        if result.stdout.strip():
            source_entitlements = plistlib.loads(result.stdout)
            entitlements.write_bytes(plistlib.dumps(adhoc_entitlements(source_entitlements)))
            sign_args += ['--entitlements', entitlements]
        run(*sign_args, resources / 'Pi Shell.app')
    for relative in ('host/bin/codexhost', 'host/libexec/codexhost-shim', 'host/runtime/node'):
        run('/usr/bin/codesign', '--force', '--sign', '-', resources / relative)
    run('/usr/bin/codesign', '--force', '--sign', '-', app)
    run('/usr/bin/codesign', '--verify', '--deep', '--strict', app)
    # Check Pi without global npm, shell profiles, or installed Node on PATH.
    with tempfile.TemporaryDirectory(prefix='pi-smoke-') as temp:
        env = {'HOME': temp, 'PI_CODING_AGENT_DIR': temp,
               'PATH': f'{resources}/pi-runtime/bin:{resources}/host/runtime:/usr/bin:/bin'}
        run(resources / 'pi-runtime/bin/pi', '--version', env=env, timeout=30)
    # Discovery also proves this payload has the patched Bundle ID allowlist.
    inspect_env = dict(os.environ, CODEXHOST_DATA_DIR=str(output / '.inspection-host'))
    inspection = run(resources / 'host/bin/codexhost', 'inspect', '--json',
        '--custom-install', resources / 'Pi Shell.app',
        env=inspect_env, stdout=subprocess.PIPE, text=True)
    validate_inspection(json.loads(inspection.stdout))
    (resources / 'build-info.json').write_text(json.dumps({
        'hostCommit': '08c7d65dddb03a79d5b311d47a0381c299316a3b',
        'codexVersion': info['CFBundleShortVersionString'],
        'codexBuild': info['CFBundleVersion'],
        'status': 'requires-macos-coexistence-validation',
    }, indent=2) + '\n')
    # Sign again after adding the recorded build information.
    run('/usr/bin/codesign', '--force', '--sign', '-', app)
    run('/usr/bin/codesign', '--verify', '--deep', '--strict', app)
    with tempfile.TemporaryDirectory(prefix='.pi-dmg-', dir=output) as temp:
        stage = Path(temp)
        run('/usr/bin/ditto', app, stage / app.name)
        (stage / 'Applications').symlink_to('/Applications')
        run('/usr/bin/hdiutil', 'create', '-volname', 'Pi Desktop', '-srcfolder',
            stage, '-format', 'UDZO', dmg)
    run('/usr/bin/hdiutil', 'verify', dmg)


if __name__ == '__main__':
    if len(sys.argv) != 5:
        raise SystemExit('Usage: package.py Codex.app pi-runtime patched-host-payload output')
    assemble(*sys.argv[1:])
