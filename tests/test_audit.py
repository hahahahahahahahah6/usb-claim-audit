"""Specification coverage, with separate cases for every claim phrase."""
import builtins
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from usb_claim_audit.audit import audit, claims, evidence
from usb_claim_audit.phrases import USB, NOUSB
from tests.cases import populate

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures'


class AuditTests(unittest.TestCase):
    def result(self, docs='connects to usb devices', source='pass', name='app.py'):
        with tempfile.TemporaryDirectory() as tmp:
            return audit(populate(tmp, docs, source, name))

    def assert_high(self, result, rule='documented-usb-claim-false'):
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertEqual(result['findings'][0]['rule'], rule)

    def cli(self, *args):
        return subprocess.run(['python3', '-m', 'usb_claim_audit', *map(str, args)], capture_output=True, text=True)

    def test_good_find(self):
        self.assertEqual(audit(FIXTURES / 'good')['findings'], [])

    def test_good_attribute(self):
        self.assertEqual(self.result(source='import usb.core\nusb.core.find()')['findings'], [])

    def test_good_alias(self):
        self.assertEqual(self.result(source='import usb.core as core\ncore.find()')['findings'], [])

    def test_good_bound_read(self):
        self.assertEqual(self.result(source='from usb.core import find\ndev=find()\ndev.read(1, 8)')['findings'], [])

    def test_good_bound_write(self):
        self.assertEqual(self.result(source='from usb.core import find\ndev=find()\ndev.write(1, b"x")')['findings'], [])

    def test_good_ctrl_transfer(self):
        self.assertEqual(self.result(source='from usb.core import find\ndev=find()\ndev.ctrl_transfer(0, 1)')['findings'], [])

    def test_good_chained(self):
        self.assertEqual(self.result(source='import usb.core\nusb.core.find().read(1, 8)')['findings'], [])

    def test_bad(self):
        self.assert_high(audit(FIXTURES / 'bad'))
        self.assertEqual(self.cli(FIXTURES / 'bad').returncode, 2)

    def test_import_only(self):
        self.assert_high(self.result(source='import usb'))

    def test_core_import_only(self):
        self.assert_high(self.result(source='import usb.core'))

    def test_unbound(self):
        self.assert_high(self.result(source='dev.read(1, 8)'))

    def test_strings(self):
        self.assert_high(self.result(source='VENDOR="usb 0x1234:0x5678"'))

    def test_subprocess(self):
        self.assert_high(self.result(source='import subprocess\nsubprocess.run(["lsusb"])'))

    def test_subprocess_other(self):
        self.assert_high(self.result(source='import subprocess\nsubprocess.run(["usb-devices"])'))

    def test_serial(self):
        self.assert_high(self.result(source='import serial\nserial.Serial("/dev/ttyUSB0")'))

    def test_testonly(self):
        result = audit(FIXTURES / 'testonly')
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['severity'], 'MEDIUM')
        self.assertEqual(result['findings'][0]['rule'], 'documented-usb-claim-false')
        self.assertEqual(self.cli(FIXTURES / 'testonly').returncode, 0)
        self.assertEqual(self.cli(FIXTURES / 'testonly', '--fail-on', 'MEDIUM').returncode, 2)

    def test_no_usb(self):
        self.assert_high(audit(FIXTURES / 'no-usb'), 'documented-no-usb-claim-false')
        self.assertEqual(self.cli(FIXTURES / 'no-usb').returncode, 2)

    def test_no_claim(self):
        self.assertEqual(self.result('Device utility', 'import usb.core\nusb.core.find()')['findings'], [])

    def test_user_instruction(self):
        self.assertEqual(self.result('Plug in the usb device first. Connect the usb cable before starting.')['findings'], [])

    def test_bare_word(self):
        self.assertEqual(self.result('# USB')['findings'], [])

    def test_fenced(self):
        self.assertEqual(self.result('```text\nconnects via usb\n```')['findings'], [])

    def test_inline(self):
        self.assert_high(self.result('Tool `connects via usb` today.'))

    def test_negation(self):
        self.assertEqual(self.result('does not connect via usb')['findings'], [])

    def test_no_source_positive(self):
        self.assert_high(self.result(source=None))

    def test_no_source_negative(self):
        self.assertEqual(self.result('no usb', None)['findings'], [])

    def test_self_audit(self):
        self.assertEqual(claims((ROOT / 'README.md').read_text()), (False, False))
        self.assertEqual(audit(ROOT)['findings'], [])
        self.assertEqual(self.cli(ROOT).returncode, 0)

    def test_cli_version(self):
        proc = self.cli('--version')
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), '0.1.0')

    def test_cli_json(self):
        proc = self.cli(FIXTURES / 'bad', '--json')
        self.assertEqual(proc.returncode, 2)
        self.assert_high(json.loads(proc.stdout))

    def test_cli_bad_path(self):
        self.assertEqual(self.cli(ROOT / 'nonexistent').returncode, 1)

    def test_cli_bad_option(self):
        self.assertEqual(self.cli('--nonexistent').returncode, 1)

    def test_ignore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = populate(tmp, 'Utility', 'pass')
            (root / 'docs').mkdir()
            (root / 'docs' / 'claim.md').write_text('connect via usb')
            self.assertEqual(self.cli(root, '--ignore', 'docs/*.md').returncode, 0)
            self.assertEqual(self.cli(root).returncode, 2)

    def test_verbose(self):
        proc = self.cli(FIXTURES / 'good', '--verbose')
        self.assertEqual(proc.returncode, 0)
        self.assertIn('Scanned', proc.stdout)

    def test_packaging(self):
        project = (ROOT / 'pyproject.toml').read_text()
        self.assertIn('usb-claim-audit = "usb_claim_audit.__main__:main"', project)
        self.assertIn('version = "0.1.0"', project)
        self.assertIn('requires-' + 'py' + 'thon = ">=3.9"', project)
        self.assertIn('MIT License', (ROOT / 'LICENSE').read_text())
        self.assertTrue((ROOT / 'README.md').is_file())
        self.assertIn('recursive-include tests *.py *.md .env', (ROOT / 'MANIFEST.in').read_text())
        self.assertTrue((FIXTURES / '.env').is_file())

    def test_no_bare_interpreter_commands(self):
        forbidden = r'\b' + 'py' + r'thon\b'
        for base in ('usb_claim_audit', 'tests'):
            for path in (ROOT / base).rglob('*.py'):
                self.assertIsNone(re.search(forbidden, path.read_text()), str(path))
        for line in (ROOT / 'README.md').read_text().splitlines():
            self.assertIsNone(re.search(forbidden, line, re.IGNORECASE) if line.lstrip().startswith(('py' + 'thon', '$ ', '>>>')) else None)

    def test_no_secret_literals(self):
        secret = re.compile(r'(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|-----BEGIN ' + r'(?:RSA |OPENSSH )?PRIVATE KEY-----)')
        for path in ROOT.rglob('*'):
            if path.is_file() and path.suffix in {'.py', '.md', '.toml'} and not any(p in {'dist', 'build', '.venv'} for p in path.parts):
                self.assertIsNone(secret.search(path.read_text()), str(path))

    def test_env_never_opened(self):
        original = builtins.open
        original_path = Path.open
        def guarded(file, *args, **kwargs):
            self.assertNotEqual(Path(file).name, '.env')
            return original(file, *args, **kwargs)
        def guarded_path(path, *args, **kwargs):
            self.assertNotEqual(path.name, '.env')
            return original_path(path, *args, **kwargs)
        with patch('builtins.open', guarded), patch.object(Path, 'open', guarded_path):
            self.assertEqual(audit(FIXTURES)['findings'], [])

    def test_more_import_aliases(self):
        for source in ['from usb import core as c\nc.find()', 'from usb.core import find as f\nf()', 'import usb as u\nu.core.find()', 'from usb import core\ncore.find()']:
            with self.subTest(source=source):
                self.assertTrue(evidence(source))

    def test_self_attribute_configuration(self):
        self.assertTrue(evidence('from usb.core import find\nself.dev=find()\nself.dev.set_configuration()'))

    def test_bare_find(self):
        self.assertFalse(evidence('def find(): return 1\nfind()'))

    def test_logging_connect(self):
        self.assert_high(self.result(source='def connect():\n print("usb")\n return True'))

    def test_decorator(self):
        self.assert_high(self.result(source='@app.get("/usb")\ndef route(): return "usb"'))

    def test_comments_docstrings(self):
        self.assertFalse(evidence('# usb.core.find()\n"""usb.core.find()"""'))

    def test_scope_exclusions(self):
        for name in ['fixtures/app.py', 'docs/app.py', 'examples/app.py']:
            with self.subTest(name=name):
                self.assert_high(self.result(source='import usb.core\nusb.core.find()', name=name))
        for name in ['test_device.py', 'device_test.py']:
            with self.subTest(name=name):
                self.assertEqual(self.result(source='import usb.core\nusb.core.find()', name=name)['findings'][0]['severity'], 'MEDIUM')

    def test_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = populate(tmp)
            target = Path(other) / 'device.py'
            target.write_text('import usb.core\nusb.core.find()')
            (root / 'device.py').symlink_to(target)
            (root / 'linked').symlink_to(other, target_is_directory=True)
            self.assert_high(audit(root))

    def test_docs_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = populate(tmp, 'Utility')
            (root / 'other.md').write_text('connect via usb')
            self.assertEqual(audit(root)['findings'], [])
            path = root / 'nested' / 'docs' / 'deep' / 'claim.md'
            path.parent.mkdir(parents=True)
            path.write_text('connect via usb')
            self.assert_high(audit(root))

    def test_test_docs_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = populate(tmp, 'Utility', 'import usb.core\nusb.core.find()')
            path = root / 'tests' / 'docs' / 'claim.md'
            path.parent.mkdir(parents=True)
            path.write_text('no usb')
            self.assert_high(audit(root), 'documented-no-usb-claim-false')

    def test_normalization(self):
        self.assertEqual(claims('CONNECTS-TO\nUSB DEVICES'), (True, False))
        self.assertEqual(claims("doesn't connect via usb"), (False, True))
        self.assertEqual(claims('reconnect via usbs'), (False, False))
        self.assertEqual(claims('connect via\n\nusb'), (False, False))

    def test_both_families_max_two(self):
        result = self.result('connect via usb. supports usb. no usb. without usb.')
        self.assert_high(result)
        result = self.result('connect via usb. no usb.', 'import usb.core\nusb.core.find()')
        self.assert_high(result, 'documented-no-usb-claim-false')

    def test_unreadable_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0)
            try:
                self.assertEqual(self.cli(root).returncode, 1)
            finally:
                root.chmod(0o700)

    def test_tilde_fence(self):
        self.assertEqual(claims('~~~text\nconnect via usb\n~~~'), (False, False))

    def test_invalid_source(self):
        self.assert_high(self.result(source='import usb.core\nusb.core.find('))


def positive_test(phrase):
    def run(self):
        self.assertEqual(claims(phrase), (True, False))
        self.assert_high(self.result(phrase))
    return run


def negative_test(phrase):
    def run(self):
        self.assertEqual(claims(phrase), (False, True))
        self.assertEqual(self.result(phrase)['findings'], [])
        self.assert_high(self.result(phrase, 'import usb.core\nusb.core.find()'), 'documented-no-usb-claim-false')
    return run


for index, phrase in enumerate(USB):
    setattr(AuditTests, 'test_positive_phrase_%02d' % index, positive_test(phrase))
for index, phrase in enumerate(NOUSB):
    setattr(AuditTests, 'test_negative_phrase_%02d' % index, negative_test(phrase))
