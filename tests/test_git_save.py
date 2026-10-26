"""Real local Git repositories reproduce remote updates during collection."""
import importlib.util
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "save_collected_data", Path(__file__).resolve().parents[1] / "scripts/save_collected_data.py"
)
save = importlib.util.module_from_spec(spec)
spec.loader.exec_module(save)


class GitSaveTests(unittest.TestCase):
    def run_git(self, where, *args):
        return subprocess.run(["git", *args], cwd=where, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit_file(self, repo, name, content):
        (repo / name).write_text(content, encoding="utf-8")
        self.run_git(repo, "add", name)
        self.run_git(repo, "commit", "-m", name)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.remote, self.worker, self.editor = [root / p for p in ("remote.git", "worker", "editor")]
        self.run_git(root, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.run_git(root, "clone", str(self.remote), str(self.worker))
        self.configure(self.worker)
        self.commit_file(self.worker, "README.md", "initial")
        self.run_git(self.worker, "push", "origin", "main")
        self.run_git(root, "clone", str(self.remote), str(self.editor))
        self.configure(self.editor)

    def configure(self, repo):
        self.run_git(repo, "config", "user.name", "test")
        self.run_git(repo, "config", "user.email", "test@example.com")

    def test_remote_readme_and_collected_data_both_preserved(self):
        self.commit_file(self.worker, "data.json", "new collection")
        self.commit_file(self.editor, "README.md", "remote edit")
        self.run_git(self.editor, "push", "origin", "main")
        save.sync_and_push(self.worker, delay=0)
        self.assertEqual((self.worker / "README.md").read_text(), "remote edit")
        self.assertEqual(self.run_git(self.remote, "show", "main:data.json"), "new collection")

    def test_source_change_blocks_stale_site_without_overwriting(self):
        self.commit_file(self.worker, "data.json", "old-source collection")
        self.commit_file(self.editor, "collect_projects.py", "new code")
        self.run_git(self.editor, "push", "origin", "main")
        before = self.run_git(self.remote, "rev-parse", "main")
        with self.assertRaisesRegex(RuntimeError, "远端代码或数据已更新"):
            save.sync_and_push(self.worker, delay=0)
        self.assertEqual(self.run_git(self.remote, "rev-parse", "main"), before)

    def test_same_data_changed_remotely_is_not_overwritten(self):
        self.commit_file(self.worker, "data.json", "local")
        self.commit_file(self.editor, "data.json", "remote")
        self.run_git(self.editor, "push", "origin", "main")
        with self.assertRaises(RuntimeError):
            save.sync_and_push(self.worker, delay=0)
        self.assertEqual(self.run_git(self.remote, "show", "main:data.json"), "remote")

    def test_last_second_remote_push_retries_successfully(self):
        self.commit_file(self.worker, "data.json", "collection")
        original_git = save.git
        pushes = []

        def race(*args, **kwargs):
            if args[0] == "push":
                pushes.append(args)
                if len(pushes) == 1:
                    self.commit_file(self.editor, "README.md", "last second edit")
                    self.run_git(self.editor, "push", "origin", "main")
            return original_git(*args, **kwargs)

        with patch.object(save, "git", side_effect=race):
            save.sync_and_push(self.worker, delay=0)
        self.assertEqual(len(pushes), 2)
        self.assertEqual(self.run_git(self.remote, "show", "main:README.md"), "last second edit")
        self.assertEqual(self.run_git(self.remote, "show", "main:data.json"), "collection")

    def test_rebase_conflict_aborts_without_remote_changes(self):
        self.commit_file(self.worker, "README.md", "worker edit")
        self.commit_file(self.editor, "README.md", "editor edit")
        self.run_git(self.editor, "push", "origin", "main")
        before = self.run_git(self.remote, "rev-parse", "main")
        with self.assertRaisesRegex(RuntimeError, "已中止"):
            save.sync_and_push(self.worker, delay=0)
        self.assertEqual(self.run_git(self.remote, "rev-parse", "main"), before)
        self.assertEqual((self.worker / "README.md").read_text(), "worker edit")


if __name__ == "__main__":
    unittest.main()
