"""Save generated data with bounded, non-forced fast-forward push retries.

Rebase only onto changes that cannot invalidate the collected site. Source/data
changes or merge conflicts stop publication rather than silently choosing a side.
"""
import subprocess
import time
from pathlib import Path

OUTPUTS = [
    "dist/projects.json", "dist/projects.csv", "dist/changes.json",
    "dist/department-audit.json", "dist/department-audit.html", "dist/reports",
    "state", "history", "采集核对报告.md", "逐部门采集核查.md",
]


def git(*args, cwd=None, check=True):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def sync_and_push(cwd=None, attempts=3, delay=2):
    for attempt in range(attempts):
        # Fetch before every push, including retries after a last-millisecond edit.
        git("fetch", "origin", "main", cwd=cwd)
        upstream = git("rev-parse", "FETCH_HEAD", cwd=cwd).stdout.strip()
        base = git("merge-base", "HEAD", upstream, cwd=cwd).stdout.strip()
        remote_changes = git("diff", "--name-only", base, upstream, cwd=cwd).stdout.splitlines()
        # A README edit is safe to integrate. Code, site inputs and generated data
        # must instead be rebuilt together by a fresh run on the new revision.
        unsafe = [p for p in remote_changes if not (
            p in ("README.md", ".gitignore") or p.startswith("docs/")
        )]
        if unsafe:
            raise RuntimeError(
                "采集期间远端代码或数据已更新，停止发布以免覆盖或混用旧数据。"
                "请在最新 main 上重新运行任务。涉及文件：" + ", ".join(unsafe)
            )
        rebased = git("rebase", upstream, cwd=cwd, check=False)
        if rebased.returncode:
            git("rebase", "--abort", cwd=cwd, check=False)
            raise RuntimeError("同步存在文件冲突，已中止；未强制覆盖远端。\n" + rebased.stderr)
        pushed = git("push", "origin", "HEAD:refs/heads/main", cwd=cwd, check=False)
        if pushed.returncode == 0:
            print("项目数据已安全保存到 main。")
            return
        # Retry only an actual non-fast-forward race; permissions/network errors
        # remain explicit failures, not reasons to alter authentication or force.
        rejected = pushed.stderr.lower()
        if not any(s in rejected for s in ("fetch first", "non-fast-forward")):
            raise RuntimeError(pushed.stderr)
        print(f"远端刚有新提交，正在重新同步（{attempt + 1}/{attempts}）。")
        if attempt + 1 < attempts:
            time.sleep(delay)
    raise RuntimeError("远端连续更新，安全重试次数已用完；未强制推送，请重新运行。")


def main():
    root = Path(__file__).resolve().parents[1]
    git("config", "user.name", "github-actions[bot]", cwd=root)
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=root)
    git("add", "--", *OUTPUTS, cwd=root)
    if git("diff", "--cached", "--quiet", cwd=root, check=False).returncode == 0:
        # Still synchronize before upload: a stale source revision must not deploy.
        print("本次数据无需提交，核对远端版本。")
    else:
        git("commit", "-m", "更新香港政府项目及每日采集记录", cwd=root)
    sync_and_push(cwd=root)


if __name__ == "__main__":
    main()
