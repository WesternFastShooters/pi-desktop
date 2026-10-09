import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('packaging', ROOT / 'package.py')
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


class PackagingTests(unittest.TestCase):
    def test_tool_wrapper_reuses_local_extension_without_duplicate_registration(self):
        for installed in ['1', '0']:
            with self.subTest(installed=installed), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                resources = root / 'Resources'
                (resources / 'pi-tools/bin').mkdir(parents=True)
                (resources / 'host/runtime').mkdir(parents=True)
                wrapper = resources / 'pi-tools/bin/pi'
                wrapper.write_bytes((ROOT / 'pi-tools.sh').read_bytes())
                node = resources / 'host/runtime/node'
                node.write_text('#!/bin/sh\necho ' + installed + '\n')
                node.chmod(0o755)
                local_pi = root / 'local-pi'
                capture = root / 'capture.json'
                local_pi.write_text('#!/usr/bin/env python3\nimport os,json,sys\nopen(os.environ["CAPTURE"],"w").write(json.dumps({"argv":sys.argv[1:],"env":dict(os.environ)}))\n')
                local_pi.chmod(0o755)
                env = dict(os.environ, PI_DESKTOP_LOCAL_PI=str(local_pi), PI_CODING_AGENT_DIR=str(root / 'profile'), CAPTURE=str(capture), PI_COMPUTER_USE_HELPER_APP_PATH='/private/helper', PI_CU_SOCKET_PATH='/private/socket')
                subprocess.run(['bash', str(wrapper), '--version'], env=env, check=True)
                result = json.loads(capture.read_text())
                self.assertIn(str(resources / 'pi-extensions/browser.ts'), result['argv'])
                computer = str(resources / 'pi-runtime/node_modules/@injaneity/pi-computer-use/extensions/computer-use.ts')
                self.assertEqual(computer in result['argv'], installed == '0')
                self.assertEqual('PI_CU_SOCKET_PATH' in result['env'], installed == '0')

    def test_adhoc_entitlements_exclude_vendor_identity_and_shared_data(self):
        original = {'com.apple.application-identifier': 'vendor.app',
                    'com.apple.developer.team-identifier': 'vendor',
                    'com.apple.developer.aps-environment': 'production',
                    'com.apple.security.application-groups': ['vendor.shared'],
                    'keychain-access-groups': ['vendor.*'],
                    'com.apple.security.cs.allow-jit': True,
                    'com.apple.security.network.client': True}
        result = packaging.adhoc_entitlements(original)
        self.assertEqual(result, {'com.apple.security.cs.allow-jit': True,
                                  'com.apple.security.network.client': True})
        self.assertIn('keychain-access-groups', original)

    def test_inspection_rejects_reported_desktop_errors(self):
        with self.assertRaises(ValueError):
            packaging.validate_inspection({"desktop": None, "desktopError": "unsupported"})
        packaging.validate_inspection({"desktop": {"bundle": "Pi Shell.app"}, "desktopError": None})

    def test_rebranding_preserves_electron_integrity_and_original_input(self):
        original = {'CFBundleIdentifier': 'com.openai.codex',
                    'CFBundleExecutable': 'Codex',
                    'ElectronAsarIntegrity': {'Resources/app.asar': {'hash': 'test'}},
                    'CFBundleURLTypes': [{'CFBundleURLSchemes': ['codex']}],
                    'SUFeedURL': 'https://example.invalid'}
        shell = packaging.configure_shell(original)
        self.assertEqual(original['CFBundleIdentifier'], 'com.openai.codex')
        self.assertEqual(shell['CFBundleIdentifier'], packaging.SHELL_ID)
        self.assertEqual(shell['ElectronAsarIntegrity'], original['ElectronAsarIntegrity'])
        self.assertEqual(shell['CFBundleExecutable'], 'Codex')
        self.assertNotIn('CFBundleURLTypes', shell)
        self.assertNotIn('SUFeedURL', shell)
        self.assertFalse(shell['SUEnableAutomaticChecks'])

    def test_runtime_rejects_external_dependencies_and_accepts_internal_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'pi'
            (root / 'bin').mkdir(parents=True)
            target = root / 'pi'
            target.write_text('#!/bin/sh\nexit 0\n')
            target.chmod(0o755)
            (root / 'bin/pi').symlink_to('../pi')
            packaging.validate_runtime(root)
            external = Path(temp) / 'external'
            external.write_text('external dependency')
            (root / 'dependency').symlink_to(external)
            with self.assertRaises(ValueError):
                packaging.validate_runtime(root)

    def test_launcher_routes_only_to_bundle_and_isolates_profiles(self):
        with tempfile.TemporaryDirectory(prefix='中文 Pi Desktop ') as temp:
            root = Path(temp)
            app = root / 'Pi Desktop.app'
            resources = app / 'Contents/Resources'
            macos = app / 'Contents/MacOS'
            host_bin = resources / 'host/bin'
            host_bin.mkdir(parents=True)
            macos.mkdir()
            launcher = macos / 'pi-desktop'
            launcher.write_bytes((ROOT / 'launch.sh').read_bytes())
            host = host_bin / 'codexhost'
            capture = root / 'capture.json'
            host.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                            'open(os.environ["CAPTURE"],"w").write(json.dumps({"argv":sys.argv[1:],"env":dict(os.environ)}))\n')
            host.chmod(0o755)
            user_home = root / 'user'
            user_home.mkdir()
            local_pi = user_home / '.pi/agent/bin/pi'
            local_pi.parent.mkdir(parents=True)
            local_pi.write_text('#!/bin/sh\nexit 0\n')
            local_pi.chmod(0o755)
            env = dict(os.environ, HOME=str(user_home), CAPTURE=str(capture),
                       CODEXHOST_REMOTE_SSH_MANAGED='1', CODEXHOST_HOST_RUNTIME_PATH='/wrong',
                       CODEXHOST_NPM_PACKAGE_ROOT='/wrong')
            subprocess.run(['bash', str(launcher)], env=env, check=True)
            actual = json.loads(capture.read_text())
            self.assertEqual(actual['argv'], ['launch', '--custom-install',
                             str(resources / 'Pi Shell.app'), '--pi', str(resources / 'pi-tools/bin/pi')])
            data = user_home / 'Library/Application Support/Pi Desktop'
            for name, sub in [('CODEXHOST_DATA_DIR','host'), ('CODEX_HOME','codex'),
                              ('CODEX_ELECTRON_USER_DATA_PATH','electron')]:
                self.assertEqual(actual['env'][name], str(data / sub))
            self.assertEqual(actual['env']['PI_CODING_AGENT_DIR'], str(user_home / '.pi/agent'))
            self.assertEqual(actual['env']['PI_DESKTOP_LOCAL_PI'], str(local_pi))
            config = (data / 'codex/config.toml').read_text()
            self.assertIn('requires_openai_auth = false', config)
            self.assertFalse((data / 'codex/auth.json').exists())
            self.assertEqual(actual['env']['CODEXHOST_CONSOLE'], '0')
            self.assertNotIn('CODEXHOST_REMOTE_SSH_MANAGED', actual['env'])
            self.assertNotIn('CODEXHOST_HOST_RUNTIME_PATH', actual['env'])
            self.assertNotIn('CODEXHOST_NPM_PACKAGE_ROOT', actual['env'])


if __name__ == '__main__':
    unittest.main()
