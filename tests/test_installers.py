"""Installer regression tests; all destinations are isolated under a temporary root.

Run with: python3 -B -m unittest discover -s tests -v
Set REVIEW_LOOP_PWSH to select a PowerShell executable when needed.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
PWSH = os.environ.get('REVIEW_LOOP_PWSH') or shutil.which('pwsh')


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

    def run_installer(self, failure=None):
        suffix = '.sh' if self.engine == 'bash' else '.ps1'
        text = (REPO / ('install_review-loop' + suffix)).read_text()
        # Only redirect the destination lookup in a disposable script copy.
        # Never modify HOME or install into the real user's skill directories.
        replacement = ('$REVIEW_LOOP_TEST_ROOT' if self.engine == 'bash'
                       else '$env:REVIEW_LOOP_TEST_ROOT')
        self.assertIn('$HOME', text)
        text = text.replace('$HOME', replacement)
        if failure:
            if self.engine == 'bash':
                program = 'cp' if failure == 'copy' else 'mv'
                original = shutil.which(program)
                bin_dir = self.root / 'bin'
                bin_dir.mkdir(exist_ok=True)
                shim = bin_dir / program
                # Fail preparation or activation of the second destination.
                shim.write_text(
                    '#!/usr/bin/env bash\n'
                    'for arg in "$@"; do previous="$last"; last="$arg"; done\n'
                    'if [[ "$last" == *"/.claude/"* ]]; then\n'
                    + ('  exit 73\n' if failure == 'copy' else
                       '  if [[ "$previous" == */new ]]; then exit 73; fi\n')
                    + 'fi\nexec "' + original + '" "$@"\n')
                shim.chmod(0o755)
                self.env['PATH'] = str(bin_dir) + os.pathsep + os.environ['PATH']
            else:
                command = 'Copy-Item' if failure == 'copy' else 'Move-Item'
                guard = ("$Destination.Contains('.claude')" if failure == 'copy' else
                         "$Destination.Contains('.claude') -and "
                         "[System.IO.Path]::GetFileName($LiteralPath) -eq 'new'")
                text = f'''function {command} {{
    [CmdletBinding()]
    param([string]$LiteralPath, [string]$Destination, [switch]$Force, [switch]$Recurse)
    if ({guard}) {{ throw 'Injected installation failure' }}
    Microsoft.PowerShell.Management\\{command} @PSBoundParameters
}}
''' + text
        script = self.source / ('install' + suffix)
        script.write_text(text)
        command = (['bash', str(script)] if self.engine == 'bash' else
                   [PWSH, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(script)])
        return subprocess.run(command, cwd=self.root, env=self.env,
                              capture_output=True, text=True, timeout=30)

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


if __name__ == '__main__':
    unittest.main()
