"""Installer regression tests; all destinations are isolated under a temporary root.

Run with: python3 -B -m unittest discover -s tests -v
Set REVIEW_LOOP_PWSH to select a PowerShell executable when needed.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]


def find_powershell():
    return (os.environ.get('REVIEW_LOOP_PWSH') or shutil.which('pwsh') or
            (shutil.which('powershell.exe') if os.name == 'nt' else None))


PWSH = find_powershell()


class PowerShellDiscovery(unittest.TestCase):
    def test_windows_powershell_without_pwsh(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(os, 'name', 'nt'), \
                mock.patch.object(shutil, 'which', side_effect=lambda name: {
                    'powershell.exe': r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
                }.get(name)):
            self.assertEqual(find_powershell(),
                             r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe')

    def test_explicit_executable_takes_precedence(self):
        with mock.patch.dict(os.environ, {'REVIEW_LOOP_PWSH': '/custom/pwsh'}), \
                mock.patch.object(shutil, 'which', return_value='/default/pwsh'):
            self.assertEqual(find_powershell(), '/custom/pwsh')

    def test_pwsh_takes_precedence_on_windows(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(os, 'name', 'nt'), \
                mock.patch.object(shutil, 'which', side_effect=lambda name: {
                    'pwsh': r'C:\PowerShell\pwsh.exe',
                    'powershell.exe': r'C:\Windows\powershell.exe'
                }.get(name)):
            self.assertEqual(find_powershell(), r'C:\PowerShell\pwsh.exe')


class InstallerCases:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='review-loop-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / 'user-root'
        self.source = self.root / 'source checkout'
        self.source.mkdir()
        shutil.copytree(REPO / 'review-loop', self.source / 'review-loop')
        self.targets = [self.destination / app / 'skills/review-loop'
                        for app in ('.agents', '.claude')]
        self.env = dict(os.environ, REVIEW_LOOP_TEST_ROOT=str(self.destination),
                        POWERSHELL_TELEMETRY_OPTOUT='1',
                        XDG_CACHE_HOME=str(self.root / 'cache'),
                        XDG_CONFIG_HOME=str(self.root / 'config'),
                        XDG_DATA_HOME=str(self.root / 'data'))

    def seed_installs(self):
        for target in self.targets:
            target.mkdir(parents=True)
            (target / 'sentinel').write_text(str(target))

    def assert_previous_installs(self):
        for target in self.targets:
            self.assertEqual((target / 'sentinel').read_text(), str(target))
            self.assertEqual(sorted(p.name for p in target.iterdir()), ['sentinel'])
        self.assert_no_stages()

    def assert_no_stages(self):
        self.assertFalse(list(self.destination.rglob('.review-loop-install.*')))

    def prepare_installer(self, failure=None, pause=False, engine=None):
        engine = engine or self.engine
        suffix = '.sh' if engine == 'bash' else '.ps1'
        text = (REPO / ('install_review-loop' + suffix)).read_text()
        # Only redirect the destination lookup in a disposable script copy.
        # Never modify HOME or install into the real user's skill directories.
        replacement = ('$REVIEW_LOOP_TEST_ROOT' if engine == 'bash'
                       else '$env:REVIEW_LOOP_TEST_ROOT')
        self.assertIn('$HOME', text)
        text = text.replace('$HOME', replacement)
        runner = Path(tempfile.mkdtemp(prefix='runner-', dir=self.root))
        env = dict(self.env)
        if failure:
            env['REVIEW_LOOP_FAILURE_MARKER'] = str(runner / 'failure-reached')
            if engine == 'bash':
                program = 'cp' if failure == 'copy' else 'mv'
                original = shutil.which(program)
                bin_dir = runner / 'bin'
                bin_dir.mkdir()
                shim = bin_dir / program
                # Fail preparation or activation of the second destination.
                guard = '"$last" == *"/.claude/"*'
                if failure != 'copy':
                    guard += ' && "$previous" == */new'
                shim.write_text(
                    '#!/usr/bin/env bash\n'
                    'for arg in "$@"; do previous="$last"; last="$arg"; done\n'
                    f'if [[ {guard} ]]; then\n'
                    '  : > "$REVIEW_LOOP_FAILURE_MARKER"\n'
                    '  exit 73\n'
                    'fi\nexec "' + original + '" "$@"\n')
                shim.chmod(0o755)
                env['PATH'] = str(bin_dir) + os.pathsep + os.environ['PATH']
            else:
                command = 'Copy-Item' if failure == 'copy' else 'Move-Item'
                guard = ("$Destination.Contains('.claude')" if failure == 'copy' else
                         "$Destination.Contains('.claude') -and "
                         "[System.IO.Path]::GetFileName($LiteralPath) -eq 'new'")
                text = f'''function {command} {{
    [CmdletBinding()]
    param([string]$LiteralPath, [string]$Destination, [switch]$Force, [switch]$Recurse)
    if ({guard}) {{
        [System.IO.File]::WriteAllText($env:REVIEW_LOOP_FAILURE_MARKER, '')
        throw 'Injected installation failure'
    }}
    Microsoft.PowerShell.Management\\{command} @PSBoundParameters
}}
''' + text
        if pause:
            # Pause after the first old installation has been moved aside,
            # recreating the activation race without relying on scheduling.
            env['REVIEW_LOOP_PAUSE_DIR'] = str(runner)
            if engine == 'bash':
                bin_dir = runner / 'bin'
                bin_dir.mkdir()
                shim = bin_dir / 'mv'
                shim.write_text(
                    '#!/usr/bin/env bash\n'
                    'for arg in "$@"; do previous="$last"; last="$arg"; done\n'
                    'if [[ "$previous" == */new && "$last" == */.agents/skills/review-loop ]]; then\n'
                    '  touch "$REVIEW_LOOP_PAUSE_DIR/paused"\n'
                    '  while [[ ! -e "$REVIEW_LOOP_PAUSE_DIR/resume" ]]; do sleep .01; done\n'
                    'fi\nexec "' + shutil.which('mv') + '" "$@"\n')
                shim.chmod(0o755)
                env['PATH'] = str(bin_dir) + os.pathsep + os.environ['PATH']
            else:
                text = '''function Move-Item {
    [CmdletBinding()]
    param([string]$LiteralPath, [string]$Destination, [switch]$Force, [switch]$Recurse)
    if ($Destination.Contains('.agents') -and [System.IO.Path]::GetFileName($LiteralPath) -eq 'new') {
        [System.IO.File]::WriteAllText((Join-Path $env:REVIEW_LOOP_PAUSE_DIR 'paused'), '')
        while (-not (Test-Path -LiteralPath (Join-Path $env:REVIEW_LOOP_PAUSE_DIR 'resume'))) {
            Start-Sleep -Milliseconds 10
        }
    }
    Microsoft.PowerShell.Management\\Move-Item @PSBoundParameters
}
''' + text
        script = self.source / ('install-' + runner.name + suffix)
        script.write_text(text)
        command = (['bash', str(script)] if engine == 'bash' else
                   [PWSH, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(script)])
        return command, env

    def run_installer(self, failure=None):
        command, env = self.prepare_installer(failure=failure)
        result = subprocess.run(command, cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=30)
        if failure:
            self.assertTrue(Path(env['REVIEW_LOOP_FAILURE_MARKER']).is_file(),
                            f'Installer did not reach the injected {failure} failure.\n'
                            f'Exit code: {result.returncode}\n{result.stdout}{result.stderr}')
        return result

    def test_existing_lock_preserves_installs_and_ownership(self):
        self.seed_installs()
        for target in self.targets:
            with self.subTest(destination=target):
                lock = target.parent / '.review-loop-install.lock'
                lock.write_text('owned by another installer')
                result = self.run_installer()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('installation lock', result.stderr.lower())
                self.assertEqual(lock.read_text(), 'owned by another installer')
                lock.unlink()
                # Also verifies release of the first lock if the second failed.
                self.assert_previous_installs()

    def check_concurrent_install(self, competing_engine):
        self.seed_installs()
        version = self.source / 'review-loop/version.txt'
        version.write_text('A')
        command, env = self.prepare_installer(pause=True)
        gate = Path(env['REVIEW_LOOP_PAUSE_DIR'])
        process = subprocess.Popen(command, cwd=self.root, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not (gate / 'paused').exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue((gate / 'paused').exists(), 'Installer did not reach the activation barrier')
            version.write_text('B')
            second_command, second_env = self.prepare_installer(engine=competing_engine)
            second = subprocess.run(second_command, cwd=self.root, env=second_env,
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(second.returncode, 0, second.stderr)
            self.assertIn('installation lock', second.stderr.lower())
            for target in self.targets:
                self.assertTrue((target.parent / '.review-loop-install.lock').is_file())
            (gate / 'resume').touch()
            _, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stderr)
            for target in self.targets:
                self.assertEqual((target / 'version.txt').read_text(), 'A')
                self.assertFalse((target / 'new').exists())
            self.assert_no_stages()
            # The rejected installer can succeed after the first releases locks.
            retry = subprocess.run(second_command, cwd=self.root, env=second_env,
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(retry.returncode, 0, retry.stderr)
            for target in self.targets:
                self.assertEqual((target / 'version.txt').read_text(), 'B')
                self.assertFalse((target / 'new').exists())
            self.assert_no_stages()
        finally:
            (gate / 'resume').touch()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()

    def test_concurrent_install(self):
        self.check_concurrent_install(self.engine)

    @unittest.skipUnless(shutil.which('bash') and PWSH, 'Requires both Bash and PowerShell')
    def test_concurrent_other_shell_install(self):
        self.check_concurrent_install('powershell' if self.engine == 'bash' else 'bash')

    def test_install_and_reinstall(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = (REPO / 'review-loop/SKILL.md').read_text()
        self.assertEqual((self.targets[0] / 'SKILL.md').read_text(), expected)
        claude = (self.targets[1] / 'SKILL.md').read_text()
        self.assertEqual(claude, expected.replace('---\n', '---\ndisable-model-invocation: true\n', 1))
        (self.targets[0] / 'obsolete').write_text('old version')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.targets[0] / 'obsolete').exists())
        self.assert_no_stages()

    def test_missing_source_preserves_installs(self):
        self.seed_installs()
        (self.source / 'review-loop/agents/openai.yaml').unlink()
        self.assertNotEqual(self.run_installer().returncode, 0)
        self.assert_previous_installs()

    def check_checkout_overlap(self, index):
        self.seed_installs()
        target = self.targets[index]
        shutil.copytree(self.source / 'review-loop', target / 'review-loop')
        self.source = target
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('overlap', result.stderr.lower())
        self.assertTrue((target / 'review-loop/SKILL.md').exists())
        for installed in self.targets:
            self.assertEqual((installed / 'sentinel').read_text(), str(installed))
        self.assert_no_stages()

    def test_codex_checkout_overlap(self):
        self.check_checkout_overlap(0)

    def test_claude_checkout_overlap(self):
        self.check_checkout_overlap(1)

    @unittest.skipIf(os.name == 'nt', 'Symlink creation may require Windows privileges')
    def test_symlinked_parent_overlap(self):
        self.destination.mkdir()
        (self.source / 'skills').mkdir()
        shutil.move(str(self.source / 'review-loop'), self.source / 'skills/review-loop')
        (self.source / 'review-loop').symlink_to('skills/review-loop', target_is_directory=True)
        (self.destination / '.agents').symlink_to(self.source, target_is_directory=True)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('overlap', result.stderr.lower())
        self.assertTrue((self.source / 'review-loop/SKILL.md').exists())
        self.assert_no_stages()

    @unittest.skipIf(os.name == 'nt', 'Symlink creation may require Windows privileges')
    def test_source_contains_destination(self):
        self.destination.mkdir()
        (self.destination / '.agents').symlink_to(self.source / 'review-loop', target_is_directory=True)
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('overlap', result.stderr.lower())
        self.assertTrue((self.source / 'review-loop/SKILL.md').exists())
        self.assertFalse((self.source / 'review-loop/skills').exists())

    @unittest.skipIf(os.name == 'nt', 'Symlink creation may require Windows privileges')
    def test_existing_relative_symlinks_are_restored_on_failure(self):
        for target in self.targets:
            target.parent.mkdir(parents=True)
            previous = target.parent / 'previous-version'
            previous.mkdir()
            (previous / 'sentinel').write_text(str(target))
            target.symlink_to('previous-version', target_is_directory=True)
        result = self.run_installer(failure='move')
        self.assertNotEqual(result.returncode, 0)
        for target in self.targets:
            self.assertTrue(target.is_symlink())
            self.assertEqual(os.readlink(target), 'previous-version')
        self.assert_previous_installs()

    @unittest.skipIf(os.name == 'nt', 'Symlink creation may require Windows privileges')
    def test_successful_replacement_preserves_symlink_referents(self):
        for target in self.targets:
            target.parent.mkdir(parents=True)
            previous = target.parent / 'previous-version'
            previous.mkdir()
            (previous / 'sentinel').write_text(str(target))
            target.symlink_to('previous-version', target_is_directory=True)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        for target in self.targets:
            self.assertFalse(target.is_symlink())
            self.assertTrue((target / 'SKILL.md').exists())
            self.assertEqual((target.parent / 'previous-version/sentinel').read_text(), str(target))
        self.assert_no_stages()

    def test_second_copy_failure_preserves_both_installs(self):
        self.seed_installs()
        self.assertNotEqual(self.run_installer(failure='copy').returncode, 0)
        self.assert_previous_installs()

    def test_second_activation_failure_restores_both_installs(self):
        self.seed_installs()
        self.assertNotEqual(self.run_installer(failure='move').returncode, 0)
        self.assert_previous_installs()

    def test_failed_first_install_leaves_no_installations(self):
        self.assertNotEqual(self.run_installer(failure='move').returncode, 0)
        for target in self.targets:
            self.assertFalse(target.exists())
        self.assert_no_stages()

    @unittest.skipIf(os.name == 'nt' or getattr(os, 'geteuid', lambda: 0)() == 0,
                     'Requires POSIX permission enforcement for an ordinary user')
    def test_unreadable_source_directory_preserves_installs(self):
        self.seed_installs()
        restricted = self.source / 'review-loop/agents'
        restricted.chmod(0o111)
        try:
            self.assertNotEqual(self.run_installer().returncode, 0)
            self.assert_previous_installs()
        finally:
            restricted.chmod(0o755)


@unittest.skipUnless(shutil.which('bash'), 'Bash unavailable')
class BashInstallers(InstallerCases, unittest.TestCase):
    engine = 'bash'


@unittest.skipUnless(PWSH, 'PowerShell unavailable')
class PowerShellInstallers(InstallerCases, unittest.TestCase):
    engine = 'powershell'

    def run_with_reparse_ancestor(self, link_type=''):
        command, env = self.prepare_installer()
        script = Path(command[-1])
        env['REVIEW_LOOP_REPARSE_PATH'] = str(self.source)
        env['REVIEW_LOOP_REPARSE_LINK_TYPE'] = link_type
        marker = self.root / 'reparse-metadata-inspected'
        env['REVIEW_LOOP_REPARSE_MARKER'] = str(marker)
        marker.unlink(missing_ok=True)
        # Simulate Windows directory metadata while exercising the complete
        # installer against real temporary source and destination directories.
        script.write_text('''function Get-Item {
    [CmdletBinding()]
    param([string]$LiteralPath, [switch]$Force)
    $item = Microsoft.PowerShell.Management\\Get-Item @PSBoundParameters
    if ($LiteralPath -eq $env:REVIEW_LOOP_REPARSE_PATH) {
        [System.IO.File]::WriteAllText($env:REVIEW_LOOP_REPARSE_MARKER, '')
        return [pscustomobject]@{
            Attributes = $item.Attributes -bor [System.IO.FileAttributes]::ReparsePoint
            PSIsContainer = $true
            LinkType = $env:REVIEW_LOOP_REPARSE_LINK_TYPE
            Target = $null
        }
    }
    return $item
}
''' + script.read_text())
        result = subprocess.run(command, cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertTrue(marker.exists(), result.stdout + result.stderr)
        return result

    def test_non_link_reparse_ancestor_can_install(self):
        self.seed_installs()
        result = self.run_with_reparse_ancestor()
        self.assertEqual(result.returncode, 0, result.stderr)
        for target in self.targets:
            self.assertTrue((target / 'SKILL.md').is_file())
            self.assertFalse((target / 'sentinel').exists())
        self.assert_no_stages()

    def test_unresolved_directory_links_preserve_installs(self):
        self.seed_installs()
        for link_type in ('SymbolicLink', 'Junction'):
            with self.subTest(link_type=link_type):
                result = self.run_with_reparse_ancestor(link_type)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Cannot resolve directory link', result.stderr)
                self.assert_previous_installs()


if __name__ == '__main__':
    unittest.main()
