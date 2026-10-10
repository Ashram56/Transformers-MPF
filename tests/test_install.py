"""The prerequisite installers (scripts/install/) and MPF Monitor's missing window layouts
(setup.install_monitor_ui). Shell scripts run in --dry-run mode only."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import setup  # noqa: E402
import toolchain as tc  # noqa: E402

INSTALL = os.path.join(ROOT, "scripts", "install")
BASH = shutil.which("bash")
POSIX = os.name == "posix"


def sh(args, env=None):
    full = dict(os.environ, **(env or {}))
    return subprocess.run([BASH] + args, capture_output=True, text=True, env=full, timeout=120, cwd=ROOT)


@unittest.skipUnless(BASH and POSIX, "needs bash on Linux or macOS")
class TestShellScripts(unittest.TestCase):
    SCRIPTS = ["install_prereqs_linux.sh", "install_prereqs_macos.sh", "build_pinproc.sh"]

    def test_syntax(self):
        for name in self.SCRIPTS:
            with self.subTest(script=name):
                r = sh(["-n", os.path.join(INSTALL, name)])
                self.assertEqual(0, r.returncode, r.stderr)

    def os_release(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".os-release", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def linux_plan(self, os_release, *args):
        return sh([os.path.join(INSTALL, "install_prereqs_linux.sh"), "--dry-run", "--no-setup"] + list(args),
                  env={"TF_OS_RELEASE": self.os_release(os_release), "DISPLAY": ":0"})

    def test_linux_families(self):
        cases = [('ID=ubuntu\nPRETTY_NAME="Ubuntu 24.04 LTS"\n', "apt", "apt"),
                 ('ID=debian\nPRETTY_NAME="Debian 12"\n', "apt", "apt"),
                 ('ID=linuxmint\nID_LIKE="ubuntu debian"\n', "apt", "apt"),
                 ('ID=fedora\nPRETTY_NAME="Fedora Linux 41"\n', "dnf", "dnf"),
                 ('ID=rocky\nID_LIKE="rhel centos fedora"\n', "dnf", "dnf"),
                 ('ID=arch\nPRETTY_NAME="Arch Linux"\n', "pacman", "pacman"),
                 ('ID=endeavouros\nID_LIKE=arch\n', "pacman", "pacman")]
        for text, family, _ in cases:
            with self.subTest(os_release=text.split("\n")[0]):
                r = self.linux_plan(text, "--monitor", "--proc")
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                self.assertIn("({},".format(family), r.stdout)
                self.assertIn("dry run", r.stdout)
                self.assertIn("build_pinproc.sh", r.stdout)
                self.assertIn("99-pinproc.rules", r.stdout)

    def test_linux_unsupported(self):
        r = self.linux_plan('ID=opensuse-tumbleweed\nID_LIKE="opensuse suse"\n')
        self.assertEqual(1, r.returncode)
        self.assertIn("unsupported distribution", r.stderr)

    def test_linux_bad_option(self):
        r = sh([os.path.join(INSTALL, "install_prereqs_linux.sh"), "--bogus"])
        self.assertEqual(2, r.returncode)

    def test_linux_setup_args(self):
        r = sh([os.path.join(INSTALL, "install_prereqs_linux.sh"), "--dry-run", "--", "--skip-media"],
               env={"TF_OS_RELEASE": self.os_release("ID=debian\n"), "DISPLAY": ":0"})
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("setup.py --dry-run --skip-media", r.stdout)

    def test_macos_plan(self):
        r = sh([os.path.join(INSTALL, "install_prereqs_macos.sh"), "--dry-run"])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("Python 3.11", r.stdout)
        self.assertIn("setup.py --dry-run", r.stdout)       # MPF Monitor is setup.py's default
        self.assertIn("run.py --monitor", r.stdout)
        r = sh([os.path.join(INSTALL, "install_prereqs_macos.sh"), "--dry-run", "--no-monitor"])
        self.assertIn("setup.py --no-monitor --dry-run", r.stdout)

    def test_standalone_clones(self):
        """Run on its own (bash <(curl ...), README "Install"), an installer clones the repository first;
        run from a clone, it never does."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        target = os.path.join(tmp, "tron")
        env = {"TF_OS_RELEASE": self.os_release("ID=debian\n"), "DISPLAY": ":0", "TF_DIR": target,
               "TF_BRANCH": "some-branch", "TF_REPO": "https://example.invalid/tron.git"}
        for name in ("install_prereqs_linux.sh", "install_prereqs_macos.sh"):
            with self.subTest(script=name):
                alone = os.path.join(tmp, name)
                shutil.copy(os.path.join(INSTALL, name), alone)
                r = sh([alone, "--dry-run"], env=env)
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                self.assertIn("git clone --branch some-branch https://example.invalid/tron.git " + target, r.stdout)
                self.assertIn(os.path.join(target, "scripts", "setup.py"), r.stdout)
                os.makedirs(os.path.join(target, ".git"), exist_ok=True)      # no branch: switch to TF_BRANCH
                r = sh([alone, "--dry-run"], env=env)
                self.assertIn("git -C {} checkout -B some-branch --track origin/some-branch".format(target), r.stdout)
                shutil.rmtree(os.path.join(target, ".git"))
                r = sh([os.path.join(INSTALL, name), "--dry-run"], env=env)
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                self.assertNotIn("git clone", r.stdout)
                self.assertIn(os.path.join(ROOT, "scripts", "setup.py"), r.stdout)

    def test_existing_clone_branch_gone(self):
        """An existing clone is pulled while its branch is on the remote, and moved to TF_BRANCH once that
        branch is deleted there (a merged pull request's branch), instead of failing."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        origin, target = os.path.join(tmp, "origin"), os.path.join(tmp, "tron")

        def git(*a, cwd=tmp):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main"]
                           + list(a), cwd=cwd, check=True, capture_output=True)
        git("init", origin)
        git("commit", "--allow-empty", "-m", "one", cwd=origin)
        git("branch", "feature", cwd=origin)
        git("clone", "--branch", "feature", origin, target)
        for name in ("install_prereqs_linux.sh", "install_prereqs_macos.sh"):
            with self.subTest(script=name):
                alone = os.path.join(tmp, name)
                shutil.copy(os.path.join(INSTALL, name), alone)
                env = {"TF_OS_RELEASE": self.os_release("ID=debian\n"), "DISPLAY": ":0", "TF_DIR": target,
                       "TF_REPO": origin}
                r = sh([alone, "--dry-run"], env=env)
                self.assertIn("git -C {} pull --ff-only".format(target), r.stdout)
        git("branch", "-D", "feature", cwd=origin)
        for name in ("install_prereqs_linux.sh", "install_prereqs_macos.sh"):
            with self.subTest(script=name, branch="gone"):
                r = sh([os.path.join(tmp, name), "--dry-run"], env=env)
                self.assertEqual(0, r.returncode, r.stdout + r.stderr)
                self.assertIn("'feature' is no longer on GitHub", r.stdout)
                self.assertIn("git -C {} checkout -B main --track origin/main".format(target), r.stdout)

    def test_github_auth(self):
        """The token step (run first, so a private repository asks for a token before the long installs): public
        repositories need none; a token that cannot read the game stops the install with a clear message, and
        is never printed; the PuP Pack's private repository unreadable only leaves the PuP out."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = os.path.join(tmp, "repo")
        subprocess.run(["git", "-c", "init.defaultBranch=main", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "one"], check=True)
        for name in ("install_prereqs_linux.sh", "install_prereqs_macos.sh"):
            script = open(os.path.join(INSTALL, name), encoding="utf-8").read()
            funcs = script[script.index("say() {"):script.index("AUTH_DONE=0")]
            missing = os.path.join(tmp, "missing")
            for env, code, out in (({"TF_REPO": repo, "TF_PUP_REPO": repo}, 0, "public: no token needed"),
                                   ({"TF_REPO": missing, "TF_PUP_REPO": repo,
                                     "TF_GITHUB_TOKEN": "secret-token-123"}, 1, "cannot read"),
                                   ({"TF_REPO": repo, "TF_PUP_REPO": missing}, 0, "installs without the PuP"),
                                   ({"TF_REPO": repo, "TF_PUP_REPO": missing,
                                     "TF_GITHUB_TOKEN": "secret-token-123"}, 0, "installs without the PuP Pack"),
                                   ({"TF_REPO": repo, "TF_PUP_REPO": missing, "TF_PUP_ZIP": "pack.zip"}, 0,
                                    "public: no token needed")):
                with self.subTest(script=name, env=sorted(env)):
                    prog = 'DRY=0 YES=1; REPO_URL="$TF_REPO"\n' + funcs + "github_auth\n"
                    r = subprocess.run(["bash", "-c", prog], capture_output=True, text=True, timeout=60,
                                       env=dict({k: v for k, v in os.environ.items()
                                                 if k not in ("GITHUB_TOKEN", "GH_TOKEN", "TF_GITHUB_TOKEN")},
                                                HOME=tmp, **env))
                    self.assertEqual(code, r.returncode, r.stdout + r.stderr)
                    self.assertIn(out, r.stdout + r.stderr)
                    self.assertNotIn("secret-token-123", r.stdout + r.stderr)
        r = sh([os.path.join(INSTALL, "install_prereqs_linux.sh"), "--dry-run"],
               env={"TF_OS_RELEASE": self.os_release("ID=debian\n"), "DISPLAY": ":0"})
        self.assertIn("GitHub access", r.stdout)

    def test_build_pinproc_plan(self):
        r = sh([os.path.join(INSTALL, "build_pinproc.sh"), "--dry-run", "--python", sys.executable,
                "--src", tempfile.gettempdir() + "/tf-pinproc-plan"])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("-DBUILD_SHARED_LIBS=ON", r.stdout)
        self.assertIn("pip install", r.stdout)


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 (pwsh) is not installed")
class TestWindowsScript(unittest.TestCase):

    def test_parses_and_plans(self):
        script = os.path.join(INSTALL, "install_prereqs_windows.ps1")
        check = ("$e = $null; $t = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
                 "'{}', [ref]$t, [ref]$e); exit $e.Count".format(script))
        r = subprocess.run(["pwsh", "-NoProfile", "-Command", check], capture_output=True, text=True, timeout=120)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        r = subprocess.run(["pwsh", "-NoProfile", "-File", script, "-DryRun", "-NoMonitor", "-Proc"],
                           capture_output=True, text=True, timeout=120, cwd=ROOT)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("Python 3.11", r.stdout)
        self.assertIn("--no-monitor --dry-run", r.stdout)


class TestMonitorUi(unittest.TestCase):

    def test_fetches_only_missing_files(self):
        with tempfile.TemporaryDirectory() as pkg:
            os.makedirs(os.path.join(pkg, "core", "ui"))
            with open(os.path.join(pkg, "core", "ui", "inspector.ui"), "w") as f:
                f.write("<ui/>")
            found = subprocess.CompletedProcess([], 0, stdout=pkg + "\n")
            with mock.patch.object(setup.subprocess, "run", return_value=found), \
                    mock.patch.object(setup, "download", return_value=b'<?xml version="1.0"?>\n<ui version="4.0"/>') as dl:
                self.assertEqual(3, setup.install_monitor_ui("python"))
            self.assertEqual(3, dl.call_count)
            for name in tc.MPF_MONITOR_UI_FILES:
                self.assertTrue(os.path.isfile(os.path.join(pkg, "core", "ui", name)))
            self.assertTrue(dl.call_args[0][0].startswith(tc.MPF_MONITOR_UI_URL))

    def test_rejects_non_ui(self):
        with tempfile.TemporaryDirectory() as pkg:
            found = subprocess.CompletedProcess([], 0, stdout=pkg)
            with mock.patch.object(setup.subprocess, "run", return_value=found), \
                    mock.patch.object(setup, "download", return_value=b"<html>404</html>"):
                with self.assertRaises(SystemExit):
                    setup.install_monitor_ui("python")


if __name__ == "__main__":
    unittest.main()
