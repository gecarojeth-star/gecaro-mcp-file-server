"""First-boot setup: create the workspace, copy handoff templates, init git."""
import shutil

from . import config
from .tools import gitlite


def bootstrap() -> None:
    config.WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    if config.TEMPLATES_DIR.is_dir():
        for tpl in sorted(config.TEMPLATES_DIR.glob("*.md")):
            dest = config.WORKSPACE_ROOT / tpl.name
            if not dest.exists():  # never overwrite an agent's real state
                shutil.copyfile(tpl, dest)
    gitlite.ensure_repo()
